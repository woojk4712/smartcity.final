import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import { dataPath, loadJson } from './dataLoader.js';
import {
  areaMeta,
  boundaryStyle,
  buildingStyle,
  buildingUseColors,
  buildingUseCategory,
  isoStyle,
  parcelStyle,
  zoningColors,
} from './layerStyles.js';

const stationIcon = L.divIcon({
  className: 'station-marker',
  html: '<span></span>',
  iconSize: [14, 14],
});

const FIELD_LABELS = {
  area_label: '지역명',
  building_name: '건물명',
  main_use: '주용도',
  gross_floor_area_m2: '연면적(㎡)',
  land_area_m2: '대지면적(㎡)',
  floor_area_ratio: '용적률(%)',
  building_coverage_ratio: '건폐율(%)',
  floors: '층수',
  approval_date: '사용승인일',
  PNU: 'PNU',
  JIBUN: '지번',
  parcel_area_m2: '필지면적(㎡)',
  zoning_primary: '용도지역',
  zoning_districts: '용도지구',
  building_count: '건축물 수',
  building_gross_floor_area_m2: '건축물 연면적 합계(㎡)',
  avg_floor_area_ratio: '평균 용적률(%)',
};

const BUILDING_FIELDS = [
  'area_label',
  'building_name',
  'main_use',
  'gross_floor_area_m2',
  'land_area_m2',
  'floor_area_ratio',
  'building_coverage_ratio',
  'floors',
  'approval_date',
];

const PARCEL_FIELDS = [
  'PNU',
  'JIBUN',
  'parcel_area_m2',
  'zoning_primary',
  'zoning_districts',
  'building_count',
  'building_gross_floor_area_m2',
  'avg_floor_area_ratio',
];

function formatValue(value) {
  if (value === null || value === undefined || value === '' || Number.isNaN(value)) return '자료 없음';
  if (typeof value === 'number') return value.toLocaleString('ko-KR', { maximumFractionDigits: 1 });
  return value;
}

function popupTable(properties = {}, fields) {
  const rows = fields
    .map((key) => `<tr><th>${FIELD_LABELS[key] || key}</th><td>${formatValue(properties[key])}</td></tr>`)
    .join('');
  return `<table class="popup-table">${rows}</table>`;
}

function popupTitle(feature, fallback) {
  const props = feature?.properties || {};
  if (props.feature_type === 'building') return props.building_name || props.main_use || '건축물';
  if (props.feature_type === 'parcel') return props.JIBUN ? `필지 ${props.JIBUN}` : '분석 필지';
  return fallback;
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
              layer.bindPopup(`<strong>${areaMeta[key].label}</strong>`);
            },
          })
            .addTo(group)
            .eachLayer((layer) => bounds.extend(layer.getBounds()));
        }

        if (layers.zoningMap || layers.parcelBoundary) {
          const parcels = await loadJson(dataPath(`parcels/${key}_matched_parcels.geojson`));
          if (alive && parcels) {
            L.geoJSON(parcels, {
              style: parcelStyle(key, layers.zoningMap),
              onEachFeature: (feature, layer) => {
                layer.bindPopup(`<strong>${popupTitle(feature, areaMeta[key].label)}</strong>${popupTable(feature.properties, PARCEL_FIELDS)}`);
              },
            })
              .addTo(group)
              .eachLayer((layer) => bounds.extend(layer.getBounds()));
          }
        }

        if (layers.buildingUseMap || layers.buildingBoundary) {
          const buildings = await loadJson(dataPath(`buildings/${key}_buildings.geojson`));
          if (alive && buildings) {
            L.geoJSON(buildings, {
              style: buildingStyle(layers.buildingUseMap),
              pointToLayer: (_feature, latlng) => L.marker(latlng, { icon: stationIcon }),
              onEachFeature: (feature, layer) => {
                const category = buildingUseCategory(feature.properties?.main_use || '');
                layer.bindPopup(
                  `<strong>${popupTitle(feature, areaMeta[key].label)}</strong><div class="popup-subtitle">${category}</div>${popupTable(feature.properties, BUILDING_FIELDS)}`,
                );
              },
            })
              .addTo(group)
              .eachLayer((layer) => {
                if (layer.getBounds) bounds.extend(layer.getBounds());
              });
          }
        }

        if (layers.isochrone) {
          const iso = await loadJson(dataPath(`transport/${key}_isochrone_${isochroneMinutes}.geojson`));
          if (alive && iso) {
            L.geoJSON(iso, {
              style: isoStyle(key, isochroneMinutes),
              onEachFeature: (feature, layer) => layer.bindPopup(popupTable(feature.properties, ['minutes', 'source'])),
            }).addTo(group);
          }
        }

        if (layers.stations) {
          const rail = await loadJson(dataPath(`transport/${key}_rail_${isochroneMinutes}.geojson`));
          if (alive && rail) {
            L.geoJSON(rail, {
              pointToLayer: (_feature, latlng) => L.marker(latlng, { icon: stationIcon }),
              onEachFeature: (feature, layer) => layer.bindPopup(popupTable(feature.properties, ['statnm', 'linenm', 'travel_time_min'])),
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

  return (
    <div className="map-frame">
      <div id="map" aria-label="비교 GIS 지도" />
      <Legend layers={layers} />
    </div>
  );
}

function Legend({ layers }) {
  return (
    <aside className="map-legend" aria-label="지도 범례">
      <strong>범례</strong>
      {layers.buildingUseMap && (
        <LegendGroup title="건축물 주용도" items={buildingUseColors} />
      )}
      {layers.zoningMap && (
        <LegendGroup title="용도지역" items={zoningColors} />
      )}
      <div className="legend-row">
        <span className="legend-line boundary" />
        <span>구역 경계</span>
      </div>
      <div className="legend-row">
        <span className="legend-line iso30" />
        <span>30분 등시간권</span>
      </div>
      <div className="legend-row">
        <span className="legend-line iso60" />
        <span>60분 등시간권</span>
      </div>
    </aside>
  );
}

function LegendGroup({ title, items }) {
  return (
    <div className="legend-group">
      <span className="legend-title">{title}</span>
      {Object.entries(items).map(([label, color]) => (
        <div className="legend-row" key={label}>
          <span className="legend-swatch" style={{ backgroundColor: color }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
