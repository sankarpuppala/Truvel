/** The laptop sidebar (SPEC §8.1 on a wide screen).
 *
 * The phone's bottom bar cannot simply be stretched across a 1440 px window:
 * five targets in a row read as a toolbar with nothing to do. On a laptop the
 * same five destinations become a rail down the left, which is where a person
 * using a mouse expects them, and the screen keeps its full width for content.
 *
 * It is hidden under 1100 px (styles/desktop.css), where the bottom bar takes
 * over, so there is exactly one visible navigation at any width.
 */
import { useState } from 'react';
import { NavLink } from 'react-router-dom';

import { initials } from '../lib/format';
import { useApp } from '../lib/app-state';
import { AddSheet } from './AddSheet';
import { Icon } from './Icon';

const ITEMS = [
  { to: '/', icon: 'i-compass', label: 'Nearby', note: 'Places around you' },
  { to: '/watch', icon: 'i-play', label: 'Watch', note: 'Places on video' },
  { to: '/explore', icon: 'i-search', label: 'Explore', note: 'Search a city' },
  { to: '/you', icon: 'i-passport', label: 'You', note: 'Passport & Studio' },
];

export function SideNav() {
  const [sheetOpen, setSheetOpen] = useState(false);
  const { me } = useApp();

  return (
    <>
      <aside className="siderail" aria-label="Truvel">
        <NavLink to="/" className="side-logo" aria-label="Truvel, home">
          <svg width="40" height="40" viewBox="0 0 58 58" aria-hidden="true">
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
          <span className="side-word">
            Truvel
            <small>Discover Hidden India</small>
          </span>
        </NavLink>

        <nav className="side-nav" aria-label="Main">
          {ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `side-link ${isActive ? 'on' : ''}`.trim()}
            >
              <Icon name={item.icon} size={22} />
              <span className="side-link-t">
                <b>{item.label}</b>
                <small>{item.note}</small>
              </span>
            </NavLink>
          ))}
        </nav>

        <button type="button" className="side-add" onClick={() => setSheetOpen(true)}>
          <Icon name="i-plus" size={20} />
          Add a place
        </button>

        <div className="side-foot">
          {me ? (
            <NavLink to="/you" className="side-me">
              <span className="avatar">{initials(me.display_name)}</span>
              <span className="side-link-t">
                <b>{me.display_name}</b>
                <small>{me.kadam} kadam</small>
              </span>
            </NavLink>
          ) : (
            <NavLink to="/signin" className="btn btn-ghost btn-sm side-signin">
              Sign in
            </NavLink>
          )}
          <p className="side-note">
            Place data © OpenStreetMap contributors. Earnings in this version are
            simulated — no real money is paid.
          </p>
        </div>
      </aside>

      <AddSheet open={sheetOpen} onClose={() => setSheetOpen(false)} />
    </>
  );
}
