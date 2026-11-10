import { useRef, useEffect } from "react";

export const HERO_VIDEO = {
  src: "/motion/Rightsidehomepage.mp4",
  altSrc: "/motion/rightsideintro.mp4",
};

export function HeroBackdrop({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (ref.current && !reduced) {
      // Delay play slightly so critical layout paint finishes first
      const t = setTimeout(() => {
        ref.current?.play().catch(() => {});
      }, 50);
      return () => clearTimeout(t);
    }
  }, [reduced]);

  return (
    <div className="hero-backdrop par-bg" aria-hidden="true">
      {!reduced && (
        <video
          ref={ref}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
        >
          <source src="/motion/Rightsidehomepage.mp4" type="video/mp4" />
          <source src="/motion/rightsideintro.mp4" type="video/mp4" />
        </video>
      )}
      <div className="hero-grid" />
      <div className="hero-veil" />
    </div>
  );
}
