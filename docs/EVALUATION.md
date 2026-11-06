# Local execution evaluation

Run from backend after installing requirements.txt and starting Ollama:

```text
python -m app.engine.evaluate --dataset /path/to/dev.json --databases /path/to/database --output /path/to/report.json --limit 10
```

The dataset must be a JSON array. Each case contains db_id, question and a reference query in query (Spider style) or SQL (BIRD style). Databases are resolved as database_directory/db_id/db_id.sqlite. Paths are checked to remain inside the supplied database directory.

Use --offset to select a later slice, --limit to bound model work, --model to select an installed model and --ollama-url to select the operator-managed local provider. Keep academic datasets outside version control.

The runner opens SQLite files read-only and enables query_only and trusted_schema=OFF. It reflects base tables and explicit foreign keys, creates a full-dataset read policy, generates SQL through the same pseudonymization/retrieval/correction code as the engine, validates the candidate and compares execution results.

## Report interpretation

- correct means exact agreement on cell values and projected column order.
- mismatch means both queries executed with different results.
- error preserves a validation, model, database or input failure in the scored denominator.
- excluded_row_cap means the reference produces more than the engine's 1,000-row cap. These cases are excluded and counted explicitly.

When the reference has a top-level ORDER BY, row order is significant. Otherwise the runner compares multisets and preserves duplicates. Float tolerances, column permutations and official dataset-specific matching are outside this diagnostic.

Queries have a ten-second SQLite progress deadline. The production SQL subset applies to both reference and candidate. Data-changing statements, unsafe functions and unsupported constructs fail validation.

The report records generated SQL, status, attempts, row counts and elapsed time, without result cells. Questions and schema-derived SQL can contain sensitive identifiers. Store evaluation reports accordingly.

## Verified smoke run

evaluation-smoke.json records a run with qwen2.5-coder:7b against three synthetic questions. The fixture table was orders(id INTEGER, product TEXT, amount INTEGER), containing (1, A, 10), (2, A, 20) and (3, B, 5). Counting orders, summing amounts and grouping totals by product all agreed with their reference SQL.

This smoke run establishes the evaluation path. Official Spider/BIRD measurements still require their datasets and scoring tools.
