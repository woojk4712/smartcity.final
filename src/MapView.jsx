import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import { dataPath, loadJson } from './dataLoader.js';
import { areaMeta, boundaryStyle, isoStyle, parcelStyle } from './layerStyles.js';

const stationIcon = L.divIcon({
  className: 'station-marker',
  html: '<span></span>',
  iconSize: [14, 14],
});

const buildingIcon = L.divIcon({
  className: 'building-marker',
  html: '<span></span>',
  iconSize: [16, 16],
});

const PROPERTY_LABELS = {
  PNU: 'PNU',
  JIBUN: '지번',
  main_use: '주용도',
  building_area_m2: '건축면적(m²)',
  gross_floor_area_m2: '연면적(m²)',
  land_area_m2: '대지면적(m²)',
  building_coverage_ratio: '건폐율(%)',
  floor_area_ratio: '용적률(%)',
  approval_date: '사용승인일',
  building_name: '건물명',
  road_address: '도로명주소',
  overlap_area: '중첩면적(m²)',
  overlap_ratio: '중첩률',
};

function popupTable(properties = {}) {
  const preferred = Object.keys(PROPERTY_LABELS)
    .filter((key) => properties[key] !== null && properties[key] !== undefined)
    .map((key) => [PROPERTY_LABELS[key], properties[key]]);
  const rest = Object.entries(properties)
    .filter(([, value]) => value !== null && value !== undefined && `${value}`.length < 120)
    .filter(([key]) => !PROPERTY_LABELS[key])
    .slice(0, 10)
    .map(([key, value]) => [key, value]);
  const rows = [...preferred, ...rest]
    .map(([key, value]) => `<tr><th>${key}</th><td>${value}</td></tr>`)
    .join('');
  return `<table class="popup-table">${rows}</table>`;
}

export function MapView({ mode, layers, isochroneMinutes }) {
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const visibleAreas = useMemo(() => (mode === 'compare' ? ['pangyo', 'cheongna'] : [mode]), [mode]);

  useEffect(() => {
    if (mapRef.current) return;
    mapRef.current = L.map('map', { zoomControl: false }).setView([37.47, 126.9], 10);
    L.control.zoom({ position: 'bottomright' }).addTo(mapRef.current);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(mapRef.current);
    layerRef.current = L.layerGroup().addTo(mapRef.current);
  }, []);

  useEffect(() => {
    let alive = true;
    const map = mapRef.current;
    const group = layerRef.current;
    if (!map || !group) return undefined;
    group.clearLayers();

    async function draw() {
      const bounds = L.latLngBounds([]);
      for (const key of visibleAreas) {
        if (layers.boundary) {
          const boundary = await loadJson(dataPath(`boundaries/${key}_boundary.geojson`));
          if (!alive || !boundary) return;
          L.geoJSON(boundary, {
            style: boundaryStyle(key),
            onEachFeature: (feature, layer) => {
              layer.bindPopup(`<strong>${areaMeta[key].label}</strong>${popupTable(feature.properties)}`);
            },
          }).addTo(group).eachLayer((l) => bounds.extend(l.getBounds()));
        }
        if (layers.parcels) {
          const parcels = await loadJson(dataPath(`parcels/${key}_matched_parcels.geojson`));
          if (alive && parcels) {
            L.geoJSON(parcels, {
              style: parcelStyle(key),
              onEachFeature: (feature, layer) => layer.bindPopup(popupTable(feature.properties)),
            }).addTo(group);
          }
        }
        if (layers.buildings) {
          const buildings = await loadJson(dataPath(`buildings/${key}_buildings.geojson`));
          if (alive && buildings) {
            L.geoJSON(buildings, {
              pointToLayer: (_feature, latlng) => L.marker(latlng, { icon: buildingIcon }),
              onEachFeature: (feature, layer) => layer.bindPopup(popupTable(feature.properties)),
            }).addTo(group);
          }
        }
        if (layers.isochrone) {
          const iso = await loadJson(dataPath(`transport/${key}_isochrone_${isochroneMinutes}.geojson`));
          if (alive && iso) {
            L.geoJSON(iso, {
              style: isoStyle(key, isochroneMinutes),
              onEachFeature: (feature, layer) => layer.bindPopup(popupTable(feature.properties)),
            }).addTo(group);
          }
        }
        if (layers.isochrone) {
          const rail = await loadJson(dataPath(`transport/${key}_rail_${isochroneMinutes}.geojson`));
          if (alive && rail) {
            L.geoJSON(rail, {
              pointToLayer: (_feature, latlng) => L.marker(latlng, { icon: stationIcon }),
              onEachFeature: (feature, layer) => layer.bindPopup(popupTable(feature.properties)),
            }).addTo(group);
          }
        }
      }
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.18), { animate: false });
    }

    draw();
    return () => {
      alive = false;
    };
  }, [visibleAreas, layers, isochroneMinutes]);

  return <div id="map" aria-label="비교 GIS 지도" />;
}
