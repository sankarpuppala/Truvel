/** Formatting rules (SPEC §7.3): Indian grouping, distances, IST dates. */
import { describe, expect, it } from 'vitest';

import {
  ago,
  clock,
  compact,
  date,
  delta,
  distance,
  num,
  num1,
  percent,
  rupees,
  stampDate,
  travel,
} from './format';

describe('numbers use Indian grouping', () => {
  it('groups lakhs the Indian way, not the Western way', () => {
    expect(num(100000)).toBe('1,00,000');
    expect(num(1284)).toBe('1,284');
    expect(num(9812)).toBe('9,812');
    expect(num(12345678)).toBe('1,23,45,678');
  });

  it('keeps one decimal for fractional visits caused', () => {
    // Visits caused is fractional by design (SPEC §9.9).
    expect(num1(41.6)).toBe('41.6');
    expect(num1(0)).toBe('0.0');
  });

  it('compacts big counts for a card', () => {
    expect(compact(812)).toBe('812');
    expect(compact(12400)).toBe('12k');
    expect(compact(1240)).toBe('1.2k');
  });
});

describe('money', () => {
  it('renders rupees with the symbol and Indian grouping', () => {
    expect(rupees(314000)).toBe('₹3,140');
    expect(rupees(100)).toBe('₹1');
  });

  it('never embeds the Simulated label in the string', () => {
    // The label is a separate element so it cannot be lost (AC-23).
    expect(rupees(314000)).not.toMatch(/simulated/i);
  });
});

describe('distance and travel', () => {
  it('switches to metres under a kilometre', () => {
    expect(distance(0.04)).toBe('40 m');
    expect(distance(0.85)).toBe('850 m');
  });

  it('keeps one decimal under 10 km', () => {
    expect(distance(6.2)).toBe('6.2 km');
    expect(distance(21.5)).toBe('22 km');
  });

  it('matches the SPEC example: 6.2 km is about 24 minutes by bike', () => {
    expect(travel(24)).toBe('~24 min');
    expect(travel(95)).toBe('~1 h 35 min');
    expect(travel(120)).toBe('~2 h');
  });

  it('shows nothing when there is no distance', () => {
    expect(distance(undefined)).toBe('');
    expect(travel(null)).toBe('');
  });
});

describe('video length', () => {
  it('reads as minutes and seconds', () => {
    expect(clock(24)).toBe('0:24');
    expect(clock(41)).toBe('0:41');
    expect(clock(95)).toBe('1:35');
  });
});

describe('dates are shown in IST from UTC timestamps', () => {
  it('formats a date the way SPEC §7.3 asks', () => {
    // 20 Oct 2026 at 06:00 UTC is 11:30 IST on the same day.
    expect(date('2026-10-20T06:00:00')).toBe('20 Oct 2026');
  });

  it('rolls over correctly near midnight UTC', () => {
    // 20:00 UTC is 01:30 IST the next day -- so this is the 21st in India.
    expect(date('2026-10-20T20:00:00')).toBe('21 Oct 2026');
  });

  it('formats a passport stamp', () => {
    expect(stampDate('2026-10-20T06:00:00')).toMatch(/20 OCT 26/);
  });

  it('treats a naive server timestamp as UTC, not local time', () => {
    const withZ = date('2026-10-20T06:00:00Z');
    const without = date('2026-10-20T06:00:00');
    expect(without).toBe(withZ);
  });

  it('describes recent times in short words', () => {
    const minutesAgo = new Date(Date.now() - 40 * 60 * 1000).toISOString();
    expect(ago(minutesAgo)).toBe('40 min');
    const hoursAgo = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
    expect(ago(hoursAgo)).toBe('3 h');
  });
});

describe('progress helpers', () => {
  it('clamps a percentage so a bar can never overflow', () => {
    expect(percent(214, 300)).toBe(71);
    expect(percent(400, 300)).toBe(100);
    expect(percent(-5, 300)).toBe(0);
    expect(percent(5, 0)).toBe(100);
  });

  it('signs a delta, and says nothing when there is nothing to compare', () => {
    expect(delta(18)).toBe('+18%');
    expect(delta(-4)).toBe('-4%');
    expect(delta(null)).toBe('');
  });
});
