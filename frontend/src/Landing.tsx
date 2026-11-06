import { HeroMorphCanvas } from "./Motion";
export function Landing({
  start,
  signin,
}: {
  start: () => void;
  signin: () => void;
}) {
  return (
    <>
      <header className="mast">
        <a className="brand" href="#">
          MORPHY
        </a>
        <nav>
          <a className="nav-work" href="#workspace">
            Workspace
          </a>
          <button className="nav-login" onClick={signin}>
            Sign in ↗
          </button>
        </nav>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="line" /> POLYGLOT DATA ENGINE
            </div>
            <h1>
              DATA TAKES
              <br />
              <em>SHAPE.</em>
            </h1>
            <p>
              One workspace for your databases, your team, and the rules that
              govern access.
            </p>
            <button className="primary" onClick={start}>
              Create workspace <b>↗</b>
            </button><a className="explore-link" href="#explore">Explore sample workspace →</a>
          </div>
          <HeroMorphCanvas />
        </section>
        <div className="strip" aria-label="Workspace features">
          <span>✳</span> GLOBAL IDENTITY <span>✳</span> ORGANIZATIONS{" "}
          <span>✳</span> GRANULAR ACCESS <span>✳</span>
        </div>
        <section id="workspace" className="overview">
          <div className="section-title">
            <div className="eyebrow">THE WORKSPACE</div>
            <h2>Built around your team.</h2>
          </div>
          <div className="features">
            {[
              [
                "@",
                "Claim your handle",
                "One global username for your profile and workspace invitations.",
              ],
              [
                "↗",
                "Bring people in",
                "Create an organization and invite teammates by their handles.",
              ],
              [
                "⌗",
                "Define access",
                "Choose who can view, query, or edit each database configuration.",
              ],
            ].map(([icon, title, copy]) => (
              <article key={title}>
                <span className="glyph">{icon}</span>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <footer>
        <strong>MORPHY</strong>
        <span>POLYGLOT DATA WORKSPACE</span>
      </footer>
    </>
  );
}


