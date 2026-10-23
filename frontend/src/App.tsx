/** Routes and the app shell (SPEC §8.1).
 *
 * One set of markup serves both widths. On a phone it is the design reference
 * exactly: a single column with the bottom bar. From 1100 px up, CSS turns the
 * same markup into a desktop layout -- a navigation rail on the left, the
 * screen's own header across the top, and content that uses the width instead
 * of a 430 px column stranded in the middle (styles/desktop.css).
 *
 * Watch gets the dark nav and no scrolling shell, because it is the one
 * full-bleed immersive surface (SPEC §12.1).
 */
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { BottomNav } from './components/BottomNav';
import { SideNav } from './components/SideNav';
import { Toasts } from './components/common';
import { Admin } from './screens/Admin';
import { AddMedia } from './screens/AddMedia';
import { AddPlace } from './screens/AddPlace';
import { AddPulse } from './screens/AddPulse';
import { Explore } from './screens/Explore';
import { Nearby } from './screens/Nearby';
import { PlacePage } from './screens/PlacePage';
import { Profile } from './screens/Profile';
import { Settings } from './screens/Settings';
import { ForgotPassword, ResetPassword } from './screens/Recover';
import { SignIn } from './screens/SignIn';
import { Watch } from './screens/Watch';
import { WriteSteps } from './screens/WriteSteps';
import { You } from './screens/You';

/** Screens that fill the viewport themselves and hide the standard chrome. */
const FULL_BLEED = ['/watch'];
const NO_NAV = ['/signin', '/forgot', '/reset', '/add/', '/settings', '/admin'];

/** A class per screen, so the desktop stylesheet can lay each one out on its
 *  own terms (a map wants the whole window; a deck wants a narrow column). */
function pageName(path: string): string {
  if (path === '/') return 'nearby';
  if (path.startsWith('/explore')) return 'explore';
  if (path.startsWith('/place/')) return 'place';
  if (path.startsWith('/you') || path.startsWith('/u/')) return 'you';
  if (path.startsWith('/settings')) return 'settings';
  if (path.startsWith('/add/')) return 'add';
  if (['/signin', '/forgot', '/reset'].some((prefix) => path.startsWith(prefix))) return 'signin';
  if (path.startsWith('/admin')) return 'admin';
  return 'other';
}

export function App() {
  const location = useLocation();
  const path = location.pathname;

  const fullBleed = FULL_BLEED.some((prefix) => path.startsWith(prefix));
  const hideNav = NO_NAV.some((prefix) => path.startsWith(prefix)) || path.includes('/steps/new');

  return (
    <div className={`shell shell-${pageName(path)}`}>
      <SideNav />
      <div className={`app ${fullBleed ? 'app-fixed' : ''} app-${pageName(path)}`.trim()}>
        <Toasts />

        {fullBleed ? (
          <>
            <main>
              <Routes>
                <Route path="/watch" element={<Watch />} />
              </Routes>
            </main>
            <BottomNav dark />
          </>
        ) : (
          <div className={`scr page-${pageName(path)}`}>
            <main>
              <Routes>
                <Route path="/" element={<Nearby />} />
                <Route path="/explore" element={<Explore />} />
                <Route path="/place/:id" element={<PlacePage />} />
                <Route path="/place/:id/pulse" element={<AddPulse />} />
                <Route path="/place/:id/steps/new" element={<WriteSteps />} />
                <Route path="/add/place" element={<AddPlace />} />
                <Route path="/add/media" element={<AddMedia />} />
                <Route path="/add/pulse" element={<AddPulse />} />
                <Route path="/you" element={<You />} />
                <Route path="/u/:handle" element={<Profile />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/signin" element={<SignIn />} />
                <Route path="/forgot" element={<ForgotPassword />} />
                <Route path="/reset" element={<ResetPassword />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            {!hideNav && <BottomNav />}
          </div>
        )}
      </div>
    </div>
  );
}
