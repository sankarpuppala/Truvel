/** Watch -- full-screen vertical videos of places. Reference screen 2.
 *
 * The one dark, immersive surface in both themes (SPEC §12.1). Tabs are
 * For you / Nearby / Following; snap scrolling moves between items, and so do
 * the arrow keys and the two buttons, because a gesture alone is never the only
 * way (SPEC §13).
 *
 * After 20 minutes of watching in one session a dismissible card appears: the
 * habit this app wants to build is going outside, not scrolling (SPEC §8.3).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { EmptyState, Loading } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { WatchPlayer } from '../components/WatchPlayer';
import { distance } from '../lib/format';
import { haptic } from '../lib/geo';
import type { WatchItem } from '../lib/types';

const TABS = [
  { key: 'foryou', label: 'For you' },
  { key: 'nearby', label: 'Nearby' },
  { key: 'following', label: 'Following' },
] as const;

type Tab = (typeof TABS)[number]['key'];

export function Watch() {
  const { me, position, requestPosition, toast, config } = useApp();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('foryou');
  const [items, setItems] = useState<WatchItem[]>([]);
  const [index, setIndex] = useState(0);
  const [muted, setMuted] = useState(true);
  const [loading, setLoading] = useState(true);
  const [nudged, setNudged] = useState(false);
  const [showNudge, setShowNudge] = useState(false);
  const watchedMs = useRef(0);
  const scroller = useRef<HTMLDivElement | null>(null);

  const nudgeAfterMin = config?.watch.break_nudge_min ?? 20;

  useEffect(() => {
    void requestPosition();
  }, [requestPosition]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .watch(tab, position, 0)
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
        setIndex(0);
      })
      .catch((error) => {
        if (!cancelled) {
          toast(error instanceof ApiError ? error.message : 'Could not load Watch.', 'bad');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, position?.lat, position?.lng, toast]);

  // The 20-minute nudge. Counted while this screen is open.
  useEffect(() => {
    const timer = window.setInterval(() => {
      watchedMs.current += 1000;
      if (!nudged && watchedMs.current >= nudgeAfterMin * 60 * 1000) {
        setNudged(true);
        setShowNudge(true);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [nudged, nudgeAfterMin]);

  const sendView = useCallback(
    (mediaId: number) => (watchedSeconds: number, duration: number) => {
      // The server decides engaged/completed from this (SPEC §9.10).
      void api.watchView(mediaId, watchedSeconds, duration).catch(() => undefined);
    },
    [],
  );

  const move = useCallback(
    (delta: number) => {
      setIndex((current) => {
        const next = Math.max(0, Math.min(items.length - 1, current + delta));
        const node = scroller.current?.children[next] as HTMLElement | undefined;
        node?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return next;
      });
    },
    [items.length],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'ArrowDown' || event.key === 'PageDown') move(1);
      else if (event.key === 'ArrowUp' || event.key === 'PageUp') move(-1);
      else if (event.key === 'm') setMuted((value) => !value);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [move]);

  // Which item is on screen, from scroll position.
  function onScroll() {
    const node = scroller.current;
    if (!node) return;
    const height = node.clientHeight || 1;
    setIndex(Math.round(node.scrollTop / height));
  }

  const current = items[index];

  async function like(item: WatchItem) {
    if (!me) {
      toast('Sign in to like videos.', 'bad');
      return;
    }
    try {
      const result = await api.likeMedia(item.media.id, !item.liked);
      haptic();
      setItems((list) =>
        list.map((entry) =>
          entry.media.id === item.media.id
            ? { ...entry, liked: result.liked, likes: result.likes }
            : entry,
        ),
      );
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  async function savePlace(item: WatchItem) {
    if (!me) {
      toast('Sign in to save places.', 'bad');
      return;
    }
    try {
      await api.save(item.place.id, true);
      haptic();
      toast(`Saved · ${item.place.name.primary.text}`, 'kadam');
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not save.', 'bad');
    }
  }

  async function share(item: WatchItem) {
    const url = `${window.location.origin}/place/${item.place.id}`;
    const text = `${item.place.name.primary.text} on Pagdandi`;
    try {
      if (navigator.share) await navigator.share({ title: text, url });
      else {
        await navigator.clipboard.writeText(`${text} — ${url}`);
        toast('Link copied.');
      }
    } catch {
      /* the user cancelled the share sheet */
    }
  }

  const savedNearby = useMemo(
    () => items.find((item) => item.place.saved && (item.place.distance_km ?? 999) < 10),
    [items],
  );

  return (
    <div className="scr scr-watch scr-fill" style={{ overflow: 'hidden' }}>
      <StatusBar />

      <div className="wtabs" role="tablist" aria-label="Watch feeds">
        {TABS.map((entry) => (
          <button
            key={entry.key}
            type="button"
            role="tab"
            aria-selected={entry.key === tab}
            className={entry.key === tab ? 'on' : ''}
            onClick={() => setTab(entry.key)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading what="Loading videos" />
      ) : items.length === 0 ? (
        <div style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
          <EmptyState
            icon="i-play"
            title={tab === 'following' ? 'Nothing from people you follow' : 'No videos yet'}
            body={
              tab === 'following'
                ? 'Follow creators from any video to see them here.'
                : 'Be the first to post a video of a place near you.'
            }
            action={
              <Link className="btn btn-primary btn-sm" to="/add/media">
                Post a video
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <div
            ref={scroller}
            onScroll={onScroll}
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              scrollSnapType: 'y mandatory',
              scrollBehavior: 'smooth',
            }}
          >
            {items.map((item, itemIndex) => (
              <div
                key={item.media.id}
                style={{ height: '100%', scrollSnapAlign: 'start', minHeight: 0 }}
              >
                <WatchPlayer
                  item={item}
                  active={itemIndex === index}
                  muted={muted}
                  onToggleMute={() => setMuted((value) => !value)}
                  onLike={() => void like(item)}
                  onSave={() => void savePlace(item)}
                  onShare={() => void share(item)}
                  onView={sendView(item.media.id)}
                />
              </div>
            ))}
          </div>

          {/* Buttons for the vertical gesture (SPEC §13). On the left edge,
              because the right rail already owns the other side. */}
          <div
            style={{
              position: 'absolute',
              left: 8,
              top: '42%',
              zIndex: 4,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <button
              type="button"
              className="round"
              aria-label="Previous video"
              onClick={() => move(-1)}
              disabled={index === 0}
            >
              <Icon name="i-up" size={18} />
            </button>
            <button
              type="button"
              className="round"
              aria-label="Next video"
              onClick={() => move(1)}
              disabled={index >= items.length - 1}
            >
              <Icon name="i-up" size={18} className="flip-y" />
            </button>
          </div>
        </>
      )}

      {/* The 20-minute card (SPEC §8.3). Dismissible, never blocking. */}
      {showNudge && (
        <div
          role="note"
          style={{
            position: 'absolute',
            left: 14,
            right: 14,
            bottom: 90,
            zIndex: 6,
            background: 'var(--surface)',
            color: 'var(--ink)',
            borderRadius: 18,
            padding: '12px 14px',
            boxShadow: 'var(--shadow)',
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
          }}
        >
          <Icon name="i-sun" size={20} />
          <div style={{ flex: 1 }}>
            <b>You&apos;ve watched {nudgeAfterMin} min.</b>{' '}
            {savedNearby ? (
              <>
                <i>{savedNearby.place.name.primary.text}</i> (saved) is{' '}
                {distance(savedNearby.place.distance_km)} away.
              </>
            ) : (
              'There is somewhere near you worth standing in.'
            )}
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() =>
                  navigate(savedNearby ? `/place/${savedNearby.place.id}` : '/')
                }
              >
                {savedNearby ? 'Take me there' : 'See what is nearby'}
              </button>
              <button
                type="button"
                className="btn btn-text btn-sm"
                onClick={() => setShowNudge(false)}
              >
                Later
              </button>
            </div>
          </div>
        </div>
      )}

      {current && (
        <span className="sr-only" aria-live="polite">
          Video {index + 1} of {items.length}: {current.place.name.primary.text}
        </span>
      )}
    </div>
  );
}
