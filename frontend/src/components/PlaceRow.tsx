/** One row in the Explore list (SPEC §8.4).
 *
 * Rank, thumbnail, both name lines, category and area, hearts and visits this
 * month, badges, and the distance. A place with no photo shows its category
 * illustration, never a grey box (SPEC §12.6).
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { categoryIcon, categoryLabel, categoryScene } from '../lib/categories';
import { compact, distance, num } from '../lib/format';
import type { Place } from '../lib/types';
import { GemBadge, LiveBadge, TrendBadge } from './common';
import { Icon, Scene } from './Icon';
import { NameBlock } from './NameBlock';

export function PlaceThumb({
  place,
  className = 'thumb',
}: {
  place: Place;
  className?: string;
}) {
  const photo = place.lead_media;
  const [failed, setFailed] = useState(false);
  if ((photo?.thumb || photo?.url) && !failed) {
    return (
      <img
        className={className}
        src={photo.thumb ?? photo.url}
        alt={photo.caption || place.name.primary.text}
        loading="lazy"
        width={64}
        height={64}
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <Scene
      name={categoryScene(place.category)}
      className={className}
      viewBox="0 50 400 400"
    />
  );
}

export function PlaceRow({ place, showRank = true }: { place: Place; showRank?: boolean }) {
  return (
    <li className="row">
      {showRank && <span className="rank">{place.rank}</span>}
      <Link to={`/place/${place.id}`} style={{ display: 'contents' }}>
        <PlaceThumb place={place} />
        <div className="rbody">
          <NameBlock name={place.name} primaryClass="rname" secondaryClass="rlname" />
          <div className="rmeta">
            <Icon name={categoryIcon(place.category)} size={14} />
            {categoryLabel(place.category)}
            {place.area ? ` · ${place.area}` : ''}
          </div>
          <div className="rstats">
            <span>
              <Icon name="i-heartf" size={13} />
              {num(place.likes)}
            </span>
            <span>
              <Icon name="i-feet" size={13} />
              {compact(place.visits_this_month)} this month
            </span>
            {place.is_gem && <GemBadge />}
            {place.is_trending && <TrendBadge />}
            {place.live && <LiveBadge />}
            {place.status === 'unverified' && (
              <span className="badge" style={{ background: 'var(--sunk)', color: 'var(--muted)' }}>
                Unverified
              </span>
            )}
          </div>
        </div>
        <div className="rdist">{distance(place.distance_km)}</div>
      </Link>
    </li>
  );
}
