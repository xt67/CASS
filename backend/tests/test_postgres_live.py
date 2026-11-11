"""Opt-in tests against a disposable DB supplied through CASS_TEST_DATABASE_URL."""
import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from cass.integrations.database.postgres import PostgresRunner


def test_real_restricted_role_limits_and_timeout():
    dsn = os.environ.get("CASS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CASS_TEST_DATABASE_URL must point to a disposable integration database")

    async def run():
        admin = await asyncpg.connect(dsn)
        suffix = uuid.uuid4().hex[:12]
        role, table = f"cass_reader_{suffix}", f"cass_test_{suffix}"
        runner = None
        try:
            await admin.execute(f'CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT')
            await admin.execute(f'CREATE TABLE public.{table} (value integer)')
            await admin.execute(f'INSERT INTO public.{table} SELECT generate_series(1,10)')
            await admin.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
            await admin.execute(f'GRANT SELECT ON public.{table} TO {role}')
            parts = urlsplit(dsn)
            host = f"{parts.hostname}:{parts.port or 5432}"
            restricted = urlunsplit((parts.scheme, f"{role}@{host}", parts.path, parts.query, ""))
            runner = PostgresRunner(restricted)
            await runner.connect()
            assert (await runner.execute(f"SELECT COUNT(*) AS n FROM {table}"))[0]["n"] == 10
            async with runner._pool.acquire() as conn:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute(f"DELETE FROM {table}")
            runner.max_rows = 5
            with pytest.raises(ValueError, match="exceeds"):
                await runner.execute(f"SELECT * FROM {table}")
            runner.timeout = .1
            with pytest.raises((TimeoutError, asyncpg.QueryCanceledError)):
                await runner.execute("SELECT pg_sleep(1)")
            runner.timeout = 5
            assert await runner.execute("SELECT 1 AS value") == [{"value":1}]
        finally:
            if runner:
                await runner.close()
            await admin.execute(f'DROP TABLE IF EXISTS public.{table}')
            await admin.execute(f'DROP OWNED BY {role}')
            await admin.execute(f'DROP ROLE IF EXISTS {role}')
            await admin.close()

    asyncio.run(run())
