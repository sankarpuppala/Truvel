/** Category metadata: the icon, the illustration and the word for each one.
 *
 * The icon ids (`i-g-*`) and illustration ids (`sc-*`) are the sprite symbols
 * from docs/design-reference.html, so a category always draws the same way the
 * reference draws it. Every place without a photo falls back to its category
 * illustration -- never a grey box (SPEC §12.6).
 */

export type Category =
  | 'viewpoint'
  | 'waterfall'
  | 'lake'
  | 'hill_trek'
  | 'fort_heritage'
  | 'temple_sacred'
  | 'park_garden'
  | 'museum_art'
  | 'market_street'
  | 'beach_river'
  | 'other';

type Meta = {
  label: string;
  icon: string;          // sprite id, without the #
  scene: string;         // illustration id, without the #
  stampColour: 'lat' | 'moss' | 'lake';
};

export const CATEGORIES: Record<string, Meta> = {
  viewpoint: { label: 'Viewpoint', icon: 'i-g-view', scene: 'sc-rocks', stampColour: 'lat' },
  waterfall: { label: 'Waterfall', icon: 'i-g-fall', scene: 'sc-fall', stampColour: 'lake' },
  lake: { label: 'Lake', icon: 'i-g-lake', scene: 'sc-lake', stampColour: 'lake' },
  hill_trek: { label: 'Hills', icon: 'i-g-hill', scene: 'sc-hills', stampColour: 'moss' },
  fort_heritage: { label: 'Heritage', icon: 'i-g-fort', scene: 'sc-fort', stampColour: 'moss' },
  temple_sacred: { label: 'Sacred', icon: 'i-g-dome', scene: 'sc-tombs', stampColour: 'lat' },
  park_garden: { label: 'Park', icon: 'i-leaf', scene: 'sc-hills', stampColour: 'moss' },
  museum_art: { label: 'Museum', icon: 'i-g-dome', scene: 'sc-tombs', stampColour: 'lake' },
  market_street: { label: 'Market', icon: 'i-list', scene: 'sc-fort', stampColour: 'lat' },
  beach_river: { label: 'Water', icon: 'i-g-well', scene: 'sc-well', stampColour: 'lake' },
  other: { label: 'Place', icon: 'i-pin', scene: 'sc-hills', stampColour: 'lat' },
};

export function categoryMeta(category: string | undefined): Meta {
  return CATEGORIES[category ?? 'other'] ?? CATEGORIES.other;
}

export function categoryLabel(category: string | undefined): string {
  return categoryMeta(category).label;
}

export function categoryIcon(category: string | undefined): string {
  return categoryMeta(category).icon;
}

export function categoryScene(category: string | undefined): string {
  return categoryMeta(category).scene;
}

/** The chips on Explore. "All" first, then the categories a city actually has. */
export const FILTER_CHIPS: { key: string; label: string; icon?: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'viewpoint', label: 'Views', icon: 'i-g-view' },
  { key: 'lake', label: 'Lakes', icon: 'i-g-lake' },
  { key: 'fort_heritage', label: 'Heritage', icon: 'i-g-fort' },
  { key: 'waterfall', label: 'Falls', icon: 'i-g-fall' },
  { key: 'hill_trek', label: 'Hills', icon: 'i-g-hill' },
  { key: 'temple_sacred', label: 'Sacred', icon: 'i-g-dome' },
  { key: 'park_garden', label: 'Parks', icon: 'i-leaf' },
  { key: 'beach_river', label: 'Water', icon: 'i-g-well' },
  { key: 'museum_art', label: 'Museums', icon: 'i-g-dome' },
  { key: 'market_street', label: 'Markets', icon: 'i-list' },
];

/** The five Explore sorts, with the ⓘ line each one shows (SPEC §8.4). */
export const SORTS: { key: string; label: string }[] = [
  { key: 'top', label: 'Top' },
  { key: 'liked', label: 'Most liked' },
  { key: 'gems', label: 'Hidden gems' },
  { key: 'trending', label: 'Trending' },
  { key: 'near', label: 'Nearest' },
];

/** Safety flags, in the order the card lists them (SPEC §8.14). */
export const SAFETY_FLAGS: {
  key: string;
  icon: string;
  yes: string;
  no?: string;
}[] = [
  {
    key: 'steep_edge',
    icon: 'i-warn',
    yes: 'Steep edges. Stay back from the edge. No photo is worth it.',
  },
  { key: 'water_danger', icon: 'i-drop', yes: 'Deep or fast water. No swimming.' },
  { key: 'slippery_in_monsoon', icon: 'i-drop', yes: 'Slippery after rain.' },
  {
    key: 'no_mobile_signal',
    icon: 'i-signal',
    yes: 'No mobile signal. Tell someone where you are going.',
    no: 'Mobile signal is good.',
  },
  { key: 'isolated', icon: 'i-group', yes: 'Quiet and isolated. Better in a group.' },
  { key: 'wildlife', icon: 'i-leaf', yes: 'Wildlife about. Keep your distance and your food shut.' },
  { key: 'permit_needed', icon: 'i-flag', yes: 'A permit or permission is needed.' },
  { key: 'sacred', icon: 'i-g-dome', yes: 'A place of worship. Dress modestly; footwear off.' },
];

/** The accessibility rows, in the order the Place page lists them (SPEC §8.5). */
export const ACCESS_ROWS: { key: string; label: string }[] = [
  { key: 'wheelchair', label: 'Wheelchair' },
  { key: 'steps_count_text', label: 'Steps' },
  { key: 'toilets', label: 'Toilets' },
  { key: 'drinking_water', label: 'Water' },
  { key: 'shade', label: 'Shade' },
  { key: 'food_nearby', label: 'Food nearby' },
];

/** Pulse field options, and how each value reads on screen (SPEC §8.8). */
export const PULSE_OPTIONS = {
  water: [
    { value: 'flowing', label: 'Flowing', icon: 'i-g-fall' },
    { value: 'low', label: 'Low', icon: 'i-drop' },
    { value: 'dry', label: 'Dry', icon: 'i-sun' },
  ],
  crowd: [
    { value: 'quiet', label: 'Quiet', icon: 'i-group' },
    { value: 'busy', label: 'Busy', icon: 'i-group' },
    { value: 'packed', label: 'Packed', icon: 'i-group' },
  ],
  path: [
    { value: 'dry', label: 'Path dry', icon: 'i-walk' },
    { value: 'muddy', label: 'Muddy', icon: 'i-walk' },
    { value: 'flooded', label: 'Flooded', icon: 'i-drop' },
    { value: 'closed', label: 'Path closed', icon: 'i-x' },
  ],
  open: [
    { value: 'yes', label: 'Open', icon: 'i-check' },
    { value: 'closed_today', label: 'Closed today', icon: 'i-x' },
  ],
} as const;

export const WATER_CATEGORIES = new Set(['waterfall', 'lake', 'beach_river']);

export function pulseLabel(field: string, value: string): string {
  const options = (PULSE_OPTIONS as Record<string, readonly { value: string; label: string }[]>)[
    field
  ];
  return options?.find((o) => o.value === value)?.label ?? value;
}

export function pulseIcon(field: string, value: string): string {
  const options = (PULSE_OPTIONS as Record<
    string,
    readonly { value: string; label: string; icon: string }[]
  >)[field];
  return options?.find((o) => o.value === value)?.icon ?? 'i-info';
}

/** Report reasons, as the sheet lists them (SPEC §8.13). */
export const REPORT_REASONS: { key: string; label: string }[] = [
  { key: 'wrong_location', label: 'The pin is in the wrong place' },
  { key: 'wrong_name', label: 'The name is wrong' },
  { key: 'closed_or_gone', label: 'Closed, or no longer there' },
  { key: 'wrong_info', label: 'Something here is out of date' },
  { key: 'private_property', label: 'Private property or trespassing' },
  { key: 'unsafe', label: 'Unsafe' },
  { key: 'offensive', label: 'Offensive' },
  { key: 'stolen_photo', label: "Someone else's photo" },
  { key: 'photo_of_me', label: 'This is a photo of me' },
  { key: 'spam', label: 'Spam' },
  { key: 'duplicate', label: 'Duplicate place' },
  { key: 'other', label: 'Something else' },
];
