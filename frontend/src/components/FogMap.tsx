/** The Explore map with fog. Reference screen 4 (SPEC §8.4, §14).
 *
 * Three rules that are not negotiable:
 *
 *  - **International boundary layers are hidden.** Indian law and policy are
 *    strict about how India's external boundaries are drawn, so we remove those
 *    layers rather than risk drawing them wrongly, and we never draw a state or
 *    country border ourselves (SPEC §14, invariant 12).
 *  - **Tiles come from OpenFreeMap and nowhere else.** That is the only
 *    third-party origin the frontend is allowed to talk to (invariant 7).
 *  - **The fog is the user's own verified visits.** Each clears a 1 km circle,
 *    cut out of a dark overlay with a dashed marigold rim.
 *
 * MapLibre is imported dynamically so its ~800 KB never lands in the app shell
 * (SPEC §15).
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Map as MapLibreMap, Marker } from 'maplibre-gl';
import { Link } from 'react-router-dom';

import { api } from '../lib/api';
import { useApp } from '../lib/app-state';
import { categoryIcon } from '../lib/categories';
import { distance, num } from '../lib/format';
import type { City, Fog, Place } from '../lib/types';
import { Icon } from './Icon';
import { PlaceThumb } from './PlaceRow';
import { Loading } from './common';

const TILES = 'https://tiles.openfreemap.org/styles/bright';

/** Layer ids in the OpenFreeMap "bright" style that draw country borders. */
const BOUNDARY_PATTERNS = [
  'boundary',
  'admin',
  'country',
  'disputed',
  'state',
  'border',
];

export function FogMap({
  city,
  places,
  header,
}: {
  city: City | null;
  places: Place[];
  header: ReactNode;
}) {
  const { me } = useApp();
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<unknown>(null);
  const [fog, setFog] = useState<Fog | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [inView, setInView] = useState<Place[]>([]);

  useEffect(() => {
    if (!me) return;
    void api
      .fog(city?.slug)
      .then(setFog)
      .catch(() => setFog(null));
  }, [me, city?.slug]);

  useEffect(() => {
    if (!city || !container.current || mapRef.current) return;
    let cancelled = false;

    void (async () => {
      try {
        const maplibre = await import('maplibre-gl');
        if (cancelled || !container.current) return;

        const map = new maplibre.Map({
          container: container.current,
          style: TILES,
          center: [city.centre[1], city.centre[0]],
          zoom: 10.5,
          attributionControl: false,
        });
        mapRef.current = map;

        map.addControl(
          new maplibre.AttributionControl({
            compact: true,
            customAttribution:
              '© OpenStreetMap contributors · OpenFreeMap',
          }),
          'bottom-right',
        );
        map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'bottom-right');

        map.on('load', () => {
          if (cancelled) return;
          hideBoundaries(map);
          restyle(map);
          setReady(true);
          updateInView(map, places, setInView);
        });
        map.on('moveend', () => updateInView(map, places, setInView));
      } catch (error) {
        if (!cancelled) {
          setFailed(true);
          // A map that will not load must not take the screen with it: the
          // bottom sheet still lists the places, which is the useful part.
          // eslint-disable-next-line no-console
          console.warn('the map could not load', error);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [city, places]);

  // Keep the pins and the fog in step with the data.
  useEffect(() => {
    const map = mapRef.current as MapLibreMap | null;
    if (!map || !ready) return;
    drawPins(map, places);
    updateInView(map, places, setInView);
  }, [places, ready]);

  useEffect(() => {
    const map = mapRef.current as MapLibreMap | null;
    if (!map || !ready || !city) return;
    drawFog(map, city, fog);
  }, [fog, ready, city]);

  // MapLibre sizes its canvas once, from the container it was given. The
  // container changes size whenever the window is resized or the layout
  // switches between the phone and the laptop one, so tell the map about it.
  useEffect(() => {
    const node = container.current;
    if (!node || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => (mapRef.current as MapLibreMap | null)?.resize());
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  if (!city) return <Loading what="Loading the map" />;

  return (
    <div className="mapwrap map-full">
      <div ref={container} className="mapsvg" aria-label={`Map of ${city.name}`} role="application" />

      {failed && (
        <div
          className="loading"
          style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}
        >
          The map could not load. The list below still works.
        </div>
      )}

      <div className="map-top">
        {header}
        {me && fog && (
          <div className="explored">
            <div className="ex-row">
              <b>{num(fog.explored)}</b>
              <span>of {num(fog.total)} neighbourhoods explored</span>
              <span className="ex-pct">{fog.percent}%</span>
            </div>
            <div className="bar">
              <i style={{ width: `${fog.percent}%` }} />
            </div>
          </div>
        )}
      </div>

      <div className="legend">
        <span>
          <i className="lg lg-v" />
          Visited
        </span>
        <span>
          <i className="lg lg-s" />
          Saved
        </span>
        <span>
          <i className="lg lg-f" />
          Fog: not yet explored
        </span>
      </div>

      <div className="sheet sheet-map">
        <div className="grab" />
        <div className="sh-head">
          <b>In view &middot; {num(inView.length || places.length)} places</b>
          <span>Top</span>
        </div>
        {(inView.length ? inView : places).slice(0, 4).map((place) => (
          <Link className="sh-row" key={place.id} to={`/place/${place.id}`}>
            <PlaceThumb place={place} className="thumb thumb-sm" />
            <div>
              <b>{place.name.primary.text}</b>
              <span>
                {place.saved && (
                  <>
                    <Icon name="i-star" size={13} />
                    Saved &middot;{' '}
                  </>
                )}
                {distance(place.distance_km)}
              </span>
            </div>
          </Link>
        ))}
      </div>

      <span className="osm">&copy; OpenStreetMap &middot; OpenFreeMap</span>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* MapLibre helpers. The library is imported dynamically; its *types* are
 * imported statically, which costs nothing at runtime. */

/**
 * Hide every layer that draws an administrative boundary (SPEC §14).
 *
 * Matched by layer id against a pattern list rather than by a hard-coded list,
 * so a style update that renames a layer cannot quietly switch borders back on.
 */
function hideBoundaries(map: MapLibreMap): void {
  for (const layer of map.getStyle().layers) {
    const id = layer.id.toLowerCase();
    if (BOUNDARY_PATTERNS.some((pattern) => id.includes(pattern))) {
      try {
        map.setLayoutProperty(layer.id, 'visibility', 'none');
      } catch {
        /* a layer that cannot be hidden is one we did not draw */
      }
    }
  }
}

/** Read a design token as a colour MapLibre will accept.
 *
 * The map tokens in SPEC §12.2 are written as `color-mix(...)`, and a browser
 * only works that out when the value is actually painted: ask for the custom
 * property and you get the text back. MapLibre validates what it is given and
 * rejects the text, which silently left the map in the stock basemap colours.
 * Painting it onto a throwaway element makes the browser resolve it to `rgb()`.
 */
function token(name: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!raw || !/color-mix|var\(/.test(raw)) return raw;

  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;left:-9999px;top:-9999px';
  probe.style.color = raw;
  document.body.appendChild(probe);
  const resolved = getComputedStyle(probe).color;
  probe.remove();
  return srgbToRgb(resolved) || raw;
}

/** `color(srgb 0.95 0.9 0.8 / .5)` -> `rgba(242, 230, 204, 0.5)`.
 *
 * Chromium resolves `color-mix()` into CSS Color 4 notation, which MapLibre's
 * style validator does not know. Everything else is passed through untouched.
 */
function srgbToRgb(value: string): string {
  const match = /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)$/.exec(
    value.trim(),
  );
  if (!match) return value;

  const channel = (text: string) =>
    Math.round(Math.min(1, Math.max(0, Number.parseFloat(text))) * 255);
  const [r, g, b] = [match[1], match[2], match[3]].map(channel);
  const alpha = match[4] === undefined ? 1 : Number.parseFloat(match[4]);
  return alpha < 1 ? `rgba(${r}, ${g}, ${b}, ${alpha})` : `rgb(${r}, ${g}, ${b})`;
}

/** Six paint overrides, so the map reads as our paper (SPEC §12.2 map tokens). */
function restyle(map: MapLibreMap): void {
  const land = token('--map-land') || '#F2E9D8';
  const road = token('--map-road') || '#FFFCF6';
  const major = token('--map-major') || '#F0D9A8';
  const water = token('--map-water') || '#BBD3DE';
  const park = token('--map-park') || '#D8E4D4';

  const overrides: [string, string, string][] = [
    ['background', 'background-color', land],
    ['water', 'fill-color', water],
    ['landcover-grass', 'fill-color', park],
    ['landuse-residential', 'fill-color', land],
    ['highway-minor', 'line-color', road],
    ['highway-trunk', 'line-color', major],
  ];

  for (const [layerId, property, value] of overrides) {
    try {
      if (map.getLayer(layerId)) map.setPaintProperty(layerId, property, value);
    } catch {
      /* the style may not have this layer; the default is acceptable */
    }
  }
}

let pinMarkers: Marker[] = [];

function drawPins(map: MapLibreMap, places: Place[]): void {
  // Markers are DOM elements so they can use the reference's `.mp` styling and
  // stay keyboard-reachable; MapLibre's own symbol layers cannot do either.
  for (const marker of pinMarkers) marker.remove();
  pinMarkers = [];

  void import('maplibre-gl').then((maplibre) => {
    for (const place of places.slice(0, 120)) {
      const element = document.createElement('a');
      element.className = `mp ${place.verified_visits > 0 ? 'mp-visited' : ''} ${
        place.saved ? 'mp-saved' : ''
      }`.trim();
      element.href = `/place/${place.id}`;
      element.setAttribute('aria-label', place.name.primary.text);
      element.innerHTML =
        `<svg class="ic" width="16" height="16" aria-hidden="true"><use href="#${categoryIcon(
          place.category,
        )}"/></svg>`;

      const marker = new maplibre.Marker({ element, anchor: 'center' })
        .setLngLat([place.lng, place.lat])
        .addTo(map);
      pinMarkers.push(marker);
    }
  });
}

/**
 * Draw the fog: a dark rectangle over the city with a hole punched for each
 * cleared circle, plus a dashed marigold rim on each hole.
 *
 * The hole is made with turf: a polygon of the city bbox with the union of the
 * circles subtracted from it. That is the same geometry the SPEC describes, and
 * doing it with real polygons (rather than a blurred mask) means the edge of
 * what you have explored is exactly where you have been.
 */
async function drawFog(map: MapLibreMap, city: City, fog: Fog | null): Promise<void> {
  const turf = await import('@turf/turf');

  for (const id of ['fog-fill', 'fog-rim']) {
    try {
      if (map.getLayer(id)) map.removeLayer(id);
    } catch {
      /* not drawn yet */
    }
  }
  for (const id of ['fog', 'fog-rims']) {
    try {
      if (map.getSource(id)) map.removeSource(id);
    } catch {
      /* not drawn yet */
    }
  }

  const bbox = city.bbox.length === 4 ? city.bbox : null;
  if (!bbox) return;
  // The city rectangle, generously padded so the fog reaches past the edge.
  const [south, west, north, east] = bbox;
  let covered = turf.polygon([
    [
      [west - 0.15, south - 0.15],
      [east + 0.15, south - 0.15],
      [east + 0.15, north + 0.15],
      [west - 0.15, north + 0.15],
      [west - 0.15, south - 0.15],
    ],
  ]) as unknown as GeoJSON.Feature<GeoJSON.Polygon>;

  const rims: GeoJSON.Feature[] = [];
  for (const circle of fog?.circles ?? []) {
    const hole = turf.circle([circle.lng, circle.lat], circle.radius_km, {
      steps: 48,
      units: 'kilometers',
    });
    rims.push(turf.polygonToLine(hole) as unknown as GeoJSON.Feature);
    const next = turf.difference(
      turf.featureCollection([covered, hole]) as never,
    );
    if (next) covered = next as unknown as GeoJSON.Feature<GeoJSON.Polygon>;
  }

  const fogColour = token('--fog') || 'rgba(196,190,176,.62)';
  const marigold = token('--marigold') || '#E9A21B';

  map.addSource('fog', { type: 'geojson', data: covered } as never);
  map.addLayer({
    id: 'fog-fill',
    type: 'fill',
    source: 'fog',
    paint: { 'fill-color': fogColour },
  } as never);

  if (rims.length) {
    map.addSource('fog-rims', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: rims },
    } as never);
    map.addLayer({
      id: 'fog-rim',
      type: 'line',
      source: 'fog-rims',
      paint: {
        'line-color': marigold,
        'line-width': 1.6,
        'line-dasharray': [3, 5],
        'line-opacity': 0.9,
      },
    } as never);
  }
}

function updateInView(
  map: MapLibreMap,
  places: Place[],
  setInView: (places: Place[]) => void,
): void {
  try {
    const bounds = map.getBounds();
    setInView(places.filter((place) => bounds.contains([place.lng, place.lat])));
  } catch {
    setInView(places);
  }
}
