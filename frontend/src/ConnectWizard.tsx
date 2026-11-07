import { useState } from "react";
import { rpc, rows, type Source } from "./client";
import { engine } from "./LiveEngine";

type Kind = "postgres" | "sqlite";
type Step = "choose" | "details" | "working" | "done";
type Tables = Record<string, Record<string, string>>;

const STAGES: Record<Kind, string[]> = {
  postgres: ["Registering source", "Testing connection", "Discovering tables"],
  sqlite: ["Registering source", "Importing file", "Reading columns"],
};

export function ConnectWizard({
  org,
  onDone,
}: {
  org: string;
  onDone: () => void;
}) {
  const [step, setStep] = useState<Step>("choose"),
    [kind, setKind] = useState<Kind>("postgres"),
    [name, setName] = useState(""),
    [uri, setUri] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<string[][]>([]),
    [stage, setStage] = useState(0),
    [error, setError] = useState(""),
    [summary, setSummary] = useState(""),
    [tables, setTables] = useState<Tables>({}),
    [sourceId, setSourceId] = useState(""),
    [failedAt, setFailedAt] = useState(""),
    [schemaFailed, setSchemaFailed] = useState(false);

  function pickFile(f: File | undefined) {
    setError("");
    if (!f) return;
    if (f.size > 1048576) return setError("Choose a CSV or Parquet file up to 1 MB.");
    setFile(f);
    if (!name) setName(f.name.replace(/\.(csv|parquet)$/i, ""));
    setPreview([]);
    if (f.name.toLowerCase().endsWith(".parquet")) return;
    void f
      .slice(0, 4000)
      .text()
      .then((t) =>
        setPreview(
          t
            .split(/\r?\n/)
            .filter(Boolean)
            .slice(0, 5)
            .map((l) => l.split(",").slice(0, 8)),
        ),
      );
  }

  async function start() {
    setError("");
    setStep("working");
    setFailedAt("");
    setStage(sourceId ? 1 : 0);
    let at = 0;
    try {
      let id = sourceId;
      if (!id) {
        await rpc("register_database", { o: org, title: name, engine: kind });
        const list = await rows<Source>("target_databases", { org_id: org });
        const source = list.filter((s) => s.name === name).pop();
        if (!source) throw Error("The source was registered but could not be found.");
        id = source.id;
        setSourceId(id);
      }
      const source = { id };
      at = 1;
      setStage(1);
      if (kind === "postgres") {
        const r = await engine<{ tables?: number }>(source.id, "connection", { uri }, "PUT");
        setUri("");
        setSummary(
          "Connection verified and stored encrypted on the server" +
            (r.tables != null ? " · " + r.tables + " tables reflected." : "."),
        );
      } else {
        const r = await engine<{ rows: number; columns: string[] }>(
          source.id,
          "import",
          file,
          "PUT",
        );
        setSummary(
          "Imported " + r.rows + " rows and " + r.columns.length + " columns into “records”.",
        );
      }
      setStage(2);
      await loadSchema(source.id);
      setStep("done");
      onDone();
    } catch (e) {
      setFailedAt(STAGES[kind][at]!);
      setUri("");
      setError(e instanceof Error ? e.message : String(e));
      setStep("details");
    }
  }

  async function loadSchema(id: string) {
    try {
      const s = await engine<{ tables: Tables }>(id, "schema");
      setTables(s.tables || {});
      setSchemaFailed(false);
    } catch {
      setTables({});
      setSchemaFailed(true);
    }
  }

  const reset = () => {
    setSourceId("");
    setFailedAt("");
    setSchemaFailed(false);
    setStep("choose");
    setName("");
    setFile(null);
    setPreview([]);
    setTables({});
    setError("");
  };

  return (
    <div className="wizard">
      <ol className="wizard-steps" aria-label="Connection steps">
        {["Choose source", "Details", "Connect", "Review"].map((l, i) => (
          <li
            key={l}
            className={
              i <= ["choose", "details", "working", "done"].indexOf(step) ? "on" : ""
            }
          >
            {l}
          </li>
        ))}
      </ol>

      {step === "choose" && (
        <div className="wizard-choices">
          <button
            type="button"
            className="choice"
            onClick={() => {
              setKind("postgres");
              setStep("details");
            }}
          >
            <b>PostgreSQL</b>
            <span>Live, read-only connection to your database.</span>
          </button>
          <button
            type="button"
            className="choice"
            onClick={() => {
              setKind("sqlite");
              setStep("details");
            }}
          >
            <b>CSV / Parquet import</b>
            <span>Upload one file, up to 1 MB and 20,000 rows.</span>
          </button>
          {["MySQL", "MongoDB", "Snowflake", "BigQuery"].map((n) => (
            <div key={n} className="choice soon" aria-disabled="true">
              <b>{n}</b>
              <span>Coming soon</span>
            </div>
          ))}
        </div>
      )}

      {step === "details" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void start();
          }}
        >
          <label>
            Source name
            <input
              required
              maxLength={80}
              readOnly={!!sourceId}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          {kind === "postgres" ? (
            <label>
              Read-only PostgreSQL connection URI
              <input
                type="password"
                autoComplete="off"
                required
                value={uri}
                onChange={(e) => setUri(e.target.value)}
                placeholder="postgresql://user:password@host:5432/database?sslmode=require"
              />
              <small>
                Use a dedicated read-only user. Sent once to the engine, never
                kept in this browser.
              </small>
            </label>
          ) : (
            <label
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                pickFile(e.dataTransfer.files[0]);
              }}
            >
              {file ? file.name : "Drop a CSV or Parquet file here or click to choose"}
              <input
                type="file"
                accept=".csv,.parquet,text/csv,application/vnd.apache.parquet"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
            </label>
          )}
          {preview.length > 0 && kind === "sqlite" && (
            <div className="data-scroll">
              <table>
                <tbody>
                  {preview.map((r, i) => (
                    <tr key={i}>
                      {r.map((c, j) =>
                        i === 0 ? <th key={j}>{c}</th> : <td key={j}>{c}</td>,
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {error && (
            <div role="alert" className="query-error">
              {failedAt && <p><b>Failed at: {failedAt}</b></p>}
              <p>{error}</p>
              {sourceId && (
                <small>
                  The source is already registered. {kind === "postgres" ? "Re-enter the connection URI and try again" : "Try the import again"} — it won't be registered twice.
                </small>
              )}
            </div>
          )}
          <div className="wizard-actions">
            <button type="button" onClick={reset}>
              {sourceId ? "Cancel" : "← Back"}
            </button>
            <button
              className="primary"
              disabled={kind === "sqlite" && !file}
            >
              {error ? "Try again" : kind === "postgres" ? "Verify & connect" : "Import file"}
            </button>
          </div>
        </form>
      )}

      {step === "working" && (
        <ul className="wizard-progress" role="status">
          {STAGES[kind].map((l, i) => (
            <li key={l} className={i < stage ? "ok" : i === stage ? "now" : ""}>
              {i < stage ? "✓" : i === stage ? "…" : "·"} {l}
            </li>
          ))}
        </ul>
      )}

      {step === "done" && (
        <div>
          <p role="status">{summary}</p>
          {Object.keys(tables).length ? (
            <div className="compiled">
              <pre>
                {Object.entries(tables)
                  .map(([t, c]) => t + " (" + Object.keys(c).join(", ") + ")")
                  .join("\n")}
              </pre>
            </div>
          ) : schemaFailed ? (
            <p role="alert">
              Couldn't read the tables yet.{" "}
              <button type="button" onClick={() => void loadSchema(sourceId)}>
                Try again
              </button>
            </p>
          ) : (
            <small>
              No columns are visible yet. Grant table and column access in the
              access policy below.
            </small>
          )}
          <div className="wizard-actions">
            <button type="button" onClick={reset}>
              Add another source
            </button>
            <a className="primary btn-link" href="#access-policy">
              Configure access →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
