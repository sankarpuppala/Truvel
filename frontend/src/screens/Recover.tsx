/** Forgotten password: ask for a link, then choose a new password (SPEC §11).
 *
 * The first screen says the same thing whether or not the address has an
 * account, so it cannot be used to find out who does. The link in the email
 * carries a one-use token that the server checks and expires after an hour.
 */
import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Icon, StatusBar } from '../components/Icon';
import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';

const MIN_PASSWORD = 8;

export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.forgotPassword(email.trim().toLowerCase());
      setSent(true);
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
        <div className="form-page auth-page">
          <h1 className="auth-word">Reset your password</h1>
          {sent ? (
            <p className="auth-note" role="status">
              If an account uses {email.trim()}, a reset link is on its way. It works for one
              hour and only once.
            </p>
          ) : (
            <form onSubmit={submit} noValidate>
              <div className="field">
                <label htmlFor="forgot-email">Email</label>
                <input
                  id="forgot-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  placeholder="you@example.com"
                  required
                />
              </div>
              {error && (
                <p className="auth-error" role="alert">
                  <Icon name="i-warn" size={16} />
                  {error}
                </p>
              )}
              <button
                type="submit"
                className="btn btn-primary btn-wide"
                disabled={busy || !email.includes('@')}
              >
                {busy ? 'One moment...' : 'Send reset link'}
              </button>
            </form>
          )}
          <p className="auth-alt">
            <Link to="/signin">Back to sign in</Link>
          </p>
        </div>
      </div>
    </>
  );
}

export function ResetPassword() {
  const navigate = useNavigate();
  const { setMe, toast } = useApp();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api.resetPassword(token, password);
      setMe(result.user);
      toast('Password changed. You are signed in.');
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
        <div className="form-page auth-page">
          <h1 className="auth-word">Choose a new password</h1>
          {!token ? (
            <p className="auth-error" role="alert">
              <Icon name="i-warn" size={16} />
              This link is missing its code. Open it again from the email, or ask for a new one.
            </p>
          ) : (
            <form onSubmit={submit} noValidate>
              <div className="field">
                <label htmlFor="new-password">New password</label>
                <span className="field-pw">
                  <input
                    id="new-password"
                    type={reveal ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                    required
                  />
                  <button
                    type="button"
                    className="field-reveal"
                    aria-pressed={reveal}
                    aria-label={reveal ? 'Hide password' : 'Show password'}
                    onClick={() => setReveal((value) => !value)}
                  >
                    {reveal ? 'Hide' : 'Show'}
                  </button>
                </span>
                <small className="field-help">At least {MIN_PASSWORD} characters.</small>
              </div>
              {error && (
                <p className="auth-error" role="alert">
                  <Icon name="i-warn" size={16} />
                  {error}
                </p>
              )}
              <button
                type="submit"
                className="btn btn-primary btn-wide"
                disabled={busy || password.length < MIN_PASSWORD}
              >
                {busy ? 'One moment...' : 'Change password'}
              </button>
            </form>
          )}
          <p className="auth-alt">
            <Link to="/forgot">Ask for a new link</Link>
          </p>
        </div>
      </div>
    </>
  );
}
