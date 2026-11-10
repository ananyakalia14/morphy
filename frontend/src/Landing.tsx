import { useEffect, useRef, useState, type CSSProperties } from "react";
import { FileSpreadsheet } from "lucide-react";
import { useReducedMotion } from "./Motion";
import { HeroBackdrop } from "./HeroBackdrop";
import { ProductStory } from "./ProductStory";
import { SiteFooter } from "./SiteFooter";
import { CliPromoSection } from "./CliPromoSection";
import "./landing-motion.css";

const SECTIONS = [
  ["#workflow", "How it works", "falcon"],
  ["#connectors", "Connectors", "crocodile"],
  ["#terminal", "Terminal", "horse"],
  ["#research", "Research", "elephant"],
  ["#explore", "Try a query", "duck"],
] as const;

const SOURCES = [
  ["PostgreSQL", "Read-only connection", "postgresql.svg"],
  ["MySQL", "Read-only connection", "mysql.svg"],
  ["MariaDB", "Read-only connection", "mariadb.svg"],
  ["CSV", "File import into SQLite", null],
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

function LandingNavigation({ signin, animate }: { signin: () => void; animate: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const closing = useRef<Animation | null>(null);
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState(0);

  useEffect(() => () => closing.current?.cancel(), []);

  function openMenu() {
    const node = dialog.current;
    const button = toggle.current;
    if (!node || !button || node.open) return;
    const { x, y, width, height } = button.getBoundingClientRect();
    node.style.setProperty("--menu-origin", `${x + width / 2}px ${y + height / 2}px`);
    setPreview(0);
    node.showModal();
    setOpen(true);
  }

  function closeMenu(destination?: string) {
    const node = dialog.current;
    if (!node?.open || closing.current) return;
    function finish() {
      closing.current = null;
      dialog.current?.close();
      if (!destination) return;
      if (location.hash !== destination) location.hash = destination;
      else document.getElementById(destination.slice(1))?.scrollIntoView();
    }
    if (!animate) {
      finish();
      return;
    }
    closing.current = node.animate([
      { clipPath: getComputedStyle(node).clipPath },
      { clipPath: "circle(0% at var(--menu-origin))" },
    ], { duration: 450, easing: "cubic-bezier(.67, 0, .86, .33)", fill: "forwards" });
    void closing.current.finished.then(finish, () => {});
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
          onClick={openMenu}
        >
          <span className="motion-menu-bars" aria-hidden="true" /> Menu
        </button>
      </nav>
      <dialog
        id="morphy-navigation"
        ref={dialog}
        className="motion-menu"
        aria-labelledby="motion-menu-title"
        onCancel={(event) => { event.preventDefault(); closeMenu(); }}
        onClose={() => {
          dialog.current?.getAnimations().forEach((animation) => animation.cancel());
          setOpen(false);
          toggle.current?.focus({ preventScroll: true });
        }}
      >
        <div className="motion-menu-top">
          <span id="motion-menu-title" className="motion-brand">MORPHY<span>■</span></span>
          <button type="button" className="motion-menu-close" onClick={() => closeMenu()} autoFocus>Close <span aria-hidden="true">×</span></button>
        </div>
        <div className="motion-menu-content">
          <nav aria-label="Site sections">
            {SECTIONS.map(([href, label], i) => (
              <a key={href} href={href} onPointerEnter={() => setPreview(i)} onFocus={() => setPreview(i)} onClick={(event) => {
                if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                closeMenu(href);
              }} style={{ "--motion-index": i } as CSSProperties}>
                <small>0{i + 1}</small><span>{label}</span><b aria-hidden="true">↗</b>
              </a>
            ))}
          </nav>
          <div className="motion-menu-note">
            <img key={preview} src={`/motion/${SECTIONS[preview]![2]}.svg`} alt="" width="380" height="220" />
            <p>0{preview + 1} / {SECTIONS[preview]![1].toUpperCase()}</p>
          </div>
        </div>
      </dialog>
    </header>
  );
}

export function Landing({ start, signin, deferVideo }: { start: () => void; signin: () => void; deferVideo: boolean }) {
  const reduced = useReducedMotion();
  const animate = !reduced;
  const sources = useRef<HTMLElement>(null);

  useEffect(() => {
    const rail = sources.current;
    const pin = rail?.querySelector<HTMLElement>(".motion-source-pin");
    const track = rail?.querySelector<HTMLElement>(".motion-source-grid");
    if (!animate || !rail || !pin || !track) return;
    const wide = matchMedia("(min-width: 850px) and (min-height: 600px)");
    let frame = 0;
    const clamp = (value: number) => Math.max(0, Math.min(1, value));
    const update = () => {
      frame = 0;
      if (!wide.matches) return;
      const railBox = rail.getBoundingClientRect();
      const pinTop = Number.parseFloat(getComputedStyle(pin).top) || 0;
      const railProgress = clamp((pinTop - railBox.top) / Math.max(1, railBox.height - pin.offsetHeight));
      const travel = Math.max(0, track.scrollWidth - track.clientWidth);
      rail.style.setProperty("--source-x", `${-travel * railProgress}px`);
      rail.style.setProperty("--source-progress", String(railProgress));
    };
    const queue = () => { if (!frame) frame = requestAnimationFrame(update); };
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    queue();
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", queue);
      window.removeEventListener("resize", queue);
      rail.style.removeProperty("--source-x");
      rail.style.removeProperty("--source-progress");
    };
  }, [animate]);

  return (
    <div className={`landing motion-landing${animate ? "" : " motion-disabled"}`} id="top">
      {animate && <PixelTrail />}
      <a className="skip-link" href="#main">Skip to content</a>
      <LandingNavigation signin={signin} animate={animate} />
      <main id="main" tabIndex={-1}>
        <section className="motion-hero" aria-labelledby="motion-hero-title">
          <HeroBackdrop reduced={reduced || deferVideo} />
          <div className="motion-hero-content motion-wrap">
            <div className="hero-copy motion-copy">
              <div className="motion-kicker motion-rise" style={{ "--motion-index": 0 } as CSSProperties}><i /> THE POLYGLOT DATA WORKSPACE</div>
              <h1 id="motion-hero-title" aria-label="Data takes shape.">
                {["DATA", "TAKES", "SHAPE."].map((word, i) => <span key={word} className="motion-title-line" aria-hidden="true"><span className="motion-title-mask" style={{ "--motion-index": i } as CSSProperties}>{word}</span></span>)}
              </h1>
              <p className="motion-rise" style={{ "--motion-index": 4 } as CSSProperties}>Ask questions across your databases, review the SQL, and share answers within the access rules your team sets.</p>
              <div className="motion-hero-actions motion-rise" style={{ "--motion-index": 5 } as CSSProperties}>
                <button className="primary motion-primary" type="button" onClick={start}>Create workspace <b aria-hidden="true">↗</b></button>
                <a className="motion-text-link" href="#explore">Try a sample query <span aria-hidden="true">→</span></a>
              </div>
            </div>
            <div className="motion-hero-meta">
              <a href="#workflow" className="motion-text-link">See how it works <span aria-hidden="true">↓</span></a>
            </div>
          </div>
        </section>

        <div className="motion-ticker" aria-label="Product highlights">
          <div className="motion-ticker-track">
            {[0, 1].map((group) => <div key={group} className="motion-ticker-group" aria-hidden={group === 1}>{SIGNALS.map((item) => <span key={item}><i aria-hidden="true" />{item}</span>)}</div>)}
          </div>
        </div>

        <ProductStory />

        <section id="connectors" ref={sources} className="motion-sources" aria-labelledby="motion-sources-title">
          <div className="motion-source-pin motion-wrap">
            <div className="motion-section-heading">
              <p className="motion-kicker"><i /> 02 / DATA SOURCES</p>
              <h2 id="motion-sources-title">Start with the data you have.</h2>
              <p>Connect a read-only database or import a CSV. Set which tables, columns, and rows each role can query.</p>
            </div>
            <div className="motion-source-window" role="region" aria-label="Supported source cards" tabIndex={0}>
              <ul className="motion-source-grid">
                {SOURCES.map(([name, mode, logo], i) => (
                  <li key={name}>
                    <span className="motion-source-chip" aria-hidden="true">
                      {logo ? <img src={`/connectors/${logo}`} alt="" width="32" height="32" decoding="async" /> : <FileSpreadsheet size={32} />}
                    </span>
                    <span className="motion-source-number" aria-hidden="true">0{i + 1} / 04</span>
                    <h3>{name}</h3>
                    <p>{mode}</p>
                  </li>
                ))}
              </ul>
            </div>
            <div className="motion-source-progress" aria-hidden="true"><span /></div>
          </div>
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
