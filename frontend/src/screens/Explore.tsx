/** Explore -- the ranked list and the fog map. Reference screens 3 and 4.
 *
 * The five sorts are the SPEC §9.1-9.3 functions, and the ⓘ line under the tabs
 * explains in one sentence what the current sort actually measures -- a ranking
 * nobody can explain is a ranking nobody should trust (SPEC §8.4).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Chip, EmptyState, Loading, Segmented, Tabs } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { PlaceRow } from '../components/PlaceRow';
import { FogMap } from '../components/FogMap';
import { FILTER_CHIPS, SORTS } from '../lib/categories';
import { num } from '../lib/format';
import type { City, Place } from '../lib/types';

export function Explore() {
  const { me, position, requestPosition, toast } = useApp();
  const [params, setParams] = useSearchParams();

  const view = (params.get('view') === 'map' ? 'map' : 'list') as 'list' | 'map';
  const sort = params.get('sort') ?? 'top';
  const category = params.get('cat') ?? 'all';
  const verifiedOnly = params.get('verified') === '1';
  const stateSlug = params.get('state');
  const citySlug = stateSlug ? null : (params.get('city') ?? me?.home_city?.slug ?? 'hyderabad');

  const [query, setQuery] = useState('');
  const [city, setCity] = useState<City | null>(null);
  const [places, setPlaces] = useState<Place[]>([]);
  const [explainer, setExplainer] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searchResults, setSearchResults] = useState<{
    cities: City[];
    states: City[];
    places: Place[];
  } | null>(null);

  useEffect(() => {
    void requestPosition();
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

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const options = {
      sort,
      cat: category === 'all' ? undefined : category,
      verified: verifiedOnly,
      at: position,
      page,
    };
    const request = stateSlug
      ? api.statePlaces(stateSlug, options)
      : api.cityPlaces(citySlug ?? 'hyderabad', options);
    request
      .then((response) => {
        if (cancelled) return;
        setCity(response.city);
        setPlaces(response.places);
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
  }, [stateSlug, citySlug, sort, category, verifiedOnly, page, position?.lat, position?.lng, toast]);

  // Search runs as you type, after a short pause.
  useEffect(() => {
    if (query.trim().length < 2) {
      setSearchResults(null);
      return undefined;
    }
    const timer = window.setTimeout(() => {
      void api
        .search(query.trim(), position)
        .then((response) =>
          setSearchResults({ cities: response.cities, states: response.states, places: response.places }),
        )
        .catch(() => setSearchResults(null));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [query, position?.lat, position?.lng]);

  const rows = searchResults?.places ?? places;

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
        {!stateSlug && (
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
    [query, update, view, stateSlug],
  );

  // A state has no bbox or fog to draw (see FogMap): the map toggle is
  // hidden above, and this guards a stale ?view=map left in the URL.
  if (view === 'map' && !stateSlug) {
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

  return (
    <>
      <StatusBar />
      {header}

      {searchResults ? (
        <div className="scr-body">
          {(searchResults.states.length > 0 || searchResults.cities.length > 0) && (
            <div style={{ padding: '4px 16px 0' }}>
              <h4
                style={{
                  font: '700 13px/1.3 Mukta,sans-serif',
                  letterSpacing: '.1em',
                  textTransform: 'uppercase',
                  color: 'var(--muted)',
                  margin: '8px 0',
                }}
              >
                {searchResults.states.length > 0 && searchResults.cities.length > 0
                  ? 'States & cities'
                  : searchResults.states.length > 0
                    ? 'States'
                    : 'Cities'}
              </h4>
              {searchResults.states.map((entry) => (
                <button
                  key={`state-${entry.slug}`}
                  type="button"
                  className="cand"
                  style={{ width: '100%', marginBottom: 6 }}
                  onClick={() => {
                    setQuery('');
                    setPage(1);
                    update({ state: entry.slug, city: null, view: 'list' });
                  }}
                >
                  <div>
                    <b>{entry.name}</b>
                    <span>{num(entry.place_count)} places across the state</span>
                  </div>
                  <Icon name="i-chevr" size={18} />
                </button>
              ))}
              {searchResults.cities.map((entry) => (
                <button
                  key={entry.slug}
                  type="button"
                  className="cand"
                  style={{ width: '100%', marginBottom: 6 }}
                  onClick={() => {
                    setQuery('');
                    setPage(1);
                    update({ city: entry.slug, state: null });
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
          {rows.length > 0 ? (
            <ol className="rows" style={{ flex: 'none' }}>
              {rows.map((place) => (
                <PlaceRow key={place.id} place={place} showRank={false} />
              ))}
            </ol>
          ) : (
            <EmptyState
              icon="i-search"
              title="Nothing matched"
              body="Try a shorter word, or the name in another script."
            />
          )}
        </div>
      ) : (
        <>
          <div className="ex-head">
            <h3 className="ex-city">{city?.name ?? '—'}</h3>
            <div className="ex-sub">
              {city ? (
                <>
                  {num(city.place_count)} places &middot; {num(city.community_count)} found by
                  locals
                </>
              ) : (
                ' '
              )}
            </div>
          </div>

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
            {loading ? (
              <Loading what="Ranking places" />
            ) : rows.length === 0 ? (
              <EmptyState
                icon="i-pin"
                title={
                  (city?.place_count ?? 0) < 5
                    ? 'This city is mostly unmapped'
                    : 'Nothing here yet'
                }
                body={
                  (city?.place_count ?? 0) < 5
                    ? 'Be its first pathfinder.'
                    : 'Try another sort, or clear the filters.'
                }
                action={
                  <Link className="btn btn-primary btn-sm" to="/add/place">
                    Add a place
                  </Link>
                }
              />
            ) : (
              <>
                <ol className="rows" style={{ flex: 'none' }}>
                  {rows.map((place) => (
                    <PlaceRow key={place.id} place={place} />
                  ))}
                </ol>
                {total > places.length + (page - 1) * 20 && (
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
                  Map data &copy; OpenStreetMap contributors &middot; famous places from Wikidata
                  (CC0)
                </p>
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
