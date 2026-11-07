const ENGINE: string = import.meta.env["VITE_ENGINE_URL"] || "/api";
import { useEffect, useRef, useState } from "react";
import { db, rows, type Source } from "./client";
import { AnimalMorphLoader } from "./Motion";
import { saveQuery } from "./Library";
import { createLatest } from "./latest";

export type Result = {
  columns: string[];
  rows: unknown[][];
  sql: string;
  row_count: number;
  elapsed_ms: number;
};
type Generated = {
  sql: string;
  provider?: string;
  attempts?: number;
  cache?: "hit" | "miss";
};
type Schema = Record<string, Record<string, string>>;
const overviewPrompt = /^(?:what is this (?:data|dataset|database|table) about|describe this (?:dataset|database|table)|give me an overview of this (?:dataset|database|table))[?.!]*$/i;

function sqlIdentifier(name: string) {
  return '"' + name.replaceAll('"', '""') + '"';
}

export const SESSION_EXPIRED = "morphy:session-expired";

export async function engine<T>(
  database: string,
  path: string,
  body?: unknown,
  method = "POST",
  fullPath?: string,
): Promise<T> {
  const { data } = await db!.auth.getSession();
  if (!data.session) {
    window.dispatchEvent(new Event(SESSION_EXPIRED));
    throw Error("Your session expired. Sign in again.");
  }
  let response: Response;
  try {
    response = await fetch(
      ENGINE + (fullPath || "/engine/databases/" + database + "/" + path),
      {
        method: body || fullPath ? method : "GET",
        headers: {
          Authorization: "Bearer " + data.session.access_token,
          "Content-Type": body instanceof File ? (body.name.toLowerCase().endsWith(".parquet") ? "application/vnd.apache.parquet" : "text/csv") : "application/json",
        },
        body: body instanceof File ? body : body ? JSON.stringify(body) : null,
        signal: AbortSignal.timeout(path === "generate" ? 195000 : 75000),
      },
    );
  } catch (e) {
    throw Error(
      e instanceof DOMException && e.name === "TimeoutError"
        ? "The query engine took too long to answer. Try again."
        : "The query engine is unavailable right now. Check that it's running and try again.",
    );
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event(SESSION_EXPIRED));
    const hint: Record<number, string> = {
      401: "Your session expired. Sign in again.",
      403: "You no longer have access to do this. Ask an administrator to check your permissions.",
      404: "This item no longer exists or isn't shared with you.",
      409: "This source isn't connected yet, or its setup doesn't match.",
      413: "That file or result is too large.",
      422: "The request couldn't be processed. Check the question or SQL and try again.",
      502: "The database couldn't be reached.",
      503: "The query engine is unavailable right now. Try again shortly.",
    };
    const detail = typeof result.detail === "string" ? result.detail : "";
    throw Error(
      (hint[response.status] || "The query engine could not complete this request.") +
        (detail && response.status !== 401 ? " (" + detail + ")" : ""),
    );
  }
  return result;
}

export function ResultTable({ result }: { result: Result }) {
  return (
    <>
      <p role="status">
        {result.row_count} rows · {result.elapsed_ms} ms
      </p>
      <div className="data-scroll">
        <table>
          <thead>
            <tr>
              {result.columns.map((c, i) => (
                <th key={i} scope="col">
                  {c}
                </th>
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
    </>
  );
}

export function LiveEngine({
  org,
  admin,
  initial,
}: {
  org: string;
  admin: boolean;
  initial?: { database: string; sql: string } | undefined;
}) {
  const [sources, setSources] = useState<Source[]>([]),
    [database, setDatabase] = useState("");
  const [uri, setUri] = useState(""),
    [question, setQuestion] = useState(""),
    [sql, setSql] = useState("");
  const [schema, setSchema] = useState<Schema>({}),
    [filter, setFilter] = useState("");
  const [result, setResult] = useState<Result>(),
    [overview, setOverview] = useState<Schema>(),
    [gen, setGen] = useState<Generated>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState(""),
    [saveTitle, setSaveTitle] = useState(""),
    [retry, setRetry] = useState<(() => void) | null>(null);
  const [latest] = useState(createLatest);
  const editor = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    let alive = true;
    setSources([]);
    setDatabase("");
    rows<Source>("target_databases", { org_id: org })
      .then((data) => {
        if (!alive) return;
        const supported = data.filter((s) => ["postgres", "sqlite"].includes(s.dialect));
        setSources(supported);
        setDatabase(
          initial && supported.some((s) => s.id === initial.database)
            ? initial.database
            : supported[0]?.id || "",
        );
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [org, initial]);
  useEffect(() => {
    latest.cancel();
    setBusy(false);
    setRetry(null);
    setSchema({});
    setUri("");
    setResult(undefined);
    setOverview(undefined);
    setGen(undefined);
    setSql(initial?.database === database ? initial.sql : "");
    setError("");
    setStatus("");
  }, [database, initial, latest]);
  async function run(action: (alive: () => boolean) => Promise<void>, retryable = false) {
    if (busy) return;
    const alive = latest.next();
    setBusy(true);
    setError("");
    setStatus("");
    setRetry(null);
    try {
      await action(alive);
    } catch (e) {
      if (!alive()) return;
      setError(e instanceof Error ? e.message : String(e));
      if (retryable) setRetry(() => () => void run(action, true));
    } finally {
      if (alive()) setBusy(false);
    }
  }
  function showOverview() {
    void run(async (alive) => {
      setOverview(undefined);
      setResult(undefined);
      setGen(undefined);
      const data = await engine<{ tables: Schema }>(database, "schema");
      if (alive()) setOverview(data.tables);
    }, true);
  }
  const wantsOverview = overviewPrompt.test(question.trim().replace(/\s+/g, " "));
  const overviewTables = overview && Object.entries(overview);
  function loadSuggestedSql(suggestion: string) {
    setSql(suggestion);
    setGen(undefined);
    setResult(undefined);
    setStatus("Suggested SQL loaded for review.");
    editor.current?.focus();
  }
  const csvSource = sources.find((source) => source.id === database)?.dialect === "sqlite";
  const f = filter.trim().toLowerCase();
  const visible = Object.entries(schema).filter(
    ([t, cols]) => !f || t.toLowerCase().includes(f) || Object.keys(cols).some((c) => c.toLowerCase().includes(f)),
  );
  const insert = (text: string) => setSql((s) => (s ? s + (s.endsWith(" ") ? "" : " ") : "") + text);
  return (
    <section className="panel">
      <h2>Query engine</h2>
      {!sources.length ? (
        <p>Ask an administrator to register a PostgreSQL or SQLite database and grant query access.</p>
      ) : (
        <>
          <label>
            Database
            <select disabled={busy} value={database} onChange={(e) => setDatabase(e.target.value)}>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          {admin && csvSource && (
            <label>
              Import or replace CSV / Parquet (up to 1 MB)
              <input
                type="file"
                accept=".csv,.parquet,text/csv,application/vnd.apache.parquet"
                disabled={busy}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file)
                    void run(async (alive) => {
                      if (file.size > 1048576) throw Error("Choose a CSV or Parquet file up to 1 MB.");
                      const saved = await engine<{ rows: number; columns: string[] }>(database, "import", file, "PUT");
                      if (!alive()) return;
                      setSchema({});
                      setResult(undefined);
                      setOverview(undefined);
                      setStatus(
                        "Imported " + saved.rows + " rows into records. Configure allowed columns in Roles & access: " + saved.columns.join(", "),
                      );
                    }, true);
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
                  const value = uri;
                  void run(async (alive) => {
                    await engine(database, "connection", { uri: value }, "PUT");
                    if (!alive()) return;
                    setUri("");
                    setOverview(undefined);
                    setStatus("Connection verified and encrypted on the server.");
                  }, true);
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
                <small>Use a dedicated read-only database user. The host must be approved in the server settings.</small>
                <button disabled={busy}>Verify & save connection</button>
              </form>
            </details>
          )}
          <div className="schema-nav">
            <button
              disabled={busy}
              onClick={() =>
                void run(async (alive) => {
                  const data = await engine<{ tables: typeof schema }>(database, "schema");
                  if (!alive()) return;
                  setSchema(data.tables);
                  setStatus(Object.keys(data.tables).length ? "Permitted schema loaded." : "No tables are permitted for you yet.");
                }, true)
              }
            >
              {Object.keys(schema).length ? "Reload schema" : "Load permitted schema"}
            </button>
            {Object.keys(schema).length > 0 && (
              <>
                <label>
                  Find a table or column
                  <input type="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
                </label>
                <ul className="schema-tree" aria-label="Permitted tables">
                  {visible.map(([table, cols]) => (
                    <li key={table}>
                      <details open={!!f}>
                        <summary>
                          {table} <small>{Object.keys(cols).length} columns</small>
                        </summary>
                        <button type="button" className="chip" onClick={() => insert(table)}>
                          Insert table name
                        </button>
                        <ul>
                          {Object.entries(cols).map(([c, type]) => (
                            <li key={c}>
                              <button type="button" className="chip" onClick={() => insert(c)} aria-label={"Insert column " + c}>
                                {c}
                              </button>{" "}
                              <small>{type}</small>
                            </li>
                          ))}
                        </ul>
                      </details>
                    </li>
                  ))}
                  {!visible.length && <li>No matches.</li>}
                </ul>
              </>
            )}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (wantsOverview) {
                showOverview();
                return;
              }
              void run(async (alive) => {
                setOverview(undefined);
                const generated = await engine<Generated>(database, "generate", { question });
                if (!alive()) return;
                setSql(generated.sql);
                setGen(generated);
                setResult(undefined);
                setStatus("SQL generated. Review it, then run.");
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
                aria-describedby="live-question-privacy"
                onChange={(e) => setQuestion(e.target.value)}
              />
            </label>
            <small id="live-question-privacy">
              Dataset overviews use schema metadata only. SQL generation sends your question as typed to Ollama.
            </small>
            <button type="submit" disabled={busy || !question.trim()}>
              {wantsOverview ? "Show dataset overview ↗" : "Generate with Ollama ↗"}
            </button>
            {!wantsOverview && (
              <button type="button" disabled={busy} onClick={showOverview}>Show dataset overview ↗</button>
            )}
          </form>
          {overviewTables && (
            <section aria-labelledby="dataset-overview">
              <h3 id="dataset-overview">Dataset overview</h3>
              <p role="status">Based on permitted table and column names only.</p>
              {overviewTables.length ? (
                <>
                  <h4>Suggested queries</h4>
                  <p>Choose a suggestion to load it in the SQL editor.</p>
                  <ul className="overview-tables">
                    {overviewTables.map(([table, columns]) => {
                      const names = Object.keys(columns);
                      const source = sqlIdentifier(table);
                      const preview = names.slice(0, 3).map(sqlIdentifier).join(", ");
                      return (
                        <li key={table}>
                          <div><strong>{table}</strong> · {names.join(", ")}</div>
                          <div className="overview-actions">
                            <button
                              type="button"
                              disabled={busy}
                              aria-label={`Count rows in ${table}`}
                              onClick={() => loadSuggestedSql(`SELECT COUNT(*) AS row_count FROM ${source}`)}
                            >
                              Count rows
                            </button>
                            <button
                              type="button"
                              disabled={busy}
                              aria-label={`Preview up to 10 rows from ${table}`}
                              onClick={() => loadSuggestedSql(`SELECT ${preview} FROM ${source} LIMIT 10`)}
                            >
                              Preview up to 10 rows
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </>
              ) : (
                <p>Your current permissions show no tables or columns for this source.</p>
              )}
            </section>
          )}
          {gen && (
            <p className="gen-meta" role="status">
              {gen.cache === "hit" ? (
                <span className="badge">Reused from cache · re-checked against your permissions</span>
              ) : (
                <span className="badge">Freshly generated</span>
              )}
              {gen.attempts != null && gen.attempts > 1 && (
                <span className="badge warn">
                  Corrected automatically after {gen.attempts - 1} failed attempt{gen.attempts > 2 ? "s" : ""}
                </span>
              )}
            </p>
          )}
          <section className="sql-panel">
            <label className="sql-toolbar" htmlFor="live-sql">
              SQL query
            </label>
            <textarea
              ref={editor}
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
                  void run(async (alive) => {
                    setResult(undefined);
                    const r = await engine<Result>(database, "query", { sql });
                    if (alive()) setResult(r);
                  })
                }
              >
                Execute query ▷
              </button>
            </div>
          </section>
          {sql.trim() && (
            <form
              className="save-row"
              onSubmit={(e) => {
                e.preventDefault();
                void run(async () => {
                  await saveQuery(org, database, saveTitle.trim(), sql);
                  setSaveTitle("");
                  setStatus("Saved privately. Share it from the Saved queries tab.");
                });
              }}
            >
              <label>
                Save this query as
                <input required maxLength={100} value={saveTitle} onChange={(e) => setSaveTitle(e.target.value)} />
              </label>
              <button disabled={busy || !saveTitle.trim()}>Save query</button>
            </form>
          )}
          {result && (
            <>
              <ResultTable result={result} />
              <details>
                <summary>Executed SQL</summary>
                <pre className="live-compiled">{result.sql}</pre>
              </details>
            </>
          )}
        </>
      )}
      {busy && <AnimalMorphLoader label="Processing database request" />}
      {error && (
        <div role="alert" className="query-error">
          <p>{error}</p>
          {retry && (
            <button type="button" onClick={retry}>
              Try again
            </button>
          )}
          <button type="button" onClick={() => { setError(""); setRetry(null); }}>
            Dismiss
          </button>
        </div>
      )}
      <p role="status">{status}</p>
    </section>
  );
}
