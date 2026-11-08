import asyncio
import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient

from app.main import app
from app.engine import api
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


def test_csv_salary_question_ranks_numbers_without_a_model(monkeypatch):
    data = (
        "first_name,last_name,salary,region,email\n"
        "Amelia,Johnson,22669.84,APAC,excluded@example.test\n"
        "Isabella,Lopez,175981.13,APAC,excluded@example.test\n"
        "Jane,Williams,50435.05,APAC,excluded@example.test\n"
        "Unknown,Person,not disclosed,APAC,excluded@example.test\n"
        "Missing,Person,,APAC,excluded@example.test\n"
        "Tied,Person,22669.840,APAC,excluded@example.test\n"
        "Other,Region,1,EMEA,excluded@example.test"
    )
    policy = {
        "mode": "QUERY_ONLY",
        "table_columns": {"records": ["first_name", "last_name", "salary"]},
        "row_rules": [{"table": "records", "column": "region", "op": "eq", "value": "APAC"}],
    }
    user, org, database = (uuid.uuid4() for _ in range(3))
    monkeypatch.setattr(api, "authorized_target", AsyncMock(return_value=(data, policy, org, "csv-v1")))
    monkeypatch.setattr(api, "track_operation", lambda *args, **kwargs: nullcontext())
    model = AsyncMock(side_effect=AssertionError("Salary ranking should never call the model"))
    monkeypatch.setattr(api, "draft", model)
    monkeypatch.setattr(api, "audit_query", AsyncMock())
    monkeypatch.setitem(app.dependency_overrides, api.identity, lambda: user)
    monkeypatch.setitem(app.dependency_overrides, api.settings, lambda: SimpleNamespace())
    endpoint = f"/api/engine/databases/{database}"

    with TestClient(app) as client:
        for question, expected in [
            ("Who earns the lowest?", [
                ["Amelia", "Johnson", "22669.84"], ["Tied", "Person", "22669.840"],
            ]),
            ("Who has the highest salary?", [["Isabella", "Lopez", "175981.13"]]),
        ]:
            generated = client.post(endpoint + "/generate", json={"question": question})
            assert generated.status_code == 200, generated.text
            draft = generated.json()
            assert draft["provider"] == "morphy-template"
            assert draft["requires_execution"]
            api.audit_query.assert_not_awaited()
            result = client.post(endpoint + "/query", json={"sql": draft["sql"]})
            assert result.status_code == 200, result.text
            assert result.json()["columns"] == ["first_name", "last_name", "salary"]
            assert sorted(result.json()["rows"]) == sorted(expected)
            api.audit_query.reset_mock()

        policy["table_columns"]["records"].remove("salary")
        denied = client.post(endpoint + "/generate", json={"question": "Who earns the lowest?"})
        assert denied.status_code == 422
        model.assert_not_awaited()


def test_csv_clarification_choices_and_examples_follow_current_permissions(monkeypatch):
    data = (
        "base_salary,annual_salary,pay,city\n"
        "10,120,99,North\n20,240,99,South"
    )
    policy = {
        "mode": "QUERY_ONLY",
        "table_columns": {"records": ["base_salary", "annual_salary", "city"]},
        "row_rules": [{"table": "records", "column": "city", "op": "eq", "value": "North"}],
    }
    user, org, database = (uuid.uuid4() for _ in range(3))
    monkeypatch.setattr(api, "authorized_target", AsyncMock(return_value=(data, policy, org, "csv-v1")))
    monkeypatch.setattr(api, "track_operation", lambda *args, **kwargs: nullcontext())
    model = AsyncMock(side_effect=AssertionError("This path must stay outside the model"))
    monkeypatch.setattr(api, "draft", model)
    monkeypatch.setattr(api, "audit_query", AsyncMock())
    monkeypatch.setitem(app.dependency_overrides, api.identity, lambda: user)
    monkeypatch.setitem(app.dependency_overrides, api.settings, lambda: SimpleNamespace())
    endpoint = f"/api/engine/databases/{database}"
    question = {"question": "What is the average pay by city?"}

    with TestClient(app) as client:
        examples = client.get(endpoint + "/schema").json()["question_examples"]
        assert "What is the average annual_salary by city?" in examples
        assert "North" not in str(examples) and "South" not in str(examples)
        legacy = client.post(endpoint + "/generate", json=question)
        assert legacy.status_code == 422 and isinstance(legacy.json()["detail"], str)
        response = client.post(
            endpoint + "/generate", json={**question, "include_clarification": True}
        )
        assert response.status_code == 200
        clarification = response.json()
        assert clarification["kind"] == "clarification"
        assert [choice["column"] for choice in clarification["choices"]] == [
            "annual_salary", "base_salary",
        ]
        assert "sql" not in clarification
        selected = {
            "question": clarification["choices"][0]["question"],
            "require_template": True,
        }
        draft = client.post(endpoint + "/generate", json=selected).json()
        assert "annual_salary" in draft["sql"]
        api.audit_query.assert_not_awaited()
        result = client.post(endpoint + "/query", json={"sql": draft["sql"]})
        assert result.json()["rows"] == [["North", 120.0]]
        policy["table_columns"]["records"].remove("annual_salary")
        stale = client.post(endpoint + "/generate", json=selected)
        assert stale.status_code == 422
        model.assert_not_awaited()
