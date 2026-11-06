import { Activity } from "./Activity";
import { LiveEngine } from "./LiveEngine";
import { useCallback, useEffect, useState } from "react";
import {
  rpc,
  rows,
  db,
  type Org,
  type Person,
  type Role,
  type Profile,
  type Invite,
  type Source,
  type Policy,
  type Rule,
} from "./client";
import { AnimalMorphLoader } from "./Motion";
import { useAction } from "./useAction";

function Avatar({ path, name }: { path: string | null; name: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let alive = true;
    setUrl("");
    if (path)
      db?.storage
        .from("avatars")
        .createSignedUrl(path, 3600)
        .then(({ data }) => {
          if (alive && data) setUrl(data.signedUrl);
        });
    return () => {
      alive = false;
    };
  }, [path]);
  return url ? (
    <img className="avatar" src={url} alt="" />
  ) : (
    <span className="avatar">{name[0]?.toUpperCase()}</span>
  );
}
type Act = (f: () => Promise<void>) => Promise<void>;
function InviteForm({
  org,
  roles,
  act,
  busy,
}: {
  org: string;
  roles: Role[];
  act: Act;
  busy: boolean;
}) {
  const [query, setQuery] = useState(""),
    [found, setFound] = useState<Profile[]>([]),
    [person, setPerson] = useState<Profile>(),
    [role, setRole] = useState(
      roles.find((r) => r.name === "VIEWER")?.id || "",
    ),
    [hint, setHint] = useState("");
  useEffect(() => {
    let alive = true;
    setFound([]);
    setHint("");
    if (person || query.length < 2) return;
    const t = setTimeout(
      () =>
        rpc<Profile[]>("find_people", { prefix: query.toLowerCase() })
          .then((p) => {
            if (alive) {
              setFound(p);
              if (!p.length) setHint("No matching handles.");
            }
          })
          .catch((e) => {
            if (alive) setHint(e.message);
          }),
      230,
    );
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [query, person]);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (person)
          void act(async () => {
            await rpc("invite_person", { o: org, person: person.id, r: role });
            setQuery("");
            setPerson(undefined);
          });
      }}
    >
      <label>
        Find a teammate by username
        <input
          placeholder="@username"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value.replace(/^@/, ""));
            setPerson(undefined);
          }}
        />
      </label>
      {found.map((p) => (
        <button
          className="person-result"
          key={p.id}
          type="button"
          onClick={() => {
            setPerson(p);
            setQuery(p.username);
          }}
        >
          <Avatar path={p.avatar_path} name={p.username} />@{p.username}
        </button>
      ))}
      <small role="status">{hint}</small>
      <label>
        Invitation role
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </label>
      <button disabled={busy || !person || !role}>Send invitation ↗</button>
    </form>
  );
}
function PolicyEditor({
  org,
  sources,
  roles,
  people,
  policies,
  act,
  busy,
}: {
  org: string;
  sources: Source[];
  roles: Role[];
  people: Person[];
  policies: Policy[];
  act: Act;
  busy: boolean;
}) {
  const [database, setDatabase] = useState(sources[0]?.id || ""),
    [subject, setSubject] = useState("r:" + roles[0]?.id);
  const policy = policies.find(
    (p) =>
      p.database_id === database &&
      (subject === "r:" + p.role_id || subject === "u:" + p.user_id),
  );
  const [mode, setMode] = useState("NONE"),
    [tables, setTables] = useState<{ name: string; columns: string }[]>([]),
    [rules, setRules] = useState<Rule[]>([]);
  useEffect(() => {
    setMode(policy?.mode || "NONE");
    setTables(
      Object.entries(policy?.table_columns || {}).map(([name, cols]) => ({
        name,
        columns: cols.join(", "),
      })),
    );
    setRules(policy?.row_rules || []);
  }, [database, subject, policy]);
  const options = tables.flatMap((t) =>
    t.columns
      .split(",")
      .map((c) => c.trim())
      .filter(Boolean)
      .map((c) => ({ table: t.name, column: c })),
  );
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void act(async () => {
          if (new Set(tables.map((t) => t.name.trim())).size !== tables.length)
            throw Error("Each table must have a unique name.");
          const cols = Object.fromEntries(
            tables.map((t) => [
              t.name.trim(),
              [
                ...new Set(
                  t.columns
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                ),
              ],
            ]),
          );
          await rpc("save_permission", {
            o: org,
            d: database,
            r: subject.startsWith("r:") ? subject.slice(2) : null,
            person: subject.startsWith("u:") ? subject.slice(2) : null,
            level: mode,
            cols,
            rules,
          });
        });
      }}
    >
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
      <label>
        Apply policy to
        <select value={subject} onChange={(e) => setSubject(e.target.value)}>
          <optgroup label="Role grants">
            {roles.map((r) => (
              <option key={r.id} value={"r:" + r.id}>
                {r.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="Individual restrictions">
            {people.map((p) => (
              <option key={p.user_id} value={"u:" + p.user_id}>
                @{p.username}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      {subject.startsWith("u:") && (
        <small>
          Individual restrictions narrow this member’s role permissions.
        </small>
      )}
      <label>
        Access mode
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          {Object.entries({
            NONE: "No access",
            VIEW_ONLY: "View shared content",
            QUERY_ONLY: "Query data",
            SCHEMA_EDIT: "Edit configuration and query",
          }).map(([v, n]) => (
            <option key={v} value={v}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>Allowed tables and columns</legend>
        {tables.map((t, i) => (
          <div key={i} className="rule-line">
            <label>
              Table
              <input
                required
                value={t.name}
                onChange={(e) =>
                  setTables(
                    tables.map((x, j) =>
                      i === j ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <label>
              Columns, comma-separated
              <input
                required
                value={t.columns}
                onChange={(e) =>
                  setTables(
                    tables.map((x, j) =>
                      i === j ? { ...x, columns: e.target.value } : x,
                    ),
                  )
                }
              />
            </label>
            <button
              type="button"
              aria-label={"Remove table " + (i + 1)}
              onClick={() => setTables(tables.filter((_, j) => j !== i))}
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setTables([...tables, { name: "", columns: "" }])}
        >
          + Table
        </button>
      </fieldset>
      <fieldset>
        <legend>Row conditions · match all</legend>
        {rules.map((r, i) => (
          <div className="rule-line" key={i}>
            <label>
              Column
              <select
                required
                value={JSON.stringify([r.table, r.column])}
                onChange={(e) => {
                  const [table, column] = JSON.parse(e.target.value);
                  setRules(
                    rules.map((q, j) =>
                      i === j ? { ...q, table, column } : q,
                    ),
                  );
                }}
              >
                {options.map((o) => (
                  <option
                    key={JSON.stringify(o)}
                    value={JSON.stringify([o.table, o.column])}
                  >
                    {o.table}.{o.column}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Equals
              <input
                value={r.value}
                required
                onChange={(e) =>
                  setRules(
                    rules.map((q, j) =>
                      i === j ? { ...q, value: e.target.value } : q,
                    ),
                  )
                }
              />
            </label>
            <button
              type="button"
              aria-label="Remove condition"
              onClick={() => setRules(rules.filter((_, j) => i !== j))}
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          disabled={!options.length}
          onClick={() =>
            setRules([...rules, { ...options[0], op: "eq", value: "" }])
          }
        >
          + Condition
        </button>
      </fieldset>
      <button className="primary" disabled={busy}>
        Save access policy ↗
      </button>
    </form>
  );
}
type Data = {
  people: Person[];
  roles: Role[];
  invites: Invite[];
  sources: Source[];
  policies: Policy[];
};
export function Workspace({
  org,
  me,
  reloadAccount,
}: {
  org: Org;
  me: string;
  reloadAccount: () => Promise<void>;
}) {
  const [data, setData] = useState<Data>(),
    [loadError, setLoadError] = useState(""),
    [tab, setTab] = useState("People"),
    [roleName, setRoleName] = useState(""),
    [dbName, setDbName] = useState(""),
    [dialect, setDialect] = useState("postgres"),
    [transfer, setTransfer] = useState(""),
    [message, setMessage] = useState("");
  const { busy, error, run } = useAction();
  const reload = useCallback(async () => {
    const [people, roles, invites, sources, policies] = await Promise.all([
      rpc<Person[]>("org_people", { o: org.id }),
      rows<Role>("roles", { org_id: org.id }),
      rows<Invite>("invitations", { org_id: org.id }),
      rows<Source>("target_databases", { org_id: org.id }),
      rows<Policy>("database_permissions", { org_id: org.id }),
    ]);
    setData({ people, roles, invites, sources, policies });
    setLoadError("");
  }, [org.id]);
  useEffect(() => {
    void reload().catch((e) => setLoadError(e.message));
  }, [reload]);
  async function act(f: () => Promise<void>) {
    setMessage("");
    await run(async () => {
      await f();
      await reload();
      await reloadAccount();
      setMessage("Changes saved.");
    });
  }
  if (loadError)
    return (
      <div role="alert">
        {loadError}{" "}
        <button
          onClick={() => void reload().catch((e) => setLoadError(e.message))}
        >
          Retry
        </button>
      </div>
    );
  if (!data) return <AnimalMorphLoader />;
  const { people, roles, invites, sources, policies } = data,
    roleFor = (id: string) => roles.find((r) => r.id === id);
  const admin =
    roleFor(people.find((p) => p.user_id === me)?.role_id || "")?.name ===
    "ADMIN";
  return (
    <section>
      <div className="work-head">
        <div className="eyebrow">ORGANIZATION WORKSPACE</div>
        <h1>{org.name}</h1>
      </div>
      <div className="tabs">
        {(admin
          ? ["People", "Query engine", "Roles & access", "Activity"]
          : ["People", "Query engine"]
        ).map((n) => (
          <button
            key={n}
            aria-pressed={tab === n}
            onClick={() => {
              setTab(n);
              setMessage("");
            }}
          >
            {n}
          </button>
        ))}
        <button onClick={() => void act(async () => {})} disabled={busy}>
          Refresh
        </button>
      </div>
      {busy && <AnimalMorphLoader label="Saving workspace" />}
      <p aria-live="polite">{error || message}</p>
      {tab === "Activity" && admin ? (
        <Activity org={org.id} key={message} />
      ) : tab === "Query engine" ? (
        <LiveEngine org={org.id} admin={admin} />
      ) : tab === "People" || !admin ? (
        <div className="columns">
          <section className="panel">
            <h2>Members</h2>
            {people.map((p) => (
              <div className="member" key={p.user_id}>
                <Avatar path={p.avatar_path} name={p.username} />
                <strong>@{p.username}</strong>
                {p.user_id === org.owner_id ? (
                  <small>OWNER</small>
                ) : admin ? (
                  <select
                    aria-label={"Role for " + p.username}
                    value={p.role_id}
                    disabled={busy}
                    onChange={(e) =>
                      void act(async () => {
                        await rpc("set_member_role", {
                          o: org.id,
                          person: p.user_id,
                          r: e.target.value,
                        });
                      })
                    }
                  >
                    {roles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <small>{roleFor(p.role_id)?.name}</small>
                )}
              </div>
            ))}
            {me === org.owner_id && people.length > 1 && (
              <details>
                <summary>Transfer ownership</summary>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void act(async () => {
                      await rpc("transfer_owner", {
                        o: org.id,
                        person: transfer,
                      });
                      setTransfer("");
                    });
                  }}
                >
                  <label>
                    New owner
                    <select
                      required
                      value={transfer}
                      onChange={(e) => setTransfer(e.target.value)}
                    >
                      <option value="">Select a member</option>
                      {people
                        .filter((p) => p.user_id !== me)
                        .map((p) => (
                          <option key={p.user_id} value={p.user_id}>
                            @{p.username}
                          </option>
                        ))}
                    </select>
                  </label>
                  <small>You will remain an administrator.</small>
                  <button disabled={busy || !transfer}>
                    Confirm ownership transfer
                  </button>
                </form>
              </details>
            )}
          </section>
          {admin && (
            <section className="panel">
              <h2>Invite a teammate.</h2>
              <InviteForm org={org.id} roles={roles} act={act} busy={busy} />
              {invites.length > 0 && (
                <div className="invites">
                  <h3>Invitations</h3>
                  {invites.map((i) => (
                    <p key={i.id}>
                      {people.find((p) => p.user_id === i.user_id)?.username ||
                        "Invited teammate"}{" "}
                      · {i.status}
                    </p>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      ) : (
        <div className="columns">
          <section className="panel">
            <h2>Roles & sources</h2>
            <p>{roles.map((r) => r.name).join(" · ")}</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void act(async () => {
                  await rpc("create_role", { o: org.id, title: roleName });
                  setRoleName("");
                });
              }}
            >
              <label>
                Custom role name
                <input
                  required
                  maxLength={40}
                  value={roleName}
                  onChange={(e) => setRoleName(e.target.value)}
                />
              </label>
              <button disabled={busy}>Add role</button>
            </form>
            <hr />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void act(async () => {
                  await rpc("register_database", {
                    o: org.id,
                    title: dbName,
                    engine: dialect,
                  });
                  setDbName("");
                });
              }}
            >
              <label>
                Database label
                <input
                  value={dbName}
                  required
                  maxLength={80}
                  onChange={(e) => setDbName(e.target.value)}
                />
              </label>
              <label>
                Dialect
                <select
                  value={dialect}
                  onChange={(e) => setDialect(e.target.value)}
                >
                  {["postgres", "sqlite"].map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </label>
              <small>
                Register metadata to configure access. Live connections arrive
                with the query engine.
              </small>
              <button disabled={busy}>Register database</button>
            </form>
          </section>
          <section className="panel">
            <h2>Access policy</h2>
            {sources.length ? (
              <PolicyEditor
                {...{
                  org: org.id,
                  sources,
                  roles,
                  people,
                  policies,
                  act,
                  busy,
                }}
              />
            ) : (
              <p>
                Register a database to define its allowed tables, columns, and
                rows.
              </p>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
