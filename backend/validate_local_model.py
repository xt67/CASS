"""Compare local-model answers against reference SQL on a disposable seeded DB."""
import asyncio
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from cass.core.agent import Agent
from cass.integrations.database.postgres import PostgresRunner
from cass.integrations.llm.ollama import OllamaProvider
from cass.tools.run_sql import RunSQLTool


async def main():
    runner = PostgresRunner(os.environ["DATABASE_URL"])
    await runner.connect()
    model = os.environ["OLLAMA_MODEL"]
    agent = Agent(OllamaProvider(model=model, timeout=180), [RunSQLTool(runner)])
    prompts = [
        ("How many customers are there? Return one column named count.", "SELECT COUNT(*) AS count FROM customers"),
        ("What is the sum of total_amount across all orders? Return one column named total.", "SELECT SUM(total_amount) AS total FROM orders"),
        ("List the three most expensive products, returning name and price, sorted by price descending and name ascending.", "SELECT name, price FROM products ORDER BY price DESC, name ASC LIMIT 3"),
    ]
    results = []
    output = Path(os.environ.get("CASS_VALIDATION_REPORT", "local-model-validation.json"))
    try:
        schema = await runner.get_schema()
        for question, reference in prompts:
            expected = await runner.execute(reference)
            answer = await agent.chat(question, schema)
            result = {"question":question, "sql":answer.sql, "passed":answer.data == expected,
                      "error":answer.error, "actual":answer.data, "expected":expected}
            results.append(result)
            output.write_text(json.dumps({"model":model,"results":results}, indent=2, default=str))
            print(json.dumps({"question":question,"passed":result["passed"],"error":answer.error}), flush=True)
    finally:
        await runner.close()
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


asyncio.run(main())
