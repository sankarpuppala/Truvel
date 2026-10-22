/** The Place page. Reference screen 5 (SPEC §8.5).
 *
 * All fifteen sections, in the order the SPEC lists them, with the pinned
 * check-in bar at the bottom. Two details matter more than they look:
 *
 *  - **Open in Maps is a plain link** to Google's free directions URL. We use
 *    no Places API, no routing API, and no Google data (SPEC §6.6, §19 D5).
 *  - **A fragile place hides its pin** until the user saves it and pledges.
 *    The server enforces that; this screen just reflects it, and must never
 *    assume it has coordinates (SPEC §8.14, invariant 5).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import {
  AccessibilityRows,
  PulseStrip,
  SafetyCard,
  StepList,
  WhenToGo,
} from '../components/PlaceParts';
import { BottomSheet, Chip, Loading } from '../components/common';
import { Icon, Scene } from '../components/Icon';
import { NameBlock } from '../components/NameBlock';
import { PlaceThumb } from '../components/PlaceRow';
import { categoryIcon, categoryLabel, categoryScene, REPORT_REASONS } from '../lib/categories';
import { clock, date, distance, num } from '../lib/format';
import { getPosition, haptic, LocationError } from '../lib/geo';
import type { CheckinResult, Place, StepVersion } from '../lib/types';
import { CheckinSheet } from './CheckinSheet';

export function PlacePage() {
  const { id } = useParams<{ id: string }>();
  const placeId = Number(id);
  const navigate = useNavigate();
  const { me, position, devTools, simulated, toast } = useApp();

  const [place, setPlace] = useState<Place | null>(null);
  const [steps, setSteps] = useState<{ locked: boolean; versions: StepVersion[] }>({
    locked: false,
    versions: [],
  });
  const [loading, setLoading] = useState(true);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [reportOpen, setReportOpen] = useState(false);
  const [buddyOpen, setBuddyOpen] = useState(false);
  const [reportNote, setReportNote] = useState('');
  const [nameSheetOpen, setNameSheetOpen] = useState(false);
  const [checkinResult, setCheckinResult] = useState<CheckinResult | null>(null);
  const [checkingIn, setCheckingIn] = useState(false);
  const [newName, setNewName] = useState({ lang: 'te', name: '' });
  const [photoFailed, setPhotoFailed] = useState(false);
  const stepsReadAt = useRef<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.place(placeId, position);
      setPlace(data);
      const stepData = await api.steps(placeId);
      setSteps(stepData);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'Could not open that place.', 'bad');
      if (error instanceof ApiError && error.status === 404) navigate('/explore');
    } finally {
      setLoading(false);
    }
  }, [placeId, position, toast, navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  // Reading the last-mile steps for 10 seconds or more is a touch that can be
  // credited with causing a visit (SPEC §9.9, attribution.steps_min_read_s).
  useEffect(() => {
    if (!me || steps.locked || !steps.versions.length) return undefined;
    stepsReadAt.current = performance.now();
    return () => {
      if (stepsReadAt.current === null) return;
      const seconds = (performance.now() - stepsReadAt.current) / 1000;
      stepsReadAt.current = null;
      if (seconds >= 10) {
        void api.touch(placeId, 'steps').catch(() => undefined);
      }
    };
  }, [me, placeId, steps]);

  if (loading && !place) return <Loading what="Opening" />;
  if (!place) return null;

  const photos = place.media?.filter((item) => item.kind === 'photo') ?? [];
  const current = photos[Math.min(photoIndex, Math.max(0, photos.length - 1))];
  const withinRadius =
    place.distance_km !== undefined &&
    place.distance_km * 1000 <= Math.max(place.radius_m, 150);

  const canDelete =
    !!me && !!current && current.source === 'upload' && current.creator?.id === me.id;

  async function deleteCurrentPhoto() {
    if (!current) return;
    if (!window.confirm('Delete this photo? This cannot be undone.')) return;
    try {
      await api.deleteMedia(current.id);
      setPhotoFailed(false);
      setPhotoIndex(0);
      setPlace((previous) =>
        previous
          ? {
              ...previous,
              media: previous.media?.filter((item) => item.id !== current.id),
              photo_count: Math.max(0, previous.photo_count - 1),
            }
          : previous,
      );
      toast('Photo deleted');
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not delete.', 'bad');
    }
  }

  async function toggleLike() {
    if (!me) {
      toast('Sign in to like places.', 'bad');
      return;
    }
    try {
      const result = await api.like(place!.id, !place!.liked);
      haptic();
      setPlace((current_) =>
        current_ ? { ...current_, liked: result.liked, likes: result.likes } : current_,
      );
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  async function toggleSave() {
    if (!me) {
      toast('Sign in to save places.', 'bad');
      return;
    }
    try {
      const result = await api.save(place!.id, !place!.saved);
      haptic();
      setPlace((current_) => (current_ ? { ...current_, saved: result.saved } : current_));
      if (result.saved) toast('Saved to Want to go', 'kadam');
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not save.', 'bad');
    }
  }

  async function pledge() {
    try {
      await api.fragilePledge(place!.id);
      toast('Thank you. Treat it gently.');
      await load();
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  async function checkIn() {
    if (!me) {
      toast('Sign in to check in.', 'bad');
      return;
    }
    setCheckingIn(true);
    try {
      let reading: { lat: number; lng: number; accuracy: number };
      if (simulated && devTools) {
        // The dev simulator. Visits made this way are marked and excluded from
        // everything that matters (SPEC §8.7, AC-25).
        reading = { lat: simulated.lat, lng: simulated.lng, accuracy: simulated.accuracy };
      } else {
        reading = await getPosition();
      }
      const result = await api.checkin(
        place!.id,
        reading.lat,
        reading.lng,
        reading.accuracy,
        Boolean(simulated && devTools),
      );
      setCheckinResult(result);
      if (result.verified) {
        haptic(18);
        if (result.kadam) toast(`+${result.kadam} kadam`, 'kadam');
        await load();
      }
    } catch (error) {
      if (error instanceof LocationError) toast(error.message, 'bad');
      else toast(error instanceof ApiError ? error.message : 'Check-in failed.', 'bad');
    } finally {
      setCheckingIn(false);
    }
  }

  /** Hand text to the phone's share sheet, or copy it where there is none. */
  async function send(title: string, text: string, url: string) {
    try {
      if (navigator.share) await navigator.share({ title, text, url });
      else {
        await navigator.clipboard.writeText(`${text} ${url}`);
        toast('Copied. Send it to someone.');
      }
    } catch {
      /* cancelled */
    }
  }

  /** The share button: this place's Truvel page, for a friend to look at. */
  function sharePlace() {
    const name = place!.name.primary.text;
    const url = `${window.location.origin}/place/${place!.id}`;
    void send(name, `Have a look at ${name} on Truvel.`, url);
  }

  /** "Check on me": a message for one trusted person, with a time. It carries
   * no location, only the place's Truvel page and when to worry (invariant 1). */
  function askFriendToCheck(hours: number) {
    const name = place!.name.primary.text;
    const by = new Date(Date.now() + hours * 3600_000).toLocaleTimeString('en-IN', {
      hour: 'numeric',
      minute: '2-digit',
    });
    setBuddyOpen(false);
    void send(
      `Check on me: ${name}`,
      `I'm going to ${name}. If you haven't heard from me by ${by}, please call me, ` +
        `and call 112 if you can't reach me.`,
      `${window.location.origin}/place/${place!.id}`,
    );
  }

  async function voteSteps(group: string, helpful: boolean) {
    if (!me) {
      toast('Sign in to vote.', 'bad');
      return;
    }
    try {
      await api.voteSteps(group, helpful);
      toast(helpful ? 'Marked helpful' : 'Thanks, noted');
      setSteps(await api.steps(place!.id));
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  async function submitName() {
    if (!newName.name.trim()) return;
    try {
      const result = await api.addName(place!.id, newName.lang, newName.name.trim());
      toast(result.added ? 'Name added. Others can vote on it.' : 'Voted for that name.');
      setNameSheetOpen(false);
      setNewName({ lang: 'te', name: '' });
      await load();
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  async function sendReport(reason: string) {
    if (!me) {
      toast('Sign in to report a place.', 'bad');
      return;
    }
    try {
      const result = await api.report('place', place!.id, reason, reportNote.trim());
      setReportOpen(false);
      setReportNote('');
      toast(
        result.already
          ? 'You already reported that. Thank you.'
          : 'Thank you. A person will look at it, and it counts for more if you have been here.',
      );
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  return (
    <>
      {/* 1. Media carousel, with attribution on Commons photos. */}
      <div className="carousel">
        {current && !photoFailed ? (
          <img
            className="car-ph"
            src={current.url}
            alt={current.caption}
            style={{ objectFit: 'cover' }}
            onError={() => setPhotoFailed(true)}
          />
        ) : (
          <Scene
            name={categoryScene(place.category)}
            className="car-ph"
            viewBox="0 80 400 300"
            alt={`${categoryLabel(place.category)} illustration for ${place.name.primary.text}`}
          />
        )}
        <div className="sb" style={{ position: 'relative', zIndex: 2, color: '#fff' }}>
          <span />
        </div>
        <div className="car-top">
          <button className="round" aria-label="Back" onClick={() => navigate(-1)}>
            <Icon name="i-back" size={22} />
          </button>
          <span className="round-group">
            <button className="round" aria-label="Share" onClick={sharePlace}>
              <Icon name="i-share" size={20} />
            </button>
            {canDelete && (
              <button
                className="round"
                aria-label="Delete this photo"
                onClick={() => void deleteCurrentPhoto()}
              >
                <Icon name="i-trash" size={20} />
              </button>
            )}
            <button className="round" aria-label="Report" onClick={() => setReportOpen(true)}>
              <Icon name="i-flag" size={20} />
            </button>
          </span>
        </div>
        <div className="car-foot">
          <span className="dots">
            {photos.slice(0, 5).map((photo, index) => (
              <i key={photo.id} className={index === photoIndex ? 'on' : ''} />
            ))}
          </span>
          {(place.photo_count > 0 || place.video_count > 0) && (
            <span className="pill pill-glass">
              {photos.length ? `${photoIndex + 1} / ${place.photo_count}` : 'No photos yet'}
              {place.video_count > 0 && (
                <>
                  {' · '}
                  <Icon name="i-video" size={14} /> {place.video_count}
                </>
              )}
            </span>
          )}
        </div>
        {photos.length > 1 && (
          <>
            <button
              aria-label="Previous photo"
              className="round"
              style={{ position: 'absolute', left: 8, top: '50%', zIndex: 3 }}
              onClick={() => setPhotoIndex((i) => Math.max(0, i - 1))}
            >
              <Icon name="i-back" size={18} />
            </button>
            <button
              aria-label="Next photo"
              className="round"
              style={{ position: 'absolute', right: 8, top: '50%', zIndex: 3 }}
              onClick={() => setPhotoIndex((i) => Math.min(photos.length - 1, i + 1))}
            >
              <Icon name="i-chevr" size={18} />
            </button>
          </>
        )}
      </div>

      <div className="scr-body">
        <div className="pl">
          {/* 2. Names, category and area. */}
          <div className="pl-head">
            <div className="pl-kicker">
              <Icon name={categoryIcon(place.category)} size={16} />
              {categoryLabel(place.category)}
              {place.area ? ` · ${place.area}` : ''}
              {place.state ? `, ${place.state}` : ''}
            </div>
            <NameBlock
              name={place.name}
              primaryClass="pl-name"
              secondaryClass="pl-lname"
              as="h1"
            />
            <button className="link link-sm" type="button" onClick={() => setNameSheetOpen(true)}>
              <Icon name="i-globe" size={15} />
              Add the name in your language
            </button>
          </div>

          {/* 3. Like, Save. Share and Report are in the carousel. */}
          <div className="pl-actions">
            <button
              type="button"
              className={`btn btn-ghost btn-like ${place.liked ? 'on' : ''}`.trim()}
              aria-pressed={place.liked}
              onClick={() => void toggleLike()}
            >
              <Icon name={place.liked ? 'i-heartf' : 'i-heart'} size={18} />
              {place.liked ? 'Liked' : 'Like'} &middot; {num(place.likes)}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={place.saved}
              onClick={() => void toggleSave()}
            >
              <Icon name={place.saved ? 'i-starf' : 'i-star'} size={18} />
              {place.saved ? 'Saved' : 'Save'}
            </button>
          </div>

          {/* 4. Pulse strip. */}
          <PulseStrip pulse={place.pulse} />

          {/* 5. Stats and who found it. */}
          <div className="pl-stats">
            <div className="stat">
              <b>{num(place.verified_visits)}</b>
              <span>verified visits</span>
            </div>
            <div className="stat">
              <b>{num(place.visits_this_month)}</b>
              <span>this month</span>
            </div>
            <div className="stat stat-by">
              {place.found_by ? (
                <>
                  <span className="avatar">{initials(place.found_by.display_name)}</span>
                  <span>
                    {place.found_by.official ? 'Posted by' : 'Found by'}{' '}
                    <Link to={`/u/${place.found_by.username}`}>
                      <b>@{place.found_by.username}</b>
                    </Link>
                    <br />
                    <small>{date(place.created_at)}</small>
                  </span>
                </>
              ) : (
                <span>
                  <b>
                    {place.source === 'osm' ? 'From OpenStreetMap' : 'From Wikidata'}
                  </b>
                  <br />
                  <small>Open data</small>
                </span>
              )}
            </div>
          </div>

          {/* 6. Unverified banner. */}
          {place.status === 'unverified' && (
            <div className="golden" role="note" style={{ margin: 0 }}>
              <Icon name="i-info" size={18} />
              <span>
                <b>Not verified yet.</b> Two people need to check in here before this place
                counts. {place.added_remotely && 'It was added from somewhere else.'}
              </span>
            </div>
          )}

          {/* 7. Description and what to do. */}
          {place.description && <p className="pl-desc">{place.description}</p>}
          {place.activities && place.activities.length > 0 && (
            <div className="chips chips-wrap">
              {place.activities.map((activity) => (
                <Chip key={activity} label={activity} as="span" />
              ))}
            </div>
          )}

          {/* 8. When to go. */}
          <WhenToGo place={place} />

          {/* 9. Getting there, access rows, last-mile steps. */}
          <section className="sec">
            <h4>Getting there</h4>
            {place.maps_url ? (
              <div className="getting">
                <a
                  className="btn btn-primary btn-wide"
                  href={place.maps_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  <Icon name="i-nav" size={18} />
                  Open in Maps
                </a>
                {place.osm_url && (
                  <a className="link" href={place.osm_url} target="_blank" rel="noreferrer noopener">
                    OpenStreetMap
                  </a>
                )}
              </div>
            ) : (
              <p className="plain" style={{ color: 'var(--muted)' }}>
                This place is fragile, so the exact pin opens after you save it and agree to
                treat it carefully.
              </p>
            )}

            {place.access && Object.keys(place.access).length > 0 && (
              <ul className="access">
                {typeof place.access.road === 'string' && place.access.road && (
                  <li>
                    <Icon name="i-bike" size={18} />
                    {place.access.road}
                  </li>
                )}
                {typeof place.access.walk_min_from_road === 'number' && (
                  <li>
                    <Icon name="i-walk" size={18} />
                    {place.access.walk_min_from_road} min walk from the road
                  </li>
                )}
                {typeof place.access.nearest_transit_text === 'string' &&
                  place.access.nearest_transit_text && (
                    <li>
                      <Icon name="i-pin" size={18} />
                      {place.access.nearest_transit_text}
                    </li>
                  )}
              </ul>
            )}

            <StepList
              versions={steps.versions}
              locked={steps.locked}
              onVote={(group, helpful) => void voteSteps(group, helpful)}
              onPledge={() => void pledge()}
            />
            {me && !steps.locked && (
              <Link className="link link-sm" to={`/place/${place.id}/steps/new`}>
                <Icon name="i-plus" size={14} />
                Write your own directions
              </Link>
            )}
          </section>

          {/* 10. Safety and access. Always open (invariant 9). */}
          <SafetyCard place={place} onAskFriend={() => setBuddyOpen(true)} />

          {/* 11. Accessibility. */}
          <AccessibilityRows place={place} />

          {/* 12. Fees and timings. */}
          {(place.entry_fee_text || place.timings_text) && (
            <section className="sec">
              <h4>Fees &amp; timings</h4>
              <p className="plain">
                {[place.entry_fee_text, place.timings_text].filter(Boolean).join(' · ')}
              </p>
            </section>
          )}

          {/* 13. Videos of this place. */}
          {place.videos && place.videos.length > 0 && (
            <section className="sec">
              <h4>Videos of this place</h4>
              <div className="vids">
                {place.videos.slice(0, 6).map((video) => (
                  <Link className="vid" key={video.id} to="/watch" aria-label={video.caption}>
                    {video.poster ? (
                      <img className="vid-ph" src={video.poster} alt="" style={{ objectFit: 'cover' }} />
                    ) : (
                      <Scene
                        name={categoryScene(place.category)}
                        className="vid-ph"
                        viewBox="60 0 280 500"
                      />
                    )}
                    <i>
                      <Icon name="i-play" size={14} />
                      {clock(video.duration_s)}
                    </i>
                    <span>@{video.creator?.username ?? ''}</span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* 14. Nearby places. */}
          {place.nearby && place.nearby.length > 0 && (
            <section className="sec">
              <h4>Nearby</h4>
              <div className="near">
                {place.nearby.map((other) => (
                  <Link className="near-c" key={other.id} to={`/place/${other.id}`}>
                    <PlaceThumb place={other} className="near-ph" />
                    <b>{other.name.primary.text}</b>
                    <span>{distance(other.distance_km)}</span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* 15. Attribution footer. Never removed to tidy a design (invariant 6). */}
          <p className="attrib">{place.attribution}</p>
          {place.media?.some((item) => item.source === 'commons') && (
            <p className="attrib">
              {place.media
                .filter((item) => item.source === 'commons' && item.attribution)
                .slice(0, 3)
                .map((item) => (
                  <span key={item.id} style={{ display: 'block' }}>
                    <a href={item.source_url} target="_blank" rel="noreferrer noopener">
                      {item.attribution}
                    </a>
                  </span>
                ))}
            </p>
          )}
        </div>
      </div>

      {/* The pinned bottom bar: distance and Check in. */}
      <div className="checkin-bar">
        <span className="ci-dist" style={{ color: withinRadius ? 'var(--moss)' : 'var(--muted)' }}>
          <Icon name="i-target" size={18} />
          {place.distance_km === undefined
            ? 'Distance unknown'
            : withinRadius
              ? `You're ${Math.round((place.distance_km ?? 0) * 1000)} m away`
              : `${distance(place.distance_km)} away`}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void checkIn()}
          disabled={checkingIn}
        >
          <Icon name="i-check" size={18} />
          {checkingIn ? 'Checking…' : 'Check in'}
        </button>
      </div>

      {/* Sheets */}
      <CheckinSheet
        result={checkinResult}
        place={place}
        onClose={() => setCheckinResult(null)}
        onPulse={() => {
          setCheckinResult(null);
          navigate(`/place/${place.id}/pulse`);
        }}
      />

      <BottomSheet
        open={buddyOpen}
        onClose={() => setBuddyOpen(false)}
        title="Ask a friend to check on me"
      >
        <p className="plain" style={{ color: 'var(--muted)', marginBottom: 12 }}>
          Sends one person a message: where you are going, and when to start worrying.
          It does not include your location.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {[
            { hours: 2, label: 'Back within 2 hours' },
            { hours: 4, label: 'Back within 4 hours' },
            { hours: 8, label: 'Back by tonight (8 hours)' },
          ].map((option) => (
            <button
              key={option.hours}
              type="button"
              className="cand"
              onClick={() => askFriendToCheck(option.hours)}
            >
              <div>
                <b>{option.label}</b>
              </div>
            </button>
          ))}
        </div>
      </BottomSheet>

      <BottomSheet open={reportOpen} onClose={() => setReportOpen(false)} title="Report this place">
        <label className="field">
          <span>What should we know? <small className="field-opt">optional</small></span>
          <textarea
            value={reportNote}
            onChange={(event) => setReportNote(event.target.value)}
            maxLength={300}
            rows={2}
            placeholder="For a wrong pin: where it really is, or what is next to it."
          />
        </label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {REPORT_REASONS.map((reason) => (
            <button
              key={reason.key}
              type="button"
              className="cand"
              onClick={() => void sendReport(reason.key)}
            >
              <div>
                <b>{reason.label}</b>
              </div>
            </button>
          ))}
        </div>
      </BottomSheet>

      <BottomSheet
        open={nameSheetOpen}
        onClose={() => setNameSheetOpen(false)}
        title="Add the name in your language"
      >
        <p className="plain" style={{ color: 'var(--muted)', marginBottom: 12 }}>
          You need a verified check-in here first. Others vote on the names people add.
        </p>
        <label className="field">
          <span>Language</span>
          <select
            value={newName.lang}
            onChange={(event) => setNewName((value) => ({ ...value, lang: event.target.value }))}
          >
            {(place.regional_langs ?? ['te']).concat(['hi', 'ta', 'kn', 'ml', 'bn', 'ur']).map(
              (lang, index, all) =>
                all.indexOf(lang) === index ? (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ) : null,
            )}
          </select>
        </label>
        <label className="field">
          <span>The name</span>
          <input
            value={newName.name}
            lang={newName.lang}
            onChange={(event) => setNewName((value) => ({ ...value, name: event.target.value }))}
            placeholder="Type it in your own script"
          />
        </label>
        <button type="button" className="btn btn-primary btn-wide" onClick={() => void submitName()}>
          Add the name
        </button>
      </BottomSheet>
    </>
  );
}

function initials(name: string): string {
  const parts = name.replace(/[^\p{L}\s.]/gu, ' ').trim().split(/[\s.]+/);
  return (
    parts
      .slice(0, 2)
      .map((part) => part[0] ?? '')
      .join('')
      .toUpperCase() || '??'
  );
}
