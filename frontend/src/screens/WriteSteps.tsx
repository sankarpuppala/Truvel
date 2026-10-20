/** Write your own last-mile directions (SPEC §8.5).
 *
 * Anyone can add a version; the best one is chosen by the Wilson score of its
 * helpful votes, so a new version has to earn its place rather than simply
 * being newest.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Icon, StatusBar } from '../components/Icon';

export function WriteSteps() {
  const { id } = useParams<{ id: string }>();
  const placeId = Number(id);
  const navigate = useNavigate();
  const { me, loadingMe, toast } = useApp();
  const [steps, setSteps] = useState<string[]>(['', '', '']);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loadingMe && !me) navigate('/signin');
  }, [loadingMe, me, navigate]);

  async function submit() {
    const written = steps.map((text) => text.trim()).filter(Boolean);
    if (!written.length) {
      toast('Write at least one step.', 'bad');
      return;
    }
    setBusy(true);
    try {
      await api.addSteps(placeId, written.map((text) => ({ text })));
      toast('Added. People can vote on whether it helped.');
      navigate(`/place/${placeId}`);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : 'That did not save.', 'bad');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <StatusBar />
      <div className="add-head">
        <button className="round round-flat" aria-label="Back" onClick={() => navigate(-1)}>
          <Icon name="i-back" size={20} />
        </button>
        <div>
          <div className="add-title">The last mile</div>
          <div className="add-sub">The bit a map cannot tell you</div>
        </div>
      </div>

      <div className="scr-body">
        <div className="form-page">
          <p className="sub">
            Write it the way you would tell a friend on the phone. Landmarks beat distances:
            &ldquo;turn at the water tank&rdquo; is more use than &ldquo;turn after 300 m&rdquo;.
          </p>

          {steps.map((text, index) => (
            <label className="field" key={index}>
              <span>Step {index + 1}</span>
              <input
                value={text}
                maxLength={140}
                onChange={(event) => {
                  const next = [...steps];
                  next[index] = event.target.value;
                  setSteps(next);
                }}
                placeholder={
                  index === 0
                    ? 'Park where the paved lane ends, next to the water tank.'
                    : 'What happens next'
                }
              />
            </label>
          ))}

          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ alignSelf: 'flex-start', marginBottom: 16 }}
            onClick={() => setSteps([...steps, ''])}
          >
            <Icon name="i-plus" size={16} />
            Another step
          </button>

          <button
            type="button"
            className="btn btn-primary btn-wide"
            onClick={() => void submit()}
            disabled={busy}
          >
            {busy ? 'Saving…' : 'Add these directions'}
          </button>
        </div>
      </div>
    </>
  );
}
