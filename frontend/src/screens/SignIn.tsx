/** Sign in or create an account (SPEC §11).
 *
 * At sign-up the user grants a display licence for what they post while keeping
 * ownership of it (SPEC §14), and that is said plainly on this screen rather
 * than buried.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Icon, StatusBar } from '../components/Icon';

export function SignIn() {
  const navigate = useNavigate();
  const { setMe, toast } = useApp();
  const [mode, setMode] = useState<'in' | 'up'>('in');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result =
        mode === 'in'
          ? await api.login(username.trim().toLowerCase(), password)
          : await api.register(username.trim().toLowerCase(), password, displayName.trim());
      setMe(result.user);
      toast(mode === 'in' ? `Welcome back, @${result.user.username}` : 'Welcome to Pagdandi');
      navigate('/');
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'That did not work. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StatusBar />
      <div className="scr-body">
        <div className="form-page">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
            <svg width="44" height="44" viewBox="0 0 58 58" aria-hidden="true">
              <path
                d="M8 50C16 44 14 36 22 32S36 30 38 22 44 10 50 8"
                fill="none"
                stroke="var(--marigold)"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray="1 8"
              />
              <path
                d="M50 4.5c-3.6 0-6.5 2.9-6.5 6.4 0 4.7 6.5 10.6 6.5 10.6s6.5-5.9 6.5-10.6c0-3.5-2.9-6.4-6.5-6.4z"
                fill="var(--laterite)"
              />
              <circle cx="50" cy="11" r="2.3" fill="var(--paper)" />
            </svg>
            <h2 style={{ margin: 0 }}>Pagdandi</h2>
          </div>
          <p className="sub">
            Every city has places the map doesn&apos;t know. This is where locals share them.
          </p>

          <form onSubmit={submit}>
            <label className="field">
              <span>Username</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="3-20 letters, numbers or underscores"
                required
              />
            </label>

            {mode === 'up' && (
              <label className="field">
                <span>Your name (shown on what you post)</span>
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  autoComplete="name"
                  placeholder="Riya S."
                />
              </label>
            )}

            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === 'in' ? 'current-password' : 'new-password'}
                placeholder="At least 8 characters"
                required
                minLength={8}
              />
            </label>

            {error && (
              <p className="field-error" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="btn btn-primary btn-wide" disabled={busy}>
              {busy ? 'One moment…' : mode === 'in' ? 'Sign in' : 'Create my account'}
            </button>
          </form>

          <button
            type="button"
            className="btn btn-text btn-wide"
            style={{ marginTop: 8 }}
            onClick={() => {
              setMode((value) => (value === 'in' ? 'up' : 'in'));
              setError('');
            }}
          >
            {mode === 'in' ? 'New here? Create an account' : 'I already have an account'}
          </button>

          {mode === 'up' && (
            <p className="sub" style={{ marginTop: 14 }}>
              You keep ownership of your photos and videos. By posting, you let Pagdandi show
              them in the app with your name on them. We never store where you are.
            </p>
          )}

          <Link className="link link-sm" to="/" style={{ marginTop: 18 }}>
            <Icon name="i-compass" size={15} />
            Look around without an account
          </Link>
        </div>
      </div>
    </>
  );
}
