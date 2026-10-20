/** The bottom bar: Nearby - Watch - (+) - Explore - You (SPEC §8.1).
 *
 * The (+) opens a sheet with the three ways to add something. It is a button,
 * not a link, because it opens a sheet rather than navigating.
 */
import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

import { useApp } from '../lib/app-state';
import { BottomSheet } from './common';
import { Icon } from './Icon';

const ITEMS = [
  { to: '/', icon: 'i-compass', label: 'Nearby' },
  { to: '/watch', icon: 'i-play', label: 'Watch' },
  { to: '/explore', icon: 'i-search', label: 'Explore' },
  { to: '/you', icon: 'i-passport', label: 'You' },
];

export function BottomNav({ dark = false }: { dark?: boolean }) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const navigate = useNavigate();
  const { me, toast } = useApp();

  function go(path: string) {
    setSheetOpen(false);
    if (!me) {
      toast('Sign in to add a place.', 'bad');
      navigate('/signin');
      return;
    }
    navigate(path);
  }

  return (
    <>
      <nav className={`nav ${dark ? 'nav-dark' : ''}`.trim()} aria-label="Main">
        {ITEMS.slice(0, 2).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => (isActive ? 'on' : '')}
          >
            <Icon name={item.icon} size={22} />
            <span>{item.label}</span>
          </NavLink>
        ))}

        <span className="nav-add-wrap">
          <button
            type="button"
            className="nav-add"
            aria-label="Add a place, photos or a live report"
            aria-expanded={sheetOpen}
            onClick={() => setSheetOpen(true)}
          >
            <Icon name="i-plus" size={26} />
          </button>
        </span>

        {ITEMS.slice(2).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? 'on' : '')}
          >
            <Icon name={item.icon} size={22} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <BottomSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        title="Add to Pagdandi"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button type="button" className="cand" onClick={() => go('/add/place')}>
            <span className="mini">
              <Icon name="i-pin" size={18} />
            </span>
            <div>
              <b>A new place</b>
              <span>Somewhere the app doesn&apos;t know yet</span>
            </div>
            <Icon name="i-chevr" size={18} />
          </button>

          <button type="button" className="cand" onClick={() => go('/add/media')}>
            <span className="mini">
              <Icon name="i-camera" size={18} />
            </span>
            <div>
              <b>Photos or a video of a place</b>
              <span>Add to a place that is already here</span>
            </div>
            <Icon name="i-chevr" size={18} />
          </button>

          <button type="button" className="cand" onClick={() => go('/add/pulse')}>
            <span className="mini">
              <Icon name="i-drop" size={18} />
            </span>
            <div>
              <b>How is it right now?</b>
              <span>On-site only, within 2 hours of checking in</span>
            </div>
            <Icon name="i-chevr" size={18} />
          </button>
        </div>
      </BottomSheet>
    </>
  );
}
