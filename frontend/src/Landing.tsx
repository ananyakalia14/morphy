import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useReducedMotion } from "./Motion";
import { ProductStory } from "./ProductStory";
import { SiteFooter } from "./SiteFooter";
import { CliPromoSection } from "./CliPromoSection";
import "./landing-motion.css";

const SECTIONS = [
  ["#workflow", "How it works"],
  ["#connectors", "Connectors"],
  ["#terminal", "Terminal"],
  ["#research", "Research"],
  ["#explore", "Try a query"],
] as const;

const SOURCES = [
  ["PG", "PostgreSQL", "Read-only connection"],
  ["MY", "MySQL", "Read-only connection"],
  ["MA", "MariaDB", "Read-only connection"],
  ["CSV", "CSV", "File import into SQLite"],
] as const;

const SIGNALS = ["REVIEWABLE SQL", "ROW & COLUMN CONTROLS", "READ-ONLY EXECUTION", "WEB + TERMINAL"];
const TRAIL = [0, 1, 2, 3, 4];

function PixelTrail() {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const pixels = Array.from(el.children) as HTMLElement[];
    const positions = pixels.map(() => ({ x: 0, y: 0 }));
    let x = 0;
    let y = 0;
    let frame = 0;
    let visible = false;

    function draw() {
      frame = 0;
      if (!visible) return;
      let nextX = x;
      let nextY = y;
      let moving = false;
      for (const [i, p] of positions.entries()) {
        p.x += (nextX - p.x) * 0.44;
        p.y += (nextY - p.y) * 0.44;
        moving ||= Math.abs(nextX - p.x) + Math.abs(nextY - p.y) > 0.5;
        pixels[i]!.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`;
        nextX = p.x;
        nextY = p.y;
      }
      if (moving) frame = requestAnimationFrame(draw);
    }

    function hide() {
      visible = false;
      el!.classList.remove("is-visible");
    }

    function move(event: PointerEvent) {
      if (event.pointerType !== "mouse" || (event.target as Element | null)?.closest("dialog, button, a, input, textarea, select")) {
        hide();
        return;
      }
      x = event.clientX + 12;
      y = event.clientY + 12;
      if (!visible) {
        positions.forEach((p) => { p.x = x; p.y = y; });
        visible = true;
        el!.classList.add("is-visible");
      }
      if (!frame) frame = requestAnimationFrame(draw);
    }

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("blur", hide);
    document.documentElement.addEventListener("pointerleave", hide);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("blur", hide);
      document.documentElement.removeEventListener("pointerleave", hide);
    };
  }, []);

  return <div ref={root} className="motion-pixels" aria-hidden="true">{TRAIL.map((i) => <i key={i} />)}</div>;
}

function LandingNavigation({ signin }: { signin: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  function closeMenu() {
    dialog.current?.close();
  }

  return (
    <header className="motion-nav">
      <a className="motion-brand" href="#top" aria-label="MORPHY home">MORPHY<span>■</span></a>
      <nav aria-label="Primary" className="motion-nav-actions">
        <a className="motion-nav-workflow" href="#workflow">How it works</a>
        <button type="button" className="motion-signin" onClick={signin}>Sign in <span aria-hidden="true">↗</span></button>
        <button
          ref={toggle}
          type="button"
          className="motion-menu-toggle"
          aria-expanded={open}
          aria-controls="morphy-navigation"
          onClick={() => { dialog.current?.showModal(); setOpen(true); }}
        >
          <span className="motion-menu-bars" aria-hidden="true" /> Menu
        </button>
      </nav>
      <dialog
        id="morphy-navigation"
        ref={dialog}
        className="motion-menu"
        aria-labelledby="motion-menu-title"
        onClose={() => { setOpen(false); toggle.current?.focus({ preventScroll: true }); }}
      >
        <div className="motion-menu-top">
          <span id="motion-menu-title" className="motion-brand">MORPHY<span>■</span></span>
          <button type="button" className="motion-menu-close" onClick={closeMenu} autoFocus>Close <span aria-hidden="true">×</span></button>
        </div>
        <div className="motion-menu-content">
          <nav aria-label="Site sections">
            {SECTIONS.map(([href, label], i) => (
              <a key={href} href={href} onClick={closeMenu} style={{ "--motion-index": i } as CSSProperties}>
                <small>0{i + 1}</small><span>{label}</span><b aria-hidden="true">↗</b>
              </a>
            ))}
          </nav>
          <div className="motion-menu-note">
            <img src="/motion/falcon.svg" alt="" width="380" height="220" />
            <p>THE POLYGLOT DATA WORKSPACE</p>
          </div>
        </div>
      </dialog>
    </header>
  );
}

function MorphArtwork({ animate }: { animate: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [loaded, setLoaded] = useState(animate);

  useEffect(() => {
    if (animate) setLoaded(true);
  }, [animate]);

  useEffect(() => {
    const node = video.current;
    if (!node) return;
    if (!animate) {
      node.pause();
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      void node.play().catch(() => {});
      return;
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) void node.play().catch(() => {});
      else node.pause();
    }, { threshold: 0.1 });
    observer.observe(node);
    return () => { observer.disconnect(); node.pause(); };
  }, [animate, loaded]);

  return (
    <figure className="motion-specimen">
      <div className="motion-specimen-top"><span><i /> MORPH SEQUENCE</span><span>FIG. 01</span></div>
      <div
        className="motion-specimen-stage"
        onPointerMove={(event) => {
          if (!animate || event.pointerType !== "mouse") return;
          const stage = event.currentTarget;
          const bounds = stage.getBoundingClientRect();
          stage.style.setProperty("--specimen-x", `${((event.clientX - bounds.left) / bounds.width - .5) * 12}px`);
          stage.style.setProperty("--specimen-y", `${((event.clientY - bounds.top) / bounds.height - .5) * 12}px`);
        }}
        onPointerLeave={(event) => {
          event.currentTarget.style.removeProperty("--specimen-x");
          event.currentTarget.style.removeProperty("--specimen-y");
        }}
      >
        <div className="motion-specimen-grid" aria-hidden="true" />
        <img src="/motion/bull.svg" alt="MORPHY lettering shaped into a bull" fetchPriority="high" />
        {loaded && (
          <video
            ref={video}
            src="/motion/loader.mp4"
            className={ready ? "is-ready" : undefined}
            muted
            loop
            playsInline
            preload="none"
            aria-hidden="true"
            onPlaying={() => setReady(true)}
            onError={() => setReady(false)}
          />
        )}
        <span className="motion-specimen-mark" aria-hidden="true">+</span>
      </div>
      <figcaption><span>ONE NAME. SIX FORMS.</span><span aria-hidden="true">01 — 06</span></figcaption>
    </figure>
  );
}

export function Landing({ start, signin }: { start: () => void; signin: () => void }) {
  const reduced = useReducedMotion();
  const [paused, setPaused] = useState(false);
  const animate = !reduced && !paused;

  return (
    <div className={`landing motion-landing${animate ? "" : " motion-disabled"}`} id="top">
      {animate && <PixelTrail />}
      <a className="skip-link" href="#main">Skip to content</a>
      <LandingNavigation signin={signin} />
      <main id="main" tabIndex={-1}>
        <section className="motion-hero" aria-labelledby="motion-hero-title">
          <div className="hero-copy motion-copy">
            <div className="motion-kicker motion-rise" style={{ "--motion-index": 0 } as CSSProperties}><i /> THE POLYGLOT DATA WORKSPACE</div>
            <h1 id="motion-hero-title" aria-label="Data takes shape.">
              <span className="motion-rise" style={{ "--motion-index": 1 } as CSSProperties} aria-hidden="true">DATA</span>
              <span className="motion-rise" style={{ "--motion-index": 2 } as CSSProperties} aria-hidden="true">TAKES</span>
              <span className="motion-rise" style={{ "--motion-index": 3 } as CSSProperties} aria-hidden="true">SHAPE.</span>
            </h1>
            <p className="motion-rise" style={{ "--motion-index": 4 } as CSSProperties}>Ask questions across your databases, review the SQL, and share answers within the access rules your team sets.</p>
            <div className="motion-hero-actions motion-rise" style={{ "--motion-index": 5 } as CSSProperties}>
              <button className="primary motion-primary" type="button" onClick={start}>Create workspace <b aria-hidden="true">↗</b></button>
              <a className="motion-text-link" href="#explore">Try a sample query <span aria-hidden="true">→</span></a>
            </div>
          </div>
          <MorphArtwork animate={animate} />
          <div className="motion-hero-meta">
            <a href="#workflow" className="motion-text-link">See how it works <span aria-hidden="true">↓</span></a>
            {!reduced && <button type="button" className="motion-pause" onClick={() => setPaused((value) => !value)}>{paused ? "Play motion" : "Pause motion"} <span aria-hidden="true">{paused ? "▷" : "Ⅱ"}</span></button>}
          </div>
        </section>

        <div className="motion-ticker" aria-label="Product highlights">
          <div className="motion-ticker-track">
            {[0, 1].map((group) => <div key={group} className="motion-ticker-group" aria-hidden={group === 1}>{SIGNALS.map((item) => <span key={item}><i aria-hidden="true" />{item}</span>)}</div>)}
          </div>
        </div>

        <ProductStory />

        <section id="connectors" className="motion-sources motion-wrap" aria-labelledby="motion-sources-title">
          <div className="motion-section-heading">
            <p className="motion-kicker"><i /> 02 / DATA SOURCES</p>
            <h2 id="motion-sources-title">Start with the data you have.</h2>
            <p>Connect a read-only database or import a CSV. Set which tables, columns, and rows each role can query.</p>
          </div>
          <ul className="motion-source-grid">
            {SOURCES.map(([initials, name, mode]) => <li key={name}><span className="motion-source-chip" aria-hidden="true">{initials}</span><h3>{name}</h3><p>{mode}</p></li>)}
          </ul>
        </section>

        <section id="terminal" className="landing-cli-section motion-terminal" aria-label="MORPHY command line">
          <div className="landing-cli-container"><CliPromoSection /></div>
        </section>

        <section id="research" className="motion-research motion-wrap" aria-labelledby="motion-research-title">
          <div className="motion-section-heading">
            <p className="motion-kicker"><i /> 03 / RESEARCH</p>
            <h2 id="motion-research-title">When read-only SQL leaks.</h2>
            <p>A read-only query can still reveal restricted information through a subtotal. We test whether results change when only restricted data changes, and whether access controls preserve the answers people are allowed to see.</p>
            <a className="motion-text-link" href="https://github.com/ananyakalia14/morphy/blob/main/docs/EVALUATION.md">Read the evaluation guide <span aria-hidden="true">↗</span></a>
          </div>
          <div className="motion-research-art" aria-hidden="true"><img src="/motion/crocodile.svg" alt="" loading="lazy" /></div>
        </section>

        <section className="motion-end" aria-labelledby="motion-end-title">
          <div className="motion-wrap">
            <p className="motion-kicker"><i /> YOUR NEXT QUERY</p>
            <h2 id="motion-end-title">Put your data to work.</h2>
            <p>Try the sample workspace, or create your own and connect a source.</p>
            <div className="motion-hero-actions">
              <button className="primary motion-primary" type="button" onClick={start}>Create workspace <b aria-hidden="true">↗</b></button>
              <a href="#explore" className="motion-text-link">Explore sample data <span aria-hidden="true">→</span></a>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
