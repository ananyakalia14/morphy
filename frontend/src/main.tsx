import { createRoot } from "react-dom/client";
import "./style.css";
import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
  useRef,
  lazy,
  Suspense,
} from "react";
import type { Session } from "@supabase/supabase-js";
import "@fontsource/syne/latin-700.css";
import "@fontsource/syne/latin-800.css";
import "@fontsource/jetbrains-mono/latin-500.css";
import {
  db,
  rpc,
  rows,
  uploadAvatar,
  type Profile,
  type Org,
  type Invite,
} from "./client";
import { AnimalMorphLoader, Intro, useReducedMotion } from "./Motion";
import { Landing } from "./Landing";
import { SESSION_EXPIRED } from "./engineBase";
import { useConstrainedConnection } from "./connection";
import { SiteFooter } from "./SiteFooter";

// Lazy-load heavier routes for instant initial landing load
const QueryWorkbench = lazy(() =>
  import("./QueryWorkbench").then((m) => ({ default: m.QueryWorkbench })),
);
const Workspace = lazy(() =>
  import("./Workspace").then((m) => ({ default: m.Workspace })),
);
const LoginPage = lazy(() =>
  import("./LoginPage").then((m) => ({ default: m.LoginPage })),
);

function ProfileEditor({ profile, done }: { profile: Profile; done: () => Promise<void> }) {
  const [name, setName] = useState(profile.display_name),
    [file, setFile] = useState<File | null>(null),
    [clear, setClear] = useState(false),
    [msg, setMsg] = useState("");
  const { busy, error, run } = useAction();
  return (
    <details className="profile-edit">
      <summary>Edit profile</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setMsg("");
          void run(async () => {
            const n = name.trim();
            if (n.length < 1 || n.length > 80) throw Error("Names must be 1–80 characters.");
            const avatar = file ? await uploadAvatar(file, profile.id) : clear ? null : profile.avatar_path;
            await rpc("update_profile", { full_name: n, avatar });
            setFile(null);
            setClear(false);
            await done();
            setMsg("Profile saved.");
          });
        }}
      >
        <label>
          Display name
          <input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          New profile picture (JPG, PNG or WebP)
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        {profile.avatar_path && !file && (
          <label className="check">
            <input type="checkbox" checked={clear} onChange={(e) => setClear(e.target.checked)} /> Remove current picture
          </label>
        )}
        <small>Your username @{profile.username} can't be changed.</small>
        <button className="primary" disabled={busy}>Save profile</button>
        <p aria-live="polite">{error || msg}</p>
      </form>
    </details>
  );
}

import { useAction } from "./useAction";
function Shell({
  children,
  back,
  signout,
  noFooter,
  fullWidth,
}: {
  children: ReactNode;
  back?: () => void;
  signout?: () => void;
  noFooter?: boolean;
  fullWidth?: boolean;
}) {
  return (
    <>
      <header className="mast">
        <button
          className="brand plain"
          onClick={back ?? (() => location.assign("/"))}
        >
          MORPHY
        </button>
        <nav>{signout && <button onClick={signout}>Sign out ↗</button>}</nav>
      </header>
      <main className={fullWidth ? "shell shell-full" : "shell"}>{children}</main>
      {!noFooter && <SiteFooter />}
    </>
  );
}
function Notice({ error }: { error: string }) {
  return error ? (
    <p role="alert" className="error">
      {error}
    </p>
  ) : null;
}
function Identity({
  session,
  done,
}: {
  session: Session;
  done: () => Promise<void>;
}) {
  const defaultName = String(
    session.user.user_metadata["full_name"] ||
      session.user.email?.split("@")[0] ||
      "",
  );
  const [name, setName] = useState(defaultName),
    [handle, setHandle] = useState(
      defaultName
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, "")
        .slice(0, 24),
    ),
    [file, setFile] = useState<File>(),
    [availability, setAvailability] = useState(""),
    [checked, setChecked] = useState("");
  const { busy, error, run } = useAction();
  useEffect(() => {
    let live = true;
    setChecked("");
    setAvailability("");
    if (!/^[a-z][a-z0-9_]{2,23}$/.test(handle)) return;
    const t = setTimeout(
      () =>
        rpc<boolean>("username_available", { handle })
          .then((ok) => {
            if (live) {
              setAvailability(ok ? "Available" : "Already claimed");
              setChecked(ok ? handle : "");
            }
          })
          .catch(() => {
            if (live)
              setAvailability("Availability check failed. Edit to retry.");
          }),
      250,
    );
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [handle]);
  return (
    <section className="panel narrow">
      <div className="eyebrow">GLOBAL IDENTITY</div>
      <h2>Claim your handle.</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            const avatar = file
              ? await uploadAvatar(file, session.user.id)
              : null;
            await rpc("claim_profile", { handle, full_name: name, avatar });
            await done();
          });
        }}
      >
        <label>
          Display name
          <input
            value={name}
            maxLength={80}
            required
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Global username
          <input
            value={handle}
            maxLength={24}
            pattern="[a-z][a-z0-9_]{2,23}"
            required
            onChange={(e) => setHandle(e.target.value.toLowerCase())}
          />
        </label>
        <small aria-live="polite">
          {availability || "3–24 characters. Start with a letter."}
        </small>
        <label>
          Profile picture (optional)
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0])}
          />
        </label>
        <button className="primary" disabled={busy || checked !== handle}>
          Claim @{handle || "username"} ↗
        </button>
      </form>
      <Notice error={error} />
      {busy && <AnimalMorphLoader label="Saving profile" />}
    </section>
  );
}
function Account({
  session,
  signout,
}: {
  session: Session;
  signout: () => void;
}) {
  const [data, setData] = useState<{
      profile?: Profile | undefined;
      orgs: Org[];
      invites: Invite[];
    }>(),
    [org, setOrg] = useState(""),
    [title, setTitle] = useState(""),
    [creating, setCreating] = useState(false),
    [loadError, setLoadError] = useState("");
  const { busy, error, run } = useAction();
  const reload = useCallback(async () => {
    setLoadError("");
    const [profiles, orgs, invites] = await Promise.all([
      rows<Profile>("profiles", { id: session.user.id }),
      rows<Org>("organizations"),
      rows<Invite>("invitations", {
        user_id: session.user.id,
        status: "pending",
      }),
    ]);
    setData({ profile: profiles[0], orgs, invites });
    setOrg((old) => (orgs.some((o) => o.id === old) ? old : orgs[0]?.id || ""));
  }, [session.user.id]);
  useEffect(() => {
    void reload().catch((e) => setLoadError(e.message));
  }, [reload]);
  const active = data?.orgs.find((o) => o.id === org);
  return (
    <Shell signout={signout} noFooter={true} fullWidth={true}>
      {loadError ? (
        <>
          <Notice error={loadError} />
          <button
            onClick={() => void reload().catch((e) => setLoadError(e.message))}
          >
            Retry
          </button>
        </>
      ) : !data ? (
        <AnimalMorphLoader />
      ) : !data.profile ? (
        <Identity session={session} done={reload} />
      ) : (
        <>
          <div className="account-bar">
            <strong>@{data.profile.username}</strong>
            {data.orgs.length > 0 && (
              <>
                <label>
                  Organization
                  <select
                    value={org}
                    onChange={(e) => {
                      setOrg(e.target.value);
                      setCreating(false);
                    }}
                  >
                    {data.orgs.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button onClick={() => setCreating(!creating)}>
                  {creating ? "Cancel" : "+ Organization"}
                </button>
              </>
            )}
          </div>
          {data.invites.map((i) => (
            <div className="invite-banner" key={i.id}>
              <span>
                You’re invited to <strong>{i.organization_name}</strong>.
              </span>
              <button
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await rpc("accept_invitation", { inv: i.id });
                    await reload();
                    setOrg(i.org_id);
                    setCreating(false);
                  })
                }
              >
                Accept invitation
              </button>
            </div>
          ))}
          {creating || !active ? (
            <section className="panel narrow">
              <div className="eyebrow">ORGANIZATION</div>
              <h2>Create a workspace.</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(async () => {
                    const id = await rpc<string>("create_workspace", { title });
                    await reload();
                    setOrg(id);
                    setCreating(false);
                    setTitle("");
                  });
                }}
              >
                <label>
                  Organization name
                  <input
                    required
                    maxLength={80}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </label>
                <button className="primary" disabled={busy}>
                  Create organization ↗
                </button>
              </form>
            </section>
          ) : (
            <Workspace
              key={active.id}
              org={active}
              me={session.user.id}
              profile={data.profile}
              reloadAccount={reload}
            />
          )}
          <Notice error={error} />
        </>
      )}
    </Shell>
  );
}
const isWorkspaceHash = (h: string) =>
  [
    "#workspace",
    "#dashboards",
    "#governance",
    "#sources",
    "#team",
    "#queries",
    "#query",
    "#activity",
    "#cli",
    "#orgs",
  ].includes(h);

const resolvePage = (hash: string) => {
  if (hash === "#signup") return "signup";
  if (hash === "#signin") return "signin";
  if (hash === "#explore") return "explore";
  if (isWorkspaceHash(hash)) return "workspace";
  return "landing";
};

export function App() {
  const reducedMotion = useReducedMotion();
  const constrained = useConstrainedConnection();
  const [session, setSession] = useState<Session | null>(null),
    [ready, setReady] = useState(!db),
    [page, setPage] = useState(() => resolvePage(location.hash));
  const [intro, setIntro] = useState(
    () =>
      location.hash === "" &&
      sessionStorage.getItem("morphy-intro-dismissed") !== "1" &&
      !reducedMotion && !constrained && !matchMedia("(max-width: 780px)").matches,
  );
  const showIntro = page === "landing" && intro && !reducedMotion && !constrained;
  const [expiredNote, setExpiredNote] = useState(false);
  useEffect(() => {
    if (session) sessionStorage.removeItem("morphy-expired");
    setExpiredNote(!session && sessionStorage.getItem("morphy-expired") === "1");
  }, [session, page]);
  useEffect(() => { if (reducedMotion || constrained) setIntro(false); }, [reducedMotion, constrained]);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [page, session?.user.id]);
  const close = useCallback((focusHero = true) => {
    sessionStorage.setItem("morphy-intro-dismissed", "1");
    setIntro(false);
    if (focusHero) requestAnimationFrame(() =>
      document
        .querySelector<HTMLButtonElement>(".hero-copy .primary")
        ?.focus({ preventScroll: true }),
    );
  }, []);
  useEffect(() => {
    const s = db?.auth.onAuthStateChange((_e, next) => {
      setSession(next);
      setReady(true);
    });
    const nav = () => setPage(resolvePage(location.hash));
    window.addEventListener("hashchange", nav);
    const expired = () => {
      sessionStorage.setItem("morphy-expired", "1");
      void db?.auth.signOut({ scope: "local" }).then(() => {
        if (!isWorkspaceHash(location.hash)) {
          location.hash = "signin";
          setPage("signin");
        }
      });
    };
    window.addEventListener(SESSION_EXPIRED, expired);
    return () => {
      window.removeEventListener(SESSION_EXPIRED, expired);
      s?.data.subscription.unsubscribe();
      window.removeEventListener("hashchange", nav);
    };
  }, []);
  function go(where: string) {
    location.hash = where === "landing" ? "" : where;
    setPage(where);
  }
  return (
    <>
      {showIntro && <Intro close={close} />}
      <div inert={showIntro}>
        <Suspense fallback={<AnimalMorphLoader />}>
          {view()}
        </Suspense>
      </div>
    </>
  );
  function view() {
    if (page === "explore") return <QueryWorkbench back={() => go("landing")} />;
    if (session) {
      return (
        <Account
          key={session.user.id}
          session={session}
          signout={() => {
            void db?.auth.signOut({ scope: "local" }).then(() => go("landing"));
            go("landing");
          }}
        />
      );
    }
    if (!ready) return <AnimalMorphLoader />;
    if (page !== "landing")
      return (
        <LoginPage
          initialMode={page === "signup" ? "signup" : "signin"}
          workspaceDestination={page === "workspace" ? location.hash : undefined}
          back={() => go("landing")}
          expiredMessage={
            expiredNote
              ? "Your session expired. Sign in again to continue."
              : undefined
          }
        />
      );
    return <Landing start={() => go("signup")} signin={() => go("signin")} deferVideo={showIntro || constrained} />;
  }
}


createRoot(document.getElementById("root")!).render(<App />);
