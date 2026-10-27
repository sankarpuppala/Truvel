/** A public creator profile (SPEC §8.9).
 *
 * "Visits caused" is the headline number rather than follower count, because
 * that is what the app is actually trying to reward (SPEC §10.6).
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { EmptyState, Loading, Tabs } from '../components/common';
import { Icon, Scene, StatusBar } from '../components/Icon';
import { PlaceRow } from '../components/PlaceRow';
import { StampTile } from '../components/StudioParts';
import { categoryMeta, categoryScene } from '../lib/categories';
import { clock, date, num, num1, stampDate } from '../lib/format';
import type { Profile as ProfileData } from '../lib/types';

export function Profile() {
  const { handle } = useParams<{ handle: string }>();
  const navigate = useNavigate();
  const { me, toast } = useApp();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'reels' | 'photos' | 'visited' | 'found'>('reels');

  useEffect(() => {
    if (!handle) return;
    setLoading(true);
    void api
      .profile(handle)
      .then(setProfile)
      .catch((error) =>
        toast(error instanceof ApiError ? error.message : 'No such creator.', 'bad'),
      )
      .finally(() => setLoading(false));
  }, [handle, toast]);

  async function toggleFollow() {
    if (!profile) return;
    if (!me) {
      toast('Sign in to follow creators.', 'bad');
      return;
    }
    try {
      const result = await api.follow(profile.username, !profile.following);
      setProfile({
        ...profile,
        following: result.following,
        followers: profile.followers + (result.following ? 1 : -1),
      });
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  if (loading) return <Loading />;
  if (!profile) return null;

  const photos = profile.posts.filter((p) => p.kind === 'photo');
  const reels = profile.videos;
  const stamps = profile.stamps ?? [];

  return (
    <>
      <StatusBar />

      <div className="add-head">
        <button className="round round-flat" aria-label="Back" onClick={() => navigate(-1)}>
          <Icon name="i-back" size={20} />
        </button>
        <div>
          <div className="add-title">@{profile.username}</div>
          <div className="add-sub">
            {profile.level}
            {profile.partner && ' · Partner'}
          </div>
        </div>
      </div>

      <div className="scr-body">
        <div className="pp-head">
          <span className="avatar avatar-lg">{initials(profile.display_name)}</span>
          <div className="pp-id">
            <div className="pp-name">{profile.display_name}</div>
            <div className="pp-level">
              <Link to={`/following?user=${profile.username}&tab=followers`}>
                <b>{num(profile.followers)}</b> follower{profile.followers === 1 ? '' : 's'}
              </Link>{' '}
              &middot;{' '}
              <Link to={`/following?user=${profile.username}&tab=following`}>
                <b>{num(profile.following_count)}</b> following
              </Link>{' '}
              &middot; since {date(profile.created_at)}
            </div>
          </div>
          {!profile.is_self && (
            <button
              type="button"
              className={`btn btn-sm ${profile.following ? 'btn-ghost' : 'btn-primary'}`}
              aria-pressed={profile.following}
              onClick={() => void toggleFollow()}
            >
              {profile.following ? 'Following' : 'Follow'}
            </button>
          )}
        </div>

        {profile.bio && (
          <p className="pl-desc" style={{ padding: '0 16px 10px' }}>
            {profile.bio}
          </p>
        )}

        <div className="pp-cards">
          <div className="ppc">
            <b>{num(profile.places_found)}</b>
            <span>places found</span>
          </div>
          <div className="ppc">
            <b>{num1(profile.visits_caused)}</b>
            <span>visits caused</span>
            <small>lifetime</small>
          </div>
          <div className="ppc">
            <b>{num(reels.length)}</b>
            <span>reels</span>
          </div>
          <div className="ppc">
            <b>{num(photos.length)}</b>
            <span>photos</span>
          </div>
        </div>

        {profile.partner && (
          <div className="simbanner" role="note">
            <Icon name="i-check" size={17} />
            <span>
              <b>Partner Program member.</b> Earnings in this version are simulated; no money
              is paid.
            </span>
          </div>
        )}

        <Tabs
          label="Profile tabs"
          className="tabs-pp"
          value={tab}
          onChange={(val) => setTab(val as typeof tab)}
          options={[
            { key: 'reels', label: `Reels (${reels.length})` },
            { key: 'photos', label: `Photos (${photos.length})` },
            { key: 'visited', label: `Visited (${stamps.length})` },
            { key: 'found', label: `Found (${num(profile.places_found)})` },
          ]}
        />

        <div style={{ padding: '12px 0 24px' }}>
          {tab === 'reels' && (
            reels.length > 0 ? (
              <div className="vids" style={{ padding: '0 16px' }}>
                {reels.map((video) => (
                  <Link className="vid" key={video.id} to="/watch" aria-label={video.caption || 'Reel'}>
                    {video.poster ? (
                      <img className="vid-ph" src={video.poster} alt="" style={{ objectFit: 'cover' }} />
                    ) : (
                      <Scene name={categoryScene('other')} className="vid-ph" viewBox="60 0 280 500" />
                    )}
                    <i>
                      <Icon name="i-play" size={14} />
                      {clock(video.duration_s)}
                    </i>
                    <span>{video.caption || `@${profile.username}`}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState icon="i-video" title="No reels yet" body={`@${profile.username} hasn't posted any Watch reels yet.`} />
            )
          )}

          {tab === 'photos' && (
            photos.length > 0 ? (
              <div className="post-grid" style={{ padding: '0 16px' }}>
                {photos.map((post) => (
                  <Link key={post.id} to={`/place/${post.place_id}`} aria-label={post.caption || 'Photo'}>
                    <img src={post.thumb ?? post.url} alt="" loading="lazy" />
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState icon="i-camera" title="No photos yet" body={`@${profile.username} hasn't posted any photos yet.`} />
            )
          )}

          {tab === 'visited' && (
            stamps.length > 0 ? (
              <div className="stamps" style={{ padding: '0 16px' }}>
                {stamps.map((stamp, index) => {
                  const meta = categoryMeta(stamp.category);
                  return (
                    <Link to={`/place/${stamp.place_id}`} key={`${stamp.place_id}-${stamp.date}-${index}`}>
                      <StampTile
                        name={stamp.name}
                        icon={meta.icon}
                        date={stampDate(stamp.date)}
                        colour={meta.stampColour}
                        rotation={[-4, 3, -2, 2, -3, 4, -1, 2][index % 8]}
                      />
                    </Link>
                  );
                })}
              </div>
            ) : (
              <EmptyState icon="i-passport" title="No check-ins yet" body={`@${profile.username} hasn't checked in to any places yet.`} />
            )
          )}

          {tab === 'found' && (
            profile.found.length > 0 ? (
              <>
                {profile.places_found > profile.found.length && (
                  <div
                    style={{
                      padding: '8px 14px',
                      margin: '0 16px 8px',
                      borderRadius: '8px',
                      background: 'rgba(47, 93, 80, 0.08)',
                      fontSize: '0.82rem',
                      color: 'var(--ink-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    <Icon name="i-info" size={15} />
                    <span>
                      Showing latest {profile.found.length} of {num(profile.places_found)} places added
                    </span>
                  </div>
                )}
                <ol className="rows" style={{ flex: 'none' }}>
                  {profile.found.map((place) => (
                    <PlaceRow key={place.id} place={place} showRank={false} />
                  ))}
                </ol>
              </>
            ) : (
              <EmptyState icon="i-pin" title="No places added" body={`@${profile.username} hasn't added any places yet.`} />
            )
          )}
        </div>
      </div>
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
