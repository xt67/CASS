"""Database-boundary regression tests; no running PostgreSQL required."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cass.integrations.database.postgres import PostgresRunner


@pytest.mark.parametrize("fails", [False, True])
def test_execute_uses_readonly_transaction_and_exits_on_error(fails):
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock()
    transaction.__aexit__ = AsyncMock(return_value=False)
    conn = MagicMock()
    conn.transaction.return_value = transaction

    async def fetch(sql):
        transaction.__aenter__.assert_awaited_once()
        if fails:
            raise RuntimeError("database rejected query")
        return [{"value": 1}]

    conn.execute = AsyncMock()
    cursor = MagicMock()
    cursor.fetch = AsyncMock(side_effect=fetch)
    conn.cursor = AsyncMock(return_value=cursor)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=False)
    runner = PostgresRunner("unused")
    runner._pool = MagicMock()
    runner._pool.acquire.return_value = acquire
    if fails:
        with pytest.raises(RuntimeError, match="rejected"):
            asyncio.run(runner.execute("SELECT 1"))
    else:
        assert asyncio.run(runner.execute("SELECT 1")) == [{"value": 1}]
    conn.transaction.assert_called_once_with(readonly=True)
    transaction.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("sql", ["DELETE FROM customers", "SELECT 1; DROP TABLE customers", "WITH gone AS (DELETE FROM customers RETURNING *) SELECT * FROM gone", "SELECT * INTO copied FROM customers", "SELECT * FROM customers FOR UPDATE"])
def test_rejects_unsafe_sql_before_acquiring_connection(sql):
    runner = PostgresRunner("unused")
    runner._pool = MagicMock()
    with pytest.raises(ValueError):
        asyncio.run(runner.execute(sql))
    runner._pool.acquire.assert_not_called()
