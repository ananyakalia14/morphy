import { useCallback, useEffect, useState } from "react";
import { db, type Source } from "./client";
import { engine, ResultTable, type Result } from "./LiveEngine";
import { useAction } from "./useAction";
import { createLatest } from "./latest";

export type SavedQuery = {
  id: string;
  org_id: string;
  database_id: string;
  author_id: string;
  title: string;
  sql_text: string;
  shared: boolean;
  revision: number;
  updated_at: string;
};
type Dashboard = Omit<SavedQuery, "sql_text">;
type Panel = { dashboard_id: string; query_id: string; position: number };

const STALE = "This item changed or your access changed. It has been reloaded.";
function friendly(e: { message: string; code?: string }) {
  if (e.code === "PGRST205" || e.code === "PGRST202")
    return "Saved queries and dashboards aren't set up on the server yet (migrations 003–005).";
  if (e.code === "42501") return "You don't have access to do this.";
  return e.message;
}
async function q<T>(p: PromiseLike<{ data: unknown; error: unknown }>) {
  const { data, error } = await p;
  if (error) throw Error(friendly(error as { message: string; code?: string }));
  return data as T;
}

export function useSavedQueries(org: string) {
  const [list, setList] = useState<SavedQuery[]>([]),
    [error, setError] = useState("");
  const [latest] = useState(createLatest);
  const reload = useCallback(async () => {
    const isLatest = latest.next();
    if (!db) {
      if (!isLatest()) return;
      setList([
        {
          id: "sq-1",
          org_id: org,
          database_id: "db-1",
          author_id: "user-demo",
          title: "Monthly Revenue Aggregation",
          sql_text: "SELECT date_trunc('month', created_at) AS month, round(sum(amount), 2) AS revenue\nFROM orders\nWHERE status = 'completed'\nGROUP BY 1\nORDER BY 1 DESC",
          shared: true,
          revision: 1,
          updated_at: new Date().toISOString(),
        },
        {
          id: "sq-2",
          org_id: org,
          database_id: "db-2",
          author_id: "user-demo",
          title: "Active Users By Geographic Region",
          sql_text: "SELECT country, count(distinct user_id) as active_count\nFROM telemetry_sessions\nGROUP BY country\nORDER BY active_count DESC",
          shared: true,
          revision: 1,
          updated_at: new Date(Date.now() - 7200000).toISOString(),
        },
      ]);
      setError("");
      return;
    }
    try {
      const data =
        await q<SavedQuery[]>(
          db
            .from("saved_queries")
            .select("*")
            .eq("org_id", org)
            .order("updated_at", { ascending: false })
            .order("id"),
        );
      if (!isLatest()) return;
      setList(data);
      setError("");
    } catch (e) {
      if (isLatest()) setError((e as Error).message);
    }
  }, [org, latest]);
  useEffect(() => {
    setList([]);
    void reload();
  }, [reload]);
  return { list, error, reload };
}

export async function saveQuery(org: string, database: string, title: string, sql: string) {
  await q(
    db!.from("saved_queries").insert({
      id: crypto.randomUUID(),
      org_id: org,
      database_id: database,
      title,
      sql_text: sql,
    }),
  );
}

async function updateVersioned(
  table: "saved_queries" | "dashboards",
  item: { id: string; revision: number },
  patch: Record<string, unknown>,
) {
  const data = await q<unknown[]>(
    db!.from(table).update(patch).eq("id", item.id).eq("revision", item.revision).select(),
  );
  if (!data.length) throw Error(STALE);
}
async function deleteVersioned(
  table: "saved_queries" | "dashboards",
  item: { id: string; revision: number },
) {
  const data = await q<unknown[]>(
    db!.from(table).delete().eq("id", item.id).eq("revision", item.revision).select(),
  );
  if (!data.length) throw Error(STALE);
}

export function SavedQueries({
  org,
  me,
  sources,
  onOpen,
}: {
  org: string;
  me: string;
  sources: Source[];
  onOpen: (database: string, sql: string) => void;
}) {
  const { list, error: loadError, reload } = useSavedQueries(org);
  const { busy, error, run } = useAction();
  const [editing, setEditing] = useState<SavedQuery>();
  const act = (f: () => Promise<void>) =>
    run(async () => {
      try {
        await f();
      } finally {
        await reload();
      }
    });
  const name = (id: string) => sources.find((s) => s.id === id)?.name || "Database";
  return (
    <section className="panel">
      <h2>Saved queries</h2>
      <p className="muted">
        Shared queries show their full SQL to everyone with access to that database.
      </p>
      {(loadError || error) && <p role="alert">{loadError || error}</p>}
      {!loadError && !list.length && (
        <p>No saved queries yet. Use “Save query” in the Query engine tab.</p>
      )}
      <ul className="lib-list">
        {list.map((s) => (
          <li key={s.id}>
            {editing?.id === s.id ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void act(async () => {
                    await updateVersioned("saved_queries", s, {
                      title: editing.title,
                      sql_text: editing.sql_text,
                    });
                    setEditing(undefined);
                  });
                }}
              >
                <label>
                  Title
                  <input
                    required
                    maxLength={100}
                    value={editing.title}
                    onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                  />
                </label>
                <label>
                  SQL
                  <textarea
                    required
                    spellCheck={false}
                    value={editing.sql_text}
                    onChange={(e) => setEditing({ ...editing, sql_text: e.target.value })}
                  />
                </label>
                <div className="wizard-actions">
                  <button type="button" onClick={() => setEditing(undefined)}>
                    Cancel
                  </button>
                  <button className="primary" disabled={busy}>
                    Save changes
                  </button>
                </div>
              </form>
            ) : (
              <>
                <div className="lib-head">
                  <b>{s.title}</b>
                  <small>
                    {name(s.database_id)} · {s.shared ? "Shared" : "Private"} · v{s.revision}
                  </small>
                </div>
                <pre className="live-compiled">{s.sql_text}</pre>
                <div className="wizard-actions">
                  <button type="button" onClick={() => onOpen(s.database_id, s.sql_text)}>
                    Open in query engine
                  </button>
                  {s.author_id === me && (
                    <>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void act(() => updateVersioned("saved_queries", s, { shared: !s.shared }))
                        }
                      >
                        {s.shared ? "Make private" : "Share with team"}
                      </button>
                      <button type="button" onClick={() => setEditing(s)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          if (confirm("Delete “" + s.title + "”?"))
                            void act(() => deleteVersioned("saved_queries", s));
                        }}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function PanelView({ dashboard, query }: { dashboard: string; query: SavedQuery | undefined }) {
  const [result, setResult] = useState<Result>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [latest] = useState(createLatest);
  const render = useCallback(async () => {
    const isLatest = latest.next();
    setResult(undefined);
    if (!query) return;
    setBusy(true);
    setError("");
    try {
      const r = await engine<Result>("", "", undefined, "POST", "/engine/dashboards/" + dashboard + "/panels/" + query.id + "/render");
      if (isLatest()) setResult(r);
    } catch (e) {
      if (!isLatest()) return;
      setResult(undefined);
      const m = (e as Error).message;
      setError(m.startsWith("You no longer have access") ? "You no longer have access to this panel. " + m : m);
    } finally {
      if (isLatest()) setBusy(false);
    }
  }, [dashboard, query, latest]);
  useEffect(() => () => latest.cancel(), [latest]);
  useEffect(() => {
    void render();
  }, [render]);
  if (!query) return <div className="tile muted">This panel's query isn't visible to you.</div>;
  return (
    <div className="tile">
      <div className="lib-head">
        <b>{query.title}</b>
        <button type="button" onClick={() => void render()} disabled={busy}>
          {busy ? "Loading…" : "Refresh"}
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {result && <ResultTable result={result} />}
    </div>
  );
}

export function Dashboards({ org, me, sources }: { org: string; me: string; sources: Source[] }) {
  const [boards, setBoards] = useState<Dashboard[]>([]),
    [panels, setPanels] = useState<Panel[]>([]),
    [open, setOpen] = useState(""),
    [title, setTitle] = useState(""),
    [database, setDatabase] = useState(sources[0]?.id || ""),
    [loadError, setLoadError] = useState("");
  const { list: queries } = useSavedQueries(org);
  const { busy, error, run } = useAction();
  const [boardsLatest] = useState(createLatest),
    [panelsLatest] = useState(createLatest);
  const reload = useCallback(async () => {
    const isLatest = boardsLatest.next();
    if (!db) {
      if (!isLatest()) return;
      setBoards([
        {
          id: "dash-1",
          org_id: org,
          database_id: sources[0]?.id || "db-1",
          author_id: me,
          title: "Executive Revenue & Churn Overview",
          shared: true,
          revision: 1,
          updated_at: new Date().toISOString(),
        },
      ]);
      setLoadError("");
      return;
    }
    try {
      const b = await q<Dashboard[]>(
        db.from("dashboards").select("*").eq("org_id", org).order("updated_at", { ascending: false }),
      );
      if (!isLatest()) return;
      setBoards(b);
      setLoadError("");
    } catch (e) {
      if (isLatest()) setLoadError((e as Error).message);
    }
  }, [org, boardsLatest]);
  const loadPanels = useCallback(
    async (id: string) => {
      const isLatest = panelsLatest.next();
      if (!db) {
        if (isLatest()) setPanels([]);
        return;
      }
      const p = id
        ? await q<Panel[]>(
            db.from("dashboard_panels").select("*").eq("dashboard_id", id).order("position").order("query_id"),
          )
        : [];
      if (isLatest()) setPanels(p);
    },
    [panelsLatest],
  );
  useEffect(() => {
    setBoards([]);
    setPanels([]);
    setOpen("");
    setLoadError("");
    void reload();
  }, [reload]);
  useEffect(() => {
    setDatabase((d) => (sources.some((s) => s.id === d) ? d : sources[0]?.id || ""));
  }, [sources]);
  useEffect(() => {
    void loadPanels(open).catch((e) => setLoadError(e.message));
  }, [open, loadPanels]);
  const act = (f: () => Promise<void>) =>
    run(async () => {
      try {
        await f();
      } finally {
        await reload();
        await loadPanels(open);
      }
    });
  const board = boards.find((b) => b.id === open);
  const mine = board?.author_id === me;
  const addable = queries.filter(
    (s) => s.database_id === board?.database_id && !panels.some((p) => p.query_id === s.id),
  );
  return (
    <section className="panel">
      <h2>Dashboards</h2>
      {(loadError || error) && <p role="alert">{loadError || error}</p>}
      {!board ? (
        <>
          <ul className="lib-list">
            {boards.map((b) => (
              <li key={b.id} className="lib-head">
                <button type="button" className="link" onClick={() => setOpen(b.id)}>
                  {b.title}
                </button>
                <small>{b.shared ? "Shared" : "Private"}</small>
              </li>
            ))}
          </ul>
          {!loadError && !boards.length && <p>No dashboards yet.</p>}
          {sources.length > 0 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void act(async () => {
                  const id = crypto.randomUUID();
                  await q(db!.from("dashboards").insert({ id, org_id: org, database_id: database, title }));
                  setTitle("");
                  setOpen(id);
                });
              }}
            >
              <h3>New dashboard</h3>
              <label>
                Title
                <input required maxLength={100} value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <label>
                Database
                <select value={database} onChange={(e) => setDatabase(e.target.value)}>
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <button className="primary" disabled={busy}>
                Create dashboard
              </button>
            </form>
          )}
        </>
      ) : (
        <>
          <div className="wizard-actions">
            <button type="button" onClick={() => setOpen("")}>
              ← All dashboards
            </button>
            {mine && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void act(() => updateVersioned("dashboards", board, { shared: !board.shared }))}
                >
                  {board.shared ? "Make private" : "Share with team"}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (confirm("Delete “" + board.title + "”?"))
                      void act(async () => {
                        await deleteVersioned("dashboards", board);
                        setOpen("");
                      });
                  }}
                >
                  Delete
                </button>
              </>
            )}
          </div>
          <h3>{board.title}</h3>
          {board.shared && (
            <small>Each panel is only visible to people who can also see its saved query.</small>
          )}
          {mine && addable.length > 0 && (
            <label>
              Add a saved query as a panel
              <select
                value=""
                disabled={busy}
                onChange={(e) =>
                  void act(async () => {
                    await q(
                      db!.from("dashboard_panels").insert({
                        dashboard_id: board.id,
                        database_id: board.database_id,
                        query_id: e.target.value,
                        position: panels.length,
                      }),
                    );
                  })
                }
              >
                <option value="">Choose a query…</option>
                {addable.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          {!panels.length && <p>No panels yet.</p>}
          <div className="tiles">
            {panels.map((p) => (
              <div key={p.query_id}>
                <PanelView dashboard={board.id} query={queries.find((s) => s.id === p.query_id)} />
                {mine && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void act(async () => {
                        await q(
                          db!.from("dashboard_panels").delete().eq("dashboard_id", board.id).eq("query_id", p.query_id),
                        );
                      })
                    }
                  >
                    Remove panel
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
