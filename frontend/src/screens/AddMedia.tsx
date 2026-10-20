/** Add photos or a video to a place that already exists (SPEC §8.6).
 *
 * The place picker lists the nearest places first, because the overwhelmingly
 * common case is standing somewhere and posting what is in front of you. An
 * upload made on site gets a "Shot here" badge.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Loading } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { PlaceThumb } from '../components/PlaceRow';
import { distance } from '../lib/format';
import { getPosition, LocationError } from '../lib/geo';
import { fileSize, readExifGps, resizePhoto, videoPoster } from '../lib/media';
import type { Place } from '../lib/types';

export function AddMedia() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { me, loadingMe, position, requestPosition, toast, config } = useApp();

  const [places, setPlaces] = useState<Place[]>([]);
  const [placeId, setPlaceId] = useState<number | null>(
    params.get('place') ? Number(params.get('place')) : null,
  );
  const [files, setFiles] = useState<File[]>([]);
  const [caption, setCaption] = useState('');
  const [lang, setLang] = useState('en');
  const [onSite, setOnSite] = useState(false);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const maxVideoS = config?.watch.video_max_s ?? 60;
  const maxVideoMb = config?.watch.video_max_mb ?? 60;
  const captionMax = config?.media.caption_max_chars ?? 150;

  useEffect(() => {
    if (!loadingMe && !me) navigate('/signin');
  }, [loadingMe, me, navigate]);

  useEffect(() => {
    void requestPosition();
  }, [requestPosition]);

  useEffect(() => {
    setLoading(true);
    void api
      .cityPlaces(me?.home_city?.slug ?? 'hyderabad', { sort: 'near', at: position })
      .then((response) => setPlaces(response.places))
      .catch(() => setPlaces([]))
      .finally(() => setLoading(false));
  }, [me?.home_city?.slug, position?.lat, position?.lng]);

  const place = places.find((entry) => entry.id === placeId) ?? null;

  /** Checking in here is what earns the "Shot here" badge (SPEC §8.6). */
  async function confirmOnSite() {
    if (!place) return;
    setChecking(true);
    try {
      const reading = await getPosition();
      const metres =
        Math.hypot(
          (reading.lat - place.lat) * 111_320,
          (reading.lng - place.lng) * 111_320 * Math.cos((place.lat * Math.PI) / 180),
        ) || 0;
      const close = metres <= Math.max(place.radius_m, 150) && reading.accuracy <= 100;
      setOnSite(close);
      toast(
        close
          ? "You're here — your upload gets a Shot here badge."
          : `You're ${Math.round(metres)} m away, so no Shot here badge.`,
        close ? 'kadam' : 'plain',
      );
    } catch (error) {
      toast(error instanceof LocationError ? error.message : 'Could not find you.', 'bad');
    } finally {
      setChecking(false);
    }
  }

  async function upload() {
    if (!place || files.length === 0) return;
    if (!caption.trim()) {
      toast('A caption is required — it is the alt text.', 'bad');
      return;
    }
    setBusy(true);
    try {
      for (const file of files) {
        const isVideo = file.type.startsWith('video/');
        const form = new FormData();

        if (isVideo) {
          if (file.size > maxVideoMb * 1024 * 1024) {
            toast(`${file.name} is ${fileSize(file.size)} — the limit is ${maxVideoMb} MB.`, 'bad');
            continue;
          }
          const poster = await videoPoster(file);
          if (poster.duration > maxVideoS + 0.5) {
            toast(
              `${file.name} is ${Math.round(poster.duration)} s — the limit is ${maxVideoS} s.`,
              'bad',
            );
            continue;
          }
          form.set('file', file);
          form.set('poster', poster.blob, 'poster.jpg');
          form.set('kind', 'video');
          form.set('duration_s', String(poster.duration));
        } else {
          const gps = await readExifGps(file);
          const resized = await resizePhoto(file);
          form.set('file', resized, 'photo.jpg');
          form.set('kind', 'photo');
          if (gps) {
            form.set('exif_lat', String(gps.lat));
            form.set('exif_lng', String(gps.lng));
          }
        }

        form.set('caption', caption.trim().slice(0, captionMax));
        form.set('lang', lang);
        form.set('on_site', String(onSite));

        const result = await api.uploadMedia(place.id, form);
        if (result.skipped) toast(result.message ?? 'Already added.', 'bad');
        if (result.warning === 'gps_mismatch') {
          toast("That photo's own location is far from the place. Flagged for review.", 'bad');
        }
      }
      toast('Added. Thank you.', 'kadam');
      navigate(`/place/${place.id}`);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That upload failed.', 'bad');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StatusBar />
      <div className="add-head">
        <button className="round round-flat" aria-label="Close" onClick={() => navigate(-1)}>
          <Icon name="i-x" size={22} />
        </button>
        <div>
          <div className="add-title">Photos or a video</div>
          <div className="add-sub">Of a place that is already here</div>
        </div>
      </div>

      <div className="scr-body">
        <div className="form-page">
          {!place ? (
            <>
              <p className="sub">Which place? Nearest first.</p>
              {loading ? (
                <Loading what="Finding places near you" />
              ) : (
                places.slice(0, 20).map((entry) => (
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
                ))
              )}
            </>
          ) : (
            <>
              <div className="cand on" style={{ marginBottom: 14 }}>
                <PlaceThumb place={place} className="thumb thumb-sm" />
                <div>
                  <b>{place.name.primary.text}</b>
                  <span>
                    {place.area} &middot; {distance(place.distance_km)}
                  </span>
                </div>
                <button type="button" className="link" onClick={() => setPlaceId(null)}>
                  Change
                </button>
              </div>

              <input
                type="file"
                accept="image/*,video/*"
                multiple
                onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                aria-label="Choose photos or a video"
                style={{ marginBottom: 12 }}
              />
              {files.length > 0 && (
                <p className="sub">
                  {files.length} file{files.length === 1 ? '' : 's'} &middot;{' '}
                  {fileSize(files.reduce((total, file) => total + file.size, 0))}
                </p>
              )}

              <label className="field">
                <span>Caption (this is the alt text, and it is required)</span>
                <textarea
                  value={caption}
                  maxLength={captionMax}
                  onChange={(event) => setCaption(event.target.value)}
                  placeholder="What this shows, and anything useful about getting there."
                />
              </label>

              <label className="field">
                <span>Caption language</span>
                <select value={lang} onChange={(event) => setLang(event.target.value)}>
                  {(config?.languages ?? ['en']).map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </label>

              <button
                type="button"
                className="btn btn-ghost btn-wide"
                onClick={() => void confirmOnSite()}
                disabled={checking}
                style={{ marginBottom: 12 }}
              >
                <Icon name={onSite ? 'i-check' : 'i-target'} size={18} />
                {onSite ? "You're here · Shot here badge" : 'Am I here right now?'}
              </button>

              <p className="sub">
                Videos up to {maxVideoS} s and {maxVideoMb} MB. Vertical works best. We do not
                re-encode video, so those are hard limits.
              </p>

              <button
                type="button"
                className="btn btn-primary btn-wide"
                onClick={() => void upload()}
                disabled={busy || files.length === 0 || !caption.trim()}
              >
                {busy ? 'Uploading…' : 'Add to this place'}
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}
