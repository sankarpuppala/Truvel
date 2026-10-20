/** Studio pieces: metric cards, the Partner checklist, top content (SPEC §8.10).
 *
 * The banner is a component rather than a prop so it cannot be switched off,
 * and every rupee goes through `<Money>`, which always carries the Simulated
 * tag (SPEC §10.5, AC-23).
 */
import { num, num1, percent } from '../lib/format';
import type { Requirement, TopContent } from '../lib/types';
import { Money, Sparkline } from './common';
import { Icon } from './Icon';

/** "Simulated earnings. No real money is paid in this version." Always shown. */
export function SimulatedBanner({ text }: { text?: string }) {
  return (
    <div className="simbanner" role="note">
      <Icon name="i-info" size={17} />
      <span>
        <b>Simulated earnings.</b>{' '}
        {text ?? 'No real money is paid in this version.'}
      </span>
    </div>
  );
}

export function MetricCard({
  title,
  value,
  deltaPct,
  spark,
  sparkLabel,
  money = false,
  key_ = false,
}: {
  title: string;
  value: string;
  deltaPct?: number | null;
  spark?: number[];
  sparkLabel?: string;
  money?: boolean;
  key_?: boolean;
}) {
  return (
    <div className={`mc ${key_ ? 'mc-key' : ''} ${money ? 'mc-money' : ''}`.trim()}>
      <span className="mc-t">{title}</span>
      <b className="mc-v">{value}</b>
      <div className="mc-f">
        {money ? (
          <span className="sim" title="No real money is paid in this version">
            Simulated
          </span>
        ) : deltaPct !== null && deltaPct !== undefined ? (
          <span className="mc-d">
            <Icon name="i-trend" size={13} />
            {deltaPct > 0 ? '+' : ''}
            {deltaPct}%
          </span>
        ) : null}
      </div>
      {spark && spark.length > 1 && (
        <Sparkline values={spark} label={sparkLabel ?? title} />
      )}
    </div>
  );
}

/** The earnings card. Separate from MetricCard so the money path is obvious. */
export function EarningsCard({
  paise,
  projection,
  spark,
}: {
  paise: number;
  projection: boolean;
  spark?: number[];
}) {
  return (
    <div className="mc mc-money">
      <span className="mc-t">Est. earnings</span>
      <b className="mc-v">
        <Money paise={paise} tag={false} />
      </b>
      <div className="mc-f">
        <span className="sim" title="No real money is paid in this version">
          Simulated
        </span>
      </div>
      {spark && spark.length > 1 && <Sparkline values={spark} label="Estimated earnings" />}
      {projection && (
        <span className="mc-t" style={{ marginTop: 4 }}>
          What your work would be worth. You are not a Partner yet, so a real
          month would pay nothing.
        </span>
      )}
    </div>
  );
}

/** The eligibility checklist, with a progress bar on what is unmet (§10.4). */
export function PartnerChecklist({
  requirements,
  done,
  total,
}: {
  requirements: Requirement[];
  done: number;
  total: number;
}) {
  return (
    <section className="partner">
      <div className="pt-h">
        <b>Partner Program</b>
        <span>
          {done} of {total} done
        </span>
      </div>
      <ul className="pt-list">
        {requirements.map((requirement) => (
          <li key={requirement.key} className={requirement.met ? 'ok' : 'todo'}>
            <span className="pt-i">
              {requirement.met && <Icon name="i-check" size={14} />}
            </span>
            {requirement.met ? (
              <span>
                {requirement.label}
                {requirement.key === 'verified_content' && (
                  <small> ({num(requirement.value)})</small>
                )}
              </span>
            ) : (
              <div className="pt-b">
                <span>{requirement.label}</span>
                <div className="pt-bar">
                  <svg viewBox="0 0 300 10" preserveAspectRatio="none" aria-hidden="true">
                    <path d="M2 5H298" className="tr-bg" />
                    <path
                      d={`M2 5H${(
                        2 +
                        (percent(requirement.value, requirement.target) / 100) * 296
                      ).toFixed(1)}`}
                      className="tr-fg"
                    />
                  </svg>
                  <b>
                    {num(requirement.value)} / {num(requirement.target)}
                  </b>
                </div>
                {requirement.note && <small>{requirement.note}</small>}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Top content by visits caused -- the metric the app exists for (§8.10). */
export function TopContentTable({
  items,
  onExplain,
}: {
  items: TopContent[];
  onExplain: () => void;
}) {
  return (
    <section className="topc">
      <div className="pt-h">
        <b>Top content</b>
        <span>visits caused</span>
      </div>
      {items.length === 0 ? (
        <p className="plain" style={{ color: 'var(--muted)' }}>
          Your first place or video starts your Studio.
        </p>
      ) : (
        items.map((item) => (
          <div className="tc" key={`${item.type}-${item.media_id ?? item.place_id}`}>
            {item.thumb ? (
              <img className="thumb thumb-sm" src={item.thumb} alt="" width={52} height={52} />
            ) : (
              <span className="thumb thumb-sm" style={{ background: 'var(--sunk)' }} />
            )}
            <div>
              <b>{item.title}</b>
              <span>
                {item.type === 'place'
                  ? `place you found · ${num(item.engaged_views)} page views`
                  : `video · ${num(item.engaged_views)} views${
                      item.avg_watched_pct !== null
                        ? ` · ${item.avg_watched_pct}% watched`
                        : ''
                    }`}
              </span>
            </div>
            <em>{num1(item.visits_caused)}</em>
          </div>
        ))
      )}
      <button type="button" className="link link-sm" onClick={onExplain}>
        How earnings are split
        <Icon name="i-chevr" size={14} />
      </button>
    </section>
  );
}

/** One passport stamp: ink-like, slightly rotated, dated (SPEC §8.9). */
export function StampTile({
  name,
  icon,
  date,
  colour,
  rotation,
  simulated,
  isNew = false,
}: {
  name: string;
  icon: string;
  date: string;
  colour: 'lat' | 'moss' | 'lake';
  rotation: number;
  simulated?: boolean;
  isNew?: boolean;
}) {
  return (
    <div
      className={`stamp st-${colour} ${isNew ? 'stamp-new' : ''}`.trim()}
      style={{ ['--r' as string]: `${rotation}deg` }}
    >
      <Icon name={icon} size={22} />
      <b>{name}</b>
      <span>{date}</span>
      {simulated && <span className="sim-badge">SIM</span>}
    </div>
  );
}

/** The "next stamp" outline, so an empty passport still shows the shape (§12.9). */
export function EmptyStamp() {
  return (
    <div className="stamp stamp-empty" style={{ ['--r' as string]: '0deg' }}>
      <span className="se-plus">+</span>
      <b>Next stamp</b>
      <span>one visit away</span>
    </div>
  );
}
