import loop from "./assets/videos/morphy_databases_v2_loop.mp4.asset.json";
import loopSmall from "./assets/videos/morphy_databases_v2_loop_720.mp4.asset.json";
import poster from "./assets/videos/morphy_databases_v2_poster.jpg.asset.json";

// Full-bleed motion-graphic background layer for the hero.
export const HERO_VIDEO: { src: string; small: string; poster: string } | null = {
  src: loop.url,
  small: loopSmall.url,
  poster: poster.url,
};

import { useRef, useState } from "react";

export function HeroBackdrop({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLVideoElement>(null),
    [paused, setPaused] = useState(false);
  return (
    <>
    <div className="hero-backdrop par-bg" aria-hidden="true">
      {HERO_VIDEO && !reduced ? (
        <video ref={ref} autoPlay={!paused} muted loop playsInline poster={HERO_VIDEO.poster}>
          <source media="(max-width: 780px)" src={HERO_VIDEO.small} type="video/mp4" />
          <source src={HERO_VIDEO.src} type="video/mp4" />
        </video>
      ) : HERO_VIDEO ? (
        <img src={HERO_VIDEO.poster} alt="" />
      ) : null}
      <div className="hero-grid" />
      <div className="hero-veil" />
    </div>
    {HERO_VIDEO && !reduced && (
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
