import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.engine.csv_queries import analytics_sql
from app.engine.imported import execute_csv, read_csv
from app.engine.nl2sql import Glossary, draft


CSV = (
    "id,city,net_revenue,quantity,private_note,region\n"
    "001,North,2.50,4,excluded,APAC\n"
    "002,North,10,3,excluded,APAC\n"
    "003,South,100,2,excluded,APAC\n"
    "004,South,unknown,1,excluded,APAC\n"
    "005,South,999,100,excluded,EMEA"
)
PERMITTED = ["id", "city", "net_revenue", "quantity"]
POLICY = {
    "mode": "QUERY_ONLY",
    "table_columns": {"records": PERMITTED},
    "row_rules": [{"table": "records", "column": "region", "op": "eq", "value": "APAC"}],
}


@pytest.mark.parametrize(
    ("question", "rows"),
    [
        ("How many records are there?", [(4,)]),
        ("Count records by city", [("North", 2), ("South", 2)]),
        ("Sum quantity", [(10,)]),
        ("What is the average net_revenue by city?", [("North", 6.25), ("South", 100.0)]),
        ("Bottom 2 by net revenue", [("001", "2.50"), ("002", "10")]),
        ("Top 1 by units", [("001", "4")]),
        ("Who has the highest net revenue?", [("003", "100")]),
    ],
)
def test_common_analytics_use_current_row_and_column_policy(question, rows):
    sql = analytics_sql(question, PERMITTED)
    assert sql and "private_note" not in sql
    assert execute_csv(CSV, POLICY, sql)["rows"] == rows


def test_unsupported_or_ambiguous_intents_are_not_guessed():
    assert analytics_sql("Sum quantity for each city this month", PERMITTED) is None
    assert analytics_sql("Average private note", PERMITTED) is None
    with pytest.raises(ValueError, match="Several permitted columns"):
        analytics_sql("Average pay", ["base_salary", "annual_salary"])


def test_csv_model_retries_lexical_ranking_without_receiving_values(monkeypatch):
    schema, _ = read_csv(CSV)
    context = {"records": {column: "TEXT" for column in PERMITTED}}
    glossary = Glossary(context, [])
    table = glossary.tables["records"]
    revenue = glossary.columns["records"]["net_revenue"]
    candidate = f"SELECT {revenue} AS metric FROM {table} ORDER BY metric ASC LIMIT 1"
    corrected = (
        f"SELECT {revenue} AS metric FROM {table} WHERE MORPHY_NUMBER({revenue}) IS NOT NULL "
        f"ORDER BY MORPHY_NUMBER({revenue}) ASC LIMIT 1"
    )
    session = AsyncMock()
    session.post.side_effect = [
        Mock(json=lambda: {"message": {"content": json.dumps({"sql": candidate})}}),
        Mock(json=lambda: {"message": {"content": json.dumps({"sql": corrected})}}),
    ]
    wrapper = AsyncMock()
    wrapper.__aenter__.return_value = session
    monkeypatch.setattr("app.engine.nl2sql.httpx.AsyncClient", Mock(return_value=wrapper))

    result = asyncio.run(
        draft(
            SimpleNamespace(ollama_url="http://localhost", ollama_model="test"),
            "Show the smallest revenue entry",
            schema,
            POLICY,
            [],
            result_dialect="sqlite",
        )
    )
    assert result["attempts"] == 2
    assert execute_csv(CSV, POLICY, result["sql"])["rows"] == [("2.50",)]
    prompt = str(session.post.await_args.kwargs["json"]["messages"])
    assert "NumericMetricRequiresConversion" in prompt
    for private in ("net_revenue", "private_note", "excluded", "APAC", "EMEA", "2.50", "001"):
        assert private not in prompt
