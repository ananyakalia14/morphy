import { QueryWorkbench } from './QueryWorkbench';
import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { createRoot } from "react-dom/client";
import type { Session } from "@supabase/supabase-js";
import "@fontsource/syne/700.css";
import "@fontsource/syne/800.css";
import "@fontsource/jetbrains-mono/500.css";
import "./style.css";
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
import { Workspace } from "./Workspace";

import { useAction } from "./useAction";
function Shell({
  children,
  back,
  signout,
}: {
  children: ReactNode;
  back?: () => void;
  signout?: () => void;
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
      <main className="shell">{children}</main>
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
function Auth({ initial, back }: { initial: string; back: () => void }) {
  const [mode, setMode] = useState(initial),
    [name, setName] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPass] = useState(""),
    [notice, setNotice] = useState("");
  const { busy, error, run } = useAction();
  function submit(e: FormEvent) {
    e.preventDefault();
    void run(async () => {
      if (!db)
        throw Error(
          "Start local Supabase with start-local.ps1 to enable accounts.",
        );
      const res =
        mode === "signup"
          ? await db.auth.signUp({
              email,
              password,
              options: {
                data: { full_name: name },
                emailRedirectTo: location.origin,
              },
            })
          : await db.auth.signInWithPassword({ email, password });
      if (res.error) throw res.error;
      if (!res.data.session)
        setNotice("Check your email to finish signing in.");
    });
  }
  return (
    <Shell back={back}>
      <div className="auth-grid">
        <aside className="auth-art">
          <img src="/motion/crocodile.svg" alt="MORPHY crocodile" />
          <span>FIG. 03 / CROCODILE</span>
        </aside>
        <section className="panel">
          <div className="eyebrow">ACCOUNT</div>
          <h2>
            {mode === "signup" ? "Create your account." : "Welcome back."}
          </h2>
          <form onSubmit={submit}>
            {mode === "signup" && (
              <label>
                Your name
                <input
                  required
                  maxLength={80}
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
            )}
            <label>
              Email
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                required
                minLength={mode === "signup" ? 8 : 1}
                autoComplete={
                  mode === "signup" ? "new-password" : "current-password"
                }
                value={password}
                onChange={(e) => setPass(e.target.value)}
              />
            </label>
            <button className="primary" disabled={busy}>
              {mode === "signup" ? "Create account" : "Sign in"} ↗
            </button>
          </form>
          {["github", "google"]
            .filter((p) =>
              (import.meta.env.VITE_OAUTH_PROVIDERS || "")
                .split(",")
                .includes(p),
            )
            .map((p) => (
              <button
                key={p}
                onClick={() =>
                  void run(async () => {
                    if (!db) throw Error("Start local Supabase first.");
                    const { error } = await db.auth.signInWithOAuth({
                      provider: p as "github" | "google",
                      options: { redirectTo: location.origin },
                    });
                    if (error) throw error;
                  })
                }
              >
                Continue with {p === "github" ? "GitHub" : "Google"}
              </button>
            ))}
          {busy && <AnimalMorphLoader label="Signing in" />}
          <Notice error={error} />
          <p role="status">{notice}</p>
          <button
            className="link"
            onClick={() => {
              setMode(mode === "signup" ? "signin" : "signup");
              setNotice("");
            }}
          >
            {mode === "signup"
              ? "Already registered? Sign in"
              : "New here? Create an account"}
          </button>
        </section>
      </div>
    </Shell>
  );
}
function Identity({
  session,
  done,
}: {
  session: Session;
  done: () => Promise<void>;
}) {
  const defaultName = String(
    session.user.user_metadata.full_name ||
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
      profile?: Profile;
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
    <Shell signout={signout}>
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
            <button disabled={busy} onClick={() => void run(reload)}>
              Refresh invitations
            </button>
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
              reloadAccount={reload}
            />
          )}
          <Notice error={error} />
        </>
      )}
    </Shell>
  );
}
function App() {
  const reduced = useReducedMotion();
  const [session, setSession] = useState<Session | null>(null),
    [ready, setReady] = useState(!db),
    [page, setPage] = useState(
      location.hash === "#signin"
        ? "signin"
        : location.hash === "#signup"
          ? "signup"
          : location.hash === "#explore" ? "explore" : "landing",
    );
  const [intro, setIntro] = useState(
    () =>
      !sessionStorage.getItem("morphy.intro") &&
      !location.hash &&
      !location.search,
  );
  const close = useCallback(() => {
    sessionStorage.setItem("morphy.intro", "1");
    setIntro(false);
    requestAnimationFrame(() =>
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
    const nav = () =>
      setPage(
        location.hash === "#signup"
          ? "signup"
          : location.hash === "#signin"
            ? "signin"
            : location.hash === "#explore" ? "explore" : "landing",
      );
    window.addEventListener("hashchange", nav);
    return () => {
      s?.data.subscription.unsubscribe();
      window.removeEventListener("hashchange", nav);
    };
  }, []);
  function go(where: string) {
    location.hash = where === "landing" ? "" : where;
    setPage(where);
  }
  if (page === "explore") return <QueryWorkbench back={() => go("landing")} />;
  if (!ready) return <AnimalMorphLoader />;
  if (session)
    return (
      <Account
        key={session.user.id}
        session={session}
        signout={() => {
          void db?.auth.signOut({ scope: "local" }).then(() => go("landing"));
        }}
      />
    );
  if (page !== "landing")
    return <Auth initial={page} back={() => go("landing")} />;
  return (
    <>
      {intro && !reduced && <Intro close={close} />}
      <div inert={intro && !reduced}>
        <Landing start={() => go("signup")} signin={() => go("signin")} />
      </div>
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

