import io

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from app.engine.imported import execute_csv, parquet_to_csv, read_csv


def encode(data):
    stream = io.BytesIO()
    pq.write_table(pa.table(data), stream)
    return stream.getvalue()


def test_parquet_normalization_and_policy():
    text = parquet_to_csv(
        encode(
            {
                "id": ["001", "002"],
                "amount": [20, 999],
                "region": ["APAC", "EMEA"],
                "optional": [None, "yes"],
            }
        )
    )
    schema, rows = read_csv(text)
    assert schema["records"]["amount"] == "TEXT"
    assert rows[0] == ("001", "20", "APAC", None)
    policy = {
        "mode": "QUERY_ONLY",
        "table_columns": {"records": ["amount"]},
        "row_rules": [
            {"table": "records", "column": "region", "op": "eq", "value": "APAC"}
        ],
    }
    assert execute_csv(text, policy, "SELECT SUM(amount) FROM records")["rows"] == [
        (20,)
    ]


@pytest.mark.parametrize(
    "payload",
    [
        b"invalid",
        encode({"nested": [[1, 2]]}),
        encode({"bad name": [1]}),
        encode({"a": list(range(20001))}),
        encode({"a": ["x" * 16385]}),
    ],
    ids=["invalid", "nested", "bad-column", "row-limit", "field-limit"],
)
def test_parquet_rejects_invalid_or_unbounded_input(payload):
    with pytest.raises(ValueError):
        parquet_to_csv(payload)
