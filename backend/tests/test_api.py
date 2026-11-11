import importlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

module = importlib.import_module("cass.server.app")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CASS_API_KEY", "test-only-token")
    monkeypatch.setattr(module, "db", SimpleNamespace(get_schema=AsyncMock(return_value="Table: customers"), execute=AsyncMock(return_value=[])))
    return TestClient(module.app)


def test_auth_required_for_all_data_routes(client):
    for path in ("/schema", "/tables", "/sample/customers", "/chat/stream?message=hello"):
        assert client.get(path).status_code == 401
    assert client.post("/sql", json={"sql":"SELECT 1"}).status_code == 401
    assert client.get("/schema", headers={"Authorization":"Bearer test-only-token"}).status_code == 200


def test_missing_auth_configuration_fails_closed(client, monkeypatch):
    monkeypatch.delenv("CASS_API_KEY")
    monkeypatch.delenv("CASS_ALLOW_ANONYMOUS", raising=False)
    assert client.get("/schema").status_code == 503


@pytest.mark.parametrize("fails", [False, True])
def test_stream_always_terminates_and_serializes_database_types(client, monkeypatch, fails):
    async def tokens(messages):
        yield "```sql SELECT 1 ```"
        if fails:
            raise RuntimeError("test LLM failure")
    tool = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(success=True, data=[{"day":date(2026,1,1),"amount":Decimal("2.5")}])) )
    agent = SimpleNamespace(system_prompt="SQL", llm=SimpleNamespace(chat_stream=tokens),
                            _extract_sql=lambda text: "SELECT 1", tools={"run_sql":tool})
    monkeypatch.setattr(module,"agent",agent)
    response = client.post("/chat/stream", json={"message":"test"}, headers={"Authorization":"Bearer test-only-token"})
    assert response.status_code == 200
    assert '"type": "end"' in response.text
    assert ('"type": "error"' in response.text) == fails
    if not fails:
        assert "2026-01-01" in response.text


def test_sample_quotes_identifier_and_binds_limit(client):
    response = client.get('/sample/evil%22name?limit=5', headers={"Authorization":"Bearer test-only-token"})
    assert response.status_code == 200
    sql, limit = module.db.execute.call_args.args
    assert sql == 'SELECT * FROM public."evil""name" LIMIT $1'
    assert limit == 5
    assert client.get('/sample/customers?limit=-1', headers={"Authorization":"Bearer test-only-token"}).status_code == 422
