import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from app.engine.nl2sql import Glossary, select_context, draft


def test_bridge_is_retained_only_when_permitted():
    schema = {
        t: {"id": "int"}
        for t in ["customers", "products", "mapping"] + [f"misc{i}" for i in range(12)]
    }
    edges = [("customers", "id", "mapping", "id"), ("mapping", "id", "products", "id")]
    assert set(select_context("customers products", schema, edges)) == {
        "customers",
        "products",
        "mapping",
    }
    del schema["mapping"]
    assert set(select_context("customers products", schema, edges)) == {
        "customers",
        "products",
    }


def test_correction_stays_inside_masked_schema(monkeypatch):
    schema = {"corp_rev": {"corp_amount": "numeric", "secret_email": "text"}}
    policy = {
        "mode": "QUERY_ONLY",
        "table_columns": {"corp_rev": ["corp_amount"]},
        "row_rules": [],
    }
    g = Glossary({"corp_rev": {"corp_amount": "numeric"}}, [])
    good = f'SELECT SUM({g.columns["corp_rev"]["corp_amount"]}) AS total FROM {g.tables["corp_rev"]}'
    import json

    replies = [
        Mock(json=lambda: {"message": {"content": '{"sql":"SELECT 1 FROM missing"}'}}),
        Mock(json=lambda: {"message": {"content": json.dumps({"sql": good})}}),
    ]
    session = AsyncMock()
    session.post.side_effect = replies
    wrapper = AsyncMock()
    wrapper.__aenter__.return_value = session
    monkeypatch.setattr(
        "app.engine.nl2sql.httpx.AsyncClient", Mock(return_value=wrapper)
    )
    result = asyncio.run(
        draft(
            SimpleNamespace(ollama_url="http://localhost", ollama_model="test"),
            "sum amounts",
            schema,
            policy,
            [],
        )
    )
    assert result["attempts"] == 2
    assert '"corp_amount"' in result["sql"]
    prompt = str(session.post.await_args.kwargs["json"]["messages"])
    assert "secret_email" not in prompt and "corp_rev" not in prompt
