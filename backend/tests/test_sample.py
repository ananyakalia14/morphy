from fastapi.testclient import TestClient
from app.main import app, EXAMPLES

client = TestClient(app)


def test_all_examples_execute():
    for sql in EXAMPLES.values():
        response = client.post("/api/sample/query", json={"sql": sql})
        assert response.status_code == 200, response.text
        assert response.json()["rows"]


def test_row_filter_cannot_be_widened():
    response = client.post("/api/sample/query", json={"sql":
        "SELECT region FROM orders WHERE region='EMEA' OR 1=1"})
    assert response.status_code == 200
    assert set(r[0] for r in response.json()["rows"]) == {"APAC"}


def test_star_excludes_pii():
    response = client.post("/api/sample/query", json={"sql": "SELECT * FROM customers"})
    assert response.status_code == 200
    assert "email" not in response.json()["columns"]
    assert {r[2] for r in response.json()["rows"]} == {"APAC"}


def test_forbidden_queries():
    for sql in [
        "DELETE FROM orders", "SELECT 1; DELETE FROM orders",
        "SELECT email FROM customers", "SELECT * FROM sqlite_master",
        "SELECT load_extension('test')", "ATTACH DATABASE 'test' AS other",
        "SELECT * FROM orders UNION SELECT * FROM orders",
        "WITH x AS (SELECT * FROM orders) SELECT * FROM x",
        "SELECT o.email FROM customers o",
        "SELECT randomblob(1000000000) FROM orders",
    ]:
        assert client.post("/api/sample/query", json={"sql": sql}).status_code == 422, sql


def test_empty_results_and_unknown_question():
    response = client.post("/api/sample/query", json={"sql": "SELECT id FROM orders WHERE region='EMEA'"})
    assert response.status_code == 200
    assert response.json()["row_count"] == 0
    assert client.post("/api/sample/generate", json={"question": "invent a query"}).status_code == 422


def test_user_limit_cannot_remove_cap():
    response = client.post("/api/sample/query", json={"sql": "SELECT o.id FROM orders o CROSS JOIN orders x CROSS JOIN orders y LIMIT -1"})
    assert response.status_code == 200
    assert response.json()["row_count"] == 100
