/** Shapes the API returns. Mirrors the payloads in app/services.py. */

export type NameLine = {
  text: string;
  lang: string;
  rtl: boolean;
  auto: boolean;
};

export type NameBlockData = {
  primary: NameLine;
  secondary: NameLine | null;
  langs: string[];
};

export type Creator = {
  id: number;
  username: string;
  display_name: string;
};

export type MediaItem = {
  id: number;
  kind: 'photo' | 'video';
  url: string;
  thumb: string | null;
  poster: string | null;
  width: number;
  height: number;
  duration_s: number;
  caption: string;
  lang: string;
  source: 'upload' | 'commons';
  licence: string;
  attribution: string;
  source_url: string;
  shot_here: boolean;
  creator: Creator | null;
};

export type PulseField = { value: string; mixed: boolean };

export type PulseSummary = {
  at: string;
  freshness: 'live' | 'recent' | 'old' | null;
  reporters: number;
  fields: Partial<Record<'water' | 'crowd' | 'path' | 'open', PulseField>>;
  note: string;
};

export type Place = {
  id: number;
  name: NameBlockData;
  category: string;
  area: string;
  state: string | null;
  lat: number;
  lng: number;
  coords_exact: boolean;
  fragile: boolean;
  pledged: boolean;
  status: 'verified' | 'unverified' | 'hidden';
  fame: 'famous' | 'known' | 'hidden';
  source: 'osm' | 'wikidata' | 'community';
  radius_m: number;
  likes: number;
  viewers: number;
  verified_visits: number;
  visits_this_month: number;
  photo_count: number;
  video_count: number;
  live: boolean;
  lead_media: MediaItem | null;
  found_by: (Creator & { official?: boolean }) | null;
  created_at: string;
  attribution: string;
  distance_km?: number;
  travel_min?: number;
  liked?: boolean;
  saved?: boolean;
  rank?: number;
  wilson?: number;
  is_gem?: boolean;
  is_trending?: boolean;
  unverified_nearby?: boolean;
  score?: number;
  score_parts?: Record<string, number>;
  tip?: { text: string; by: string | null };
  // Only on the full Place page payload.
  description?: string;
  activities?: string[];
  best_time?: Record<string, string>;
  entry_fee_text?: string;
  timings_text?: string;
  access?: Record<string, unknown>;
  accessibility?: Record<string, string>;
  safety?: Record<string, string>;
  tags?: string[];
  media?: MediaItem[];
  pulse?: PulseSummary | null;
  maps_url?: string | null;
  osm_url?: string | null;
  regional_langs?: string[];
  added_remotely?: boolean;
  nearby?: Place[];
  videos?: MediaItem[];
};

export type City = {
  /** null for a state browsed by its `state` column, which has no City row. */
  id: number | null;
  slug: string;
  name: string;
  state: string;
  centre: [number, number] | null;
  bbox: number[] | null;
  regional_langs: string[];
  place_count: number;
  community_count: number;
  neighbourhood_count: number;
};

export type Me = {
  id: number;
  username: string;
  email: string;
  official: boolean;
  display_name: string;
  bio: string;
  role: 'user' | 'admin';
  strikes: number;
  kadam: number;
  level: string;
  next_level: string | null;
  level_floor: number;
  next_level_floor: number;
  names_mode: 'en_local' | 'mine_local' | 'en';
  names_lang: string;
  ui_lang: string;
  theme: 'system' | 'light' | 'dark';
  home_city: { id: number; slug: string; name: string } | null;
  created_at: string;
  streak?: { weeks: number; rain_checks_left: number };
};

export type DeckResponse = {
  cards: Place[];
  radius_km: number;
  location_fallback: boolean;
  total_candidates: number;
  end_card: { message: string };
};

export type WatchItem = {
  media: MediaItem;
  place: Place;
  likes: number;
  engaged_views: number;
  following: boolean;
  score: number;
  score_parts: Record<string, number>;
  safety_overlay: boolean;
  blur_location?: boolean;
  liked?: boolean;
};

export type WatchResponse = {
  tab: 'foryou' | 'nearby' | 'following';
  cursor: number;
  next_cursor: number | null;
  total: number;
  items: WatchItem[];
  nudge_after_min: number;
};

export type Stamp = {
  place_id: number;
  name: string;
  name_block: NameBlockData;
  category: string;
  date: string;
  simulated: boolean;
};

export type LedgerLine = {
  delta: number;
  reason: string;
  text: string;
  place: string | null;
  at: string;
};

export type Passport = {
  user: Me;
  kadam: number;
  level: string;
  next_level: string | null;
  level_floor: number;
  next_level_floor: number;
  streak: { weeks: number; rain_checks_left: number };
  stamps: Stamp[];
  found: Place[];
  visits_caused: number;
  want_to_go: Place[];
  ledger: LedgerLine[];
  neighbourhoods_explored: number;
  neighbourhoods_total: number;
};

export type Requirement = {
  key: string;
  label: string;
  met: boolean;
  value: number;
  target: number;
  note: string;
};

export type TopContent = {
  type: string;
  media_id?: number;
  place_id: number;
  title: string;
  duration_s?: number;
  engaged_views: number;
  avg_watched_pct: number | null;
  visits_caused: number;
  thumb: string | null;
};

export type Studio = {
  creator: { id: number; username: string; display_name: string; followers: number };
  period_days: number;
  simulated: boolean;
  banner: string;
  metrics: {
    engaged_views: { value: number; delta_pct: number | null };
    watch_time_h: { value: number; delta_pct: number | null };
    visits_caused: { value: number; delta_pct: number | null };
    estimated_earnings_paise: number;
    earnings_are_projection: boolean;
  };
  score: number;
  score_parts: Record<string, number>;
  sparklines: {
    engaged_views: number[];
    visits_caused: number[];
    watch_time_h: number[];
    earnings: number[];
  };
  partner: {
    eligible: boolean;
    done: number;
    total: number;
    requirements: Requirement[];
  };
  top_content: TopContent[];
  audience: {
    cities: { name: string; viewers: number }[];
    languages: { lang: string; viewers: number }[];
  };
  split_explainer: {
    creator_share_pct: number;
    weights: Record<string, number>;
    lines: string[];
  };
};

export type Fog = {
  city: { slug: string; name: string; bbox: number[] };
  circles: { lat: number; lng: number; radius_km: number; simulated: boolean }[];
  explored: number;
  total: number;
  explored_names: string[];
  percent: number;
};

export type StepVersion = {
  version_group: string;
  author: { id: number; username: string } | null;
  helpful: number;
  votes: number;
  score: number;
  steps: { order: number; text: string; media_id: number | null }[];
};

export type CheckinResult = {
  verified: boolean;
  code: string;
  message: string;
  kadam?: number;
  first_visit?: boolean;
  flag?: string | null;
  simulated?: boolean;
  visit_id?: number;
  distance_m: number;
  accuracy_m?: number;
  place_verified?: boolean;
  attributed?: { creator_id: number; share: number }[];
  can_pulse?: boolean;
  stamp?: { place_id: number; name: string; category: string; date: string };
};

export type Profile = {
  id: number;
  username: string;
  display_name: string;
  bio: string;
  level: string;
  followers: number;
  following: boolean;
  is_self: boolean;
  places_found: number;
  visits_caused: number;
  partner: boolean;
  found: Place[];
  videos: MediaItem[];
  created_at: string;
};

export type AppConfig = {
  languages: string[];
  state_languages: Record<string, string[]>;
  ui_languages: { available: string[]; in_review: string[] };
  kadam: { levels: Record<string, number> };
  deck: { radii_km: number[] };
  media: Record<string, number>;
  watch: { video_max_s: number; video_max_mb: number; break_nudge_min: number };
  verification: Record<string, number>;
  pulse: Record<string, number>;
  partner: { demo_pool_inr: number; creator_share: number; weights: Record<string, number> };
  attribution: Record<string, number>;
  simulated_money: boolean;
};
