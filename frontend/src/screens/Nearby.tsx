/** Nearby -- the deck. Reference screen 1 (SPEC §8.2, ranking §9.4).
 *
 * One card at a time with the next peeking below. The deck **ends**: after the
 * last candidate there is an end card offering a wider radius or a saved place,
 * and no infinite feed (SPEC §19 D12).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { DeckActions, DeckCard, DeckCardBack, type SwipeAction } from '../components/DeckCard';
import { EmptyState, Loading } from '../components/common';
import { DevTools } from '../components/DevTools';
import { Icon, StatusBar } from '../components/Icon';
import { LocationPicker } from '../components/LocationPicker';
import { num } from '../lib/format';
import type { DeckResponse, Place } from '../lib/types';

const RADII = [5, 10, 25, 50];

export function Nearby() {
  const { me, position, activeCityName, requestPosition, toast, config } = useApp();
  const navigate = useNavigate();
  const [radius, setRadius] = useState(10);
  const [deck, setDeck] = useState<DeckResponse | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [requestNo, setRequestNo] = useState(0);
  const [hereName, setHereName] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  const radii = config?.deck.radii_km ?? RADII;

  useEffect(() => {
    void requestPosition(true);
  }, [requestPosition]);

  // The header should say where someone actually *is* ("Tirupati"), not
  // their saved home city ("Hyderabad") -- that is a different thing, and
  // only the fallback for when location is off (see `homeCity` below).
  useEffect(() => {
    if (!position) {
      setHereName(null);
      return undefined;
    }
    let cancelled = false;
    void api
      .here(position.lat, position.lng)
      .then((result) => {
        if (!cancelled) setHereName(result.name);
      })
      .catch(() => {
        if (!cancelled) setHereName(null);
      });
    return () => {
      cancelled = true;
    };
  }, [position?.lat, position?.lng]);

  const load = useCallback(
    async (km: number, bump = false, resetTo?: number) => {
      setLoading(true);
      try {
        // `resetTo` wins over `bump`: a new radius starts back at page 0,
        // whatever page the previous radius had reached.
        const next = resetTo ?? (bump ? requestNo + 1 : requestNo);
        if (next !== requestNo) setRequestNo(next);
        const response = await api.deck(position, km, next);
        setDeck(response);
        setIndex(0);
      } catch (error) {
        toast(error instanceof ApiError ? error.message : 'Could not load the deck.', 'bad');
      } finally {
        setLoading(false);
      }
    },
    [position, requestNo, toast],
  );

  useEffect(() => {
    // A new radius is a new candidate pool, so it starts back at page 0 --
    // never mid-way through wherever the previous radius had been paged to.
    void load(radius, false, 0);
    // `load` changes with position; re-running on radius and position is what
    // we want, and `requestNo` only changes when the user asks for more.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radius, position?.lat, position?.lng]);

  const cards = deck?.cards ?? [];
  const current: Place | undefined = cards[index];
  const next: Place | undefined = cards[index + 1];

  // Preload the next two cards' photos, so a swipe never shows a blank
  // (SPEC §15).
  useEffect(() => {
    for (const place of cards.slice(index + 1, index + 3)) {
      const url = place.lead_media?.url;
      if (url) {
        const image = new Image();
        image.src = url;
      }
    }
  }, [cards, index]);

  const handle = useCallback(
    async (action: SwipeAction) => {
      if (!current) return;
      const place = current;

      if (action === 'open') {
        // Opening a place page is a touch: it may later be credited with
        // causing a visit (SPEC §9.9). The server decides the creator.
        if (me) void api.touch(place.id, 'place').catch(() => undefined);
        navigate(`/place/${place.id}`);
        return;
      }

      setIndex((value) => value + 1);

      if (!me) {
        toast('Sign in to save places.', 'bad');
        return;
      }
      try {
        await api.swipe(place.id, action);
        if (action === 'save') toast(`Saved · ${place.name.primary.text}`, 'kadam');
      } catch (error) {
        toast(error instanceof ApiError ? error.message : 'That did not save.', 'bad');
      }
    },
    [current, me, navigate, toast],
  );

  // Arrow keys drive the deck, so it works without a pointer (SPEC §13).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === 'ArrowRight') void handle('save');
      else if (event.key === 'ArrowLeft') void handle('skip');
      else if (event.key === 'ArrowUp' || event.key === 'Enter') void handle('open');
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [handle]);

  // Signed out, or an account with no home city yet: the header still needs a
  // word, but the sentence below it must not read "the centre of Nearby".
  const homeCity = me?.home_city?.name ?? null;
  const cityName = hereName ?? activeCityName ?? homeCity ?? 'Nearby';
  const kadam = me?.kadam ?? 0;

  const header = useMemo(
    () => (
      <div className="topbar">
        <button
          className="city"
          type="button"
          onClick={() => setPickerOpen(true)}
          aria-label={`Location: ${cityName}. Tap to change.`}
        >
          {cityName} <Icon name="i-chev" size={18} />
        </button>
        <div className="tb-r">
          <button
            type="button"
            className="chip-sm"
            onClick={() => {
              const position_ = radii.indexOf(radius);
              setRadius(radii[(position_ + 1) % radii.length]);
            }}
            // WCAG 2.5.3: the visible text ("10 km") has to be inside the
            // accessible name, so speech control can act on what is on screen.
            aria-label={`${radius} km search radius. Tap to widen.`}
          >
            {radius} km <Icon name="i-chev" size={14} />
          </button>
          {me && (
            <span className="kadam" title="Kadam">
              <Icon name="i-feet" size={16} />
              {num(kadam)}
            </span>
          )}
        </div>
      </div>
    ),
    [cityName, kadam, me, radii, radius],
  );

  return (
    <>
      <StatusBar />
      {header}

      {deck?.location_fallback && (
        <div
          className="golden"
          role="note"
          style={{ cursor: 'pointer' }}
          onClick={() => setPickerOpen(true)}
        >
          <Icon name="i-info" size={18} />
          <span>
            {`Showing places near ${cityName} — tap here to change or detect your location.`}
          </span>
        </div>
      )}

      <LocationPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelectCity={(city) => {
          if (city.name) setHereName(city.name);
          void load(radius, false, 0);
        }}
      />

      <div className="scr-body">
        {loading && !cards.length ? (
          <Loading what="Finding places near you" />
        ) : current ? (
          <>
            <div className="deck">
              {next && <DeckCardBack place={next} />}
              <DeckCard key={current.id} place={current} onAction={handle} />
            </div>
            <DeckActions onAction={handle} />
            <p
              style={{
                textAlign: 'center',
                color: 'var(--muted)',
                fontSize: 13,
                margin: '10px 0 0',
              }}
            >
              {cards.length - index} of {deck?.total_candidates ?? cards.length} within{' '}
              {radius} km
            </p>
          </>
        ) : (
          /* The end card. No infinite feed (SPEC §8.2). */
          <EmptyState
            icon="i-compass"
            title={
              deck?.more_at_this_radius
                ? 'More within this radius'
                : deck && deck.total_candidates > 0
                  ? "That's everything nearby"
                  : 'Nothing in range yet'
            }
            body={
              deck?.end_card.message ??
              'Widen the radius, or be the first to add a place here.'
            }
            action={
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                {deck?.more_at_this_radius ? (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => void load(radius, true)}
                  >
                    Keep swiping
                  </button>
                ) : (
                  radius < radii[radii.length - 1] && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => setRadius(radii[radii.indexOf(radius) + 1] ?? 25)}
                    >
                      Widen to {radii[radii.indexOf(radius) + 1] ?? 25} km
                    </button>
                  )
                )}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => navigate('/you')}
                >
                  See what you saved
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => navigate('/add/place')}
                >
                  Add a place here
                </button>
              </div>
            }
          />
        )}
      </div>

      {/* The location simulator is development scaffolding and lives only
          here, where the deck it changes is. It is absent from production. */}
      <DevTools />
    </>
  );
}
