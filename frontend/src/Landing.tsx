import { useEffect, useRef, type CSSProperties, type MouseEvent, type ReactNode } from "react";
import { useReducedMotion } from "./Motion";
import { HeroBackdrop } from "./HeroBackdrop";

const FEATURES = [
  ["@", "Claim your handle", "One global username for your profile and workspace invitations."],
  ["↗", "Bring people in", "Create an organization and invite teammates by their handles."],
  ["⌗", "Define access", "Choose who can view, query, or edit each database configuration."],
] as const;

const TICKER = ["GLOBAL IDENTITY", "ORGANIZATIONS", "GRANULAR ACCESS", "GOVERNED SQL", "READ-ONLY BY DESIGN"];

function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e?.isIntersecting) {
          el.classList.add("is-in");
          io.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={"reveal " + className} style={{ "--d": delay + "ms" } as CSSProperties}>
      {children}
    </div>
  );
}

function tilt(e: MouseEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--rx", ((e.clientY - r.top) / r.height - 0.5) * -8 + "deg");
  e.currentTarget.style.setProperty("--ry", ((e.clientX - r.left) / r.width - 0.5) * 8 + "deg");
}
function untilt(e: MouseEvent<HTMLElement>) {
  e.currentTarget.style.setProperty("--rx", "0deg");
  e.currentTarget.style.setProperty("--ry", "0deg");
}

function Cursor() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!matchMedia("(pointer: fine)").matches) return;
    const el = ref.current!;
    document.documentElement.classList.add("has-cursor");
    const move = (e: PointerEvent) => {
      el.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      const t = e.target as Element | null;
      el.classList.toggle("snap", !!t?.closest("a,button"));
    };
    window.addEventListener("pointermove", move);
    return () => {
      window.removeEventListener("pointermove", move);
      document.documentElement.classList.remove("has-cursor");
    };
  }, []);
  return <div ref={ref} className="cursor" aria-hidden="true" />;
}

export function Landing({ start, signin }: { start: () => void; signin: () => void }) {
  const reduced = useReducedMotion();
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const y = window.scrollY;
      root.current?.style.setProperty("--sy", String(reduced ? 0 : y));
      root.current?.classList.toggle("scrolled", y > 24);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [reduced]);

  return (
    <div ref={root} className="landing">
      {!reduced && <Cursor />}
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="mast">
        <a className="brand" href="#">
          MORPHY
        </a>
        <nav>
          <a className="nav-work ink-link" href="#workspace">
            Workspace
          </a>
          <button className="nav-login sweep" onClick={signin}>
            Sign in ↗
          </button>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <section className="hero hero-stage">
          <HeroBackdrop reduced={reduced} />
          <div className="hero-copy par-slow">
            <div className="eyebrow rise" style={{ "--d": "0ms" } as CSSProperties}>
              <span className="line" /> POLYGLOT DATA ENGINE
            </div>
            <h1 aria-label="Data takes shape.">
              {["DATA", "TAKES"].map((w, i) => (
                <span key={w} className="word rise" style={{ "--d": 120 + i * 110 + "ms" } as CSSProperties} aria-hidden="true">
                  {w}{" "}
                </span>
              ))}
              <br />
              <em className="word rise" style={{ "--d": "360ms" } as CSSProperties} aria-hidden="true">
                SHAPE.
              </em>
            </h1>
            <p className="rise" style={{ "--d": "520ms" } as CSSProperties}>
              One workspace for your databases, your team, and the rules that govern access.
            </p>
            <div className="rise" style={{ "--d": "640ms" } as CSSProperties}>
              <button className="primary" onClick={start}>
                Create workspace <b>↗</b>
              </button>
              <a className="explore-link ink-link" href="#explore">
                Explore sample workspace →
              </a>
            </div>
          </div>
        </section>
        <div className="strip ticker" aria-label="Workspace features">
          <div className="ticker-track">
            {[0, 1].map((k) => (
              <div key={k} className="ticker-set" aria-hidden={k === 1}>
                {TICKER.map((t) => (
                  <span key={t} className="ticker-item">
                    <span>✳</span> {t}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
        <section id="workspace" className="overview">
          <Reveal className="section-title">
            <div className="eyebrow">THE WORKSPACE</div>
            <h2>Built around your team.</h2>
          </Reveal>
          <div className="features">
            {FEATURES.map(([icon, title, copy], i) => (
              <Reveal key={title} delay={i * 140} className="feature-cell">
                <article className="tilt" onMouseMove={tilt} onMouseLeave={untilt}>
                  <span className="glyph">{icon}</span>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </section>
      </main>
      <footer>
        <strong>MORPHY</strong>
        <span>POLYGLOT DATA WORKSPACE</span>
      </footer>
    </div>
  );
}
