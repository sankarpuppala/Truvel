/** Sign in or create an account (SPEC §11).
 *
 * The rules this screen follows, and why:
 *
 *  - You sign in with an email address or your handle, because people remember
 *    one or the other, not reliably both.
 *  - Password requirements are shown *before* you are told you failed them,
 *    and they are length and a blocklist rather than forced symbols, which is
 *    what NIST SP 800-63B recommends and what actually produces strong
 *    passwords instead of "Password1!".
 *  - The server returns one message for a wrong email and a wrong password, so
 *    this page cannot be used to find out who has an account.
 *  - Nothing is checked only in the browser. Every rule here is enforced again
 *    in `auth.py`; this is to save you a round trip, not to be the gate.
 *  - At sign-up you grant a display licence for what you post while keeping
 *    ownership of it (SPEC §14), said plainly rather than buried.
 */
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Icon, StatusBar } from '../components/Icon';
import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';

const MIN_PASSWORD = 8;
/** Mirrors `EMAIL_RE` in auth.py: one @, something either side, a dot after. */
const EMAIL_RE = /^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/;
const HANDLE_RE = /^[a-z0-9_]{3,20}$/;

type Mode = 'in' | 'up';

/** What the password still needs, in the order a person meets it. */
function passwordChecks(password: string, email: string, handle: string) {
  const folded = password.toLowerCase();
  const local = email.split('@')[0].toLowerCase();
  const containsOwnName = [local, handle.toLowerCase()].some(
    (own) => own.length >= 3 && folded.includes(own),
  );
  return [
    { ok: password.length >= MIN_PASSWORD, text: `At least ${MIN_PASSWORD} characters` },
    { ok: password.length === 0 || !containsOwnName, text: 'Not your name or email' },
  ];
}

export function SignIn() {
  const navigate = useNavigate();
  const { setMe, toast } = useApp();

  const [mode, setMode] = useState<Mode>('in');
  const [identifier, setIdentifier] = useState('');
  const [email, setEmail] = useState('');
  const [handle, setHandle] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [touched, setTouched] = useState(false);

  const checks = useMemo(
    () => passwordChecks(password, email, handle),
    [password, email, handle],
  );

  const emailBad = touched && mode === 'up' && email.length > 0 && !EMAIL_RE.test(email.trim());
  const handleBad = touched && mode === 'up' && handle.length > 0 && !HANDLE_RE.test(handle.trim());

  const canSubmit =
    !busy &&
    password.length > 0 &&
    (mode === 'in'
      ? identifier.trim().length > 0
      : EMAIL_RE.test(email.trim()) &&
        HANDLE_RE.test(handle.trim()) &&
        checks.every((check) => check.ok));

  function switchMode(next: Mode) {
    setMode(next);
    setError('');
    setTouched(false);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!canSubmit) return;

    setBusy(true);
    setError('');
    try {
      const result =
        mode === 'in'
          ? await api.login(identifier.trim().toLowerCase(), password)
          : await api.register({
              email: email.trim().toLowerCase(),
              username: handle.trim().toLowerCase(),
              password,
              display_name: displayName.trim(),
            });
      setMe(result.user);
      toast(
        mode === 'in'
          ? `Welcome back, @${result.user.username}`
          : `Welcome to Truvel, @${result.user.username}`,
      );
      navigate('/');
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'That did not work. Try again.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StatusBar />
      <div className="scr-body">
        <div className="form-page auth-page">
          <div className="auth-brand">
            <svg width="46" height="46" viewBox="0 0 58 58" aria-hidden="true">
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
            <div>
              <h1 className="auth-word">Truvel</h1>
              <p className="auth-tag">Discover Hidden India</p>
            </div>
          </div>

          <div className="seg seg-full auth-seg" role="tablist" aria-label="Sign in or join">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'in'}
              className={mode === 'in' ? 'on' : ''}
              onClick={() => switchMode('in')}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'up'}
              className={mode === 'up' ? 'on' : ''}
              onClick={() => switchMode('up')}
            >
              Create account
            </button>
          </div>

          <form onSubmit={submit} noValidate>
            {mode === 'in' ? (
              <div className="field">
                <label htmlFor="identifier">Email or handle</label>
                <input
                  id="identifier"
                  type="text"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  autoComplete="username"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  placeholder="you@example.com"
                  required
                />
              </div>
            ) : (
              <>
                <div className="field">
                  <label htmlFor="email">Email</label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    onBlur={() => setTouched(true)}
                    autoComplete="email"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    placeholder="you@example.com"
                    aria-invalid={emailBad || undefined}
                    aria-describedby={emailBad ? 'email-help' : undefined}
                    required
                  />
                  {emailBad && (
                    <small id="email-help" className="field-bad">
                      That does not look like an email address.
                    </small>
                  )}
                </div>

                <div className="field">
                  <label htmlFor="handle">Handle</label>
                  <input
                    id="handle"
                    type="text"
                    value={handle}
                    onChange={(event) => setHandle(event.target.value.toLowerCase())}
                    onBlur={() => setTouched(true)}
                    autoComplete="username"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    placeholder="arjun_r"
                    maxLength={20}
                    aria-invalid={handleBad || undefined}
                    aria-describedby="handle-help"
                    required
                  />
                  <small
                    id="handle-help"
                    className={handleBad ? 'field-bad' : 'field-help'}
                  >
                    {handleBad
                      ? '3 to 20 characters: lowercase letters, numbers or underscores.'
                      : 'What other people see, like @arjun_r.'}
                  </small>
                </div>

                <div className="field">
                  <label htmlFor="display-name">
                    Display name <small className="field-opt">optional</small>
                  </label>
                  <input
                    id="display-name"
                    type="text"
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    autoComplete="name"
                    placeholder="Riya S."
                    maxLength={60}
                  />
                </div>
              </>
            )}

            <div className="field">
              <label htmlFor="password">Password</label>
              {/* The reveal button sits outside the label on purpose: inside
                  it, its text becomes part of the input's accessible name and
                  a screen reader announces "Password Show". */}
              <span className="field-pw">
                <input
                  id="password"
                  type={reveal ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={mode === 'in' ? 'current-password' : 'new-password'}
                  aria-describedby={mode === 'up' ? 'pw-rules' : undefined}
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
            </div>

            {mode === 'up' && (
              <ul className="pw-rules" id="pw-rules">
                {checks.map((check) => (
                  <li key={check.text} className={check.ok ? 'ok' : ''}>
                    <Icon name={check.ok ? 'i-check' : 'i-info'} size={14} />
                    {check.text}
                  </li>
                ))}
              </ul>
            )}

            {error && (
              <p className="auth-error" role="alert">
                <Icon name="i-warn" size={16} />
                {error}
              </p>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-wide"
              disabled={!canSubmit}
            >
              {busy
                ? 'One moment...'
                : mode === 'in'
                  ? 'Sign in'
                  : 'Create account'}
            </button>
          </form>

          {mode === 'up' ? (
            <p className="auth-note">
              By creating an account you let Truvel show what you post, while it stays
              yours (SPEC §14). Your email is used to sign you in and to reach you about
              your account; it is never shown to anyone else.
            </p>
          ) : (
            <p className="auth-note">
              <Link to="/forgot">Forgot your password?</Link>
            </p>
          )}

          <p className="auth-alt">
            <Link to="/">Keep looking around without an account</Link>
          </p>
        </div>
      </div>
    </>
  );
}
