"""
PostgreSQL Database Runner for CASS
===================================
Handles database connections and query execution using asyncpg.
"""

import asyncpg
import asyncio
import os
import sqlglot
from sqlglot import exp
from typing import Any


class PostgresRunner:
    """
    Async PostgreSQL database runner.

    Usage:
        runner = PostgresRunner("postgresql://postgres:casspass@localhost:5432/cassdb")
        await runner.connect()
        results = await runner.execute("SELECT * FROM customers LIMIT 5")
        schema = await runner.get_schema()
        await runner.close()
    """

    def __init__(self, connection_string: str) -> None:
        """
        Initialize with database connection string.

        Args:
            connection_string: PostgreSQL URL
                e.g., "postgresql://postgres:casspass@localhost:5432/cassdb"
        """
        self.connection_string = connection_string
        self._pool: asyncpg.Pool | None = None
        self.max_rows = int(os.environ.get("CASS_MAX_ROWS", "500"))
        self.timeout = float(os.environ.get("CASS_QUERY_TIMEOUT", "10"))
        if not 1 <= self.max_rows <= 10000 or not 0 < self.timeout <= 60:
            raise ValueError("CASS_MAX_ROWS must be 1..10000 and CASS_QUERY_TIMEOUT 0..60 seconds")

    async def connect(self) -> None:
        """Create a connection pool to the database."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60,
            )

    async def execute(self, sql: str, *args) -> list[dict[str, Any]]:
        """
        Execute a SQL query and return results as list of dictionaries.

        Args:
            sql: SQL query string to execute

        Returns:
            List of rows, each row is a dictionary with column names as keys

        Raises:
            RuntimeError: If not connected to database
            asyncpg.PostgresError: If SQL execution fails
        """
        if self._pool is None:
            raise RuntimeError("Not connected. Call connect() first.")

        if len(sql) > 20000:
            raise ValueError("Query exceeds 20000 characters")
        statements = sqlglot.parse(sql, read="postgres")
        if len(statements) != 1 or not isinstance(statements[0], exp.Query):
            raise ValueError("Exactly one SELECT query is required")
        if any(isinstance(node, (exp.DML, exp.DDL, exp.Into, exp.Lock)) for node in statements[0].walk()):
            raise ValueError("Writes and locking queries are not allowed")

        async with asyncio.timeout(self.timeout):
            async with self._pool.acquire() as conn:
                # Enforce read-only execution at the database boundary, including
                # writes hidden inside CTEs. Use a least-privilege DB role as well.
                async with conn.transaction(readonly=True):
                    await conn.execute("SELECT set_config('statement_timeout', $1, true)", str(int(self.timeout * 1000)))
                    cursor = await conn.cursor(sql, *args)
                    rows = await cursor.fetch(self.max_rows + 1)
                    if len(rows) > self.max_rows:
                        raise ValueError(f"Query exceeds {self.max_rows} rows; add a LIMIT or aggregate the results")
                return [dict(row) for row in rows]

    async def get_schema(self) -> str:
        """
        Get database schema information for LLM context.

        Returns:
            Formatted string describing all tables and their columns
        """
        if self._pool is None:
            raise RuntimeError("Not connected. Call connect() first.")

        # Query to get all tables and columns from public schema
        schema_query = """
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(schema_query)

        # Format schema as readable text for LLM
        schema_text = []
        current_table = None

        for row in rows:
            table = row["table_name"]
            column = row["column_name"]
            dtype = row["data_type"]
            nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"

            if table != current_table:
                if current_table is not None:
                    schema_text.append("")  # Blank line between tables
                schema_text.append(f"Table: {table}")
                current_table = table

            schema_text.append(f"  - {column} ({dtype}, {nullable})")

        return "\n".join(schema_text)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def __aenter__(self) -> "PostgresRunner":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
