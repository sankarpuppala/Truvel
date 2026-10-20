/** Getting the user's position, and the distance maths the client needs.
 *
 * The one rule that matters: a position is read for a single request and
 * **never persisted** -- not to state that outlives the screen, not to
 * localStorage, not to a URL. The server stores only a distance (CLAUDE.md
 * invariant 1), and the client should not be the weak link in that promise.
 */

export type Position = { lat: number; lng: number; accuracy: number };

export const EARTH_RADIUS_KM = 6371.0088;

/** The same haversine the server uses, for distances we show before a fetch. */
export function haversineKm(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const p1 = toRad(lat1);
  const p2 = toRad(lat2);
  const dp = p2 - p1;
  const dl = toRad(lng2 - lng1);
  const h =
    Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/** haversine x 1.3 / 20 km/h, in whole minutes (SPEC §8.2). */
export function travelMinutes(km: number): number {
  return Math.round(((km * 1.3) / 20) * 60);
}

export class LocationError extends Error {
  code: 'denied' | 'unavailable' | 'timeout' | 'insecure';

  constructor(code: LocationError['code'], message: string) {
    super(message);
    this.name = 'LocationError';
    this.code = code;
  }
}

/**
 * One high-accuracy reading, as SPEC §8.7 specifies:
 * `{enableHighAccuracy: true, timeout: 15000, maximumAge: 0}`.
 *
 * `maximumAge: 0` matters -- a cached fix from an hour ago would let someone
 * check in to a place they have left.
 */
export function getPosition(timeoutMs = 15_000): Promise<Position> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new LocationError('unavailable', 'This browser cannot find your location.'));
      return;
    }
    if (!window.isSecureContext) {
      // Geolocation needs HTTPS. On a phone that means the dev certificate
      // (`npm run dev -- --host`); on the laptop, localhost is already secure.
      reject(
        new LocationError(
          'insecure',
          'Location needs a secure connection. Open the app over HTTPS.',
        ),
      );
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
        }),
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          reject(new LocationError('denied', 'Location is switched off for this site.'));
        } else if (error.code === error.TIMEOUT) {
          reject(
            new LocationError('timeout', "Your phone couldn't find you in time. Try again."),
          );
        } else {
          reject(new LocationError('unavailable', 'Your location is not available right now.'));
        }
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 },
    );
  });
}

/** A coarse position for the deck and Explore, where a cached fix is fine. */
export function getCoarsePosition(timeoutMs = 8_000): Promise<Position> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator) || !window.isSecureContext) {
      reject(new LocationError('unavailable', 'Location is not available.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
        }),
      () => reject(new LocationError('denied', 'Location is not available.')),
      { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 120_000 },
    );
  });
}

/** Whether the browser is on a metered or slow connection (SPEC §8.3). */
export function saveData(): boolean {
  const connection = (
    navigator as Navigator & {
      connection?: { saveData?: boolean; effectiveType?: string };
    }
  ).connection;
  if (!connection) return false;
  if (connection.saveData) return true;
  return connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g';
}

/** A short vibration on save and check-in, where the device supports it. */
export function haptic(ms = 12): void {
  if (typeof navigator.vibrate === 'function') {
    try {
      navigator.vibrate(ms);
    } catch {
      /* a refused vibration is not worth reporting */
    }
  }
}
