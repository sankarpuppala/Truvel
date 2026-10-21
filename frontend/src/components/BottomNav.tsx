/** The bottom bar: Nearby - Watch - (+) - Explore - You (SPEC §8.1).
 *
 * The (+) opens a sheet with the three ways to add something. It is a button,
 * not a link, because it opens a sheet rather than navigating.
 */
import { useState } from 'react';
import { NavLink } from 'react-router-dom';

import { AddSheet } from './AddSheet';
import { Icon } from './Icon';

const ITEMS = [
  { to: '/', icon: 'i-compass', label: 'Nearby' },
  { to: '/watch', icon: 'i-play', label: 'Watch' },
  { to: '/explore', icon: 'i-search', label: 'Explore' },
  { to: '/you', icon: 'i-passport', label: 'You' },
];

export function BottomNav({ dark = false }: { dark?: boolean }) {
  const [sheetOpen, setSheetOpen] = useState(false);

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

      <AddSheet open={sheetOpen} onClose={() => setSheetOpen(false)} />
    </>
  );
}
