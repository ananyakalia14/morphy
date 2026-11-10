import { useCallback, useEffect, useRef, useState } from "react";
import { useConstrainedConnection } from "./connection";
const names = [
  "Bull",
  "Duck",
  "Crocodile",
  "Falcon",
  "Elephant",
  "Horse",
  "Wordmark",
];
export function useReducedMotion() {
  const [reduced, set] = useState(
    () => matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const m = matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => set(m.matches);
    m.addEventListener("change", change);
    return () => m.removeEventListener("change", change);
  }, []);
  return reduced;
}
export function AnimalMorphLoader({
  label = "Loading workspace",
}: {
  label?: string;
}) {
  const reduced = useReducedMotion();
  const constrained = useConstrainedConnection();
  const [failed, setFailed] = useState(false);

  return (
    <div className="wait" role="status">
      {failed || reduced || constrained ? (
        <img src="/motion/bull.svg" alt="" />
      ) : (
        <video
          aria-hidden="true"
          autoPlay
          loop
          muted
          playsInline
          poster="/motion/bull.svg"
          onError={() => setFailed(true)}
        >
          <source src="/motion/loader.mp4" type="video/mp4" />
          <source
            src="/motion/loader.webm"
            type="video/webm"
            onError={() => setFailed(true)}
          />
        </video>
      )}
      <span>{label}…</span>
    </div>
  );
}
export function Intro({ close }: { close: (focusHero?: boolean) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [exiting, setExiting] = useState(false);
  const exitingRef = useRef(false);
  const exitTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const startupTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const finish = useCallback(() => {
    if (exitingRef.current) return;
    exitingRef.current = true;
    clearTimeout(startupTimer.current);
    setExiting(true);
    exitTimer.current = setTimeout(close, 450);
  }, [close]);

  const applyRate = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = 1.2;
    }
  }, []);

  useEffect(() => {
    applyRate();
    if (videoRef.current) {
      videoRef.current.play().catch(() => {});
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        finish();
      }
    };
    window.addEventListener("keydown", onKey);

    // Let the website open if video playback cannot start promptly.
    startupTimer.current = setTimeout(() => close(false), 1250);
    const timer = setTimeout(finish, 7500);

    return () => {
      clearTimeout(timer);
      clearTimeout(startupTimer.current);
      clearTimeout(exitTimer.current);
      window.removeEventListener("keydown", onKey);
    };
  }, [applyRate, close, finish]);

  return (
    <div
      className={`curtain ${exiting ? "is-exiting" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-label="MORPHY animated introduction"
      onClick={finish}
    >
      <video
        ref={videoRef}
        src="/motion/intro-web.mp4"
        autoPlay
        muted
        playsInline
        preload="auto"
        aria-hidden="true"
        onLoadedMetadata={applyRate}
        onPlay={applyRate}
        onPlaying={() => clearTimeout(startupTimer.current)}
        onEnded={finish}
        onError={() => close(false)}
      />
      <button type="button" className="motion-intro-skip" onClick={finish} autoFocus>
        Skip intro <span aria-hidden="true">↗</span>
      </button>
    </div>
  );
}
export function HeroMorphCanvas() {
  const v = useRef<HTMLVideoElement>(null),
    surface = useRef<HTMLDivElement>(null),
    reduced = useReducedMotion();
  const [index, setIndex] = useState(0),
    [playing, setPlaying] = useState(!reduced),
    [failed, setFailed] = useState(false);
  function select(n: number) {
    setPlaying(false);
    v.current?.pause();
    if (v.current) v.current.currentTime = Math.min(7.99, (n * 8) / 6);
    setIndex(n);
  }
  function toggle() {
    if (!v.current) return;
    if (playing) v.current.pause();
    else void v.current.play().catch(() => setPlaying(false));
  }
  useEffect(() => {
    if (reduced) {
      v.current?.pause();
      setPlaying(false);
    }
  }, [reduced]);
  return (
    <section className="specimen" aria-label="Interactive MORPHY motion study">
      <div className="spec-head">
        <span>
          <i /> MORPH SEQUENCE
        </span>
        <span>FIG. 01</span>
      </div>
      <div
        className="spec-canvas"
        ref={surface}
        onPointerMove={(e) => {
          if (reduced || e.pointerType !== "mouse") return;
          let r = e.currentTarget.getBoundingClientRect();
          e.currentTarget.style.setProperty(
            "--mx",
            ((e.clientX - r.left) / r.width) * 6 - 3 + "px",
          );
          e.currentTarget.style.setProperty(
            "--my",
            ((e.clientY - r.top) / r.height) * 6 - 3 + "px",
          );
        }}
        onPointerLeave={() => {
          surface.current?.style.setProperty("--mx", "0px");
          surface.current?.style.setProperty("--my", "0px");
        }}
      >
        <span className="cross tl">+</span>
        <span className="cross tr">+</span>
        <span className="cross bl">+</span>
        <span className="cross br">+</span>
        {failed || reduced ? (
          <img
            className="animal"
            src={"/motion/" + names[index]!.toLowerCase() + ".svg"}
            alt={"MORPHY " + names[index]}
          />
        ) : (
          <video
            className="animal"
            ref={v}
            muted
            playsInline
            loop
            autoPlay
            poster="/motion/bull.svg"
            aria-label="Six MORPHY animal calligrams"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onError={() => setFailed(true)}
            onTimeUpdate={() => {
              if (v.current && !v.current.paused)
                setIndex(
                  Math.min(6, Math.floor((v.current.currentTime * 6) / 8)),
                );
            }}
          >
            <source src="/motion/intro.mp4" type="video/mp4" />
            <source
              src="/motion/intro.webm"
              type="video/webm"
              onError={() => setFailed(true)}
            />
          </video>
        )}
      </div>
      <div className="spec-controls">
        <div>
          <small>CURRENT FORM</small>
          <strong>{names[index]}</strong>
        </div>
        <div className="transport">
          <button
            aria-label="Previous pose"
            onClick={() => select((index + 6) % 7)}
          >
            ←
          </button>
          {!failed && !reduced && (
            <button
              onClick={toggle}
              aria-label={playing ? "Pause animation" : "Play animation"}
            >
              {playing ? "Ⅱ" : "▷"}
            </button>
          )}
          <button
            aria-label="Next pose"
            onClick={() => select((index + 1) % 7)}
          >
            →
          </button>
        </div>
      </div>
    </section>
  );
}
