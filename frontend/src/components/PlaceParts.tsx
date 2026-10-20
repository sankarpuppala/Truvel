/** The Place page's sections: Pulse, safety, steps, accessibility (SPEC §8.5).
 *
 * The safety card is **never** hidden or collapsed (CLAUDE.md invariant 9), it
 * always shows India's emergency number 112, and it always offers "Share your
 * trip". The last-mile steps are numbered on a dashed trail, which is the
 * app's signature motif (SPEC §12.1).
 */
import { useState } from 'react';

import { ACCESS_ROWS, SAFETY_FLAGS, pulseIcon, pulseLabel } from '../lib/categories';
import { ago, num } from '../lib/format';
import type { Place, PulseSummary, StepVersion } from '../lib/types';
import { LivePill } from './common';
import { Icon } from './Icon';

/** Live conditions, if anyone has reported in the last 48 hours (SPEC §8.8). */
export function PulseStrip({ pulse }: { pulse: PulseSummary | null | undefined }) {
  if (!pulse || !pulse.freshness || pulse.freshness === 'old') return null;

  const fields = Object.entries(pulse.fields) as [string, { value: string; mixed: boolean }][];

  return (
    <div className="pulse" aria-label="Live conditions">
      <div className="pulse-h">
        {pulse.freshness === 'live' ? (
          <LivePill solid />
        ) : (
          <span className="pill" style={{ background: 'var(--sunk)', color: 'var(--muted)' }}>
            Recent
          </span>
        )}
        <span>
          {ago(pulse.at)} ago &middot; {pulse.reporters}{' '}
          {pulse.reporters === 1 ? 'visitor' : 'visitors'}
        </span>
      </div>
      {fields.length > 0 && (
        <div className="pulse-c">
          {fields.map(([field, value]) => (
            <span key={field}>
              <Icon name={pulseIcon(field, value.value)} size={16} />
              {pulseLabel(field, value.value)}
              {value.mixed && (
                <em style={{ fontStyle: 'normal', color: 'var(--muted)', fontWeight: 500 }}>
                  {' '}
                  (mixed reports)
                </em>
              )}
            </span>
          ))}
        </div>
      )}
      {pulse.note && <p className="pulse-n">&ldquo;{pulse.note}&rdquo;</p>}
    </div>
  );
}

/**
 * Safety and access (SPEC §8.14).
 *
 * Only answered flags are listed: "don't know" is shown as nothing rather than
 * as reassurance, because an unanswered question is not a safe answer.
 */
export function SafetyCard({
  place,
  onShareTrip,
}: {
  place: Place;
  onShareTrip: () => void;
}) {
  const safety = place.safety ?? {};
  const rows = SAFETY_FLAGS.map((flag) => {
    const value = safety[flag.key];
    if (value === 'yes') return { ...flag, tone: 'bad' as const, text: flag.yes };
    if (value === 'no' && flag.no) return { ...flag, tone: 'ok' as const, text: flag.no };
    return null;
  }).filter((row): row is NonNullable<typeof row> => row !== null);

  const note = typeof safety.women_safety_note === 'string' ? safety.women_safety_note : '';

  return (
    <section className="sec safety" aria-labelledby="safety-heading">
      <h4 id="safety-heading">
        <Icon name="i-warn" size={18} />
        Safety &amp; access
      </h4>

      {rows.length > 0 ? (
        <ul className="sflags">
          {rows.map((row) => {
            const [lead, ...rest] = row.text.split('. ');
            return (
              <li key={row.key} className={row.tone}>
                <Icon name={row.icon} size={18} />
                <span>
                  <b>{rest.length ? `${lead}.` : row.text}</b>
                  {rest.length ? ` ${rest.join('. ')}` : ''}
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="plain" style={{ marginBottom: 10 }}>
          Nobody has answered the safety questions for this place yet. Go carefully, and
          add what you find.
        </p>
      )}

      {note && (
        <p className="plain" style={{ marginBottom: 10 }}>
          <b>Note from visitors:</b> {note}
        </p>
      )}

      <div className="sf-foot">
        <span className="sos">
          <Icon name="i-call" size={18} />
          Emergency <b>112</b>
        </span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onShareTrip}>
          <Icon name="i-share" size={16} />
          Share your trip
        </button>
      </div>
    </section>
  );
}

/** Last-mile steps on the dashed trail, best version first (SPEC §8.5). */
export function StepList({
  versions,
  locked,
  onVote,
  onPledge,
}: {
  versions: StepVersion[];
  locked: boolean;
  onVote: (group: string, helpful: boolean) => void;
  onPledge?: () => void;
}) {
  const [index, setIndex] = useState(0);

  if (locked) {
    return (
      <div className="lastmile">
        <div className="lm-head">
          <b>Last mile</b>
          <span>
            <Icon name="i-leaf" size={14} />
            This place is fragile
          </span>
        </div>
        <p className="plain">
          The directions and the exact pin open once you save this place and agree to
          treat it carefully.
        </p>
        {onPledge && (
          <button
            type="button"
            className="btn btn-primary btn-wide btn-sm"
            style={{ marginTop: 10 }}
            onClick={onPledge}
          >
            Save it and show me
          </button>
        )}
      </div>
    );
  }

  if (!versions.length) return null;

  const version = versions[Math.min(index, versions.length - 1)];

  return (
    <div className="lastmile">
      <div className="lm-head">
        <b>Last mile</b>
        <span>
          {version.author ? `by @${version.author.username} · ` : ''}
          <Icon name="i-thumb" size={14} />
          {num(version.helpful)} found this helpful
        </span>
      </div>

      <ol className="steps">
        {version.steps.map((step) => (
          <li className="step" key={step.order}>
            <span className="step-n">{step.order}</span>
            <div className="step-b">
              <p>{step.text}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="lm-foot">
        <span>Was this helpful?</span>
        <button
          type="button"
          className="mini"
          aria-label="These directions helped"
          onClick={() => onVote(version.version_group, true)}
        >
          <Icon name="i-thumb" size={16} />
        </button>
        <button
          type="button"
          className="mini flip"
          aria-label="These directions did not help"
          onClick={() => onVote(version.version_group, false)}
        >
          <Icon name="i-thumb" size={16} />
        </button>
        {versions.length > 1 && (
          <button
            type="button"
            className="link"
            onClick={() => setIndex((current) => (current + 1) % versions.length)}
          >
            {versions.length - 1} other {versions.length === 2 ? 'version' : 'versions'}
          </button>
        )}
      </div>
    </div>
  );
}

/** The accessibility rows (SPEC §8.5 item 11). */
export function AccessibilityRows({ place }: { place: Place }) {
  const data = place.accessibility ?? {};
  const rows = ACCESS_ROWS.map((row) => {
    const value = data[row.key];
    if (!value || value === 'unknown' || value === '') return null;
    return { label: row.label, value: humanise(row.key, value) };
  }).filter((row): row is { label: string; value: string } => row !== null);

  if (!rows.length) return null;

  return (
    <section className="sec">
      <h4>
        <Icon name="i-wheel" size={17} />
        Accessibility
      </h4>
      <div className="when">
        {rows.map((row) => (
          <div key={row.label} style={{ display: 'contents' }}>
            <span className="when-k">{row.label}</span>
            <span>{row.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function humanise(key: string, value: string): string {
  if (key !== 'wheelchair') return value;
  if (value === 'yes') return 'Yes';
  if (value === 'no') return 'No';
  if (value === 'partly' || value === 'limited') return 'Partly';
  return value;
}

/** When to go (SPEC §8.5 item 8). */
export function WhenToGo({ place }: { place: Place }) {
  const best = place.best_time ?? {};
  const rows: [string, string][] = [];
  if (best.time) rows.push(['Time', best.time]);
  if (best.months) rows.push(['Months', best.months]);
  if (best.avoid) rows.push(['Avoid', best.avoid]);
  if (!rows.length) return null;

  return (
    <section className="sec">
      <h4>When to go</h4>
      <div className="when">
        {rows.map(([key, value]) => (
          <div key={key} style={{ display: 'contents' }}>
            <span className="when-k">{key}</span>
            <span>{value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
