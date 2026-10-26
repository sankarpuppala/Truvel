/** One full-screen Watch item: the video, the overlay and the right rail.
 *
 * Three things here are load-bearing rather than decorative:
 *
 *  - **The heartbeat.** When the item stops being the current one, we post how
 *    long it was watched and how long it is. The *server* decides whether that
 *    was an engaged view (SPEC §9.10) -- the client never asserts it, because
 *    engaged views feed the Partner Program.
 *  - **saveData.** On a metered or 2G connection we show the poster and wait
 *    for a tap rather than autoplaying (SPEC §8.3).
 *  - **Captions.** Every video has uploader text, and it is shown on request,
 *    because a video with no captions is unusable for some people (SPEC §13).
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { categoryIcon, categoryLabel, categoryScene } from '../lib/categories';
import { compact, distance } from '../lib/format';
import { saveData } from '../lib/geo';
import type { WatchItem } from '../lib/types';
import { LivePill } from './common';
import { Icon, Scene } from './Icon';
import { NameBlock } from './NameBlock';

export function WatchPlayer({
  item,
  active,
  muted,
  onToggleMute,
  onLike,
  onSave,
  onShare,
  onComments,
  onFollow,
  onView,
}: {
  item: WatchItem;
  active: boolean;
  muted: boolean;
  onToggleMute: () => void;
  onLike: () => void;
  onSave: () => void;
  onShare: () => void;
  onComments: () => void;
  /** Undefined when there is no one to follow (your own video, or no creator). */
  onFollow?: () => void;
  /** Called when this item stops being current: (watched seconds, duration). */
  onView: (watchedSeconds: number, duration: number) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const startedAt = useRef<number | null>(null);
  const watched = useRef(0);
  const [progress, setProgress] = useState(0);
  const [showCaption, setShowCaption] = useState(false);
  const [posterOnly] = useState(() => saveData());
  const [playing, setPlaying] = useState(false);

  const media = item.media;
  const place = item.place;
  const hasVideoFile = Boolean(media.url) && media.kind === 'video' && !media.url.endsWith('/');

  // Count watch time while this item is the current one.
  useEffect(() => {
    const video = videoRef.current;
    if (active) {
      startedAt.current = performance.now();
      if (hasVideoFile && !posterOnly && video) {
        video.currentTime = 0;
        void video.play().then(
          () => setPlaying(true),
          () => setPlaying(false),   // autoplay refused: the poster stays up
        );
      }
      return undefined;
    }

    // Left the item: stop, measure, and send the heartbeat once.
    if (video && !video.paused) video.pause();
    setPlaying(false);
    if (startedAt.current !== null) {
      const seconds = (performance.now() - startedAt.current) / 1000;
      startedAt.current = null;
      watched.current = seconds;
      if (seconds > 0.2) onView(seconds, media.duration_s);
    }
    return undefined;
  }, [active, hasVideoFile, posterOnly, media.duration_s, onView]);

  // Send the heartbeat if the tab is closed or hidden mid-watch.
  useEffect(() => {
    function flush() {
      if (!active || startedAt.current === null) return;
      const seconds = (performance.now() - startedAt.current) / 1000;
      startedAt.current = null;
      if (seconds > 0.2) onView(seconds, media.duration_s);
    }
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', flush);
    return () => {
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', flush);
    };
  }, [active, media.duration_s, onView]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.muted = muted;
  }, [muted]);

  // With no video file (demo posters, or a metered connection) the progress bar
  // still moves, so the item does not look broken.
  useEffect(() => {
    if (!active || hasVideoFile) return undefined;
    const started = performance.now();
    const timer = window.setInterval(() => {
      const elapsed = (performance.now() - started) / 1000;
      const ratio = media.duration_s > 0 ? elapsed / media.duration_s : 0;
      setProgress(Math.min(1, ratio));
    }, 250);
    return () => window.clearInterval(timer);
  }, [active, hasVideoFile, media.duration_s]);

  const poster = media.poster ?? media.thumb;

  return (
    <section
      className="scr scr-watch"
      style={{ position: 'relative', height: '100%', minHeight: 0 }}
      aria-label={`${place.name.primary.text}, video by @${media.creator?.username ?? 'someone'}`}
    >
      {hasVideoFile && !posterOnly ? (
        <video
          ref={videoRef}
          className="watch-ph"
          src={media.url}
          poster={poster ?? undefined}
          muted={muted}
          loop
          playsInline
          preload={active ? 'auto' : 'metadata'}
          style={{ objectFit: 'cover' }}
          onTimeUpdate={(event) => {
            const video = event.currentTarget;
            if (video.duration > 0) setProgress(video.currentTime / video.duration);
          }}
        >
          {/* Uploader captions, required on every video (SPEC §13). */}
          <track kind="captions" srcLang={media.lang} label="Captions" default={false} />
        </video>
      ) : poster ? (
        <img className="watch-ph" src={poster} alt={media.caption} style={{ objectFit: 'cover' }} />
      ) : (
        <Scene
          name={categoryScene(place.category)}
          className="watch-ph"
          viewBox="40 0 320 560"
          alt={media.caption || place.name.primary.text}
        />
      )}

      <div className="watch-shade" />

      {/* Tap to play: autoplay was refused, or saveData is on and we are
          showing the poster until the viewer asks for the video (SPEC §8.3).
          With no video file at all there is nothing to play, so no button. */}
      {active && !playing && hasVideoFile && (
        <button
          type="button"
          onClick={() => {
            const video = videoRef.current;
            if (video) void video.play().then(() => setPlaying(true), () => undefined);
          }}
          aria-label="Play this video"
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 2,
            display: 'grid',
            placeItems: 'center',
            color: 'var(--on-photo)',
          }}
        >
          <span className="round" style={{ width: 64, height: 64 }}>
            <Icon name="i-play" size={30} />
          </span>
        </button>
      )}

      <button className="wmute" onClick={onToggleMute} aria-label={muted ? 'Sound on' : 'Sound off'}>
        <Icon name={muted ? 'i-mute' : 'i-play'} size={20} />
      </button>

      {/* Safety overlay: videos of steep edges or dangerous water (SPEC §8.14). */}
      {item.safety_overlay && (
        <div
          style={{
            position: 'absolute',
            left: 14,
            right: 70,
            top: 120,
            zIndex: 2,
            display: 'flex',
            gap: 8,
            alignItems: 'flex-start',
            background: 'var(--live-badge)',
            color: 'var(--on-photo)',
            borderRadius: 14,
            padding: '8px 12px',
            fontSize: 13.5,
            lineHeight: 1.35,
          }}
        >
          <Icon name="i-warn" size={17} />
          <span>Steep edges and fast water here. Stay back from the edge.</span>
        </div>
      )}

      <div className="wrail">
        <div className="wr wr-av">
          <Link
            to={`/u/${media.creator?.username ?? ''}`}
            aria-label={`Open @${media.creator?.username ?? 'creator'}`}
          >
            <span className="avatar av-watch">{initials(media.creator?.display_name)}</span>
          </Link>
          {item.following ? (
            <span className="wr-plus" aria-hidden="true">
              <Icon name="i-check" size={11} />
            </span>
          ) : (
            onFollow && (
              <button
                type="button"
                className="wr-follow"
                onClick={onFollow}
                aria-label={`Follow @${media.creator?.username ?? 'creator'}`}
              >
                <Icon name="i-plus" size={14} />
              </button>
            )
          )}
        </div>
        {/* WCAG 2.5.3: each accessible name contains the visible text. */}
        <button
          className="wr"
          onClick={onLike}
          aria-pressed={item.liked}
          aria-label={`Like, ${compact(item.likes)} likes`}
        >
          <Icon name={item.liked ? 'i-heartf' : 'i-heart'} size={28} />
          <span>{compact(item.likes)}</span>
        </button>
        <button className="wr" onClick={onSave} aria-label="Save this place">
          <Icon name="i-star" size={28} />
          <span>Save</span>
        </button>
        <button className="wr" onClick={onComments} aria-label="Comments">
          <Icon name="i-comment" size={28} />
          <span>Comments</span>
        </button>
        <button className="wr" onClick={onShare} aria-label="Share">
          <Icon name="i-share" size={28} />
          <span>Share</span>
        </button>
        <button
          className="wr"
          onClick={() => setShowCaption((value) => !value)}
          aria-pressed={showCaption}
          aria-label="Text captions on this video"
        >
          <Icon name="i-list" size={28} />
          <span>Text</span>
        </button>
      </div>

      <div className="wbody">
        <div className="wcreator">
          {media.creator?.username ? (
            <Link
              to={`/u/${media.creator.username}`}
              className="wcreator-link"
              aria-label={`Open @${media.creator.username}'s profile`}
            >
              <b>@{media.creator.username}</b>
            </Link>
          ) : (
            <b>@{media.creator?.username ?? 'someone'}</b>
          )}
          {item.following && <span className="pill pill-outline">Following</span>}
          {media.shot_here && (
            <span className="shot">
              <Icon name="i-check" size={12} />
              Shot here
            </span>
          )}
        </div>

        {place.live && <LivePill solid text={liveText(item)} />}

        <NameBlock name={place.name} primaryClass="wname" secondaryClass="wlname" as="h3" />

        <div className="wmeta">
          <Icon name={categoryIcon(place.category)} size={15} />
          {categoryLabel(place.category)}
          {item.blur_location ? ' · area hidden' : place.area ? ` · ${place.area}` : ''}
          {place.state ? `, ${place.state}` : ''}
          {place.distance_km !== undefined ? ` · ${distance(place.distance_km)}` : ''}
        </div>

        <p className="wcap" lang={media.lang}>
          {media.caption}
        </p>

        <Link className="btn btn-primary btn-go" to={`/place/${place.id}`}>
          <Icon name="i-nav" size={17} />
          Go here
        </Link>
      </div>

      {/* Captions as on-video text, shown on request (SPEC §13). */}
      {showCaption && (
        <p
          lang={media.lang}
          style={{
            position: 'absolute',
            left: 14,
            right: 14,
            bottom: 300,
            zIndex: 3,
            margin: 0,
            background: 'var(--scrim-strong)',
            color: 'var(--on-photo)',
            borderRadius: 12,
            padding: '10px 12px',
            fontSize: 15,
            lineHeight: 1.4,
          }}
        >
          {media.caption}
        </p>
      )}

      <div className="wprog">
        <i style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
    </section>
  );
}

function liveText(item: WatchItem): string | undefined {
  const pulse = item.place.pulse;
  if (!pulse) return undefined;
  const water = pulse.fields.water?.value;
  if (water === 'flowing') return 'flowing strongly';
  const crowd = pulse.fields.crowd?.value;
  if (crowd) return `${crowd} now`;
  return undefined;
}

function initials(name: string | undefined): string {
  if (!name) return '??';
  const parts = name.replace(/[^\p{L}\s.]/gu, ' ').trim().split(/[\s.]+/);
  const letters = parts.slice(0, 2).map((part) => part[0] ?? '');
  return letters.join('').toUpperCase() || '??';
}
