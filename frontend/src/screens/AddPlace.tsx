/** Add a new place: three steps on a dashed path. Reference screen 6 (SPEC §8.6).
 *
 * 1. Photos & videos -- each needs a caption, which is also its alt text.
 * 2. Pin & verify -- within 300 m at <= 100 m accuracy is an on-site add;
 *    anything else stays Unverified until two people check in. The duplicate
 *    check (SPEC §9.6) runs as the pin moves.
 * 3. Details -- including every safety question, answered yes / no / don't know.
 *
 * Photos are resized to <= 2048 px here, and their EXIF GPS is read *before*
 * the resize (which destroys it) so the server can cross-check it against the
 * pin (SPEC §9.7). The server re-encodes everything it stores, so nothing with
 * EXIF is ever saved (invariant 2).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { BottomSheet, Chip } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { PlaceThumb } from '../components/PlaceRow';
import { SAFETY_FLAGS } from '../lib/categories';
import { distance } from '../lib/format';
import { getPosition, LocationError, type Position } from '../lib/geo';
import { readExifGps, resizePhoto, videoPoster } from '../lib/media';
import type { MediaItem, Place } from '../lib/types';

const CATEGORIES = [
  { key: 'viewpoint', label: 'Viewpoint' },
  { key: 'waterfall', label: 'Waterfall' },
  { key: 'lake', label: 'Lake' },
  { key: 'hill_trek', label: 'Hill or trek' },
  { key: 'fort_heritage', label: 'Fort or heritage' },
  { key: 'temple_sacred', label: 'Temple or sacred' },
  { key: 'park_garden', label: 'Park or garden' },
  { key: 'museum_art', label: 'Museum or art' },
  { key: 'market_street', label: 'Market or street' },
  { key: 'beach_river', label: 'Water, beach or ghat' },
  { key: 'other', label: 'Something else' },
];

type Draft = {
  name: string;
  category: string;
  description: string;
  activities: string;
  best_time: { time: string; months: string; avoid: string };
  entry_fee_text: string;
  timings_text: string;
  access: { road: string; walk_min_from_road: string; nearest_transit_text: string };
  accessibility: Record<string, string>;
  safety: Record<string, string>;
  fragile: boolean;
  steps: string[];
};

const EMPTY: Draft = {
  name: '',
  category: 'viewpoint',
  description: '',
  activities: '',
  best_time: { time: '', months: '', avoid: '' },
  entry_fee_text: '',
  timings_text: '',
  access: { road: '', walk_min_from_road: '', nearest_transit_text: '' },
  accessibility: {
    wheelchair: 'unknown',
    steps_count_text: '',
    toilets: 'unknown',
    drinking_water: 'unknown',
    shade: 'unknown',
    food_nearby: 'unknown',
  },
  safety: Object.fromEntries(SAFETY_FLAGS.map((flag) => [flag.key, 'unknown'])),
  fragile: false,
  steps: [''],
};

const RULES_KEY = 'pagdandi.contentRulesSeen';

export function AddPlace() {
  const navigate = useNavigate();
  const { me, loadingMe, toast, config } = useApp();
  const [step, setStep] = useState(1);
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null);
  const [reading, setReading] = useState<Position | null>(null);
  const [candidates, setCandidates] = useState<Place[]>([]);
  const [chosenCandidate, setChosenCandidate] = useState<number | null>(null);
  const [dupeOpen, setDupeOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(() => !localStorage.getItem(RULES_KEY));
  const [saving, setSaving] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);

  const maxPhotos = config?.media.max_photos ?? 10;
  const maxVideos = config?.media.max_videos ?? 2;
  const maxAccuracy = config?.verification.max_accuracy_m ?? 100;
  const maxDrag = config?.verification.add_pin_max_drag_m ?? 300;

  useEffect(() => {
    // Only redirect once the session check has finished (see Settings.tsx).
    if (!loadingMe && !me) navigate('/signin');
  }, [loadingMe, me, navigate]);

  // Step 2 opens by reading the position once, which becomes the pin's start.
  useEffect(() => {
    if (step !== 2 || reading) return;
    void (async () => {
      try {
        const position = await getPosition();
        setReading(position);
        setPin({ lat: position.lat, lng: position.lng });
      } catch (error) {
        toast(
          error instanceof LocationError
            ? `${error.message} You can still add the place; it stays unverified.`
            : 'Could not find you.',
          'bad',
        );
      }
    })();
  }, [step, reading, toast]);

  // The duplicate check runs whenever the pin or the name changes (SPEC §9.6).
  const checkDuplicates = useCallback(
    async (lat: number, lng: number, name: string, category: string) => {
      try {
        const response = await api.candidates(lat, lng, name, category);
        setCandidates(response.candidates);
        if (response.candidates.length > 0) setDupeOpen(true);
      } catch {
        setCandidates([]);
      }
    },
    [],
  );

  useEffect(() => {
    if (step !== 2 || !pin) return undefined;
    const timer = window.setTimeout(() => {
      void checkDuplicates(pin.lat, pin.lng, draft.name, draft.category);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [step, pin, draft.name, draft.category, checkDuplicates]);

  async function addFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const isVideo = file.type.startsWith('video/');
        const photos = media.filter((item) => item.kind === 'photo').length;
        const videos = media.filter((item) => item.kind === 'video').length;
        if (isVideo && videos >= maxVideos) {
          toast(`Up to ${maxVideos} videos.`, 'bad');
          continue;
        }
        if (!isVideo && photos >= maxPhotos) {
          toast(`Up to ${maxPhotos} photos.`, 'bad');
          continue;
        }

        const form = new FormData();
        if (isVideo) {
          const poster = await videoPoster(file);
          form.set('file', file);
          form.set('poster', poster.blob, 'poster.jpg');
          form.set('kind', 'video');
          form.set('duration_s', String(poster.duration));
        } else {
          // Read EXIF GPS before resizing, which strips it (SPEC §9.7).
          const gps = await readExifGps(file);
          const resized = await resizePhoto(file);
          form.set('file', resized, 'photo.jpg');
          form.set('kind', 'photo');
          if (gps) {
            form.set('exif_lat', String(gps.lat));
            form.set('exif_lng', String(gps.lng));
          }
        }
        form.set(
          'caption',
          `Photo of ${draft.name || 'this place'} by @${me?.username ?? 'me'}`,
        );
        form.set('lang', 'en');
        form.set('on_site', String(Boolean(reading && reading.accuracy <= maxAccuracy)));

        // place_id 0: the place does not exist yet; POST /places attaches these.
        const result = await api.uploadMedia(0, form);
        if (result.media) setMedia((items) => [...items, result.media!]);
        else if (result.skipped) toast(result.message ?? 'Already added.', 'bad');
        if (result.warning === 'gps_mismatch') {
          toast("That photo's own location is far from your pin. Flagged for review.", 'bad');
        }
      }
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That upload failed.', 'bad');
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  async function submit() {
    if (!pin) {
      toast('Drop a pin first.', 'bad');
      return;
    }
    if (draft.name.trim().length < 2) {
      toast('Give the place a name.', 'bad');
      return;
    }
    setSaving(true);
    try {
      const response = await api.createPlace({
        lat: pin.lat,
        lng: pin.lng,
        accuracy_m: reading?.accuracy ?? null,
        name: draft.name.trim(),
        category: draft.category,
        description: draft.description.trim(),
        activities: draft.activities
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
        best_time: Object.fromEntries(
          Object.entries(draft.best_time).filter(([, value]) => value.trim()),
        ),
        entry_fee_text: draft.entry_fee_text.trim(),
        timings_text: draft.timings_text.trim(),
        access: {
          road: draft.access.road.trim(),
          walk_min_from_road: draft.access.walk_min_from_road
            ? Number(draft.access.walk_min_from_road)
            : null,
          nearest_transit_text: draft.access.nearest_transit_text.trim(),
        },
        accessibility: draft.accessibility,
        safety: draft.safety,
        fragile: draft.fragile,
        media_ids: media.map((item) => item.id),
      });

      const steps = draft.steps.map((text) => text.trim()).filter(Boolean);
      if (steps.length) {
        await api.addSteps(response.place.id, steps.map((text) => ({ text })));
      }

      toast(response.message || 'Added. Thank you.', 'kadam');
      navigate(`/place/${response.place.id}`);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not save.', 'bad');
    } finally {
      setSaving(false);
    }
  }

  const onSite = Boolean(reading && reading.accuracy <= maxAccuracy);
  const dragDistance =
    pin && reading
      ? Math.round(
          Math.hypot(
            (pin.lat - reading.lat) * 111_320,
            (pin.lng - reading.lng) * 111_320 * Math.cos((pin.lat * Math.PI) / 180),
          ),
        )
      : 0;

  return (
    <>
      <StatusBar />

      <div className="add-head">
        <button
          className="round round-flat"
          aria-label="Close"
          onClick={() => (step === 1 ? navigate(-1) : setStep((value) => value - 1))}
        >
          <Icon name={step === 1 ? 'i-x' : 'i-back'} size={22} />
        </button>
        <div>
          <div className="add-title">Add a place</div>
          <div className="add-sub">
            Step {step} of 3 &middot;{' '}
            {step === 1 ? 'Photos & videos' : step === 2 ? 'Pin & verify' : 'Details'}
          </div>
        </div>
      </div>

      {/* The dashed progress path (SPEC §12.1, §12.5 DashedProgress). */}
      <div className="dprog" aria-label={`Step ${step} of 3`}>
        <svg viewBox="0 0 300 24" aria-hidden="true">
          <path d="M12 12H288" className="dp-track" />
          <path d={`M12 12H${12 + ((step - 1) / 2) * 276}`} className="dp-done" />
        </svg>
        {[1, 2, 3].map((number) => (
          <span
            key={number}
            className={`dp-dot ${number < step ? 'done' : ''} ${number === step ? 'cur' : ''}`.trim()}
            style={{ left: `${number === 1 ? 4 : number === 2 ? 50 : 96}%` }}
          >
            {number < step && <Icon name="i-check" size={12} />}
          </span>
        ))}
        <span className="dp-lab" style={{ left: '4%' }}>
          Photos
        </span>
        <span className="dp-lab" style={{ left: '50%' }}>
          Pin
        </span>
        <span className="dp-lab" style={{ left: '96%' }}>
          Details
        </span>
      </div>

      <div className="scr-body">
        {step === 1 && (
          <div className="form-page">
            <p className="sub">
              One to {maxPhotos} photos, up to {maxVideos} videos. Every one needs a caption,
              which doubles as its alt text.
            </p>

            <div className="media-strip" style={{ flexWrap: 'wrap', padding: '0 0 10px' }}>
              {media.map((item) => (
                <span className={`ms ${item.kind === 'video' ? 'ms-vid' : ''}`} key={item.id}>
                  <img className="ms-in" src={item.thumb ?? item.poster ?? item.url} alt={item.caption} />
                  {item.kind === 'video' && (
                    <i>
                      <Icon name="i-video" size={14} />
                    </i>
                  )}
                </span>
              ))}
              <span className="ms-count">
                {media.filter((item) => item.kind === 'photo').length} photos &middot;{' '}
                {media.filter((item) => item.kind === 'video').length} video
              </span>
            </div>

            <input
              ref={fileInput}
              type="file"
              accept="image/*,video/*"
              multiple
              onChange={(event) => void addFiles(event.target.files)}
              style={{ marginBottom: 12 }}
              aria-label="Choose photos or videos"
            />
            {uploading && <p className="sub">Uploading&hellip;</p>}

            <button
              type="button"
              className="btn btn-primary btn-wide"
              onClick={() => setStep(2)}
              disabled={media.length === 0}
            >
              Next: pin &amp; verify
            </button>
            {media.length === 0 && (
              <p className="sub" style={{ marginTop: 8 }}>
                Add at least one photo so people know what they are looking for.
              </p>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="form-page">
            {/* A real map is heavy here; the pin is adjusted numerically and
                against the duplicate list, which is what the check needs. */}
            <div className="addmap" style={{ borderRadius: 18, background: 'var(--sunk)' }}>
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'grid',
                  placeItems: 'center',
                  color: 'var(--muted)',
                  fontSize: 14,
                  textAlign: 'center',
                  padding: 16,
                }}
              >
                {pin ? (
                  <span>
                    Pin at {pin.lat.toFixed(5)}, {pin.lng.toFixed(5)}
                    <br />
                    {dragDistance > 0 && `${dragDistance} m from where you are`}
                  </span>
                ) : (
                  <span>Finding you&hellip;</span>
                )}
              </div>
              <span className="newpin" style={{ left: '50%', top: '52%' }}>
                <Icon name="i-pin" size={34} />
              </span>
              {onSite && (
                <div className="here">
                  <Icon name="i-check" size={16} />
                  You&apos;re here &middot; on-site add &middot; &plusmn;
                  {Math.round(reading?.accuracy ?? 0)} m
                </div>
              )}
            </div>

            {!onSite && (
              <div className="golden" role="note" style={{ margin: '12px 0' }}>
                <Icon name="i-info" size={18} />
                <span>
                  <b>Adding from elsewhere.</b> This place stays Unverified until 2 people
                  check in there.
                </span>
              </div>
            )}

            {dragDistance > maxDrag && (
              <div className="golden" role="note" style={{ margin: '0 0 12px', borderColor: 'var(--danger)' }}>
                <Icon name="i-warn" size={18} />
                <span>
                  The pin is {dragDistance} m from you, further than the {maxDrag} m an
                  on-site add allows.
                </span>
              </div>
            )}

            <label className="field">
              <span>What is it called?</span>
              <input
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                placeholder="The name locals use"
              />
            </label>

            <label className="field">
              <span>Nudge the pin (latitude, longitude)</span>
              <input
                value={pin ? `${pin.lat.toFixed(5)}, ${pin.lng.toFixed(5)}` : ''}
                onChange={(event) => {
                  const [lat, lng] = event.target.value.split(',').map((part) => Number(part.trim()));
                  if (Number.isFinite(lat) && Number.isFinite(lng)) setPin({ lat, lng });
                }}
              />
            </label>

            {candidates.length > 0 && (
              <button
                type="button"
                className="btn btn-ghost btn-wide"
                onClick={() => setDupeOpen(true)}
                style={{ marginBottom: 12 }}
              >
                <Icon name="i-info" size={18} />
                {candidates.length} nearby {candidates.length === 1 ? 'place looks' : 'places look'}{' '}
                similar
              </button>
            )}

            <button
              type="button"
              className="btn btn-primary btn-wide"
              onClick={() => setStep(3)}
              disabled={!pin || draft.name.trim().length < 2}
            >
              Next: details
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="form-page">
            <label className="field">
              <span>Category</span>
              <select
                value={draft.category}
                onChange={(event) => setDraft({ ...draft, category: event.target.value })}
              >
                {CATEGORIES.map((category) => (
                  <option key={category.key} value={category.key}>
                    {category.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>What is it like? (up to 600 characters)</span>
              <textarea
                value={draft.description}
                maxLength={600}
                onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                placeholder="What you see, and what it is actually like to be there."
              />
            </label>

            <label className="field">
              <span>What to do there (commas between)</span>
              <input
                value={draft.activities}
                onChange={(event) => setDraft({ ...draft, activities: event.target.value })}
                placeholder="Sunset, Photography, Short climb"
              />
            </label>

            <label className="field">
              <span>Best time of day</span>
              <input
                value={draft.best_time.time}
                onChange={(event) =>
                  setDraft({ ...draft, best_time: { ...draft.best_time, time: event.target.value } })
                }
                placeholder="Evening, 5:00-6:30 pm"
              />
            </label>
            <label className="field">
              <span>Best months</span>
              <input
                value={draft.best_time.months}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    best_time: { ...draft.best_time, months: event.target.value },
                  })
                }
                placeholder="Oct-Feb best"
              />
            </label>

            <label className="field">
              <span>Getting there by road</span>
              <input
                value={draft.access.road}
                onChange={(event) =>
                  setDraft({ ...draft, access: { ...draft.access, road: event.target.value } })
                }
                placeholder="Bike or car to the end of the lane"
              />
            </label>
            <label className="field">
              <span>Minutes of walking from the road</span>
              <input
                inputMode="numeric"
                value={draft.access.walk_min_from_road}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    access: { ...draft.access, walk_min_from_road: event.target.value },
                  })
                }
              />
            </label>

            <label className="field">
              <span>Fees</span>
              <input
                value={draft.entry_fee_text}
                onChange={(event) => setDraft({ ...draft, entry_fee_text: event.target.value })}
                placeholder="Free, or the ticket price"
              />
            </label>
            <label className="field">
              <span>Timings</span>
              <input
                value={draft.timings_text}
                onChange={(event) => setDraft({ ...draft, timings_text: event.target.value })}
                placeholder="9:00 am - 5:30 pm"
              />
            </label>

            {/* Every safety question, answered yes / no / don't know (SPEC §8.14). */}
            <h4
              style={{
                font: '700 13px/1.3 Mukta,sans-serif',
                letterSpacing: '.1em',
                textTransform: 'uppercase',
                color: 'var(--muted)',
                margin: '14px 0 8px',
              }}
            >
              Safety
            </h4>
            {SAFETY_FLAGS.map((flag) => (
              <div className="field" key={flag.key}>
                <span>{flag.yes.split('.')[0]}?</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[
                    ['yes', 'Yes'],
                    ['no', 'No'],
                    ['unknown', "Don't know"],
                  ].map(([value, label]) => (
                    <Chip
                      key={value}
                      label={label}
                      on={draft.safety[flag.key] === value}
                      onClick={() =>
                        setDraft({ ...draft, safety: { ...draft.safety, [flag.key]: value } })
                      }
                    />
                  ))}
                </div>
              </div>
            ))}

            <label className="field">
              <span>Wheelchair access</span>
              <select
                value={draft.accessibility.wheelchair}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    accessibility: { ...draft.accessibility, wheelchair: event.target.value },
                  })
                }
              >
                <option value="unknown">Don&apos;t know</option>
                <option value="yes">Yes</option>
                <option value="partly">Partly</option>
                <option value="no">No</option>
              </select>
            </label>

            <h4
              style={{
                font: '700 13px/1.3 Mukta,sans-serif',
                letterSpacing: '.1em',
                textTransform: 'uppercase',
                color: 'var(--muted)',
                margin: '14px 0 8px',
              }}
            >
              Last mile (optional)
            </h4>
            {draft.steps.map((text, index) => (
              <label className="field" key={index}>
                <span>Step {index + 1}</span>
                <input
                  value={text}
                  maxLength={140}
                  onChange={(event) => {
                    const steps = [...draft.steps];
                    steps[index] = event.target.value;
                    setDraft({ ...draft, steps });
                  }}
                  placeholder="Turn where the paved lane ends"
                />
              </label>
            ))}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ marginBottom: 14, alignSelf: 'flex-start' }}
              onClick={() => setDraft({ ...draft, steps: [...draft.steps, ''] })}
            >
              <Icon name="i-plus" size={16} />
              Another step
            </button>

            <label className="opt" style={{ borderRadius: 14, border: '1.5px solid var(--line)' }}>
              <input
                type="checkbox"
                checked={draft.fragile}
                onChange={(event) => setDraft({ ...draft, fragile: event.target.checked })}
              />
              <div>
                <b>This place is fragile</b>
                <span className="prev">
                  Its exact pin and directions stay hidden until someone saves it and agrees to
                  treat it carefully.
                </span>
              </div>
            </label>

            <button
              type="button"
              className="btn btn-primary btn-wide"
              style={{ marginTop: 16 }}
              onClick={() => void submit()}
              disabled={saving}
            >
              {saving ? 'Adding…' : 'Add this place'}
            </button>
          </div>
        )}
      </div>

      {/* "Is it one of these?" -- the duplicate check (SPEC §9.6). */}
      <BottomSheet
        open={dupeOpen}
        onClose={() => setDupeOpen(false)}
        className="sheet-dup"
      >
        <h4 id="dupt">Is it one of these?</h4>
        <p className="sub">Near your pin, with similar names:</p>
        {candidates.map((candidate) => (
          <label
            className={`cand ${chosenCandidate === candidate.id ? 'on' : ''}`.trim()}
            key={candidate.id}
          >
            <PlaceThumb place={candidate} className="thumb thumb-sm" />
            <div>
              <b>{candidate.name.primary.text}</b>
              <span>
                {distance((candidate as Place & { distance_m?: number }).distance_m
                  ? ((candidate as Place & { distance_m?: number }).distance_m ?? 0) / 1000
                  : candidate.distance_km)}{' '}
                away &middot; {(candidate as Place & { reason?: string }).reason ?? 'nearby'}
              </span>
            </div>
            <input
              type="radio"
              name="dupe"
              className="sr-only"
              checked={chosenCandidate === candidate.id}
              onChange={() => setChosenCandidate(candidate.id)}
            />
            <span className={`radio ${chosenCandidate === candidate.id ? 'on' : ''}`.trim()} />
          </label>
        ))}
        <button
          type="button"
          className="btn btn-primary btn-wide"
          disabled={chosenCandidate === null}
          onClick={() => {
            setDupeOpen(false);
            navigate(`/add/media?place=${chosenCandidate}`);
          }}
        >
          Yes, add my photos there
        </button>
        <button
          type="button"
          className="btn btn-text btn-wide"
          onClick={() => {
            setDupeOpen(false);
            setChosenCandidate(null);
          }}
        >
          No, it&apos;s a different place
        </button>
      </BottomSheet>

      {/* The content rules, shown before the first add (SPEC §8.6). */}
      <BottomSheet
        open={rulesOpen}
        onClose={() => {
          localStorage.setItem(RULES_KEY, '1');
          setRulesOpen(false);
        }}
        title="Before you add a place"
      >
        <ul style={{ margin: '0 0 14px', paddingLeft: 18, lineHeight: 1.6, fontSize: 15 }}>
          <li>No private property, and no trespassing to get a photo.</li>
          <li>No homes, and no one&apos;s gate or front door.</li>
          <li>Strangers&apos; faces should not be the subject of the photo.</li>
          <li>No stunts at edges. Nothing here rewards a dangerous photo.</li>
        </ul>
        <button
          type="button"
          className="btn btn-primary btn-wide"
          onClick={() => {
            localStorage.setItem(RULES_KEY, '1');
            setRulesOpen(false);
          }}
        >
          Understood
        </button>
      </BottomSheet>
    </>
  );
}
