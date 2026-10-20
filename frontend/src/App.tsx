/** Routes and the app shell (SPEC §8.1).
 *
 * Watch gets the dark nav and no scrolling shell, because it is the one
 * full-bleed immersive surface (SPEC §12.1). Everything else sits in the
 * standard column with the bottom bar.
 */
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { BottomNav } from './components/BottomNav';
import { DevTools } from './components/DevTools';
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
import { SignIn } from './screens/SignIn';
import { Watch } from './screens/Watch';
import { WriteSteps } from './screens/WriteSteps';
import { You } from './screens/You';

/** Screens that fill the viewport themselves and hide the standard chrome. */
const FULL_BLEED = ['/watch'];
const NO_NAV = ['/signin', '/add/', '/settings', '/admin'];

export function App() {
  const location = useLocation();
  const path = location.pathname;

  const fullBleed = FULL_BLEED.some((prefix) => path.startsWith(prefix));
  const hideNav = NO_NAV.some((prefix) => path.startsWith(prefix)) || path.includes('/steps/new');
  const dark = fullBleed;

  return (
    <div className="app">
      <Toasts />

      {fullBleed ? (
        <Routes>
          <Route path="/watch" element={<Watch />} />
        </Routes>
      ) : (
        <div className="scr">
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
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          {/* The dev simulator sits just above the nav, so it never pushes a
              screen's own layout around (and it does not exist in production). */}
          <DevTools />
          {!hideNav && <BottomNav />}
        </div>
      )}

      {fullBleed && <BottomNav dark={dark} />}
    </div>
  );
}
