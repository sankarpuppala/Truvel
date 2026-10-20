/** A public creator profile (SPEC §8.9).
 *
 * "Visits caused" is the headline number rather than follower count, because
 * that is what the app is actually trying to reward (SPEC §10.6).
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { EmptyState, Loading } from '../components/common';
import { Icon, Scene, StatusBar } from '../components/Icon';
import { PlaceRow } from '../components/PlaceRow';
import { categoryScene } from '../lib/categories';
import { clock, date, num, num1 } from '../lib/format';
import type { Profile as ProfileData } from '../lib/types';

export function Profile() {
  const { handle } = useParams<{ handle: string }>();
  const navigate = useNavigate();
  const { me, toast } = useApp();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);

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
              {num(profile.followers)} follower{profile.followers === 1 ? '' : 's'} &middot; since{' '}
              {date(profile.created_at)}
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
            <b>{num(profile.videos.length)}</b>
            <span>videos</span>
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

        {profile.videos.length > 0 && (
          <section className="sec" style={{ padding: '0 16px 14px' }}>
            <h4>Videos</h4>
            <div className="vids">
              {profile.videos.map((video) => (
                <Link className="vid" key={video.id} to="/watch" aria-label={video.caption}>
                  {video.poster ? (
                    <img className="vid-ph" src={video.poster} alt="" style={{ objectFit: 'cover' }} />
                  ) : (
                    <Scene name={categoryScene('other')} className="vid-ph" viewBox="60 0 280 500" />
                  )}
                  <i>
                    <Icon name="i-play" size={14} />
                    {clock(video.duration_s)}
                  </i>
                  <span>@{profile.username}</span>
                </Link>
              ))}
            </div>
          </section>
        )}

        {profile.found.length > 0 ? (
          <section className="sec" style={{ padding: '0 0 14px' }}>
            <h4 style={{ padding: '0 16px' }}>Places they found</h4>
            <ol className="rows" style={{ flex: 'none' }}>
              {profile.found.map((place) => (
                <PlaceRow key={place.id} place={place} showRank={false} />
              ))}
            </ol>
          </section>
        ) : (
          profile.videos.length === 0 && (
            <EmptyState icon="i-compass" title="Nothing posted yet" />
          )
        )}
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
