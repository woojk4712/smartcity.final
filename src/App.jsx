import { useEffect, useState } from 'react';
import { Layers, Map, SplitSquareHorizontal } from 'lucide-react';
import { Charts } from './Charts.jsx';
import { loadAnalytics } from './dataLoader.js';
import { MapView } from './MapView.jsx';
import { StatsPanel } from './StatsPanel.jsx';

const modes = [
  ['compare', '비교'],
  ['pangyo', '판교'],
  ['cheongna', '청라'],
];

export function App() {
  const [mode, setMode] = useState('compare');
  const [isochroneMinutes, setIsochroneMinutes] = useState(30);
  const [layers, setLayers] = useState({ boundary: true, parcels: false, buildings: true, isochrone: false });
  const [analytics, setAnalytics] = useState({ summary: [], landuse: [], accessibility: [], industry: [], bonus: [], validation: {} });

  useEffect(() => {
    loadAnalytics().then(setAnalytics);
  }, []);

  const toggleLayer = (key) => setLayers((current) => ({ ...current, [key]: !current[key] }));

  return (
    <main className="app-shell">
      <aside className="side-panel">
        <div className="brand">
          <Map size={22} />
          <div>
            <h1>업무지구 비교 GIS</h1>
            <p>판교 1테크노밸리 · 청라국제도시</p>
          </div>
        </div>

        <div className="control-block">
          <div className="control-title">
            <SplitSquareHorizontal size={16} />
            <span>보기</span>
          </div>
          <div className="segmented">
            {modes.map(([key, label]) => (
              <button key={key} className={mode === key ? 'active' : ''} onClick={() => setMode(key)}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="control-block">
          <div className="control-title">
            <Layers size={16} />
            <span>레이어</span>
          </div>
          {[
            ['boundary', '구역계'],
            ['parcels', '매칭 필지'],
            ['buildings', '건축물'],
            ['isochrone', '등시간권'],
          ].map(([key, label]) => (
            <label className="toggle-row" key={key}>
              <input type="checkbox" checked={layers[key]} onChange={() => toggleLayer(key)} />
              <span>{label}</span>
            </label>
          ))}
          <div className="segmented compact">
            {[30, 60].map((minutes) => (
              <button
                key={minutes}
                className={isochroneMinutes === minutes ? 'active' : ''}
                onClick={() => setIsochroneMinutes(minutes)}
              >
                {minutes}분
              </button>
            ))}
          </div>
        </div>

        <p className="data-note">
          SGIS 경계, 도로망, 용도지역 공간자료가 없는 항목은 산출물에 대체 출처가 표시됩니다.
        </p>
      </aside>

      <section className="workspace">
        <MapView mode={mode} layers={layers} isochroneMinutes={isochroneMinutes} />
        <StatsPanel summary={analytics.summary} validation={analytics.validation} mode={mode} />
        <Charts
          summary={analytics.summary}
          landuse={analytics.landuse}
          accessibility={analytics.accessibility}
          industry={analytics.industry}
        />
      </section>
    </main>
  );
}
