/** You -- Passport and Studio. Reference screens 7 and 8 (SPEC §8.9, §8.10).
 *
 * The Passport is the record of where you have actually been: stamps, the
 * weekly streak, places you found, what you saved, and the kadam ledger with a
 * reason on every line.
 *
 * The Studio is the creator side. Its banner says the earnings are simulated
 * and cannot be dismissed, and every rupee figure carries the Simulated tag
 * (SPEC §10.5, AC-23).
 */
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import {
  BottomSheet,
  DashedProgress,
  EmptyState,
  Loading,
  Segmented,
  Tabs,
} from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { PlaceRow } from '../components/PlaceRow';
import {
  EarningsCard,
  EmptyStamp,
  MetricCard,
  PartnerChecklist,
  SimulatedBanner,
  StampTile,
  TopContentTable,
} from '../components/StudioParts';
import { categoryMeta } from '../lib/categories';
import { ago, hours, num, num1, stampDate } from '../lib/format';
import type { Passport, Studio } from '../lib/types';

type PassportTab = 'stamps' | 'found' | 'want' | 'kadam';

export function You() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { me, loadingMe, toast } = useApp();

  const view = (params.get('view') === 'studio' ? 'studio' : 'passport') as
    | 'passport'
    | 'studio';
  const [tab, setTab] = useState<PassportTab>('stamps');
  const [passport, setPassport] = useState<Passport | null>(null);
  const [studio, setStudio] = useState<Studio | null>(null);
  const [period, setPeriod] = useState(28);
  const [loading, setLoading] = useState(true);
  const [splitOpen, setSplitOpen] = useState(false);

  useEffect(() => {
    if (!loadingMe && !me) navigate('/signin');
  }, [loadingMe, me, navigate]);

  const load = useCallback(async () => {
    if (!me) return;
    setLoading(true);
    try {
      if (view === 'passport') setPassport(await api.passport());
      else setStudio(await api.studio(period));
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'Could not load that.', 'bad');
    } finally {
      setLoading(false);
    }
  }, [me, view, period, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!me) return <Loading />;

  const header = (
    <div className="you-top">
      <Segmented
        label="Passport or Studio"
        className="seg-full"
        value={view}
        onChange={(key) => setParams(key === 'studio' ? { view: 'studio' } : {}, { replace: true })}
        options={[
          { key: 'passport', label: 'Passport' },
          { key: 'studio', label: 'Studio' },
        ]}
      />
      <Link className="round round-flat" to="/following" aria-label="Following">
        <Icon name="i-group" size={20} />
      </Link>
      <Link className="round round-flat" to="/settings" aria-label="Settings">
        <Icon name="i-gear" size={20} />
      </Link>
    </div>
  );

  if (view === 'studio') {
    return (
      <>
        <StatusBar />
        {header}
        <div className="scr-body">
          {loading && !studio ? (
            <Loading what="Measuring your month" />
          ) : studio ? (
            <>
              <div className="st-period">
                <button
                  type="button"
                  className="chip-sm"
                  onClick={() => setPeriod((value) => (value === 7 ? 28 : value === 28 ? 90 : 7))}
                >
                  Last {period} days <Icon name="i-chev" size={14} />
                </button>
                <span className="st-who">
                  {studio.creator.display_name} &middot; {num(studio.creator.followers)} followers
                </span>
              </div>

              {/* Always present, never dismissible (AC-23). */}
              <SimulatedBanner />

              <div className="metrics">
                <MetricCard
                  title="Engaged views"
                  value={num(studio.metrics.engaged_views.value)}
                  deltaPct={studio.metrics.engaged_views.delta_pct}
                  spark={studio.sparklines.engaged_views}
                  sparkLabel="Engaged views per day"
                />
                <MetricCard
                  title="Watch time"
                  value={hours(studio.metrics.watch_time_h.value)}
                  deltaPct={studio.metrics.watch_time_h.delta_pct}
                  spark={studio.sparklines.watch_time_h}
                  sparkLabel="Watch time per day, in hours"
                />
                <MetricCard
                  title="Visits caused"
                  value={num1(studio.metrics.visits_caused.value)}
                  deltaPct={studio.metrics.visits_caused.delta_pct}
                  spark={studio.sparklines.visits_caused}
                  sparkLabel="Visits caused per day"
                  key_
                />
                <EarningsCard
                  paise={studio.metrics.estimated_earnings_paise}
                  projection={studio.metrics.earnings_are_projection}
                  spark={studio.sparklines.earnings}
                />
              </div>

              <PartnerChecklist
                requirements={studio.partner.requirements}
                done={studio.partner.done}
                total={studio.partner.total}
              />

              <TopContentTable
                items={studio.top_content}
                onExplain={() => setSplitOpen(true)}
              />

              {(studio.audience.cities.length > 0 || studio.audience.languages.length > 0) && (
                <section className="topc">
                  <div className="pt-h">
                    <b>Audience</b>
                    <span>where they are</span>
                  </div>
                  {studio.audience.cities.map((city) => (
                    <div className="tc" key={city.name}>
                      <div>
                        <b>{city.name}</b>
                      </div>
                      <em>{num(city.viewers)}</em>
                    </div>
                  ))}
                  {studio.audience.languages.length > 0 && (
                    <p className="plain" style={{ color: 'var(--muted)', marginTop: 8 }}>
                      Reading names in:{' '}
                      {studio.audience.languages.map((entry) => entry.lang).join(', ')}
                    </p>
                  )}
                </section>
              )}

              <p className="pp-note">
                Your score this period is {num1(studio.score)} points. Views, visits caused,
                helpful votes on your directions and confirmed live reports all count &mdash; a
                visit counts most.
              </p>
            </>
          ) : (
            <EmptyState
              icon="i-video"
              title="Your Studio is empty"
              body="Your first place or video starts your Studio."
              action={
                <Link className="btn btn-primary btn-sm" to="/add/place">
                  Add a place
                </Link>
              }
            />
          )}
        </div>

        <BottomSheet
          open={splitOpen}
          onClose={() => setSplitOpen(false)}
          title="How earnings are split"
        >
          {studio?.split_explainer.lines.map((line) => (
            <p className="plain" key={line} style={{ marginBottom: 10 }}>
              {line}
            </p>
          ))}
          <div className="simbanner" style={{ margin: '4px 0 0' }}>
            <Icon name="i-info" size={17} />
            <span>
              The pool in this version is a fixed, made-up figure from the app&apos;s config.
              Nothing is paid, and nothing is owed.
            </span>
          </div>
        </BottomSheet>
      </>
    );
  }

  return (
    <>
      <StatusBar />
      {header}

      {loading && !passport ? (
        <Loading what="Opening your passport" />
      ) : passport ? (
        <>
          <div className="pp-head">
            <span className="avatar avatar-lg">{initials(passport.user.display_name)}</span>
            <div className="pp-id">
              <div className="pp-name">{passport.user.display_name}</div>
              <div className="pp-level">
                {passport.level}
                {passport.user.home_city ? ` · ${passport.user.home_city.name}` : ''}
              </div>
            </div>
            <span className="kadam kadam-lg">
              <Icon name="i-feet" size={18} />
              {num(passport.kadam)}
            </span>
          </div>

          <div className="pp-prog">
            <div className="pp-prog-t">
              <span>
                {num(passport.kadam)}
                {passport.next_level ? ` / ${num(passport.next_level_floor)}` : ''} kadam
              </span>
              <span>
                {passport.next_level ? `to ${passport.next_level}` : 'Local Legend'}
              </span>
            </div>
            <DashedProgress
              value={passport.kadam - passport.level_floor}
              max={Math.max(1, passport.next_level_floor - passport.level_floor)}
            />
          </div>

          <div className="pp-cards">
            <div className="ppc">
              <b>{passport.streak.weeks}</b>
              <span>week streak</span>
              <small>
                {passport.streak.rain_checks_left} rain check
                {passport.streak.rain_checks_left === 1 ? '' : 's'} left
              </small>
            </div>
            <div className="ppc">
              <b>{num(passport.places_found ?? passport.found.length)}</b>
              <span>places found</span>
              <small>caused {num1(passport.visits_caused)} visits</small>
            </div>
            <div className="ppc">
              <b>{passport.stamps.length}</b>
              <span>stamps</span>
              <small>
                {passport.neighbourhoods_explored} / {passport.neighbourhoods_total} areas
              </small>
            </div>
          </div>

          <Tabs
            label="Passport sections"
            className="tabs-pp"
            value={tab}
            onChange={setTab}
            options={[
              { key: 'stamps', label: 'Stamps' },
              { key: 'found', label: 'Found by me' },
              { key: 'want', label: 'Want to go' },
              { key: 'kadam', label: 'Kadam' },
            ]}
          />

          <div className="scr-body">
            {tab === 'stamps' && (
              <div className="stamps">
                {passport.stamps.map((stamp, index) => {
                  const meta = categoryMeta(stamp.category);
                  return (
                    <Link to={`/place/${stamp.place_id}`} key={`${stamp.place_id}-${stamp.date}`}>
                      <StampTile
                        name={stamp.name}
                        icon={meta.icon}
                        date={stampDate(stamp.date)}
                        colour={meta.stampColour}
                        rotation={[-4, 3, -2, 2, -3, 4, -1, 2][index % 8]}
                        simulated={stamp.simulated}
                      />
                    </Link>
                  );
                })}
                <EmptyStamp />
              </div>
            )}

            {tab === 'found' && (
              <>
                {passport.found.length === 0 ? (
                  <EmptyState
                    icon="i-pin"
                    title="You haven't added a place yet"
                    body="Found something the map doesn't know? That is what this app is for."
                    action={
                      <Link className="btn btn-primary btn-sm" to="/add/place">
                        Add a place
                      </Link>
                    }
                  />
                ) : (
                  <>
                    {(passport.places_found ?? passport.found.length) > passport.found.length && (
                      <div
                        style={{
                          padding: '8px 14px',
                          margin: '8px 16px 4px',
                          borderRadius: '8px',
                          background: 'rgba(47, 93, 80, 0.08)',
                          fontSize: '0.82rem',
                          color: 'var(--ink-secondary)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <Icon name="i-info" size={15} />
                        <span>
                          Showing latest {passport.found.length} of {num(passport.places_found ?? passport.found.length)} places added
                        </span>
                      </div>
                    )}
                    <ol className="rows" style={{ flex: 'none' }}>
                      {passport.found.map((place) => (
                        <PlaceRow key={place.id} place={place} showRank={false} />
                      ))}
                    </ol>
                  </>
                )}
              </>
            )}

            {tab === 'want' && (
              <>
                {passport.want_to_go.length === 0 ? (
                  <EmptyState
                    icon="i-star"
                    title="Nothing saved yet"
                    body="Swipe right on the deck to keep a place for later."
                  />
                ) : (
                  <ol className="rows" style={{ flex: 'none' }}>
                    {passport.want_to_go.map((place) => (
                      <PlaceRow key={place.id} place={place} showRank={false} />
                    ))}
                  </ol>
                )}
              </>
            )}

            {tab === 'kadam' && (
              <>
                <div className="ledger">
                  {passport.ledger.length === 0 ? (
                    <p className="plain" style={{ color: 'var(--muted)', padding: '12px 0' }}>
                      Nothing yet. Check in somewhere, and it starts here.
                    </p>
                  ) : (
                    passport.ledger.map((line, index) => (
                      <div className="lg-row" key={`${line.at}-${index}`}>
                        <span
                          className="lg-d"
                          style={{ color: line.delta < 0 ? 'var(--danger)' : 'var(--moss)' }}
                        >
                          {line.delta > 0 ? '+' : ''}
                          {line.delta}
                        </span>
                        <span>{line.text}</span>
                        <small>{ago(line.at)}</small>
                      </div>
                    ))
                  )}
                </div>
                <p className="pp-note">
                  Kadam measure how much you&apos;ve helped people explore. They can&apos;t be
                  cashed yet.
                </p>
              </>
            )}

            {passport.stamps.length === 0 && tab === 'stamps' && (
              <p className="pp-note">Your first stamp is one visit away.</p>
            )}
          </div>
        </>
      ) : null}
    </>
  );
}

function initials(name: string): string {
  const parts = name.replace(/[^\p{L}\s.]/gu, ' ').trim().split(/[\s.]+/);
  return (
    parts
      .slice(0, 2)
      .map((part) => part[0] ?? '')
      .join('')
      .toUpperCase() || '??'
  );
}
