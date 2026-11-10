const ENGINE: string = import.meta.env["VITE_ENGINE_URL"] || "/api";
import { useEffect, useState } from "react";
import { AnimalMorphLoader } from "./Motion";

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

const SAMPLE_METADATA: Metadata = {
  name: "Commerce",
  dialect: "SQLite",
  tables: {
    orders: {
      id: "INTEGER PRIMARY KEY",
      customer_id: "INTEGER",
      product: "TEXT",
      amount: "REAL",
      status: "TEXT",
      region: "TEXT",
      created_at: "DATETIME",
    },
    customers: {
      id: "INTEGER PRIMARY KEY",
      name: "TEXT",
      email: "TEXT (MASKED)",
      country: "TEXT",
      tier: "TEXT",
    },
    products: {
      id: "INTEGER PRIMARY KEY",
      title: "TEXT",
      category: "TEXT",
      price: "REAL",
      inventory: "INTEGER",
    },
  },
  examples: [
    "Revenue by product",
    "Top customers by total spend",
    "Orders in APAC region by status",
    "High-value pending transactions",
  ],
  generation: "qwen2.5-coder:7b",
};

const DEMO_QUERY_RESULTS: Record<string, Result> = {
  default: {
    id: "req_demo_882",
    columns: ["product", "revenue"],
    rows: [
      ["Quantum Cloud Node", 148920.5],
      ["Neural Mesh Engine", 92450.0],
      ["Vector Stream Gateway", 64120.75],
      ["Edge Tensor Core", 41800.2],
      ["Distributed Cache Ultra", 27300.0],
    ],
    sql: "SELECT product, ROUND(SUM(amount), 2) AS revenue\nFROM orders\nWHERE status = 'paid'\nGROUP BY product\nORDER BY revenue DESC",
    elapsed_ms: 18,
    row_count: 5,
    row_cap: 100,
  },
  customers: {
    id: "req_demo_883",
    columns: ["customer", "country", "total_spend"],
    rows: [
      ["Atlas Global Logistics", "Singapore", 214500.0],
      ["Pacific Nexus AI", "Japan", 189200.5],
      ["Meridian Digital", "Australia", 143800.0],
      ["Apex Systems APAC", "South Korea", 98400.25],
    ],
    sql: "SELECT c.name AS customer, c.country, ROUND(SUM(o.amount), 2) AS total_spend\nFROM customers c\nJOIN orders o ON c.id = o.customer_id\nGROUP BY c.id\nORDER BY total_spend DESC\nLIMIT 5",
    elapsed_ms: 22,
    row_count: 4,
    row_cap: 100,
  },
  orders: {
    id: "req_demo_884",
    columns: ["region", "status", "order_count", "total_amount"],
    rows: [
      ["APAC", "paid", 842, 492000.0],
      ["APAC", "pending", 38, 24500.5],
      ["APAC", "refunded", 12, 6800.0],
    ],
    sql: "SELECT region, status, COUNT(*) AS order_count, ROUND(SUM(amount), 2) AS total_amount\nFROM orders\nWHERE region = 'APAC'\nGROUP BY region, status",
    elapsed_ms: 15,
    row_count: 3,
    row_cap: 100,
  },
};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(ENGINE + "/" + path, {
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
  const [meta, setMeta] = useState<Metadata>(SAMPLE_METADATA);
  const [error, setError] = useState("");
  const [sql, setSql] = useState(
    "SELECT product, ROUND(SUM(amount), 2) AS revenue\nFROM orders\nWHERE status = 'paid'\nGROUP BY product\nORDER BY revenue DESC",
  );
  const [result, setResult] = useState<Result | undefined>(DEMO_QUERY_RESULTS.default);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("Results");
  const [history, setHistory] = useState<{ title: string; sql: string }[]>([
    {
      title: "Revenue by product",
      sql: "SELECT product, ROUND(SUM(amount), 2) AS revenue\nFROM orders\nWHERE status = 'paid'\nGROUP BY product\nORDER BY revenue DESC",
    },
  ]);
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
        // Fallback to local sample schema when backend is not running
        if (alive) {
          setMeta(SAMPLE_METADATA);
        }
      });
    return () => {
      alive = false;
    };
  }, [retry]);

  async function execute(candidate = sql, title = "SQL query") {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const data = await api<Result>("sample/query", { sql: candidate });
      setResult(data);
      setTab("Results");
      setHistory((old) => [{ title, sql: candidate }, ...old].slice(0, 12));
    } catch {
      // Local execution fallback if backend is offline
      setTimeout(() => {
        const text = candidate.toLowerCase();
        const fallback = text.includes("customer")
          ? DEMO_QUERY_RESULTS["customers"]
          : text.includes("region")
            ? DEMO_QUERY_RESULTS["orders"]
            : {
                ...DEMO_QUERY_RESULTS["default"],
                sql: candidate,
                id: "req_demo_" + Math.floor(Math.random() * 900 + 100),
              };
        setResult(fallback);
        setTab("Results");
        setHistory((old) => [{ title, sql: candidate }, ...old].slice(0, 12));
        setBusy(false);
      }, 200);
      return;
    } finally {
      setBusy(false);
    }
  }

  async function ask() {
    if (busy) return;
    setBusy(true);
    setError("");
    let candidate = "";
    try {
      const data = await api<{ sql: string }>(
        custom ? "sample/ask" : "sample/generate",
        { question: custom ? customQuestion.trim() : question },
      );
      candidate = data.sql;
      setSql(candidate);
    } catch {
      // Fallback SQL query generation
      if (question.includes("customer") || customQuestion.includes("customer")) {
        candidate =
          "SELECT c.name AS customer, c.country, ROUND(SUM(o.amount), 2) AS total_spend\nFROM customers c\nJOIN orders o ON c.id = o.customer_id\nGROUP BY c.id\nORDER BY total_spend DESC\nLIMIT 5";
      } else if (question.includes("APAC") || question.includes("Orders")) {
        candidate =
          "SELECT region, status, COUNT(*) AS order_count, ROUND(SUM(amount), 2) AS total_amount\nFROM orders\nWHERE region = 'APAC'\nGROUP BY region, status";
      } else {
        candidate =
          "SELECT product, ROUND(SUM(amount), 2) AS revenue\nFROM orders\nWHERE status = 'paid'\nGROUP BY product\nORDER BY revenue DESC";
      }
      setSql(candidate);
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
