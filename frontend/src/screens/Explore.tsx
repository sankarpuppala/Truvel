/** Explore -- the ranked list and the fog map. Reference screens 3 and 4.
 *
 * The five sorts are the SPEC §9.1-9.3 functions, and the ⓘ line under the tabs
 * explains in one sentence what the current sort actually measures -- a ranking
 * nobody can explain is a ranking nobody should trust (SPEC §8.4).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Chip, EmptyState, Loading, Segmented, Tabs } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { LocationPicker } from '../components/LocationPicker';
import { PlaceRow } from '../components/PlaceRow';
import { FogMap } from '../components/FogMap';
import { FILTER_CHIPS, SORTS } from '../lib/categories';
import { num } from '../lib/format';
import type { City, Place } from '../lib/types';

export function Explore() {
  const { position, requestPosition, toast } = useApp();
  const [params, setParams] = useSearchParams();

  const view = (params.get('view') === 'map' ? 'map' : 'list') as 'list' | 'map';
  const sort = params.get('sort') ?? 'top';
  const category = params.get('cat') ?? 'all';
  const verifiedOnly = params.get('verified') === '1';
  const stateSlug = params.get('state');
  const localitySlug = params.get('locality');
  const citySlug =
    stateSlug || localitySlug
      ? null
      : (params.get('city') ?? 'all');
  const scoped = Boolean(stateSlug || localitySlug);

  const [locationPickerOpen, setLocationPickerOpen] = useState(false);
  const [query, setQuery] = useState('');
  // Debounced: what the scoped list and the "browse elsewhere" suggestions
  // actually search for, so every keystroke does not re-fetch.
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [city, setCity] = useState<City | null>(null);
  const [places, setPlaces] = useState<Place[]>([]);
  const [explainer, setExplainer] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [suggestions, setSuggestions] = useState<{
    cities: City[];
    states: City[];
    localities: City[];
  } | null>(null);

  useEffect(() => {
    void requestPosition(true);
  }, [requestPosition]);

  const update = useCallback(
    (next: Record<string, string | null>) => {
      const merged = new URLSearchParams(params);
      for (const [key, value] of Object.entries(next)) {
        if (value === null) merged.delete(key);
        else merged.set(key, value);
      }
      setParams(merged, { replace: true });
    },
    [params, setParams],
  );

  // Opening Explore with no city/state/locality in the URL used to mean "all
  // 18,000+ places in India" -- both the slowest possible list and not where
  // the person actually is. Once, per screen, jump the (otherwise untouched)
  // default to wherever `position` resolves to -- the same detection
  // Nearby's header already uses (SPEC §8.4), which covers an unseeded town
  // (Araku) as a `locality` just as well as a seeded `City` -- and leave it
  // alone the moment the person picks somewhere themselves. The list itself
  // waits for this (`scopeReady`) so it fetches the detected place once
  // instead of all of India and then the detected place.
  const hasExplicitScope = params.has('city') || params.has('state') || params.has('locality');
  const appliedDefaultLocation = useRef(false);
  const [scopeReady, setScopeReady] = useState(hasExplicitScope);
  useEffect(() => {
    if (hasExplicitScope) {
      appliedDefaultLocation.current = true;
      setScopeReady(true);
      return undefined;
    }
    if (appliedDefaultLocation.current) return undefined;
    if (position) {
      appliedDefaultLocation.current = true;
      void api
        .here(position.lat, position.lng)
        .then((info) => {
          if (info.kind === 'city' && info.slug) update({ city: info.slug });
          else if (info.kind === 'locality' && info.slug) update({ locality: info.slug });
          else if (info.kind === 'state' && info.slug) update({ state: info.slug });
        })
        .catch(() => undefined)
        .finally(() => setScopeReady(true));
      return undefined;
    }
    // No position yet: fall back to All India after a short wait rather
    // than leaving the list blocked forever when location is off.
    const timer = window.setTimeout(() => {
      appliedDefaultLocation.current = true;
      setScopeReady(true);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [position?.lat, position?.lng, hasExplicitScope, update]);

  useEffect(() => {
    setPage(1);
  }, [stateSlug, localitySlug, citySlug, sort, category, verifiedOnly]);

  useEffect(() => {
    if (!scopeReady) return undefined;
    let cancelled = false;
    setLoading(true);
    const options = {
      sort,
      cat: category === 'all' ? undefined : category,
      verified: verifiedOnly,
      at: position,
      page,
      q: debouncedQuery.length >= 2 ? debouncedQuery : undefined,
    };
    const request = stateSlug
      ? api.statePlaces(stateSlug, options)
      : localitySlug
        ? api.localityPlaces(localitySlug, options)
        : api.cityPlaces(citySlug ?? 'all', options);
    request
      .then((response) => {
        if (cancelled) return;
        setCity(response.city);
        if (page === 1) {
          setPlaces(response.places);
        } else {
          setPlaces((prev) => {
            const seen = new Set(prev.map((p) => p.id));
            const fresh = response.places.filter((p) => !seen.has(p.id));
            return [...prev, ...fresh];
          });
        }
        setExplainer(response.explainer);
        setTotal(response.total);
      })
      .catch((error) => {
        if (!cancelled) {
          toast(error instanceof ApiError ? error.message : 'Could not load the list.', 'bad');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    stateSlug,
    localitySlug,
    citySlug,
    sort,
    category,
    verifiedOnly,
    page,
    debouncedQuery,
    position?.lat,
    position?.lng,
    scopeReady,
    toast,
  ]);

  // Runs as you type, after a short pause: narrows the current city/state/
  // town's own list (via the scoped `q` above) and, separately, offers a
  // whole other place to browse ("Goa", "Tirupati") if the text matches one.
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setSuggestions(null);
      setDebouncedQuery('');
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setPage(1);
      setDebouncedQuery(trimmed);
      void api
        .search(trimmed, position)
        .then((response) =>
          setSuggestions({
            cities: response.cities,
            states: response.states,
            localities: response.localities,
          }),
        )
        .catch(() => setSuggestions(null));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [query, position?.lat, position?.lng]);

  const rows = places;

  const header = useMemo(
    () => (
      <div className="srow">
        <div className="search">
          <Icon name="i-search" size={20} />
          <input
            className="search-v"
            style={{ border: 0, background: 'transparent', minHeight: 'auto', padding: 0 }}
            placeholder={view === 'map' ? 'Search the map' : 'Search a city, area or place'}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search cities, areas and places in any script"
          />
          {query && (
            <button
              type="button"
              className="search-x"
              aria-label="Clear the search"
              onClick={() => setQuery('')}
            >
              <Icon name="i-x" size={16} />
            </button>
          )}
        </div>
        {!scoped && (
          <Segmented
            label="List or map"
            value={view}
            onChange={(key) => update({ view: key })}
            options={[
              { key: 'list', label: 'List', icon: 'i-list' },
              { key: 'map', label: 'Map', icon: 'i-map' },
            ]}
          />
        )}
      </div>
    ),
    [query, update, view, scoped],
  );

  // A state or town browsed by its column rather than a seeded City has no
  // bbox or fog to draw (see FogMap): the map toggle is hidden above, and
  // this guards a stale ?view=map left in the URL.
  if (view === 'map' && !scoped) {
    return (
      <>
        <FogMap
          city={city}
          places={places}
          header={
            <>
              <StatusBar />
              {header}
            </>
          }
        />
      </>
    );
  }

  const hasSuggestions =
    !!suggestions &&
    (suggestions.states.length > 0 ||
      suggestions.localities.length > 0 ||
      suggestions.cities.length > 0);

  return (
    <>
      <StatusBar />
      {header}

      <div className="ex-head">
        <button
          type="button"
          onClick={() => setLocationPickerOpen(true)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            background: 'transparent',
            border: 0,
            padding: 0,
            cursor: 'pointer',
            textAlign: 'left',
          }}
          aria-label={`City: ${city?.name ?? 'All India'}. Tap to change city.`}
        >
          <h3 className="ex-city" style={{ margin: 0 }}>
            {city?.name ?? 'All India'}
          </h3>
          <Icon name="i-chev" size={18} />
        </button>
        <div className="ex-sub">
          {city ? (
            <>
              {num(city.place_count)} places &middot; {num(city.community_count)} found by locals
            </>
          ) : (
            ' '
          )}
        </div>
      </div>

      <LocationPicker
        open={locationPickerOpen}
        onClose={() => setLocationPickerOpen(false)}
        showAllIndia
        onSelectCity={(selected) => {
          if (selected.slug === 'all') {
            update({ city: null, state: null, locality: null });
          } else {
            update({ city: selected.slug, state: null, locality: null });
          }
        }}
      />

      <Tabs
        label="Sort the list"
        value={sort}
        onChange={(key) => {
          setPage(1);
          update({ sort: key });
        }}
        options={SORTS}
      />

      <p className="why">
        <Icon name="i-info" size={15} />
        {explainer}
      </p>

      <div className="chips" style={{ overflowX: 'auto', paddingBottom: 6 }}>
        {FILTER_CHIPS.map((chip) => (
          <Chip
            key={chip.key}
            label={chip.label}
            icon={chip.icon}
            on={category === chip.key}
            onClick={() => {
              setPage(1);
              update({ cat: chip.key === 'all' ? null : chip.key });
            }}
          />
        ))}
        <Chip
          label="Verified only"
          icon="i-check"
          on={verifiedOnly}
          onClick={() => update({ verified: verifiedOnly ? null : '1' })}
        />
      </div>

      <div className="scr-body">
        {/* A match elsewhere in India -- offered, never substituted for the
            current city/state/town's own (now query-filtered) list below. */}
        {hasSuggestions && (
          <div style={{ padding: '0 16px 10px' }}>
            <h4
              style={{
                font: '700 13px/1.3 Mukta,sans-serif',
                letterSpacing: '.1em',
                textTransform: 'uppercase',
                color: 'var(--muted)',
                margin: '8px 0',
              }}
            >
              Browse somewhere else
            </h4>
            {suggestions!.states.map((entry) => (
              <button
                key={`state-${entry.slug}`}
                type="button"
                className="cand"
                style={{ width: '100%', marginBottom: 6 }}
                onClick={() => {
                  setQuery('');
                  setPage(1);
                  update({ state: entry.slug, city: null, locality: null, view: 'list' });
                }}
              >
                <div>
                  <b>{entry.name}</b>
                  <span>{num(entry.place_count)} places across the state</span>
                </div>
                <Icon name="i-chevr" size={18} />
              </button>
            ))}
            {suggestions!.localities.map((entry) => (
              <button
                key={`locality-${entry.slug}`}
                type="button"
                className="cand"
                style={{ width: '100%', marginBottom: 6 }}
                onClick={() => {
                  setQuery('');
                  setPage(1);
                  update({ locality: entry.slug, city: null, state: null, view: 'list' });
                }}
              >
                <div>
                  <b>{entry.name}</b>
                  <span>
                    {entry.state ? `${entry.state} · ` : ''}
                    {num(entry.place_count)} places
                  </span>
                </div>
                <Icon name="i-chevr" size={18} />
              </button>
            ))}
            {suggestions!.cities.map((entry) => (
              <button
                key={entry.slug}
                type="button"
                className="cand"
                style={{ width: '100%', marginBottom: 6 }}
                onClick={() => {
                  setQuery('');
                  setPage(1);
                  update({ city: entry.slug, state: null, locality: null });
                }}
              >
                <div>
                  <b>{entry.name}</b>
                  <span>
                    {entry.state} &middot; {num(entry.place_count)} places
                  </span>
                </div>
                <Icon name="i-chevr" size={18} />
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <Loading what="Ranking places" />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={debouncedQuery ? 'i-search' : 'i-pin'}
            title={
              debouncedQuery
                ? 'Nothing matched here'
                : (city?.place_count ?? 0) < 5
                  ? 'This city is mostly unmapped'
                  : 'Nothing here yet'
            }
            body={
              debouncedQuery
                ? `No place in ${city?.name ?? 'this list'} matches "${debouncedQuery}". Try the search above for places elsewhere too.`
                : (city?.place_count ?? 0) < 5
                  ? 'Be its first pathfinder.'
                  : 'Try another sort, or clear the filters.'
            }
            action={
              debouncedQuery ? undefined : (
                <Link className="btn btn-primary btn-sm" to="/add/place">
                  Add a place
                </Link>
              )
            }
          />
        ) : (
          <>
            <ol className="rows" style={{ flex: 'none' }}>
              {rows.map((place) => (
                <PlaceRow key={place.id} place={place} />
              ))}
            </ol>
            {total > places.length && (
              <div style={{ padding: 16, display: 'flex', justifyContent: 'center' }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPage((value) => value + 1)}
                >
                  Show more
                </button>
              </div>
            )}
            <p className="attrib" style={{ padding: '4px 16px 10px' }}>
              Map data &copy; OpenStreetMap contributors &middot; famous places from Wikidata (CC0)
            </p>
          </>
        )}
      </div>
    </>
  );
}
