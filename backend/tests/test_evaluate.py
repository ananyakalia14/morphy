import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.engine.evaluate import agreement, dataset_database, evaluate_case


def test_comparison_preserves_duplicates_and_order():
    assert agreement([(1,), (2,)], [(2,), (1,)], False)
    assert not agreement([(1,), (2,)], [(2,), (1,)], True)
    assert not agreement([(1,), (1,)], [(1,)], False)


def test_dataset_path_cannot_escape(tmp_path):
    with pytest.raises(ValueError):
        dataset_database(tmp_path, "../secret")


def create_fixture(tmp_path, count=2):
    path = tmp_path / "shop" / "shop.sqlite"
    path.parent.mkdir()
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE orders(id INT,amount INT)")
        conn.executemany(
            "INSERT INTO orders VALUES(?,?)", [(i, i * 10) for i in range(1, count + 1)]
        )
    return path


def test_bird_case_and_database_unchanged(tmp_path, monkeypatch):
    path = create_fixture(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr(
        "app.engine.evaluate.draft",
        AsyncMock(
            return_value={"sql": "SELECT SUM(amount) FROM orders", "attempts": 1}
        ),
    )
    result = asyncio.run(
        evaluate_case(
            {
                "db_id": "shop",
                "question": "total",
                "SQL": "SELECT SUM(amount) FROM orders",
            },
            tmp_path,
            SimpleNamespace(),
        )
    )
    assert result["status"] == "correct"
    assert path.read_bytes() == before


def test_row_cap_is_excluded_before_generation(tmp_path, monkeypatch):
    create_fixture(tmp_path, 1001)
    model = AsyncMock()
    monkeypatch.setattr("app.engine.evaluate.draft", model)
    result = asyncio.run(
        evaluate_case(
            {"db_id": "shop", "question": "all", "query": "SELECT id FROM orders"},
            tmp_path,
            SimpleNamespace(),
        )
    )
    assert result["status"] == "excluded_row_cap"
    model.assert_not_awaited()


def test_mismatch_and_error_are_retained(tmp_path, monkeypatch):
    create_fixture(tmp_path)
    model = AsyncMock(return_value={"sql": "SELECT id FROM orders", "attempts": 1})
    monkeypatch.setattr("app.engine.evaluate.draft", model)
    case = {
        "db_id": "shop",
        "question": "total",
        "query": "SELECT SUM(amount) FROM orders",
    }
    assert (
        asyncio.run(evaluate_case(case, tmp_path, SimpleNamespace()))["status"]
        == "mismatch"
    )
    model.side_effect = ValueError("invalid generation")
    assert (
        asyncio.run(evaluate_case(case, tmp_path, SimpleNamespace()))["status"]
        == "error"
    )
