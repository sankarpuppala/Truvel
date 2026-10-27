import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { useApp } from '../lib/app-state';
import { BottomSheet } from './common';
import { Icon } from './Icon';
import type { City } from '../lib/types';

interface LocationPickerProps {
  open: boolean;
  onClose: () => void;
  showAllIndia?: boolean;
  onSelectCity?: (city: {
    name: string;
    slug: string;
    id?: number;
    lat?: number;
    lng?: number;
  }) => void;
}

export function LocationPicker({
  open,
  onClose,
  showAllIndia = false,
  onSelectCity,
}: LocationPickerProps) {
  const { me, setPosition, setActiveCityName, requestPosition, toast } = useApp();
  const [cities, setCities] = useState<City[]>([]);
  const [detecting, setDetecting] = useState(false);

  useEffect(() => {
    if (!open) return;
    api
      .cities()
      .then((res) => {
        setCities(res.cities);
      })
      .catch(() => {
        // Fallback default list if API fails
      });
  }, [open]);

  const handleDetectLiveLocation = async () => {
    setDetecting(true);
    try {
      const pos = await requestPosition(true);
      if (pos) {
        const hereInfo = await api.here(pos.lat, pos.lng).catch(() => null);
        const name = hereInfo?.name || 'Your Location';
        setActiveCityName(name);
        onSelectCity?.({
          name,
          slug: 'nearby',
          lat: pos.lat,
          lng: pos.lng,
        });
        toast(`Location set to ${name}`, 'kadam');
        onClose();
      } else {
        toast('Could not detect current location. Please pick a city below.', 'bad');
      }
    } catch {
      toast('Could not detect location. Please pick a city below.', 'bad');
    } finally {
      setDetecting(false);
    }
  };

  const handleSelectCity = async (c: City) => {
    if (c.centre && c.centre.length >= 2) {
      const lat = c.centre[0];
      const lng = c.centre[1];
      setPosition({
        lat,
        lng,
        accuracy: 1000,
      });
      setActiveCityName(c.name);
      onSelectCity?.({
        name: c.name,
        slug: c.slug,
        id: c.id ?? undefined,
        lat,
        lng,
      });
    } else if (c.slug === 'all') {
      setActiveCityName('All India');
      onSelectCity?.({
        name: c.name,
        slug: c.slug,
        id: undefined,
      });
    }

    if (me && c.id) {
      try {
        await api.saveSettings({ home_city_id: c.id });
      } catch {
        // Ignore settings save failure
      }
    }

    toast(`Location changed to ${c.name}`, 'plain');
    onClose();
  };

  return (
    <BottomSheet open={open} onClose={onClose} title="Choose Location">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 16 }}>
        {/* Detect live location */}
        <button
          type="button"
          className="cand"
          style={{
            borderColor: 'var(--laterite)',
            background: 'color-mix(in srgb, var(--laterite) 8%, var(--surface))',
          }}
          onClick={handleDetectLiveLocation}
          disabled={detecting}
        >
          <span className="mini" style={{ color: 'var(--laterite)' }}>
            <Icon name="i-target" size={20} />
          </span>
          <div>
            <b style={{ color: 'var(--laterite)' }}>
              {detecting ? 'Detecting your location...' : 'Use Current / Live Location'}
            </b>
            <span>Detect via device GPS or local network</span>
          </div>
        </button>

        {showAllIndia && (
          <button
            type="button"
            className="cand"
            onClick={() =>
              handleSelectCity({
                id: null,
                slug: 'all',
                name: 'All India',
                state: '',
                centre: null,
                bbox: null,
                place_count: 18320,
                community_count: 0,
                neighbourhood_count: 0,
                regional_langs: [],
              })
            }
          >
            <span className="mini">
              <Icon name="i-globe" size={20} />
            </span>
            <div>
              <b>All India</b>
              <span>Explore all 18,000+ places across India</span>
            </div>
          </button>
        )}

        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginTop: 6,
          }}
        >
          Cities
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {cities
            .filter((c) => c.slug !== 'all')
            .map((c) => (
              <button
                key={c.slug}
                type="button"
                className="cand"
                onClick={() => handleSelectCity(c)}
              >
                <span className="mini">
                  <Icon name="i-pin" size={18} />
                </span>
                <div>
                  <b>{c.name}</b>
                  <span>
                    {c.state}
                    {c.place_count ? ` · ${c.place_count} places` : ''}
                  </span>
                </div>
              </button>
            ))}
        </div>
      </div>
    </BottomSheet>
  );
}
