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
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { BottomNav } from './components/BottomNav';
import { SideNav } from './components/SideNav';
import { Loading } from './components/common';
import { Toasts } from './components/common';
import { Nearby } from './screens/Nearby';

// Every other screen is its own chunk, fetched the first time its route is
// visited (SPEC §15): the entry bundle used to carry Admin, Watch, every Add
// flow and Settings up front, which is most of what made the first paint of
// *any* page slow, not just the heavy ones (Watch already pays for MapLibre
// and turf as separate chunks -- see vite.config.ts).
const Admin = lazy(() => import('./screens/Admin').then((m) => ({ default: m.Admin })));
const AddMedia = lazy(() => import('./screens/AddMedia').then((m) => ({ default: m.AddMedia })));
const AddPlace = lazy(() => import('./screens/AddPlace').then((m) => ({ default: m.AddPlace })));
const AddPulse = lazy(() => import('./screens/AddPulse').then((m) => ({ default: m.AddPulse })));
const Explore = lazy(() => import('./screens/Explore').then((m) => ({ default: m.Explore })));
const PlacePage = lazy(() => import('./screens/PlacePage').then((m) => ({ default: m.PlacePage })));
const Following = lazy(() => import('./screens/Following').then((m) => ({ default: m.Following })));
const Profile = lazy(() => import('./screens/Profile').then((m) => ({ default: m.Profile })));
const Settings = lazy(() => import('./screens/Settings').then((m) => ({ default: m.Settings })));
const ForgotPassword = lazy(() =>
  import('./screens/Recover').then((m) => ({ default: m.ForgotPassword })),
);
const ResetPassword = lazy(() =>
  import('./screens/Recover').then((m) => ({ default: m.ResetPassword })),
);
const SignIn = lazy(() => import('./screens/SignIn').then((m) => ({ default: m.SignIn })));
const Watch = lazy(() => import('./screens/Watch').then((m) => ({ default: m.Watch })));
const WriteSteps = lazy(() =>
  import('./screens/WriteSteps').then((m) => ({ default: m.WriteSteps })),
);
const You = lazy(() => import('./screens/You').then((m) => ({ default: m.You })));

/** Screens that fill the viewport themselves and hide the standard chrome. */
const FULL_BLEED = ['/watch'];
const NO_NAV = ['/signin', '/forgot', '/reset', '/add/', '/settings', '/admin'];

/** A class per screen, so the desktop stylesheet can lay each one out on its
 *  own terms (a map wants the whole window; a deck wants a narrow column). */
function pageName(path: string): string {
  if (path === '/') return 'nearby';
  if (path.startsWith('/explore')) return 'explore';
  if (path.startsWith('/place/')) return 'place';
  if (path.startsWith('/you') || path.startsWith('/u/') || path.startsWith('/following')) return 'you';
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
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/watch" element={<Watch />} />
              </Routes>
            </Suspense>
            <BottomNav dark />
          </>
        ) : (
          // The screen itself is the <main> landmark: an extra wrapper here would
          // break every `.scr > …` layout rule (scrolling, the Place split).
          <main className={`scr page-${pageName(path)}`}>
            <Suspense fallback={<Loading />}>
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
                <Route path="/users/:handle" element={<Profile />} />
                <Route path="/following" element={<Following />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/signin" element={<SignIn />} />
                <Route path="/forgot" element={<ForgotPassword />} />
                <Route path="/reset" element={<ResetPassword />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
            {!hideNav && <BottomNav />}
          </main>
        )}
      </div>
    </div>
  );
}
