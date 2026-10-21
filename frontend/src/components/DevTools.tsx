/** The dev location simulator (SPEC §8.7, AC-25).
 *
 * This renders only when the frontend was built with `VITE_DEV_TOOLS=1` **and**
 * the server reports `DEV_ALLOW_FAKE_LOCATION=1`. A production build has no
 * teleport UI at all, and the API returns 404 without the server flag, so there
 * are two independent locks rather than one.
 *
 * Visits made with a simulated position are stored `simulated=true`, shown with
 * a SIM badge, and excluded from metrics, attribution and earnings.
 */
import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import { useApp } from '../lib/app-state';
import { Icon } from './Icon';

export function DevTools() {
  const { devTools, simulated, setSimulated, toast } = useApp();
  const [places, setPlaces] = useState<{ id: number; name: string; area: string }[]>([]);
  const [chosen, setChosen] = useState<string>('');

  useEffect(() => {
    if (!devTools) return;
    void api
      .devPlaces()
      .then((response) => setPlaces(response.places))
      .catch(() => setPlaces([]));
  }, [devTools]);

  if (!devTools) return null;

  async function teleport(placeId: number) {
    try {
      const position = await api.teleport(placeId);
      setSimulated({ lat: position.lat, lng: position.lng, accuracy: position.accuracy });
      toast('Simulated location set. Visits from here are marked SIM.');
    } catch {
      toast('The simulator is not available.', 'bad');
    }
  }

  return (
    <div className="devbar devbar-compact" role="note">
      <span className="sim-badge">DEV</span>
      <b>Location simulator</b>
      <select
        value={chosen}
        onChange={(event) => {
          setChosen(event.target.value);
          if (event.target.value) void teleport(Number(event.target.value));
        }}
        aria-label="Pretend to be at a place"
      >
        <option value="">Pick a place&hellip;</option>
        {places.map((place) => (
          <option key={place.id} value={place.id}>
            {place.name}
            {place.area ? ` — ${place.area}` : ''}
          </option>
        ))}
      </select>
      {simulated && (
        <button
          type="button"
          className="btn btn-text btn-sm"
          onClick={() => {
            setSimulated(null);
            setChosen('');
            toast('Back to real location.');
          }}
        >
          <Icon name="i-x" size={14} />
          Clear
        </button>
      )}
      {/* AC-25: the warning is always visible, never only a tooltip. */}
      <span className="devbar-note">
        Simulated visits never reach metrics, attribution or earnings.
      </span>
    </div>
  );
}
