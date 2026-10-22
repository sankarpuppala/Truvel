/** The three ways to add something (SPEC §8.6).
 *
 * Shared by the phone's bottom bar and the laptop sidebar so there is one list
 * of options and one sign-in check, not two that can drift apart.
 */
import { useNavigate } from 'react-router-dom';

import { useApp } from '../lib/app-state';
import { BottomSheet } from './common';
import { Icon } from './Icon';

const OPTIONS = [
  {
    to: '/add/place',
    icon: 'i-pin',
    title: 'A new place',
    note: "Somewhere the app doesn't know yet",
  },
  {
    to: '/add/media',
    icon: 'i-camera',
    title: 'Photos or a video of a place',
    note: 'Add to a place that is already here',
  },
  {
    to: '/add/pulse',
    icon: 'i-drop',
    title: 'How is it right now?',
    note: 'On-site only, within 2 hours of checking in',
  },
];

export function AddSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { me, toast } = useApp();

  function go(path: string) {
    onClose();
    if (!me) {
      toast('Sign in to add a place.', 'bad');
      navigate('/signin');
      return;
    }
    navigate(path);
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="Add to Truvel">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {OPTIONS.map((option) => (
          <button
            key={option.to}
            type="button"
            className="cand"
            onClick={() => go(option.to)}
          >
            <span className="mini">
              <Icon name={option.icon} size={18} />
            </span>
            <div>
              <b>{option.title}</b>
              <span>{option.note}</span>
            </div>
            <Icon name="i-chevr" size={18} />
          </button>
        ))}
      </div>
    </BottomSheet>
  );
}
