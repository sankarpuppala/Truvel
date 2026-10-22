/** The one place the app talks to the server.
 *
 * Two rules live here so no screen has to remember them:
 *  - every mutating request carries `X-Requested-With: truvel`, which is the
 *    CSRF defence the server requires (SPEC §11);
 *  - errors come back as `{error: {code, message, detail}}` and are turned into
 *    an `ApiError` whose `message` is already written for a person to read.
 */
import type {
  AppConfig,
  CheckinResult,
  City,
  DeckResponse,
  Fog,
  Me,
  MediaItem,
  Passport,
  Place,
  Profile,
  PulseSummary,
  StepVersion,
  Studio,
  WatchResponse,
} from './types';

const BASE = '/api';

export class ApiError extends Error {
  code: string;
  status: number;
  detail: unknown;

  constructor(status: number, code: string, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = {};
  // Required on anything that changes state; harmless on a GET.
  if (method !== 'GET') headers['X-Requested-With'] = 'truvel';

  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;              // let the browser set the boundary
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.body);
  }

  const response = await fetch(BASE + path, {
    method,
    headers,
    body,
    credentials: 'same-origin',
    signal: options.signal,
  });

  if (response.status === 204) return undefined as T;

  let payload: unknown;
  const text = await response.text();
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const error = (payload as { error?: { code: string; message: string; detail?: unknown } })
      ?.error;
    throw new ApiError(
      response.status,
      error?.code ?? `http_${response.status}`,
      error?.message ?? 'Something went wrong. Try again.',
      error?.detail,
    );
  }
  return payload as T;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export type Coords = { lat: number; lng: number } | null;

export const api = {
  // --- meta ------------------------------------------------------------- //
  health: () => request<{ ok: boolean; dev_fake_location: boolean }>('/health'),
  config: () => request<AppConfig>('/config'),

  // --- accounts --------------------------------------------------------- //
  register: (body: {
    email: string;
    username: string;
    password: string;
    display_name?: string;
  }) => request<{ user: Me }>('/auth/register', { method: 'POST', body }),
  /** `identifier` is an email address or a handle; the server works out which. */
  login: (identifier: string, password: string) =>
    request<{ user: Me }>('/auth/login', { method: 'POST', body: { identifier, password } }),
  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
  /** Always succeeds, whether or not the address has an account. */
  forgotPassword: (email: string) =>
    request<{ ok: boolean }>('/auth/forgot', { method: 'POST', body: { email } }),
  resetPassword: (token: string, password: string) =>
    request<{ user: Me }>('/auth/reset', { method: 'POST', body: { token, password } }),
  deleteMedia: (mediaId: number) =>
    request<{ ok: boolean }>(`/media/${mediaId}`, { method: 'DELETE' }),
  me: () => request<{ user: Me }>('/me'),

  // --- places and explore ------------------------------------------------ //
  cities: () => request<{ cities: City[] }>('/cities'),
  cityPlaces: (
    slug: string,
    options: {
      sort?: string;
      cat?: string;
      verified?: boolean;
      at?: Coords;
      page?: number;
      q?: string;
    } = {},
  ) =>
    request<{
      city: City;
      sort: string;
      explainer: string;
      total: number;
      page: number;
      page_size: number;
      places: Place[];
    }>(
      `/cities/${slug}/places` +
        query({
          sort: options.sort,
          cat: options.cat,
          verified: options.verified ? 1 : undefined,
          lat: options.at?.lat,
          lng: options.at?.lng,
          page: options.page,
          q: options.q,
        }),
    ),
  search: (q: string, at?: Coords) =>
    request<{
      query: string;
      cities: City[];
      areas: { id: number; name: string; city_id: number }[];
      places: Place[];
    }>('/search' + query({ q, lat: at?.lat, lng: at?.lng })),
  place: (id: number, at?: Coords) =>
    request<Place>(`/places/${id}` + query({ lat: at?.lat, lng: at?.lng })),

  // --- engagement -------------------------------------------------------- //
  like: (id: number, on: boolean) =>
    request<{ liked: boolean; likes: number }>(`/places/${id}/like`, {
      method: on ? 'POST' : 'DELETE',
    }),
  save: (id: number, on: boolean) =>
    request<{ saved: boolean; pledged?: boolean }>(`/places/${id}/save`, {
      method: on ? 'POST' : 'DELETE',
    }),
  fragilePledge: (id: number) =>
    request<{ saved: boolean; pledged: boolean }>(`/places/${id}/fragile-pledge`, {
      method: 'POST',
    }),
  likeMedia: (id: number, on: boolean) =>
    request<{ liked: boolean; likes: number }>(`/media/${id}/like`, {
      method: on ? 'POST' : 'DELETE',
    }),
  follow: (handle: string, on: boolean) =>
    request<{ following: boolean }>(`/users/${handle}/follow`, {
      method: on ? 'POST' : 'DELETE',
    }),
  touch: (place_id: number, content_type: string, content_id?: number) =>
    request<{ recorded: boolean }>('/touch', {
      method: 'POST',
      body: { place_id, content_type, content_id },
    }),
  report: (target_type: string, target_id: number, reason: string, note = '') =>
    request<{ filed: boolean; hidden: boolean; already?: boolean }>('/reports', {
      method: 'POST',
      body: { target_type, target_id, reason, note },
    }),

  // --- deck -------------------------------------------------------------- //
  deck: (at: Coords, radius_km: number, request_no = 0) =>
    request<DeckResponse>('/deck' + query({ lat: at?.lat, lng: at?.lng, radius_km, request_no })),
  swipe: (place_id: number, action: 'save' | 'skip' | 'open') =>
    request<{ recorded: boolean; category: string; alpha: number; beta: number }>('/deck/swipe', {
      method: 'POST',
      body: { place_id, action },
    }),

  // --- watch ------------------------------------------------------------- //
  watch: (tab: string, at: Coords, cursor = 0) =>
    request<WatchResponse>('/watch' + query({ tab, lat: at?.lat, lng: at?.lng, cursor })),
  watchView: (media_id: number, watched_s: number, duration_s: number, simulated = false) =>
    request<{ engaged: boolean; completed: boolean; invalid_reason: string | null }>(
      `/watch/${media_id}/view`,
      { method: 'POST', body: { watched_s, duration_s, simulated_session: simulated } },
    ),

  // --- check-in and pulse ------------------------------------------------ //
  checkin: (id: number, lat: number, lng: number, accuracy: number, simulated = false) =>
    request<CheckinResult>(`/places/${id}/checkin`, {
      method: 'POST',
      body: { lat, lng, accuracy, simulated },
    }),
  pulse: (id: number) => request<{ pulse: PulseSummary | null }>(`/places/${id}/pulse`),
  postPulse: (
    id: number,
    body: {
      water?: string | null;
      crowd?: string | null;
      path?: string | null;
      open?: string | null;
      note?: string;
    },
  ) =>
    request<{ posted: boolean; kadam: number; pulse: PulseSummary | null }>(
      `/places/${id}/pulse`,
      { method: 'POST', body },
    ),

  // --- last-mile steps and names ----------------------------------------- //
  steps: (id: number) =>
    request<{ locked: boolean; versions: StepVersion[] }>(`/places/${id}/steps`),
  addSteps: (id: number, steps: { text: string }[]) =>
    request<{ version_group: string }>(`/places/${id}/steps`, { method: 'POST', body: { steps } }),
  voteSteps: (group: string, helpful: boolean) =>
    request<{ helpful: number; votes: number; score: number }>(`/steps/${group}/vote`, {
      method: 'POST',
      body: { helpful },
    }),
  names: (id: number) =>
    request<{ names: { id: number; lang: string; name: string; source: string; votes: number }[] }>(
      `/places/${id}/names`,
    ),
  addName: (id: number, lang: string, name: string) =>
    request<{ added: boolean; voted: boolean; votes: number }>(`/places/${id}/names`, {
      method: 'POST',
      body: { lang, name },
    }),

  // --- adding ------------------------------------------------------------ //
  candidates: (lat: number, lng: number, name: string, category: string) =>
    request<{ candidates: Place[] }>('/places/candidates', {
      method: 'POST',
      body: { lat, lng, name, category },
    }),
  createPlace: (body: Record<string, unknown>) =>
    request<{ place: Place; on_site: boolean; message: string }>('/places', {
      method: 'POST',
      body,
    }),
  uploadMedia: (placeId: number, form: FormData) =>
    request<{ media: MediaItem | null; skipped?: boolean; message?: string; warning?: string }>(
      `/places/${placeId}/media`,
      { method: 'POST', form },
    ),

  // --- you --------------------------------------------------------------- //
  passport: () => request<Passport>('/me/passport'),
  kadamLedger: (limit = 50) =>
    request<{ balance: number; entries: { delta: number; reason: string; at: string }[] }>(
      '/me/kadam' + query({ limit }),
    ),
  fog: (city?: string) => request<Fog>('/me/fog' + query({ city })),
  settings: () =>
    request<{
      names_mode: string;
      names_lang: string;
      ui_lang: string;
      theme: string;
      home_city_id: number | null;
      languages: string[];
      ui_available: string[];
      ui_in_review: string[];
    }>('/me/settings'),
  saveSettings: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/me/settings', { method: 'PATCH', body }),
  studio: (period = 28) => request<Studio>('/studio' + query({ period })),
  profile: (handle: string) => request<Profile>(`/users/${handle}`),

  // --- dev tools (404 unless the server allows them) --------------------- //
  devPlaces: () =>
    request<{ places: { id: number; name: string; category: string; area: string }[] }>(
      '/dev/places',
      { method: 'GET' },
    ),
  teleport: (place_id?: number) =>
    request<{ lat: number; lng: number; accuracy: number; simulated: boolean }>('/dev/teleport', {
      method: 'POST',
      body: { place_id },
    }),

  // --- admin ------------------------------------------------------------- //
  adminCases: () => request<{ cases: Record<string, unknown>[] }>('/admin/cases'),
  adminQueue: () => request<{ reports: Record<string, unknown>[] }>('/admin/queue'),
  adminAction: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/admin/actions', { method: 'POST', body }),
  partnerRun: (month: string) =>
    request<Record<string, unknown>>(`/admin/partner/run?month=${month}`, { method: 'POST' }),
  adminStats: () => request<Record<string, unknown>>('/admin/stats'),
};
