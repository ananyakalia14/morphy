import { useEffect, useState } from "react";
import { AnimalMorphLoader } from "./Motion";
import { ENGINE_BASE } from "./engineBase";

type Metadata = {
  name: string;
  dialect: string;
  tables: Record<string, Record<string, string>>;
  examples: string[];
  generation: string;
};
type Result = {
  id: string;
  columns: string[];
  rows: unknown[][];
  sql: string;
  elapsed_ms: number;
  row_count: number;
  row_cap: number;
};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(ENGINE_BASE + "/" + path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
    signal: AbortSignal.timeout(path === "sample/ask" ? 195000 : 15000),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw Error(
      typeof error.detail === "string"
        ? error.detail
        : "The query service is unavailable. Check that the backend is running.",
    );
  }
  return response.json();
}

export function QueryWorkbench({ back }: { back: () => void }) {
  const [meta, setMeta] = useState<Metadata>();
  const [error, setError] = useState("");
  const [sql, setSql] = useState(
    "SELECT product, ROUND(SUM(amount), 2) AS revenue\nFROM orders\nWHERE status = 'paid'\nGROUP BY product\nORDER BY revenue DESC",
  );
  const [result, setResult] = useState<Result>();
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("Results");
  const [history, setHistory] = useState<{ title: string; sql: string }[]>([]);
  const [question, setQuestion] = useState("Revenue by product");
  const [customQuestion, setCustomQuestion] = useState("");
  const custom = question === "custom";
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let alive = true;
    api<Metadata>("sample/schema")
      .then((data) => {
        if (alive) {
          setMeta(data);
          setError("");
        }
      })
      .catch(() => {
        if (alive) setError("The sample query service is unavailable. Try reconnecting.");
      });
    return () => {
      alive = false;
    };
  }, [retry]);

  async function execute(candidate = sql, title = "SQL query") {
    if (busy || !meta || !candidate.trim()) return;
    setBusy(true);
    setError("");
    setResult(undefined);
    try {
      const data = await api<Result>("sample/query", { sql: candidate });
      setResult(data);
      setTab("Results");
      setHistory((old) => [{ title, sql: candidate }, ...old].slice(0, 12));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not run the query.");
    } finally {
      setBusy(false);
    }
  }

  async function ask() {
    if (busy || !meta || (custom && !customQuestion.trim())) return;
    setBusy(true);
    setError("");
    setResult(undefined);
    let candidate = "";
    try {
      const data = await api<{ sql: string }>(
        custom ? "sample/ask" : "sample/generate",
        { question: custom ? customQuestion.trim() : question },
      );
      candidate = data.sql;
      setSql(candidate);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not generate SQL.");
    } finally {
      setBusy(false);
    }
    if (candidate) {
      void execute(candidate, custom ? customQuestion : question);
    }
  }
  return (
    <div className="query-app">
      <header className="mast">
        <button className="brand plain" onClick={back}>
          MORPHY
        </button>
        <div className="query-label">
          COMMERCE <span>/</span> SAMPLE WORKSPACE
        </div>
        <button onClick={back}>← Website</button>
      </header>
      <div className="query-layout">
        <aside className="query-sidebar">
          <div className="source-label">
            <span className="eyebrow">DATABASE</span>
            <strong>Commerce</strong>
            <small>SQLite · synthetic data</small>
          </div>
          <div className="schema-title">
            SCHEMA <span>{Object.keys(meta?.tables || {}).length} TABLES</span>
          </div>
          {Object.entries(meta?.tables || {}).map(([name, columns]) => (
            <details key={name} open>
              <summary>▦ {name}</summary>
              {Object.entries(columns).map(([column, type]) => (
                <div className="schema-column" key={column}>
                  <span>{column}</span>
                  <small>{type}</small>
                </div>
              ))}
            </details>
          ))}
          <div className="policy-note">
            <span className="eyebrow">ACTIVE POLICY</span>
            <strong>APAC analyst</strong>
            <p>
              Read queries · APAC rows
              <br />
              Email column restricted
              <br />
              100-row result cap
            </p>
          </div>
        </aside>
        <main className="query-main">
          <div className="query-heading">
            <div>
              <div className="eyebrow">QUERY WORKSPACE</div>
              <h1>Ask. Inspect. Explore.</h1>
            </div>
            <span className="sample-tag">SAMPLE DATA</span>
          </div>
          <section className="ask-panel" aria-label="Example questions">
            <h2>Start with a question.</h2>
            <p>
              Choose an example to generate SQL, then make it your own in the
              editor.
            </p>
            <div className="ask-row">
              <label>
                Question
                <select
                  value={question}
                  disabled={busy || !meta}
                  onChange={(e) => setQuestion(e.target.value)}
                >
                  <option value="custom">Ask your own question</option>
                  {(meta?.examples || ["Revenue by product"]).map((q) => (
                    <option key={q}>{q}</option>
                  ))}
                </select>
              </label>
              <button
                className="primary"
                disabled={busy || !meta || (custom && !customQuestion.trim())}
                onClick={() => void ask()}
              >
                Generate & run ↗
              </button>
            </div>
            {custom && (
              <label>
                Your question
                <input
                  disabled={busy}
                  maxLength={200}
                  value={customQuestion}
                  onChange={(e) => setCustomQuestion(e.target.value)}
                  placeholder="Which customer has the highest paid revenue?"
                />
              </label>
            )}
            <small>
              {custom
                ? "SQL source · local Ollama model"
                : "SQL source · curated example"}
            </small>
          </section>
          <section className="sql-panel">
            <div className="sql-toolbar">
              <h2>SQL editor</h2>
              <span>SQLITE</span>
            </div>
            <label className="sr-only" htmlFor="query-sql">
              SQL query
            </label>
            <textarea
              id="query-sql"
              value={sql}
              spellCheck={false}
              disabled={busy}
              onChange={(e) => setSql(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                  e.preventDefault();
                  void execute();
                }
              }}
            />
            <div className="sql-bottom">
              <small>SELECT queries · Ctrl / ⌘ + Enter to run</small>
              <button
                className="primary"
                disabled={busy || !meta || !sql.trim()}
                onClick={() => void execute()}
              >
                Run query ▷
              </button>
            </div>
          </section>
          {busy && (
            <AnimalMorphLoader label="Validating and querying sample data" />
          )}
          {error && (
            <div className="query-error" role="alert">
              <strong>Request could not complete</strong>
              <p>{error}</p>
              {!meta && (
                <button onClick={() => setRetry((n) => n + 1)}>
                  Retry connection
                </button>
              )}
            </div>
          )}
          <section className="result-panel" aria-label="Query output">
            <div className="result-tabs">
              {["Results", "Governed SQL", "Session history"].map((name) => (
                <button
                  key={name}
                  aria-pressed={tab === name}
                  onClick={() => setTab(name)}
                >
                  {name}
                </button>
              ))}
              {result && (
                <small aria-live="polite">
                  {result.row_count} rows · {result.elapsed_ms} ms
                </small>
              )}
            </div>
            {tab === "Results" ? (
              result ? (
                <>
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
                              <td key={j}>
                                {v === null ? <em>NULL</em> : String(v)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="result-foot">
                    <span>
                      APAC row policy applied before joins and aggregation.
                    </span>
                    <span>REQUEST {result.id}</span>
                  </div>
                  {!result.rows.length && (
                    <p className="empty-result">
                      Query completed with no matching rows.
                    </p>
                  )}
                </>
              ) : (
                <div className="empty-result">
                  <span>↗</span>
                  <h3>Your results belong here.</h3>
                  <p>
                    Run an example or write a SELECT query to explore the sample
                    database.
                  </p>
                </div>
              )
            ) : tab === "Governed SQL" ? (
              <div className="compiled">
                <p>
                  Each source is filtered to APAC and restricted columns are
                  removed before execution.
                </p>
                <pre>
                  {result?.sql ||
                    "Run a query to inspect the SQL that was executed."}
                </pre>
              </div>
            ) : (
              <div className="query-history">
                {history.length ? (
                  history.map((entry, i) => (
                    <button
                      disabled={busy}
                      key={i}
                      onClick={() => {
                        setSql(entry.sql);
                        setTab("Results");
                        setResult(undefined);
                      }}
                    >
                      <span>{entry.title}</span>
                      <small>Load SQL ↗</small>
                    </button>
                  ))
                ) : (
                  <p>Successful queries from this session will appear here.</p>
                )}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
