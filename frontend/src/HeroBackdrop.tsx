import { useEffect, useRef, useState } from "react";

const POSTER = "/motion/morphy_databases_v2_poster.jpg";
const COMPACT_VIEWPORT = "(max-width: 780px)";

export function HeroBackdrop({ reduced, paused }: { reduced: boolean; paused: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  const [compact, setCompact] = useState(() => matchMedia(COMPACT_VIEWPORT).matches);
  const [failedSource, setFailedSource] = useState<string>();
  const src = compact ? "/motion/morphy_databases_v2_loop_540.mp4" : "/motion/morphy_databases_v2_loop.mp4";
  const showVideo = !reduced && src !== failedSource;

  useEffect(() => {
    const viewport = matchMedia(COMPACT_VIEWPORT);
    const resize = () => setCompact(viewport.matches);
    viewport.addEventListener("change", resize);
    return () => viewport.removeEventListener("change", resize);
  }, []);

  useEffect(() => {
    const node = video.current;
    if (!node || paused) return;
    if (typeof IntersectionObserver === "undefined") {
      void node.play().catch(() => {});
      return () => node.pause();
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) void node.play().catch(() => {});
      else node.pause();
    });
    observer.observe(node);
    return () => { observer.disconnect(); node.pause(); };
  }, [paused, showVideo, src]);

  return (
    <div className="hero-backdrop" aria-hidden="true">
      {showVideo ? (
        <video
          key={src}
          ref={video}
          src={src}
          muted
          loop
          playsInline
          preload="metadata"
          poster={POSTER}
          onError={() => setFailedSource(src)}
        />
      ) : (
        <img src={POSTER} alt="" />
      )}
      <div className="hero-veil" />
    </div>
  );
}
