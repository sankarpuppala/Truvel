/** What happens after a check-in (SPEC §8.7).
 *
 * Verified: the stamp drops in, then the one-tap Pulse prompt. Refused: the
 * exact reason, in words a person can act on -- "step into open sky", not
 * "accuracy exceeded threshold".
 */
import { categoryMeta } from '../lib/categories';
import { stampDate } from '../lib/format';
import type { CheckinResult, Place } from '../lib/types';
import { BottomSheet } from '../components/common';
import { Icon } from '../components/Icon';
import { StampTile } from '../components/StudioParts';

export function CheckinSheet({
  result,
  place,
  onClose,
  onPulse,
}: {
  result: CheckinResult | null;
  place: Place;
  onClose: () => void;
  onPulse: () => void;
}) {
  if (!result) return null;

  const meta = categoryMeta(place.category);

  if (!result.verified) {
    return (
      <BottomSheet open onClose={onClose} title="Not yet">
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 14 }}>
          <Icon name={result.code === 'poor_accuracy' ? 'i-target' : 'i-pin'} size={22} />
          <p className="plain">{result.message}</p>
        </div>
        <button type="button" className="btn btn-primary btn-wide" onClick={onClose}>
          Got it
        </button>
      </BottomSheet>
    );
  }

  return (
    <BottomSheet open onClose={onClose} title={result.code === 'already_today' ? 'Already here today' : "You're here!"}>
      {result.code === 'already_today' ? (
        <p className="plain" style={{ marginBottom: 14 }}>
          {result.message}
        </p>
      ) : (
        <>
          <div style={{ display: 'grid', placeItems: 'center', padding: '6px 0 14px' }}>
            <div style={{ width: 140 }}>
              <StampTile
                name={result.stamp?.name ?? place.name.primary.text}
                icon={meta.icon}
                date={stampDate(result.stamp?.date ?? new Date().toISOString())}
                colour={meta.stampColour}
                rotation={-4}
                simulated={result.simulated}
                isNew
              />
            </div>
          </div>

          {result.flag === 'speed' && (
            <div className="golden" role="note" style={{ margin: '0 0 12px' }}>
              <Icon name="i-warn" size={18} />
              <span>
                <b>Flagged for review.</b> This check-in came too soon after one a long way
                away, so it earns no kadam and does not verify the place.
              </span>
            </div>
          )}

          {result.simulated && (
            <div className="devbar" style={{ margin: '0 0 12px' }}>
              <span className="sim-badge">SIM</span>
              <span>
                Simulated location. This visit is excluded from metrics, attribution and
                earnings.
              </span>
            </div>
          )}

          {Boolean(result.kadam) && (
            <p className="plain" style={{ marginBottom: 10 }}>
              <b>+{result.kadam} kadam</b> for your first visit here.
            </p>
          )}

          {result.place_verified && (
            <p className="plain" style={{ marginBottom: 10 }}>
              That is two visitors &mdash; this place is now <b>verified</b>, and whoever found
              it has been paid their discovery kadam.
            </p>
          )}

          {(result.attributed?.length ?? 0) > 0 && (
            <p className="plain" style={{ marginBottom: 10, color: 'var(--muted)' }}>
              Credited to{' '}
              {result.attributed!.length === 1 ? 'the creator' : `${result.attributed!.length} creators`}{' '}
              whose posts you saw before coming.
            </p>
          )}
        </>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        {result.can_pulse && (
          <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={onPulse}>
            <Icon name="i-drop" size={18} />
            How is it right now?
          </button>
        )}
        <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>
          Done
        </button>
      </div>
    </BottomSheet>
  );
}
