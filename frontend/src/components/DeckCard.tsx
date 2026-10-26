/** The Nearby deck card and its three buttons (SPEC §8.2, §12.7).
 *
 * The card follows the finger and rotates by `x/12` degrees; releasing past
 * 30 % of the width commits the swipe, otherwise it springs back. Every gesture
 * has a button underneath it, which is not a nicety -- it is required
 * (SPEC §13), and it is also how the deck works with a keyboard.
 *
 * Under `prefers-reduced-motion` the drag does not rotate and the card
 * cross-fades instead of flying off.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDrag } from '@use-gesture/react';

import { categoryIcon, categoryLabel, categoryScene } from '../lib/categories';
import { distance, num, travel } from '../lib/format';
import { haptic } from '../lib/geo';
import type { Place } from '../lib/types';
import { GemPill, LivePill, TipNote } from './common';
import { Icon, Scene } from './Icon';
import { NameBlock } from './NameBlock';

export type SwipeAction = 'save' | 'skip' | 'open';

const COMMIT_FRACTION = 0.3;

function reducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function CardArt({ place, priority }: { place: Place; priority?: boolean }) {
  const photo = place.lead_media;
  // A photo that fails to load (offline, licence refused) falls back to the
  // category illustration -- never a broken-image icon (SPEC §12.6).
  const [failed, setFailed] = useState(false);
  if (photo?.url && !failed) {
    return (
      <img
        className="ph"
        src={photo.url}
        alt={photo.caption || place.name.primary.text}
        style={{ objectFit: 'cover' }}
        // The front card's photo is the page's LCP element (Lighthouse,
        // card A2): hint the browser to fetch it first.
        fetchPriority={priority ? 'high' : undefined}
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <Scene
      name={categoryScene(place.category)}
      className="ph"
      alt={`${categoryLabel(place.category)} illustration for ${place.name.primary.text}`}
    />
  );
}

/** The card behind the front one, peeking below (SPEC §8.2). */
export function DeckCardBack({ place }: { place: Place }) {
  return (
    <div className="card card-back" aria-hidden="true">
      <CardArt place={place} />
    </div>
  );
}

export function DeckCard({
  place,
  onAction,
}: {
  place: Place;
  onAction: (action: SwipeAction) => void;
}) {
  const [{ x, y, rotate, gone }, setDrag] = useState({
    x: 0,
    y: 0,
    rotate: 0,
    gone: false,
  });
  const widthRef = useRef(360);
  const cardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (cardRef.current) widthRef.current = cardRef.current.offsetWidth || 360;
    setDrag({ x: 0, y: 0, rotate: 0, gone: false });
  }, [place.id]);

  function commit(action: SwipeAction) {
    if (action === 'save') haptic();
    const reduce = reducedMotion();
    if (reduce || action === 'open') {
      onAction(action);
      return;
    }
    // Let the card leave the screen before the next one takes its place.
    const flyX = action === 'save' ? widthRef.current * 1.4 : -widthRef.current * 1.4;
    setDrag({ x: flyX, y: 0, rotate: flyX / 12, gone: true });
    window.setTimeout(() => onAction(action), 180);
  }

  const bind = useDrag(
    ({ active, movement: [mx, my], velocity: [vx], direction: [dx], tap }) => {
      if (tap) {
        commit('open');
        return;
      }
      const reduce = reducedMotion();
      const threshold = widthRef.current * COMMIT_FRACTION;

      if (active) {
        setDrag({
          x: mx,
          y: my,
          rotate: reduce ? 0 : mx / 12,
          gone: false,
        });
        return;
      }

      // Released: commit past 30 % of the width, or on a decisive flick.
      const far = Math.abs(mx) > threshold;
      const flicked = vx > 0.5 && Math.abs(mx) > threshold * 0.5;
      if (far || flicked) {
        commit(dx > 0 || mx > 0 ? 'save' : 'skip');
        return;
      }
      // Swipe up opens.
      if (my < -threshold) {
        commit('open');
        return;
      }
      setDrag({ x: 0, y: 0, rotate: 0, gone: false });
    },
    { filterTaps: true, pointer: { touch: true } },
  );

  const saving = x > 40;
  const skipping = x < -40;

  return (
    <>
      <article
        {...bind()}
        ref={(node) => {
          cardRef.current = node;
        }}
        className="card card-front"
        aria-label={`${place.name.primary.text}, ${distance(place.distance_km)} away`}
        style={{
          transform: `translate3d(${x}px, ${y}px, 0) rotate(${rotate}deg)`,
          transition: gone || x === 0 ? 'transform 180ms ease-out' : 'none',
          opacity: gone ? 0 : 1,
          touchAction: 'none',
        }}
      >
        <CardArt place={place} priority />

        <div className="card-top">
          {place.is_gem ? <GemPill /> : <span />}
          {place.live && <LivePill />}
        </div>

        {/* The stamp that flashes as a saved card leaves (SPEC §12.7). */}
        {(saving || skipping) && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: 28,
              left: saving ? 18 : 'auto',
              right: skipping ? 18 : 'auto',
              zIndex: 3,
              transform: `rotate(${saving ? -8 : 8}deg)`,
              border: `2.5px solid ${saving ? 'var(--marigold)' : 'var(--on-photo)'}`,
              color: saving ? 'var(--marigold)' : 'var(--on-photo)',
              borderRadius: 10,
              padding: '4px 10px',
              fontWeight: 800,
              letterSpacing: '.06em',
              fontSize: 15,
              textTransform: 'uppercase',
              background: 'var(--scrim-soft)',
            }}
          >
            {saving ? 'Want to go' : 'Skip'}
          </div>
        )}

        <div className="card-text">
          {place.found_by && (
            <div className="by">
              {place.found_by.official ? 'Posted by' : 'Found by'}{' '}
              <Link
                to={`/u/${place.found_by.username}`}
                onClick={(e) => e.stopPropagation()}
                className="deck-creator-link"
              >
                <b>@{place.found_by.username}</b>
              </Link>
            </div>
          )}
          <NameBlock name={place.name} primaryClass="pname" secondaryClass="lname" as="h3" />
          <div className="meta">
            <Icon name={categoryIcon(place.category)} size={16} />
            {categoryLabel(place.category)} &middot; {distance(place.distance_km)} &middot;{' '}
            {travel(place.travel_min)} <Icon name="i-bike" size={16} />
          </div>
          <div className="cstats">
            <span>
              <Icon name="i-heartf" size={15} />
              {num(place.likes)}
            </span>
            <span>
              <Icon name="i-feet" size={15} />
              {num(place.verified_visits)} visits
            </span>
            {place.unverified_nearby && <span>Unverified</span>}
          </div>
        </div>

        {place.tip && <TipNote text={place.tip.text} by={place.tip.by} className="tip-deck" />}
      </article>
    </>
  );
}

/** Skip - Open - Save. Every gesture also has a button (SPEC §8.2, §13). */
export function DeckActions({ onAction }: { onAction: (action: SwipeAction) => void }) {
  return (
    <div className="actions">
      <button
        type="button"
        className="act act-skip"
        aria-label="Skip this place"
        onClick={() => onAction('skip')}
      >
        <Icon name="i-x" size={26} />
        <span>Skip</span>
      </button>
      <button
        type="button"
        className="act act-open"
        aria-label="Open this place"
        onClick={() => onAction('open')}
      >
        <Icon name="i-up" size={22} />
        <span>Open</span>
      </button>
      <button
        type="button"
        className="act act-save"
        aria-label="Save to Want to go"
        onClick={() => onAction('save')}
      >
        <Icon name="i-star" size={26} />
        <span>Save</span>
      </button>
    </div>
  );
}
