/** Formatting. Indian grouping and IST, everywhere (SPEC §7.3).
 *
 * `Intl.NumberFormat('en-IN')` gives 1,00,000 rather than 100,000, which is
 * what a number means to the people this app is for.
 */

const numbers = new Intl.NumberFormat('en-IN');
const oneDecimal = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const money = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 0,
});

/** 1,00,000 */
export function num(value: number): string {
  return numbers.format(Math.round(value));
}

/** 41.6 -- used for "visits caused", which is fractional by design (SPEC §9.9). */
export function num1(value: number): string {
  return oneDecimal.format(value);
}

/** 12.4k for big counts on a card, where space is tight. */
export function compact(value: number): string {
  if (value < 1000) return String(value);
  if (value < 100_000) {
    const thousands = value / 1000;
    return `${thousands < 10 ? thousands.toFixed(1) : Math.round(thousands)}k`;
  }
  return num(value);
}

/**
 * Rupees from integer paise, with the symbol.
 *
 * Deliberately has no "Simulated" tag of its own: that tag is a separate
 * element so it cannot be lost in a string, and `<Money>` always renders both
 * (SPEC §10.5, AC-23).
 */
export function rupees(paise: number): string {
  return `₹${money.format(Math.round(paise / 100))}`;
}

/** 6.2 km, or 850 m when it is close enough to walk. */
export function distance(km: number | undefined | null): string {
  if (km === undefined || km === null) return '';
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km < 10 ? km.toFixed(1) : Math.round(km)} km`;
}

/** "~24 min" -- the deck's travel estimate (SPEC §8.2). */
export function travel(minutes: number | undefined | null): string {
  if (!minutes) return '';
  if (minutes < 60) return `~${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `~${hours} h ${rest} min` : `~${hours} h`;
}

/** 0:24 for a video length. */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(whole / 60);
  return `${minutes}:${String(whole % 60).padStart(2, '0')}`;
}

/** 612 h of watch time. */
export function hours(value: number): string {
  return `${num1(value)} h`;
}

const IST = 'Asia/Kolkata';

/** "20 Oct 2026" in IST, from a UTC timestamp (SPEC §5, §7.3). */
export function date(iso: string): string {
  return new Date(parseUtc(iso)).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: IST,
  });
}

/** "20 OCT 26" -- the passport stamp's date line. */
export function stampDate(iso: string): string {
  return new Date(parseUtc(iso))
    .toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: '2-digit',
      timeZone: IST,
    })
    .replace(/\s/g, ' ')
    .toUpperCase();
}

/** "2 h", "Today", "Sat" -- short relative time for ledgers and Pulse. */
export function ago(iso: string): string {
  const then = parseUtc(iso);
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes} min`;
  const h = Math.round(minutes / 60);
  if (h < 24) return `${h} h`;
  const days = Math.round(h / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) {
    return new Date(then).toLocaleDateString('en-IN', { weekday: 'short', timeZone: IST });
  }
  return date(iso);
}

/**
 * The server sends naive UTC timestamps (SPEC §5). `new Date("...")` without a
 * zone treats them as local time, which in IST would read 5.5 hours wrong, so
 * the Z is added here rather than in twelve call sites.
 */
function parseUtc(iso: string): number {
  const text = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : `${iso}Z`;
  return new Date(text).getTime();
}

/** Percent for progress bars, clamped so a bar can never overflow. */
export function percent(value: number, target: number): number {
  if (target <= 0) return 100;
  return Math.max(0, Math.min(100, Math.round((value / target) * 100)));
}

/** "+18%" with the sign, or an empty string when there is nothing to compare. */
export function delta(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '';
  return `${pct > 0 ? '+' : ''}${pct}%`;
}
