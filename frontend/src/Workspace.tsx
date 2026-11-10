import { ConnectWizard } from "./ConnectWizard";
import { Activity } from "./Activity";
import { LiveEngine } from "./LiveEngine";
import { SavedQueries, Dashboards } from "./Library";
import { CliPromoSection } from "./CliPromoSection";
import { useCallback, useEffect, useState } from "react";
import {
  Menu,
  Home,
  Package,
  Users,
  Settings,
  FileCode,
  LayoutDashboard,
  Activity as ActivityIcon,
  RotateCw,
  X,
  UserPen,
  Terminal,
  Download,
  Copy,
  Check,
  ExternalLink,
} from "lucide-react";
import {
  rpc,
  rows,
  db,
  uploadAvatar,
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
            setRules([...rules, { ...options[0]!, op: "eq", value: "" } as Rule])
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
function WorkspaceOverview({
  org,
  people,
  sources,
  policies,
  roles,
  me,
  onNavigate,
}: {
  org: Org;
  people: Person[];
  sources: Source[];
  policies: Policy[];
  roles: Role[];
  me: string;
  onNavigate: (tab: string) => void;
}) {
  const isOwner = me === org.owner_id;
  const ownerPerson = people.find((p) => p.user_id === org.owner_id);

  return (
    <div className="workspace-overview-grid">
      {/* 1. Welcome / Primary Action Row */}
      <div className="overview-stats-grid">
        <div className="overview-stat-card">
          <div className="stat-label">TEAM COLLABORATORS</div>
          <div className="stat-value">{people.length}</div>
          <div className="stat-sub">
            {roles.length} roles active across workspace
          </div>
          <button
            type="button"
            className="stat-action-btn"
            onClick={() => onNavigate("People")}
          >
            Manage team ↗
          </button>
        </div>

        <div className="overview-stat-card">
          <div className="stat-label">CONNECTED ENGINES</div>
          <div className="stat-value">{sources.length}</div>
          <div className="stat-sub">
            {sources.map((s) => s.name).join(", ") || "No databases linked"}
          </div>
          <button
            type="button"
            className="stat-action-btn"
            onClick={() => onNavigate("Query engine")}
          >
            Launch SQL engine ↗
          </button>
        </div>

        <div className="overview-stat-card">
          <div className="stat-label">ACCESS POLICIES</div>
          <div className="stat-value">{policies.length}</div>
          <div className="stat-sub">Row & column-level security</div>
          <button
            type="button"
            className="stat-action-btn"
            onClick={() => onNavigate("Roles & access")}
          >
            Configure RBAC ↗
          </button>
        </div>

        <div className="overview-stat-card">
          <div className="stat-label">MESH STATUS</div>
          <div className="stat-value text-emerald-500">LIVE</div>
          <div className="stat-sub">Distributed query federation active</div>
          <button
            type="button"
            className="stat-action-btn"
            onClick={() => onNavigate("Activity")}
          >
            View telemetry ↗
          </button>
        </div>
      </div>

      {/* Quick Launch Cards */}
      <div className="overview-sections-grid">
        <div className="overview-card">
          <h3>Quick Launchpad</h3>
          <p className="overview-desc">
            Explore databases, execute federated queries, or visualize metrics
            directly inside Morphy.
          </p>
          <div className="overview-actions-row">
            <button
              type="button"
              className="overview-primary-btn"
              onClick={() => onNavigate("Query engine")}
            >
              <Package className="w-4 h-4 mr-2" />
              Open Query Engine
            </button>
            <button
              type="button"
              className="overview-secondary-btn"
              onClick={() => onNavigate("Dashboards")}
            >
              <LayoutDashboard className="w-4 h-4 mr-2" />
              Dashboards
            </button>
            <button
              type="button"
              className="overview-secondary-btn"
              onClick={() => onNavigate("Saved queries")}
            >
              <FileCode className="w-4 h-4 mr-2" />
              Saved Queries
            </button>
          </div>
        </div>

        <div className="overview-card">
          <h3>Workspace Metadata</h3>
          <dl className="overview-meta-list">
            <div>
              <dt>Organization</dt>
              <dd>{org.name}</dd>
            </div>
            <div>
              <dt>Owner</dt>
              <dd>@{ownerPerson?.username || "administrator"}</dd>
            </div>
            <div>
              <dt>Your Permission</dt>
              <dd>
                {isOwner
                  ? "OWNER (Full Administrative Access)"
                  : "MEMBER (Standard Access)"}
              </dd>
            </div>
            <div>
              <dt>Federation Engine</dt>
              <dd>Apache Arrow / DuckDB / Polyglot SQL</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* 2. MORPHY CLI Promotional Section (Secondary Action) */}
      <CliPromoSection />
    </div>
  );
}

export function Workspace({
  org,
  me,
  profile,
  reloadAccount,
}: {
  org: Org;
  me: string;
  profile?: Profile;
  reloadAccount: () => Promise<void>;
}) {
  const [data, setData] = useState<Data>(),
    [loadError, setLoadError] = useState(""),
    [tab, setTab] = useState(() => {
      const h = location.hash;
      if (h === "#dashboards") return "Dashboards";
      if (h === "#sources" || h === "#query") return "Query engine";
      if (h === "#team") return "People";
      if (h === "#queries") return "Saved queries";
      if (h === "#governance") return "Roles & access";
      if (h === "#activity") return "Activity";
      return "Home";
    }),
    [collapsed, setCollapsed] = useState(() => {
      return localStorage.getItem("morphy_sidebar_collapsed") !== "false";
    }),
    [mobileOpen, setMobileOpen] = useState(false),
    [roleName, setRoleName] = useState(""),
    [transfer, setTransfer] = useState(""),
    [message, setMessage] = useState(""),
    [opened, setOpened] = useState<{ database: string; sql: string }>();
  const { busy, error, run } = useAction();

  // Profile editing state
  const currentUser: Profile = profile || {
    id: me,
    username: "ananya",
    display_name: "Ananya Kalia",
    avatar_path: null,
  };
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [editName, setEditName] = useState(currentUser.display_name || "");
  const [editFile, setEditFile] = useState<File | null>(null);
  const [clearAvatar, setClearAvatar] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");
  const [profileError, setProfileError] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string>("");

  useEffect(() => {
    let alive = true;
    setAvatarUrl("");
    if (currentUser.avatar_path) {
      db?.storage
        .from("avatars")
        .createSignedUrl(currentUser.avatar_path, 3600)
        .then(({ data }) => {
          if (alive && data) setAvatarUrl(data.signedUrl);
        })
        .catch(() => {});
    }
    return () => {
      alive = false;
    };
  }, [currentUser.avatar_path]);

  useEffect(() => {
    const handleHash = () => {
      const h = location.hash;
      if (h === "#dashboards") setTab("Dashboards");
      else if (h === "#sources" || h === "#query") setTab("Query engine");
      else if (h === "#team") setTab("People");
      else if (h === "#queries") setTab("Saved queries");
      else if (h === "#governance") setTab("Roles & access");
      else if (h === "#activity") setTab("Activity");
      else if (h === "#workspace" || h === "") setTab("Home");
    };
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  useEffect(() => {
    if (profileModalOpen) {
      setEditName(currentUser.display_name || "");
      setEditFile(null);
      setClearAvatar(false);
      setProfileMsg("");
      setProfileError("");
      setPreviewUrl(null);
    }
  }, [profileModalOpen, currentUser.display_name]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setEditFile(f);
    if (f) {
      setPreviewUrl(URL.createObjectURL(f));
    } else {
      setPreviewUrl(null);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileMsg("");
    setProfileError("");
    const n = editName.trim();
    if (n.length < 1 || n.length > 80) {
      setProfileError("Display name must be 1–80 characters.");
      return;
    }
    setProfileBusy(true);
    try {
      let avatar = currentUser.avatar_path;
      if (editFile) {
        if (db) {
          avatar = await uploadAvatar(editFile, currentUser.id);
        } else {
          avatar = previewUrl;
        }
      } else if (clearAvatar) {
        avatar = null;
      }
      if (db) {
        await rpc("update_profile", { full_name: n, avatar });
      }
      await reloadAccount();
      setProfileMsg("Profile updated successfully.");
      setTimeout(() => {
        setProfileModalOpen(false);
      }, 700);
    } catch (err: any) {
      setProfileError(err?.message || "Failed to update profile.");
    } finally {
      setProfileBusy(false);
    }
  };

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("morphy_sidebar_collapsed", String(next));
      return next;
    });
  };
  const reload = useCallback(async () => {
    const CANONICAL_ROLES: Role[] = [
      { id: "role-admin", name: "ADMIN", builtin: true },
      { id: "role-data-engineer", name: "DATA_ENGINEER", builtin: true },
      { id: "role-analyst", name: "ANALYST", builtin: true },
      { id: "role-viewer", name: "VIEWER", builtin: true },
    ];

    if (!db) {
      setData({
        people: [
          { user_id: me, username: "ananya", role_id: "role-admin", avatar_path: null },
          { user_id: "u-2", username: "alex_lead", role_id: "role-data-engineer", avatar_path: null },
          { user_id: "u-3", username: "sarah_data", role_id: "role-analyst", avatar_path: null },
          { user_id: "u-4", username: "marcus_view", role_id: "role-viewer", avatar_path: null },
        ],
        roles: CANONICAL_ROLES,
        invites: [],
        sources: [
          { id: "db-1", name: "production_pg", dialect: "PostgreSQL" },
          { id: "db-2", name: "analytics_duckdb", dialect: "DuckDB" },
          { id: "db-3", name: "telemetry_csv", dialect: "SQLite" },
        ],
        policies: [],
      });
      setLoadError("");
      return;
    }
    const [people, fetchedRoles, invites, sources, policies] = await Promise.all([
      rpc<Person[]>("org_people", { o: org.id }),
      rows<Role>("roles", { org_id: org.id }),
      rows<Invite>("invitations", { org_id: org.id }),
      rows<Source>("target_databases", { org_id: org.id }),
      rows<Policy>("database_permissions", { org_id: org.id }),
    ]);

    // Ensure the 4 canonical roles (ADMIN, DATA_ENGINEER, ANALYST, VIEWER) are present
    const rolesMap = new Map<string, Role>();
    for (const r of CANONICAL_ROLES) rolesMap.set(r.name, r);
    for (const r of fetchedRoles) rolesMap.set(r.name, r);
    const roles = Array.from(rolesMap.values());

    setData({ people, roles, invites, sources, policies });
    setLoadError("");
  }, [org.id, me]);
  useEffect(() => {
    void reload().catch((e) => setLoadError(e.message));
  }, [reload]);
  async function act(f: () => Promise<void>) {
    setMessage("");
    await run(async () => {
      if (db) await f();
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
  const navItems = [
    { id: "Home", label: "Home", icon: Home },
    { id: "Query engine", label: "Query engine", badge: "SQL", icon: Package },
    { id: "People", label: "Team", badge: `${people.length}`, icon: Users },
    { id: "Saved queries", label: "Saved queries", icon: FileCode },
    { id: "Dashboards", label: "Dashboards", icon: LayoutDashboard },
    ...(admin
      ? [
          { id: "Roles & access", label: "Settings", badge: "RBAC", icon: Settings },
          { id: "Activity", label: "Activity", badge: "LOGS", icon: ActivityIcon },
        ]
      : []),
  ];

  const activeNavItem = navItems.find((i) => i.id === tab);

  return (
    <div className="workspace-wrapper">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="workspace-sheet-backdrop"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Vertical Navigation Sidebar */}
      <aside
        className={`workspace-sidebar ${collapsed ? "is-collapsed" : "is-expanded"} ${mobileOpen ? "is-mobile-open" : ""}`}
        aria-label="Workspace navigation"
      >
        {/* Sidebar Header with Menu hamburger button */}
        <div className="workspace-sidebar-header">
          <button
            type="button"
            className="workspace-menu-btn"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Menu className="w-5 h-5" />
          </button>
          {!collapsed && (
            <div className="workspace-sidebar-brand">
              <span className="workspace-sidebar-title">Dashboard</span>
            </div>
          )}
          {mobileOpen && (
            <button
              type="button"
              className="workspace-close-btn md:hidden"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Divider line directly below menu icon */}
        <div className="workspace-sidebar-divider" />

        {/* Navigation list */}
        <div className="workspace-sidebar-body">
          <nav className="workspace-nav-list">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = tab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`workspace-nav-btn ${isActive ? "is-active" : ""}`}
                  onClick={() => {
                    setTab(item.id);
                    setMessage("");
                    setMobileOpen(false);
                  }}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon className="workspace-nav-icon" />
                  {!collapsed && (
                    <span className="workspace-nav-label">{item.label}</span>
                  )}
                  {!collapsed && item.badge && (
                    <span className="workspace-nav-badge">{item.badge}</span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer with Profile & Refresh */}
        <div className="workspace-sidebar-footer">
          <div className="workspace-sidebar-divider" />

          {/* User Profile / Edit Profile Button */}
          <button
            type="button"
            className={`workspace-profile-btn ${collapsed ? "is-collapsed" : ""}`}
            onClick={() => setProfileModalOpen(true)}
            title={collapsed ? `Edit profile (@${currentUser.username})` : undefined}
            aria-label="Edit user profile"
          >
            <div className="workspace-profile-avatar">
              {avatarUrl ? (
                <img src={avatarUrl} alt="" className="w-full h-full object-cover rounded-full" />
              ) : (
                <span>{currentUser.display_name?.[0]?.toUpperCase() || currentUser.username?.[0]?.toUpperCase() || "U"}</span>
              )}
            </div>
            {!collapsed && (
              <div className="workspace-profile-info">
                <span className="workspace-profile-name">{currentUser.display_name || currentUser.username}</span>
                <span className="workspace-profile-handle">@{currentUser.username}</span>
              </div>
            )}
            {!collapsed && (
              <span className="workspace-profile-edit-badge" title="Edit profile">
                <UserPen className="w-3.5 h-3.5" />
                <span>Edit</span>
              </span>
            )}
          </button>

          <button
            type="button"
            className={`workspace-nav-btn workspace-refresh-btn ${busy ? "is-busy" : ""}`}
            onClick={() => void act(async () => {})}
            disabled={busy}
            title={collapsed ? "Refresh workspace" : undefined}
          >
            <RotateCw className={`workspace-nav-icon ${busy ? "animate-spin" : ""}`} />
            {!collapsed && (
              <span className="workspace-nav-label">Refresh</span>
            )}
            {!collapsed && (
              <span className="workspace-nav-badge">SYNC</span>
            )}
          </button>
        </div>
      </aside>

      {/* Edit Profile Modal Dialog */}
      {profileModalOpen && (
        <div
          className="workspace-modal-overlay"
          onClick={() => setProfileModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-profile-title"
        >
          <div
            className="workspace-modal-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="workspace-modal-header">
              <div>
                <div className="workspace-modal-eyebrow">USER SETTINGS</div>
                <h2 id="edit-profile-title" className="workspace-modal-title">Edit Profile</h2>
              </div>
              <button
                type="button"
                className="workspace-modal-close-btn"
                onClick={() => setProfileModalOpen(false)}
                aria-label="Close profile editor"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleProfileSubmit} className="workspace-profile-form">
              <div className="workspace-profile-preview-row">
                <div className="workspace-profile-preview-avatar">
                  {previewUrl || avatarUrl ? (
                    <img
                      src={previewUrl || avatarUrl}
                      alt="Avatar preview"
                      className="w-full h-full object-cover rounded-full"
                    />
                  ) : (
                    <span>{editName?.[0]?.toUpperCase() || currentUser.username?.[0]?.toUpperCase() || "U"}</span>
                  )}
                </div>
                <div>
                  <div className="font-semibold text-sm">@{currentUser.username}</div>
                  <div className="text-xs text-slate-500">Your handle cannot be changed</div>
                </div>
              </div>

              <label className="workspace-form-field">
                <span>Display Name</span>
                <input
                  type="text"
                  required
                  maxLength={80}
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Your full name"
                  className="workspace-form-input"
                />
              </label>

              <label className="workspace-form-field">
                <span>Profile Picture (JPG, PNG, or WebP)</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileChange}
                  className="workspace-file-input"
                />
              </label>

              {currentUser.avatar_path && !editFile && (
                <label className="workspace-checkbox-label">
                  <input
                    type="checkbox"
                    checked={clearAvatar}
                    onChange={(e) => setClearAvatar(e.target.checked)}
                  />
                  <span>Remove current profile picture</span>
                </label>
              )}

              {profileMsg && (
                <div className="workspace-modal-feedback success">
                  {profileMsg}
                </div>
              )}
              {profileError && (
                <div className="workspace-modal-feedback error">
                  {profileError}
                </div>
              )}

              <div className="workspace-modal-actions">
                <button
                  type="button"
                  className="workspace-btn-secondary"
                  onClick={() => setProfileModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="workspace-btn-primary"
                  disabled={profileBusy}
                >
                  {profileBusy ? "Saving..." : "Save Profile ↗"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="workspace-main-content">
        {/* Mobile Header Bar */}
        <div className="workspace-mobile-bar">
          <button
            type="button"
            className="workspace-menu-btn"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="workspace-mobile-title">
            {activeNavItem?.label || tab}
          </span>
        </div>

        {/* Workspace Header */}
        <div className="workspace-header">
          <div className="workspace-eyebrow">
            ORGANIZATION WORKSPACE / {activeNavItem?.label || tab}
          </div>
          <div className="workspace-title-row">
            <h1>{org.name}</h1>
          </div>
        </div>

        {busy && <AnimalMorphLoader label="Saving workspace" />}
        <p aria-live="polite" className="workspace-msg">{error || message}</p>

        {/* Active Tab View */}
        <div className="workspace-view-container">
          {tab === "Home" ? (
            <WorkspaceOverview
              org={org}
              people={people}
              sources={sources}
              policies={policies}
              roles={roles}
              me={me}
              onNavigate={(t) => setTab(t)}
            />
          ) : tab === "Activity" && admin ? (
            <Activity org={org.id} key={message} />
          ) : tab === "Query engine" ? (
            <LiveEngine org={org.id} admin={admin} initial={opened} />
          ) : tab === "Saved queries" ? (
            <SavedQueries
              org={org.id}
              me={me}
              sources={sources}
              onOpen={(database, sql) => {
                setOpened({ database, sql });
                setTab("Query engine");
              }}
            />
          ) : tab === "Dashboards" ? (
            <Dashboards org={org.id} me={me} sources={sources} />
          ) : tab === "Roles & access" && admin ? (
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
                <h3>Connect a data source</h3>
                <ConnectWizard org={org.id} onDone={() => void reload()} />
              </section>
              <section className="panel">
                <h2 id="access-policy">Access policy</h2>
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
          ) : (
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
                        <div className="member" key={i.id}>
                          <span>
                            {people.find((p) => p.user_id === i.user_id)?.username ||
                              "Invited teammate"}{" "}
                            · {roleFor(i.role_id)?.name} ·{" "}
                            <b>{i.status === "revoked" ? "withdrawn" : i.status}</b>
                          </span>
                          {i.status === "pending" && (
                            <button
                              disabled={busy}
                              onClick={() => {
                                if (confirm("Withdraw this invitation?"))
                                  void act(() => rpc("revoke_invitation", { inv: i.id }).then(() => {}));
                              }}
                            >
                              Withdraw
                            </button>
                          )}
                          {i.status === "revoked" && (
                            <button
                              disabled={busy}
                              onClick={() =>
                                void act(() =>
                                  rpc("invite_person", { o: org.id, person: i.user_id, r: i.role_id }).then(() => {}),
                                )
                              }
                            >
                              Reissue
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
