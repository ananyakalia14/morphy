import { useRef, useState } from "react";

const video = "/motion/morphy_databases_v2_loop.mp4";
const videoSmall = "/motion/morphy_databases_v2_loop_540.mp4";
const poster = "/motion/morphy_databases_v2_poster.jpg";

export function HeroBackdrop({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLVideoElement>(null),
    [paused, setPaused] = useState(false),
    [failed, setFailed] = useState(false);
  const animated = !reduced && !failed;
  return (
    <>
    <div className="hero-backdrop par-bg" aria-hidden="true">
      {animated ? (
        <video
          ref={ref}
          autoPlay={!paused}
          muted
          loop
          playsInline
          poster={poster}
          onError={() => setFailed(true)}
        >
          <source media="(max-width: 780px)" src={videoSmall} type="video/mp4" />
          <source src={video} type="video/mp4" onError={() => setFailed(true)} />
        </video>
      ) : (
        <img src={poster} alt="" />
      )}
      <div className="hero-grid" />
      <div className="hero-veil" />
    </div>
    {animated && (
      <button
        type="button"
        className="video-toggle"
        aria-pressed={paused}
        onClick={() => {
          const v = ref.current;
          if (!v) return;
          if (paused) void v.play().catch(() => setPaused(true));
          else v.pause();
          setPaused(!paused);
        }}
      >
        {paused ? "▶ Play background" : "❚❚ Pause background"}
      </button>
    )}
    </>
  );
}
