/** The small shared pieces: money, pills, chips, sheets, toasts, empty states.
 *
 * `<Money>` is the important one. Every rupee figure in the app goes through
 * it, and it always renders the **Simulated** tag beside the number -- the tag
 * is a separate element rather than part of a string so it cannot be dropped by
 * a careless template (SPEC §10.5, AC-23).
 */
import { useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { rupees } from '../lib/format';
import { useApp } from '../lib/app-state';
import { Icon } from './Icon';

/** A rupee amount from integer paise, always labelled Simulated. */
export function Money({
  paise,
  className = '',
  tag = true,
}: {
  paise: number;
  className?: string;
  tag?: boolean;
}) {
  return (
    <span className={className}>
      {rupees(paise)}
      {tag && (
        <>
          {' '}
          <span className="sim" title="No real money is paid in this version">
            Simulated
          </span>
        </>
      )}
    </span>
  );
}

/** The standalone Simulated tag, for a card that shows money in its value slot. */
export function SimulatedTag() {
  return (
    <span className="sim" title="No real money is paid in this version">
      Simulated
    </span>
  );
}

/** The Live pill: a Pulse report under 6 hours old (SPEC §8.8). */
export function LivePill({
  text,
  solid = false,
  className = '',
}: {
  text?: string;
  solid?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`pill pill-live ${solid ? 'pill-live-solid' : ''} ${className}`.trim()}
    >
      <i className="dot" />
      {text ? `Live · ${text}` : 'Live'}
    </span>
  );
}

/** The Live badge used inside an Explore row's stats line. */
export function LiveBadge() {
  return (
    <span className="badge badge-live">
      <i className="dot" />
      Live
    </span>
  );
}

export function GemPill() {
  return (
    <span className="pill pill-gem">
      <Icon name="i-leaf" size={14} />
      Hidden gem
    </span>
  );
}

export function GemBadge() {
  return (
    <span className="badge badge-gem">
      <Icon name="i-leaf" size={12} />
      Hidden gem
    </span>
  );
}

export function TrendBadge() {
  return <span className="badge badge-trend">Trending</span>;
}

/** The handwritten slip a local tip sits on (SPEC §12.5 TipNote). */
export function TipNote({
  text,
  by,
  className = '',
}: {
  text: string;
  by?: string | null;
  className?: string;
}) {
  return (
    <p className={`tip ${className}`.trim()}>
      {text}
      {by && (
        <span>
          <Link to={`/u/${by}`} style={{ color: 'inherit', textDecoration: 'none', fontWeight: 600 }}>
            @{by}
          </Link>
        </span>
      )}
    </p>
  );
}

/** A two-or-more-option segmented control (List|Map, Passport|Studio). */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  className = '',
  label,
}: {
  options: { key: T; label: string; icon?: string }[];
  value: T;
  onChange: (key: T) => void;
  className?: string;
  label: string;
}) {
  return (
    <div className={`seg ${className}`.trim()} role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={option.key === value}
          className={option.key === value ? 'on' : ''}
          onClick={() => onChange(option.key)}
        >
          {option.icon && <Icon name={option.icon} size={16} />}
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** The underlined tab row used by Explore's sorts and the Passport's tabs. */
export function Tabs<T extends string>({
  options,
  value,
  onChange,
  className = '',
  label,
}: {
  options: { key: T; label: string }[];
  value: T;
  onChange: (key: T) => void;
  className?: string;
  label: string;
}) {
  return (
    <div className={`tabs ${className}`.trim()} role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={option.key === value}
          className={`tab ${option.key === value ? 'on' : ''}`.trim()}
          onClick={() => onChange(option.key)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** A horizontally scrolling chip row (categories, activities). */
export function Chip({
  label,
  icon,
  on = false,
  onClick,
  as = 'button',
}: {
  label: string;
  icon?: string;
  on?: boolean;
  onClick?: () => void;
  as?: 'button' | 'span';
}) {
  const className = `chip ${on ? 'on' : ''}`.trim();
  if (as === 'span' || !onClick) {
    return (
      <span className={className}>
        {icon && <Icon name={icon} size={15} />}
        {label}
      </span>
    );
  }
  return (
    <button type="button" className={className} aria-pressed={on} onClick={onClick}>
      {icon && <Icon name={icon} size={15} />}
      {label}
    </button>
  );
}

/** A bottom sheet. Closes on Escape and on a backdrop click (SPEC §12.5). */
export function BottomSheet({
  open,
  onClose,
  title,
  children,
  className = '',
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="sheet-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className={`sheet ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="grab" />
        {title && (
          <div className="sheet-head-row">
            <h4 style={{ font: "400 22px/1.15 var(--f-display)", margin: 0 }}>
              {title}
            </h4>
            <button
              type="button"
              className="sheet-close-btn"
              onClick={onClose}
              aria-label="Close"
            >
              <Icon name="i-x" size={16} />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

/** The toast stack. Kadam toasts are marigold; errors are danger (SPEC §12.7). */
export function Toasts() {
  const { toasts } = useApp();
  if (!toasts.length) return null;
  return (
    <div className="toast-wrap" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast ${toast.kind === 'kadam' ? 'toast-kadam' : ''} ${
            toast.kind === 'bad' ? 'toast-bad' : ''
          }`.trim()}
        >
          {toast.kind === 'kadam' && <Icon name="i-feet" size={16} />}
          {toast.text}
        </div>
      ))}
    </div>
  );
}

/** An empty state with a reason and a way forward (SPEC §12.9). */
export function EmptyState({
  icon = 'i-compass',
  title,
  body,
  action,
}: {
  icon?: string;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Icon name={icon} size={34} />
      <b>{title}</b>
      {body && <p>{body}</p>}
      {action}
    </div>
  );
}

export function Loading({ what = 'Loading' }: { what?: string }) {
  return (
    <div className="loading" role="status">
      {what}&hellip;
    </div>
  );
}

/** A dashed-trail progress bar: levels, Partner progress, Add steps. */
export function DashedProgress({
  value,
  max,
  label,
}: {
  value: number;
  max: number;
  label?: string;
}) {
  const fraction = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const x = 2 + fraction * 296;
  return (
    <div className="trail" aria-hidden={label ? undefined : true}>
      <svg viewBox="0 0 300 14" preserveAspectRatio="none" role={label ? 'img' : undefined} aria-label={label}>
        <path d="M2 7H298" className="tr-bg" />
        <path d={`M2 7H${x.toFixed(1)}`} className="tr-fg" />
      </svg>
    </div>
  );
}

/** A sparkline, with its values also available as text (SPEC §13, AC-19). */
export function Sparkline({
  values,
  label,
  className = 'spk',
}: {
  values: number[];
  label: string;
  className?: string;
}) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * 120;
      const y = 28 - ((value - min) / span) * 24;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <>
      <svg className={className} viewBox="0 0 120 30" preserveAspectRatio="none" aria-hidden="true">
        <polyline points={points} />
      </svg>
      {/* The same numbers in words, so the trend is not colour-and-shape only. */}
      <span className="sr-only">
        {label}: {values.map((v) => Math.round(v * 10) / 10).join(', ')}
      </span>
    </>
  );
}
