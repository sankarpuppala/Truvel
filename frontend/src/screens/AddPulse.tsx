/** "How is it right now?" -- the Pulse form (SPEC §8.8).
 *
 * Only someone with a verified, unflagged, non-simulated visit in the last two
 * hours can post, because the whole value of a live report is that the person
 * was standing there. The server enforces that; this screen explains it when
 * it refuses.
 *
 * Every field is optional, and the water field only appears for water places.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Chip, Loading } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { PlaceThumb } from '../components/PlaceRow';
import { PULSE_OPTIONS, WATER_CATEGORIES } from '../lib/categories';
import { distance } from '../lib/format';
import type { Place } from '../lib/types';

export function AddPulse() {
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const [params] = useSearchParams();
  const { me, loadingMe, position, requestPosition, toast } = useApp();

  const initialId = id ? Number(id) : params.get('place') ? Number(params.get('place')) : null;
  const [placeId, setPlaceId] = useState<number | null>(initialId);
  const [place, setPlace] = useState<Place | null>(null);
  const [nearby, setNearby] = useState<Place[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState<Record<string, string | null>>({
    water: null,
    crowd: null,
    path: null,
    open: null,
  });
  const [note, setNote] = useState('');

  useEffect(() => {
    if (!loadingMe && !me) navigate('/signin');
  }, [loadingMe, me, navigate]);

  useEffect(() => {
    void requestPosition();
  }, [requestPosition]);

  useEffect(() => {
    setLoading(true);
    if (placeId) {
      void api
        .place(placeId, position)
        .then(setPlace)
        .catch(() => setPlace(null))
        .finally(() => setLoading(false));
    } else {
      void api
        .cityPlaces(me?.home_city?.slug ?? 'hyderabad', { sort: 'near', at: position })
        .then((response) => setNearby(response.places))
        .catch(() => setNearby([]))
        .finally(() => setLoading(false));
    }
  }, [placeId, me?.home_city?.slug, position?.lat, position?.lng]);

  async function post() {
    if (!place) return;
    const anything = Object.values(fields).some(Boolean) || note.trim();
    if (!anything) {
      toast('Tell us at least one thing.', 'bad');
      return;
    }
    setBusy(true);
    try {
      const result = await api.postPulse(place.id, {
        water: fields.water,
        crowd: fields.crowd,
        path: fields.path,
        open: fields.open,
        note: note.trim(),
      });
      if (result.kadam) toast(`+${result.kadam} kadam`, 'kadam');
      else toast('Posted. Thank you.');
      navigate(`/place/${place.id}`);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not post.', 'bad');
    } finally {
      setBusy(false);
    }
  }

  const showWater = place ? WATER_CATEGORIES.has(place.category) : false;

  return (
    <>
      <StatusBar />
      <div className="add-head">
        <button className="round round-flat" aria-label="Close" onClick={() => navigate(-1)}>
          <Icon name="i-x" size={22} />
        </button>
        <div>
          <div className="add-title">How is it right now?</div>
          <div className="add-sub">For people arriving in the next few hours</div>
        </div>
      </div>

      <div className="scr-body">
        <div className="form-page">
          {loading ? (
            <Loading />
          ) : !place ? (
            <>
              <p className="sub">
                Which place are you at? You need a check-in here in the last 2 hours.
              </p>
              {nearby.slice(0, 15).map((entry) => (
                <button
                  key={entry.id}
                  type="button"
                  className="cand"
                  style={{ marginBottom: 6 }}
                  onClick={() => setPlaceId(entry.id)}
                >
                  <PlaceThumb place={entry} className="thumb thumb-sm" />
                  <div>
                    <b>{entry.name.primary.text}</b>
                    <span>
                      {entry.area} &middot; {distance(entry.distance_km)}
                    </span>
                  </div>
                  <Icon name="i-chevr" size={18} />
                </button>
              ))}
            </>
          ) : (
            <>
              <div className="cand on" style={{ marginBottom: 14 }}>
                <PlaceThumb place={place} className="thumb thumb-sm" />
                <div>
                  <b>{place.name.primary.text}</b>
                  <span>{place.area}</span>
                </div>
                <button type="button" className="link" onClick={() => setPlaceId(null)}>
                  Change
                </button>
              </div>

              {showWater && (
                <div className="field">
                  <span>Water</span>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {PULSE_OPTIONS.water.map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        icon={option.icon}
                        on={fields.water === option.value}
                        onClick={() =>
                          setFields((value) => ({
                            ...value,
                            water: value.water === option.value ? null : option.value,
                          }))
                        }
                      />
                    ))}
                  </div>
                </div>
              )}

              {(['crowd', 'path', 'open'] as const).map((field) => (
                <div className="field" key={field}>
                  <span>
                    {field === 'crowd' ? 'How busy' : field === 'path' ? 'The path' : 'Open?'}
                  </span>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {PULSE_OPTIONS[field].map((option) => (
                      <Chip
                        key={option.value}
                        label={option.label}
                        icon={option.icon}
                        on={fields[field] === option.value}
                        onClick={() =>
                          setFields((value) => ({
                            ...value,
                            [field]: value[field] === option.value ? null : option.value,
                          }))
                        }
                      />
                    ))}
                  </div>
                </div>
              ))}

              <label className="field">
                <span>Anything else? (80 characters)</span>
                <input
                  value={note}
                  maxLength={80}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Breezy on top, carry water."
                />
              </label>

              <button
                type="button"
                className="btn btn-primary btn-wide"
                onClick={() => void post()}
                disabled={busy}
              >
                {busy ? 'Posting…' : 'Post this report'}
              </button>
              <p className="sub" style={{ marginTop: 10 }}>
                Reports show as <b>Live</b> for 6 hours, <b>Recent</b> for 48, then they go.
              </p>
            </>
          )}
        </div>
      </div>
    </>
  );
}
