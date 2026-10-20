/** Admin: the moderation queue and the monthly Partner run (SPEC §8.13, §10).
 *
 * Tier 1 only required the API for this; the screen is small on purpose. The
 * Partner run button is the one place a month's `EarningLine`s get written, and
 * the result is shown in full so the arithmetic can be checked against the
 * pool (AC-18).
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Loading } from '../components/common';
import { Icon, StatusBar } from '../components/Icon';
import { num, rupees } from '../lib/format';

type Report = {
  id: number;
  target_type: string;
  target_id: number;
  reason: string;
  note: string;
  at: string;
  reporter: string | null;
  target: Record<string, unknown> | null;
};

export function Admin() {
  const navigate = useNavigate();
  const { me, loadingMe, toast } = useApp();
  const [reports, setReports] = useState<Report[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [runResult, setRunResult] = useState<Record<string, unknown> | null>(null);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loadingMe) return;
    if (!me || me.role !== 'admin') navigate('/');
  }, [loadingMe, me, navigate]);

  async function load() {
    setLoading(true);
    try {
      const [queue, statistics] = await Promise.all([api.adminQueue(), api.adminStats()]);
      setReports(queue.reports as unknown as Report[]);
      setStats(statistics);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'Could not load the queue.', 'bad');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (me?.role === 'admin') void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.role]);

  async function act(body: Record<string, unknown>) {
    try {
      await api.adminAction(body);
      toast('Done.');
      await load();
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
    }
  }

  async function runMonth() {
    setBusy(true);
    try {
      setRunResult(await api.partnerRun(month));
      toast(`Partner month ${month} computed.`);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'The run failed.', 'bad');
    } finally {
      setBusy(false);
    }
  }

  if (!me || me.role !== 'admin') return null;
  if (loading) return <Loading what="Loading the queue" />;

  const lines = (runResult?.lines ?? []) as {
    creator_id: number;
    score: number;
    share: number;
    amount_paise: number;
    eligible: boolean;
    engaged_views: number;
    visits_caused: number;
  }[];

  return (
    <>
      <StatusBar />
      <div className="add-head">
        <button className="round round-flat" aria-label="Back" onClick={() => navigate('/you')}>
          <Icon name="i-back" size={20} />
        </button>
        <div>
          <div className="add-title">Admin</div>
          <div className="add-sub">Moderation and the Partner month</div>
        </div>
      </div>

      <div className="scr-body">
        <section className="lsec">
          <h4>Reports ({reports.length})</h4>
          {reports.length === 0 ? (
            <p className="plain" style={{ color: 'var(--muted)' }}>
              Nothing waiting.
            </p>
          ) : (
            reports.map((report) => (
              <div className="cand" key={report.id} style={{ marginBottom: 8, alignItems: 'flex-start' }}>
                <div>
                  <b>
                    {report.reason.replace(/_/g, ' ')} &middot; {report.target_type} #
                    {report.target_id}
                  </b>
                  <span>
                    by @{report.reporter ?? 'someone'}
                    {report.note ? ` — ${report.note}` : ''}
                  </span>
                  <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() =>
                        void act({
                          action: 'hide',
                          target_type: report.target_type,
                          target_id: report.target_id,
                        })
                      }
                    >
                      Hide
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() =>
                        void act({
                          action: 'approve',
                          target_type: report.target_type,
                          target_id: report.target_id,
                        })
                      }
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn btn-text btn-sm"
                      onClick={() => void act({ action: 'dismiss', report_id: report.id })}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </section>

        <section className="lsec">
          <h4>Partner month</h4>
          <div className="simbanner" style={{ margin: '0 0 12px' }}>
            <Icon name="i-info" size={17} />
            <span>
              <b>Simulated pool.</b> Running a month writes earning lines in points and paise,
              but no money moves.
            </span>
          </div>
          <label className="field">
            <span>Month</span>
            <input
              value={month}
              onChange={(event) => setMonth(event.target.value)}
              placeholder="2026-10"
            />
          </label>
          <button
            type="button"
            className="btn btn-primary btn-wide"
            onClick={() => void runMonth()}
            disabled={busy}
          >
            {busy ? 'Computing…' : `Run ${month}`}
          </button>

          {runResult && (
            <div style={{ marginTop: 14 }}>
              <p className="plain">
                Pool {rupees(Number(runResult.pool_paise))} &middot; paid{' '}
                {rupees(Number(runResult.paid_paise))} &middot; left by rounding{' '}
                {rupees(Number(runResult.remainder_paise))}
                <br />
                {num(Number(runResult.creators))} creators,{' '}
                {num(Number(runResult.eligible_creators))} eligible,{' '}
                {num(Number(runResult.held_engaged_views))} views held for review
              </p>
              {lines.slice(0, 10).map((line) => (
                <div className="tc" key={line.creator_id}>
                  <div>
                    <b>Creator #{line.creator_id}</b>
                    <span>
                      score {Math.round(line.score)} &middot; {num(line.engaged_views)} views
                      &middot; {line.visits_caused.toFixed(1)} visits
                      {line.eligible ? '' : ' · not eligible'}
                    </span>
                  </div>
                  <em>{rupees(line.amount_paise)}</em>
                </div>
              ))}
            </div>
          )}
        </section>

        {stats && (
          <section className="lsec">
            <h4>Coverage</h4>
            <p className="plain">
              {num(Number(stats.places))} places &middot;{' '}
              {Math.round(Number(stats.photo_share) * 100)}% with a photo
            </p>
            <p className="plain" style={{ color: 'var(--muted)', fontSize: 13.5 }}>
              Names per language:{' '}
              {Object.entries((stats.names_by_lang ?? {}) as Record<string, number>)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 12)
                .map(([lang, count]) => `${lang} ${count}`)
                .join(', ')}
            </p>
          </section>
        )}
      </div>
    </>
  );
}
