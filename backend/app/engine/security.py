import base64
import os
from urllib.parse import urlsplit, parse_qs
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlglot import exp, parse
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

FUNCTIONS = {
    "sum",
    "count",
    "avg",
    "min",
    "max",
    "round",
    "lower",
    "upper",
    "length",
    "substring",
    "substr",
    "coalesce",
    "abs",
}


def encrypt_uri(uri, key, database_id):
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, uri.encode(), str(database_id).encode())


def decrypt_uri(blob, key, database_id):
    return (
        AESGCM(key)
        .decrypt(bytes(blob[:12]), bytes(blob[12:]), str(database_id).encode())
        .decode()
    )


def check_uri(uri, allowed_hosts):
    value = urlsplit(uri)
    if (
        value.scheme not in {"postgres", "postgresql"}
        or not value.hostname
        or not value.username
        or not value.path.strip("/")
        or value.fragment
    ):
        raise ValueError("Provide a PostgreSQL URI with a host, user and database.")
    if f"{value.hostname.lower()}:{value.port or 5432}" not in allowed_hosts:
        raise ValueError(
            "This database host and port are outside the server connection allowlist."
        )
    params = parse_qs(value.query, keep_blank_values=True)
    if set(params) - {"sslmode"} or any(len(v) != 1 for v in params.values()):
        raise ValueError("Only a single sslmode connection option is supported.")
    if params and params["sslmode"][0] not in {"require", "verify-full", "disable"}:
        raise ValueError("Use sslmode=require, verify-full or disable.")


def physical_tables(tree):
    tables = {}
    scopes = list(traverse_scope(tree))
    if len(scopes) > 32:
        raise ValueError("Use at most 32 query scopes.")
    for scope in scopes:
        if not isinstance(scope.expression, (exp.Select, exp.SetOperation)):
            raise ValueError("Unsupported query source.")
        for source in scope.sources.values():
            if isinstance(source, exp.Table):
                tables[id(source)] = source
    return list(tables.values())


def compile_query(sql, schema, policy, dialect="postgres"):
    if policy.get("mode") not in {"QUERY_ONLY", "SCHEMA_EDIT"}:
        raise PermissionError("Your current role cannot execute queries.")
    allowed = {}
    for table, columns in policy.get("table_columns", {}).items():
        if table in schema:
            allowed[table] = {
                c: schema[table][c] for c in columns if c in schema[table]
            }
    allowed = {t: cols for t, cols in allowed.items() if cols}
    statements = parse(sql, read=dialect)
    if len(statements) != 1 or not isinstance(
        statements[0], (exp.Select, exp.SetOperation)
    ):
        raise ValueError("Submit exactly one read query.")
    tree = statements[0]
    if any(with_.args.get("recursive") for with_ in tree.find_all(exp.With)) or any(
        tree.find_all(
            exp.DDL,
            exp.DML,
            exp.Command,
            exp.Into,
            exp.Lock,
            exp.Dot,
            exp.Lateral,
            exp.TableSample,
        )
    ):
        raise ValueError(
            "Recursive queries, writes, locks and specialized table sources are unsupported."
        )
    sources = physical_tables(tree)
    if not sources or len(sources) > 12:
        raise ValueError("Select from one to twelve authorized tables.")
    for table in sources:
        if table.name not in allowed or table.db or table.catalog:
            raise PermissionError("The query references a table outside your policy.")
    functions = FUNCTIONS | {"morphy_number"} if dialect == "sqlite" else FUNCTIONS
    for f in tree.find_all(exp.Func):
        if isinstance(f, (exp.And, exp.Or, exp.Exists)):
            continue
        name = f.name if isinstance(f, exp.Anonymous) else f.sql_name()
        if name.lower() not in functions:
            raise ValueError("The query uses an unsupported function.")
    tree = qualify(tree, dialect=dialect, schema=allowed, validate_qualify_columns=True)
    for table in physical_tables(tree):
        name, alias = table.name, table.alias_or_name
        source = exp.select(*[exp.column(c, quoted=True) for c in allowed[name]])
        source = source.from_(
            exp.Table(
                this=exp.to_identifier(name, quoted=True),
                db=exp.to_identifier(
                    "public" if dialect == "postgres" else "main", quoted=True
                ),
            )
        )
        for rule in policy.get("row_rules", []):
            if rule.get("table") != name:
                continue
            column, value = rule.get("column"), rule.get("value")
            if rule.get("op") != "eq" or column not in schema[name] or value is None:
                raise PermissionError(
                    "A row policy is invalid. Contact an administrator."
                )
            if isinstance(value, bool):
                literal = exp.Boolean(this=value)
            elif isinstance(value, (int, float)):
                literal = exp.Literal.number(value)
            elif isinstance(value, str):
                literal = exp.Literal.string(value)
            else:
                raise PermissionError("A row policy value is invalid.")
            source = source.where(exp.column(column, quoted=True).eq(literal))
        table.replace(source.subquery(exp.to_identifier(alias, quoted=True)))
    return (
        exp.select("*")
        .from_(tree.subquery("governed"))
        .limit(1000)
        .sql(dialect=dialect, pretty=True)
    )
