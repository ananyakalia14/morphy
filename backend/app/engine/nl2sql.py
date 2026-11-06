"""Build the model context exclusively from the caller's effective schema."""

from collections import deque
import asyncio
from hashlib import blake2s
import json
import re

import httpx
from sqlglot import exp, parse
from sqlglot.optimizer.qualify import qualify
from sqlglot.errors import SqlglotError

from .security import compile_query, physical_tables
from sqlglot.optimizer.scope import traverse_scope
from .retrieval import semantic_anchors

VOCABULARY = {
    "customer": "customer",
    "client": "customer",
    "cust": "customer",
    "order": "order",
    "sale": "sale",
    "payment": "payment",
    "product": "product",
    "revenue": "income",
    "rev": "income",
    "amount": "amount",
    "price": "price",
    "total": "total",
    "id": "id",
    "name": "name",
    "date": "date",
    "created": "created",
    "region": "region",
    "status": "status",
    "employee": "employee",
    "patient": "individual",
    "dob": "birth_date",
}


def words(value):
    return [word.removesuffix("s") for word in re.findall("[a-z]+", value.lower())]


def alias(name, namespace, fallback):
    terms = [VOCABULARY[w] for w in words(name) if w in VOCABULARY]
    suffix = blake2s((namespace + "/" + name).encode(), digest_size=5).hexdigest()
    return "_".join(terms or [fallback]) + "_" + suffix


def select_context(question, tables, edges, semantic=()):
    if len(tables) <= 12:
        return tables
    tokens = set(words(question))
    scores = {
        t: 4 * len(tokens.intersection(words(t)))
        + len(tokens.intersection(words(" ".join(cols))))
        for t, cols in tables.items()
    }
    anchors = sorted((t for t in tables if scores[t]), key=lambda t: (-scores[t], t))[
        :8
    ]
    anchors.extend(t for t in semantic if t not in anchors)
    if not anchors:
        return tables
    graph = {t: set() for t in tables}
    for a, ac, b, bc in edges:
        if ac in tables.get(a, {}) and bc in tables.get(b, {}):
            graph[a].add(b)
            graph[b].add(a)
    selected = {anchors[0]}
    for anchor in anchors[1:]:
        queue = deque([(anchor, [anchor])])
        seen = {anchor}
        while queue:
            node, path = queue.popleft()
            if node in selected:
                selected.update(path)
                break
            for neighbor in sorted(graph[node] - seen):
                seen.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
        selected.add(anchor)
    return {t: tables[t] for t in sorted(selected)}


class Glossary:
    def __init__(self, tables, edges):
        self.tables = {t: alias(t, "table", "entity") for t in tables}
        self.columns = {
            t: {c: alias(c, t, "field") for c in cols} for t, cols in tables.items()
        }
        self.schema = {
            self.tables[t]: {self.columns[t][c]: typ for c, typ in cols.items()}
            for t, cols in tables.items()
        }
        self.joins = [
            [self.tables[a], self.columns[a][ac], self.tables[b], self.columns[b][bc]]
            for a, ac, b, bc in edges
            if ac in self.columns.get(a, {}) and bc in self.columns.get(b, {})
        ]

    def restore(self, candidate):
        statements = parse(candidate, read="postgres")
        if len(statements) != 1 or not isinstance(
            statements[0], (exp.Select, exp.SetOperation)
        ):
            raise ValueError("Expected one read query")
        tree = qualify(statements[0], dialect="postgres", schema=self.schema)
        names = {masked: original for original, masked in self.tables.items()}
        physical = physical_tables(tree)
        restored_columns = set()
        # Resolve columns before renaming tables so each nested alias has its
        # own scope. CTE output names retain their projected aliases.
        for scope in traverse_scope(tree):
            for column in scope.columns:
                if id(column) in restored_columns:
                    continue
                if not column.table:
                    continue
                owner = scope
                while owner is not None and column.table not in owner.sources:
                    owner = owner.parent
                source = owner.sources.get(column.table) if owner else None
                if isinstance(source, exp.Table):
                    original_table = names.get(source.name)
                    if not original_table:
                        raise ValueError("Unknown table alias")
                    columns = {v: k for k, v in self.columns[original_table].items()}
                    original_column = columns.get(column.name)
                    if not original_column:
                        raise ValueError("Unknown column alias")
                    column.set("this", exp.to_identifier(original_column, quoted=True))
                    restored_columns.add(id(column))
        for table in physical:
            original = names.get(table.name)
            if not original or table.db or table.catalog:
                raise ValueError("Unknown table alias")
            table.set("this", exp.to_identifier(original, quoted=True))
        return tree.sql(dialect="postgres")


async def draft(config, question, reflected, policy, edges, validate_plan=None):
    permitted = {
        t: {c: reflected[t][c] for c in cols if c in reflected[t]}
        for t, cols in policy["table_columns"].items()
        if t in reflected
    }
    permitted = {t: c for t, c in permitted.items() if c}
    anchors = await asyncio.to_thread(semantic_anchors, question, permitted)
    context = select_context(question, permitted, edges, anchors)
    if not context:
        raise ValueError("No permitted columns")
    glossary = Glossary(context, edges)
    guide = json.dumps({"tables": glossary.schema, "foreign_keys": glossary.joins})
    if len(guide) > 32000:
        raise ValueError("Please narrow the question")
    messages = [
        {
            "role": "system",
            "content": "Return JSON with one sql string containing a PostgreSQL read query. Use the exact identifiers listed here. Use authorized joins and aggregates. Give result columns readable aliases. Non-recursive CTEs, nested queries and UNION are supported. No writes, locks or recursive CTEs. Schema: "
            + guide,
        },
        {"role": "user", "content": question},
    ]
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(1, 4):
            response = await client.post(
                config.ollama_url + "/api/chat",
                json={
                    "model": config.ollama_model,
                    "format": "json",
                    "stream": False,
                    "messages": messages,
                    "options": {"temperature": 0, "num_predict": 1500},
                },
            )
            response.raise_for_status()
            answer = response.json()["message"]["content"]
            try:
                candidate = json.loads(answer)["sql"]
                if not isinstance(candidate, str) or len(candidate) > 12000:
                    raise ValueError("Invalid query length")
                sql = glossary.restore(candidate)
                compiled = compile_query(sql, reflected, policy)
                if validate_plan:
                    await validate_plan(compiled)
                return {
                    "sql": sql,
                    "provider": config.ollama_model,
                    "requires_execution": True,
                    "attempts": attempt,
                }
            except PermissionError:
                raise
            except (KeyError, ValueError, SqlglotError) as error:
                if attempt == 3:
                    raise
                diagnostic = (
                    str(error)
                    if str(error).startswith("PostgreSQL validation: ")
                    else type(error).__name__
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": answer[:12000]},
                        {
                            "role": "user",
                            "content": "Correct the SQL. Validator category: "
                            + diagnostic
                            + ". Check the listed table/column identifiers, aliases, aggregate grouping, SELECT syntax and permitted functions.",
                        },
                    ]
                )
