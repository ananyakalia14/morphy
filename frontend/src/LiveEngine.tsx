import { useEffect, useState } from "react";
import { db, rows, type Source } from "./client";
import { AnimalMorphLoader } from "./Motion";

type Result = {
  columns: string[];
  rows: unknown[][];
  sql: string;
  row_count: number;
  elapsed_ms: number;
};
async function engine<T>(
  database: string,
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  const { data } = await db!.auth.getSession();
  if (!data.session) throw Error("Sign in again to use the query engine.");
  const response = await fetch(
    "/api/engine/databases/" + database + "/" + path,
    {
      method: body ? method : "GET",
      headers: {
        Authorization: "Bearer " + data.session.access_token,
        "Content-Type": body instanceof File ? "text/csv" : "application/json",
      },
      body:
        body instanceof File ? body : body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(path === "generate" ? 195000 : 75000),
    },
  );
  const result = await response.json().catch(() => ({}));
  if (!response.ok)
    throw Error(
      typeof result.detail === "string"
        ? result.detail
        : "The query engine could not complete this request.",
    );
  return result;
}

export function LiveEngine({ org, admin }: { org: string; admin: boolean }) {
  const [sources, setSources] = useState<Source[]>([]),
    [database, setDatabase] = useState("");
  const [uri, setUri] = useState(""),
    [question, setQuestion] = useState(""),
    [sql, setSql] = useState("");
  const [schema, setSchema] = useState<Record<string, Record<string, string>>>(
    {},
  );
  const [result, setResult] = useState<Result>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState("");
  useEffect(() => {
    let alive = true;
    rows<Source>("target_databases", { org_id: org })
      .then((data) => {
        if (!alive) return;
        const supported = data.filter((s) =>
          ["postgres", "sqlite"].includes(s.dialect),
        );
        setSources(supported);
        setDatabase(supported[0]?.id || "");
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [org]);
  useEffect(() => {
    setSchema({});
    setUri("");
    setResult(undefined);
    setSql("");
    setError("");
    setStatus("");
  }, [database]);
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  const csvSource =
    sources.find((source) => source.id === database)?.dialect === "sqlite";
  return (
    <section className="panel">
      <h2>Query engine</h2>
      {!sources.length ? (
        <p>
          Ask an administrator to register a PostgreSQL or SQLite database and
          grant query access.
        </p>
      ) : (
        <>
          <label>
            Database
            <select
              disabled={busy}
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
            >
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          {admin && csvSource && (
            <label>
              Import or replace CSV (UTF-8, up to 1 MB)
              <input
                type="file"
                accept=".csv,text/csv"
                disabled={busy}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file)
                    void run(async () => {
                      if (file.size > 1048576)
                        throw Error("Choose a CSV up to 1 MB.");
                      const saved = await engine<{
                        rows: number;
                        columns: string[];
                      }>(database, "import", file, "PUT");
                      setSchema({});
                      setResult(undefined);
                      setStatus(
                        "Imported " +
                          saved.rows +
                          " rows into records. Configure allowed columns in Roles & access: " +
                          saved.columns.join(", "),
                      );
                    });
                }}
              />
            </label>
          )}
          {admin && !csvSource && (
            <details>
              <summary>Connect database</summary>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(async () => {
                    await engine(database, "connection", { uri }, "PUT");
                    setUri("");
                    setStatus(
                      "Connection verified and encrypted on the server.",
                    );
                  });
                }}
              >
                <label>
                  Read-only PostgreSQL connection URI
                  <input
                    type="password"
                    autoComplete="off"
                    required
                    value={uri}
                    onChange={(e) => setUri(e.target.value)}
                    placeholder="postgresql://user:password@host/database"
                  />
                </label>
                <small>
                  Use a dedicated read-only database user. The host must be
                  approved in the server settings.
                </small>
                <button disabled={busy}>Verify & save connection</button>
              </form>
            </details>
          )}
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const data = await engine<{ tables: typeof schema }>(
                  database,
                  "schema",
                );
                setSchema(data.tables);
                setStatus("Permitted schema loaded.");
              })
            }
          >
            Load permitted schema
          </button>
          {Object.keys(schema).length > 0 && (
            <div className="compiled">
              <pre>
                {Object.entries(schema)
                  .map(
                    ([table, cols]) =>
                      table + " (" + Object.keys(cols).join(", ") + ")",
                  )
                  .join("\n")}
              </pre>
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                const generated = await engine<{ sql: string }>(
                  database,
                  "generate",
                  { question },
                );
                setSql(generated.sql);
                setResult(undefined);
                setStatus(
                  "SQL generated by the local model. Review it, then run.",
                );
              });
            }}
          >
            <label>
              Ask about this database
              <input
                required
                maxLength={2000}
                disabled={busy}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </label>
            <button disabled={busy || !question.trim()}>
              Generate with Ollama ↗
            </button>
          </form>
          <section className="sql-panel">
            <label className="sql-toolbar" htmlFor="live-sql">
              SQL query
            </label>
            <textarea
              id="live-sql"
              spellCheck={false}
              value={sql}
              disabled={busy}
              onChange={(e) => setSql(e.target.value)}
              placeholder="SELECT ... FROM your_table"
            />
            <div className="sql-bottom">
              <small>Read-only · 1,000 rows · 10-second statement limit</small>
              <button
                className="primary"
                disabled={busy || !sql.trim()}
                onClick={() =>
                  void run(async () => {
                    setResult(undefined);
                    setResult(await engine<Result>(database, "query", { sql }));
                  })
                }
              >
                Execute query ▷
              </button>
            </div>
          </section>
          {result && (
            <>
              <p role="status">
                {result.row_count} rows · {result.elapsed_ms} ms
              </p>
              <div className="data-scroll">
                <table>
                  <thead>
                    <tr>
                      {result.columns.map((c, i) => (
                        <th key={i}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i}>
                        {row.map((v, j) => (
                          <td key={j}>{v === null ? "NULL" : String(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details>
                <summary>Executed SQL</summary>
                <pre className="live-compiled">{result.sql}</pre>
              </details>
            </>
          )}
        </>
      )}
      {busy && <AnimalMorphLoader label="Processing database request" />}
      {error && <p role="alert">{error}</p>}
      <p role="status">{status}</p>
    </section>
  );
}
