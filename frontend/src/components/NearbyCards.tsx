/** Watch > Nearby: places close to you as cards, not full-screen video.
 *
 * Nearby is about where to go next, so it is a list of what is within reach,
 * nearest first, each with its photo, name in both scripts, distance and how
 * many people have been. A card opens the place; nothing autoplays.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../lib/api';
import { useApp } from '../lib/app-state';
import { distance } from '../lib/format';
import type { Place } from '../lib/types';
import { Loading } from './common';
import { Icon } from './Icon';
import { NameBlock } from './NameBlock';
import { PlaceThumb } from './PlaceRow';

export function NearbyCards() {
  const { me, position } = useApp();
  const [places, setPlaces] = useState<Place[] | null>(null);
  const citySlug = me?.home_city?.slug ?? 'hyderabad';

  useEffect(() => {
    let cancelled = false;
    setPlaces(null);
    api
      .cityPlaces(citySlug, { sort: 'near', at: position })
      .then((response) => {
        if (!cancelled) setPlaces(response.places);
      })
      .catch(() => {
        if (!cancelled) setPlaces([]);
      });
    return () => {
      cancelled = true;
    };
  }, [citySlug, position?.lat, position?.lng]);

  if (places === null) return <Loading what="Finding places near you" />;
  if (places.length === 0) {
    return <p className="plain nearby-empty">Nothing near you yet. Try Explore.</p>;
  }

  return (
    <ul className="ncards" aria-label="Places near you">
      {places.map((place) => (
        <li key={place.id}>
          <Link className="ncard" to={`/place/${place.id}`}>
            <PlaceThumb place={place} className="ncard-ph" />
            <div className="ncard-body">
              <NameBlock name={place.name} primaryClass="ncard-name" secondaryClass="lname" as="h3" />
              <p className="ncard-meta">
                {distance(place.distance_km)}
                {place.video_count > 0 && (
                  <>
                    {' · '}
                    <Icon name="i-video" size={13} /> {place.video_count}
                  </>
                )}
                {place.likes > 0 && ` · ${place.likes} liked`}
              </p>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
