/** Following (SPEC §8.11): a feed of what the people you follow post and the
 * places they add, newest first; plus who you follow, who follows you, and
 * people worth following. `?user=<handle>&tab=followers|following` shows
 * another person's lists, reached from their profile. */
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { EmptyState, Loading, Segmented } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { NameBlock } from '../components/NameBlock';
import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { categoryLabel } from '../lib/categories';
import { date } from '../lib/format';
import type { FeedItem, SocialUser } from '../lib/types';

type Tab = 'feed' | 'following' | 'followers';

export function Following() {
  const { me, toast } = useApp();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const handle = params.get('user') ?? me?.username ?? '';
  const ownLists = !params.get('user') || params.get('user') === me?.username;
  const tab = (params.get('tab') as Tab | null) ?? (ownLists ? 'feed' : 'followers');

  const setTab = (next: Tab) => {
    const p: Record<string, string> = { tab: next };
    if (!ownLists) p.user = handle;
    setParams(p, { replace: true });
  };

  const fail = useCallback(
    (error: unknown) =>
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad'),
    [toast],
  );

  if (!me && ownLists) {
    return (
      <>
        <StatusBar />
        <div className="scr-body">
          <EmptyState
            icon="i-group"
            title="Follow people who find good places"
            body="Sign in to see what they post and the places they add."
            action={
              <Link className="btn btn-primary btn-sm" to="/signin">
                Sign in
              </Link>
            }
          />
        </div>
      </>
    );
  }

  const options: { key: Tab; label: string }[] = ownLists
    ? [
        { key: 'feed', label: 'Feed' },
        { key: 'following', label: 'Following' },
        { key: 'followers', label: 'Followers' },
      ]
    : [
        { key: 'followers', label: 'Followers' },
        { key: 'following', label: 'Following' },
      ];

  return (
    <>
      <StatusBar />
      <div className="add-head">
        <button className="round round-flat" aria-label="Back" onClick={() => navigate(-1)}>
          <Icon name="i-back" size={20} />
        </button>
        <div>
          <div className="add-title">{ownLists ? 'Following' : `@${handle}`}</div>
          <div className="add-sub">
            {ownLists ? 'What people you follow post and find' : 'Followers and following'}
          </div>
        </div>
      </div>
      <Segmented label="Following views" options={options} value={tab} onChange={setTab} className="fl-tabs" />
      <div className="scr-body">
        {tab === 'feed' ? (
          <Feed fail={fail} />
        ) : (
          <UserList key={`${handle}-${tab}`} handle={handle} tab={tab} fail={fail} />
        )}
      </div>
    </>
  );
}

function Feed({ fail }: { fail: (e: unknown) => void }) {
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .feed()
      .then((r) => {
        setItems(r.items);
        setNext(r.next);
        setCount(r.following);
      })
      .catch((e) => {
        setItems([]);
        fail(e);
      });
  }, [fail]);

  async function more() {
    if (!next) return;
    setBusy(true);
    try {
      const r = await api.feed(next);
      setItems((list) => [...(list ?? []), ...r.items]);
      setNext(r.next);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  if (items === null) return <Loading />;
  return (
    <>
      {items.length === 0 && (
        <EmptyState
          icon="i-group"
          title={count === 0 ? 'You are not following anyone yet' : 'Nothing new yet'}
          body={
            count === 0
              ? 'Follow people below and their photos, videos and places show up here.'
              : 'When the people you follow post or add a place, it shows up here.'
          }
        />
      )}
      <ul className="feed">
        {items.map((item) => (
          <FeedCard key={`${item.type}-${item.media?.id ?? item.place.id}`} item={item} />
        ))}
      </ul>
      {next && (
        <div className="feed-more">
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void more()}>
            Show older
          </button>
        </div>
      )}
      <Suggestions fail={fail} />
    </>
  );
}

function FeedCard({ item }: { item: FeedItem }) {
  const { creator, place } = item;
  // A place card shows the place's own lead photo, as a post shows its media.
  const media = item.media ?? place.lead_media;
  const verb =
    item.type === 'place' ? 'added a place' : media?.kind === 'video' ? 'posted a video' : 'posted a photo';
  return (
    <li className="feed-card">
      <div className="feed-head">
        <Link to={`/u/${creator.username}`} className="feed-who">
          <span className="avatar">{initials(creator.display_name)}</span>
          <span>
            <b>@{creator.username}</b> {verb}
            <small>{date(item.at)}</small>
          </span>
        </Link>
      </div>
      {media && (
        <div className="feed-media">
          {media.kind === 'video' ? (
            <video src={media.url} poster={media.poster ?? undefined} controls preload="none" playsInline />
          ) : (
            <img src={media.url} alt={media.caption || ''} loading="lazy" />
          )}
          {media.source === 'commons' && media.attribution && (
            <small className="feed-credit">{media.attribution}</small>
          )}
        </div>
      )}
      <Link to={`/place/${place.id}`} className="feed-place">
        <NameBlock name={place.name} primaryClass="feed-pname" secondaryClass="lname" as="h3" />
        <span className="feed-meta">
          {categoryLabel(place.category)}
          {place.area ? ` · ${place.area}` : ''}
        </span>
      </Link>
      {media?.caption && item.type === 'post' && <p className="feed-cap">{media.caption}</p>}
    </li>
  );
}

function UserList({ handle, tab, fail }: { handle: string; tab: Tab; fail: (e: unknown) => void }) {
  const [users, setUsers] = useState<SocialUser[] | null>(null);
  useEffect(() => {
    (tab === 'followers' ? api.followers(handle) : api.followingList(handle))
      .then((r) => setUsers(r.users))
      .catch((e) => {
        setUsers([]);
        fail(e);
      });
  }, [handle, tab, fail]);
  if (users === null) return <Loading />;
  if (users.length === 0) {
    return (
      <EmptyState
        icon="i-group"
        title={tab === 'followers' ? 'No followers yet' : 'Not following anyone yet'}
      />
    );
  }
  return <People users={users} fail={fail} />;
}

function Suggestions({ fail }: { fail: (e: unknown) => void }) {
  const [users, setUsers] = useState<SocialUser[]>([]);
  useEffect(() => {
    api.suggestedCreators().then((r) => setUsers(r.users)).catch(() => setUsers([]));
  }, []);
  if (users.length === 0) return null;
  return (
    <section className="sec" style={{ padding: '6px 16px 14px' }}>
      <h4>People to follow</h4>
      <People users={users} fail={fail} />
    </section>
  );
}

function People({ users, fail }: { users: SocialUser[]; fail: (e: unknown) => void }) {
  const { me, toast } = useApp();
  const [list, setList] = useState(users);
  useEffect(() => setList(users), [users]);

  async function toggle(user: SocialUser) {
    if (!me) {
      toast('Sign in to follow people.', 'bad');
      return;
    }
    try {
      const r = await api.follow(user.username, !user.followed_by_me);
      setList((l) => l.map((u) => (u.id === user.id ? { ...u, followed_by_me: r.following } : u)));
    } catch (e) {
      fail(e);
    }
  }

  return (
    <ul className="people">
      {list.map((user) => (
        <li key={user.id} className="person">
          <Link to={`/u/${user.username}`} className="feed-who">
            <span className="avatar">{initials(user.display_name)}</span>
            <span>
              <b>{user.display_name}</b>
              <small>
                @{user.username}
                {user.posts ? ` · ${user.posts} posts and places` : ''}
              </small>
            </span>
          </Link>
          {!user.is_me && (
            <button
              type="button"
              className={`btn btn-sm ${user.followed_by_me ? 'btn-ghost' : 'btn-primary'}`}
              aria-pressed={user.followed_by_me}
              onClick={() => void toggle(user)}
            >
              {user.followed_by_me ? 'Following' : 'Follow'}
            </button>
          )}
        </li>
      ))}
    </ul>
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
