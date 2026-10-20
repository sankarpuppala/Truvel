/** An icon from the sprite in index.html, plus the two other SVG primitives.
 *
 * Icons are decorative by default (`aria-hidden`), because they always sit
 * beside a word -- colour and shape are never the only signal (SPEC §13). Pass
 * `label` for the rare icon that stands alone.
 */
import { useEffect, useState } from 'react';

export function Icon({
  name,
  size = 20,
  className = '',
  label,
}: {
  name: string;
  size?: number;
  className?: string;
  label?: string;
}) {
  return (
    <svg
      className={`ic ${className}`.trim()}
      width={size}
      height={size}
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
      focusable="false"
    >
      <use href={`#${name}`} />
    </svg>
  );
}

/**
 * A flat layered-landscape illustration, for a place with no photo (SPEC §12.6).
 * Never a grey box.
 */
export function Scene({
  name,
  className = '',
  viewBox = '0 0 400 500',
  alt,
}: {
  name: string;
  className?: string;
  viewBox?: string;
  alt?: string;
}) {
  return (
    <svg
      className={className}
      viewBox={viewBox}
      preserveAspectRatio="xMidYMid slice"
      role={alt ? 'img' : undefined}
      aria-label={alt}
      aria-hidden={alt ? undefined : true}
      focusable="false"
    >
      <use href={`#${name}`} />
    </svg>
  );
}

function currentTime(): string {
  return new Date().toLocaleTimeString('en-IN', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  });
}

/**
 * The status bar the reference draws at the top of every screen.
 *
 * Decorative: it shows the real time in IST so a screenshot looks like a phone,
 * and it is hidden from assistive technology because a screen reader already
 * announces the system clock.
 */
export function StatusBar() {
  const [time, setTime] = useState(currentTime);

  useEffect(() => {
    const timer = window.setInterval(() => setTime(currentTime()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="sb" aria-hidden="true">
      <span>{time}</span>
      <span className="sb-r">
        <svg width="17" height="11" aria-hidden="true" focusable="false">
          <path d="M1 10h2V7H1zm4 0h2V5H5zm4 0h2V3H9zm4 0h2V1h-2z" fill="currentColor" />
        </svg>
        <svg width="24" height="11" aria-hidden="true" focusable="false">
          <rect
            x=".5"
            y=".5"
            width="20"
            height="10"
            rx="3"
            fill="none"
            stroke="currentColor"
            opacity=".5"
          />
          <rect x="2" y="2" width="14" height="7" rx="1.5" fill="currentColor" />
        </svg>
      </span>
    </div>
  );
}
