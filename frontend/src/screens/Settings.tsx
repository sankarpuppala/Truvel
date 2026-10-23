/** Languages & cities, plus theme and account. Reference screen 9 (SPEC §7.3).
 *
 * The important honesty here: **a UI language switches on only after a native
 * speaker has checked it.** Everything else is listed with its real status --
 * available, in native review, or not yet -- and the ones that are not ready
 * cannot be selected (CLAUDE.md invariant 11). Place names, by contrast,
 * already appear in all 22 languages wherever the data has them, and the note
 * at the bottom says exactly that so nobody confuses the two.
 *
 * Every language's own name is written in its own script, which is also the
 * glyph test for AC-4: if a font is missing, this screen shows it.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { LANGUAGES } from '../lib/languages';
import { useApp } from '../lib/app-state';
import { Loading, Segmented } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import type { City } from '../lib/types';

/** City names in their own scripts, as the reference shows them. */
const CITY_SCRIPTS: Record<string, { text: string; lang: string; rtl?: boolean }> = {
  hyderabad: { text: 'హైదరాబాద్', lang: 'te' },
  chennai: { text: 'சென்னை', lang: 'ta' },
  bengaluru: { text: 'ಬೆಂಗಳೂರು', lang: 'kn' },
  kochi: { text: 'കൊച്ചി', lang: 'ml' },
  mumbai: { text: 'मुंबई', lang: 'mr' },
  kolkata: { text: 'কলকাতা', lang: 'bn' },
  ahmedabad: { text: 'અમદાવાદ', lang: 'gu' },
  amritsar: { text: 'ਅੰਮਿਰਤਸਰ', lang: 'pa' },
  bhubaneswar: { text: 'ଭୁବନେଶ୍ୱର', lang: 'or' },
  guwahati: { text: 'গুৱাহাটী', lang: 'as' },
  imphal: { text: 'ꯀꯣꯍꯩꯆꯣꯁ', lang: 'mni' },
  srinagar: { text: 'سری نگر', lang: 'ur', rtl: true },
};

export function Settings() {
  const navigate = useNavigate();
  const { me, loadingMe, refreshMe, theme, setTheme, toast, logout } = useApp();

  const [settings, setSettings] = useState<{
    names_mode: string;
    names_lang: string;
    ui_lang: string;
    home_city_id: number | null;
    languages: string[];
    ui_available: string[];
    ui_in_review: string[];
  } | null>(null);
  const [cities, setCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Wait for the session check to finish: on a fresh page load `me` is null
    // for a moment while /api/me is in flight, and redirecting then would bounce
    // a signed-in user to the sign-in screen.
    if (loadingMe) return;
    if (!me) {
      navigate('/signin');
      return;
    }
    void Promise.all([api.settings(), api.cities()])
      .then(([settingsData, citiesData]) => {
        setSettings(settingsData);
        setCities(citiesData.cities);
      })
      .catch(() => toast('Could not load your settings.', 'bad'))
      .finally(() => setLoading(false));
  }, [me, loadingMe, navigate, toast]);

  async function save(patch: Record<string, unknown>) {
    try {
      const updated = (await api.saveSettings(patch)) as typeof settings;
      setSettings(updated);
      await refreshMe();
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not save.', 'bad');
    }
  }

  if (loading || !settings) return <Loading what="Loading settings" />;

  const myLang =
    LANGUAGES.find((entry) => entry.code === settings.names_lang) ?? LANGUAGES[2];

  return (
    <>
      <StatusBar />

      <div className="lg-head">
        <button className="round round-flat" aria-label="Back" onClick={() => navigate(-1)}>
          <Icon name="i-back" size={20} />
        </button>
        <h3>Languages &amp; cities</h3>
      </div>

      <div className="scr-body">
        {/* Place names: the three modes from SPEC §7.2. */}
        <section className="lsec">
          <h4>Place names</h4>
          <div className="opts">
            <label className={`opt ${settings.names_mode === 'en_local' ? 'on' : ''}`.trim()}>
              <input
                type="radio"
                name="names_mode"
                className="sr-only"
                checked={settings.names_mode === 'en_local'}
                onChange={() => void save({ names_mode: 'en_local' })}
              />
              <span className={`radio ${settings.names_mode === 'en_local' ? 'on' : ''}`.trim()} />
              <div>
                <b>English + local script</b>
                <span className="prev">
                  Golconda Fort &middot;{' '}
                  <span lang="te">
                    {'గోల్కొండ కోట'}
                  </span>
                </span>
              </div>
            </label>

            <label className={`opt ${settings.names_mode === 'mine_local' ? 'on' : ''}`.trim()}>
              <input
                type="radio"
                name="names_mode"
                className="sr-only"
                checked={settings.names_mode === 'mine_local'}
                onChange={() => void save({ names_mode: 'mine_local' })}
              />
              <span className={`radio ${settings.names_mode === 'mine_local' ? 'on' : ''}`.trim()} />
              <div>
                <b>My language + local script</b>
                <span className="prev">
                  The name in {myLang.english}, then the place&apos;s own script
                </span>
                <select
                  className="chip-sm chip-lang"
                  value={settings.names_lang}
                  onChange={(event) => void save({ names_lang: event.target.value })}
                  aria-label="Your language for place names"
                >
                  {LANGUAGES.filter((entry) => settings.languages.includes(entry.code)).map(
                    (entry) => (
                      <option key={entry.code} value={entry.code} lang={entry.code}>
                        {entry.autonym}
                      </option>
                    ),
                  )}
                </select>
              </div>
            </label>

            <label className={`opt ${settings.names_mode === 'en' ? 'on' : ''}`.trim()}>
              <input
                type="radio"
                name="names_mode"
                className="sr-only"
                checked={settings.names_mode === 'en'}
                onChange={() => void save({ names_mode: 'en' })}
              />
              <span className={`radio ${settings.names_mode === 'en' ? 'on' : ''}`.trim()} />
              <div>
                <b>English only</b>
                <span className="prev">Golconda Fort</span>
              </div>
            </label>
          </div>
        </section>

        {/* Your city. */}
        <section className="lsec">
          <h4>Your city</h4>
          <div className="cities">
            {cities.map((city) => {
              const script = CITY_SCRIPTS[city.slug];
              const chosen = settings.home_city_id === city.id;
              return (
                <button
                  type="button"
                  key={city.id}
                  className={`ct ${chosen ? 'on' : ''}`.trim()}
                  onClick={() => void save({ home_city_id: city.id })}
                  aria-pressed={chosen}
                >
                  <b>{city.name}</b>
                  {script &&
                    (script.rtl ? (
                      <span lang={script.lang} dir="rtl">
                        <bdi>{script.text}</bdi>
                      </span>
                    ) : (
                      <span lang={script.lang}>{script.text}</span>
                    ))}
                  {chosen && (
                    <span className="ct-chk">
                      <Icon name="i-check" size={13} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </section>

        {/* App language. Only reviewed languages can be chosen (invariant 11). */}
        <section className="lsec">
          <h4>App language</h4>
          <div className="lchips">
            {LANGUAGES.map((entry) => {
              const available = settings.ui_available.includes(entry.code);
              const inReview = settings.ui_in_review.includes(entry.code);
              const chosen = settings.ui_lang === entry.code;
              const className = chosen
                ? 'lc lc-on'
                : inReview
                  ? 'lc lc-review'
                  : available
                    ? 'lc'
                    : 'lc lc-no';
              return (
                <button
                  type="button"
                  key={entry.code}
                  className={className}
                  lang={entry.code}
                  dir={entry.rtl ? 'rtl' : undefined}
                  disabled={!available}
                  aria-pressed={chosen}
                  title={
                    available
                      ? `Use ${entry.english}`
                      : inReview
                        ? `${entry.english} is being checked by a native speaker`
                        : `${entry.english} is not translated yet`
                  }
                  onClick={() => void save({ ui_lang: entry.code })}
                >
                  {entry.rtl ? <bdi>{entry.autonym}</bdi> : entry.autonym}
                </button>
              );
            })}
          </div>

          <div className="llegend">
            <span>
              <i className="lk lk-on" />
              Available
            </span>
            <span>
              <i className="lk lk-review" />
              In native review
            </span>
            <span>
              <i className="lk lk-no" />
              Not yet
            </span>
          </div>

          <p className="lnote">
            Place names already appear in all 22 languages wherever OpenStreetMap, Wikidata or
            visitors have them. The app&apos;s own words switch language only after a native
            speaker has checked them.
          </p>
        </section>

        {/* Theme. */}
        <section className="lsec">
          <h4>Theme</h4>
          <Segmented
            label="Theme"
            className="seg-full"
            value={theme}
            onChange={(key) => {
              setTheme(key);
              void save({ theme: key });
            }}
            options={[
              { key: 'system', label: 'System' },
              { key: 'light', label: 'Light' },
              { key: 'dark', label: 'Dark' },
            ]}
          />
        </section>

        {/* Account. */}
        <section className="lsec">
          <h4>Account</h4>
          <p className="plain" style={{ marginBottom: 10 }}>
            Signed in as <b>@{me?.username}</b>
            {me?.role === 'admin' && ' (admin)'}
          </p>
          {me?.role === 'admin' && (
            <button
              type="button"
              className="btn btn-ghost btn-wide"
              style={{ marginBottom: 8 }}
              onClick={() => navigate('/admin')}
            >
              Admin queue
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost btn-wide"
            onClick={() => {
              void logout().then(() => navigate('/'));
            }}
          >
            Sign out
          </button>
        </section>

        <p className="pp-note">
          We never store where you are. A check-in sends one position reading, the server keeps
          only how far away you were and how accurate it was, and the coordinates are thrown
          away.
        </p>
      </div>
    </>
  );
}
