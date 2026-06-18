import { Building2, MapPinned, TrainFront, UsersRound } from 'lucide-react';

const format = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 });

function Metric({ icon: Icon, label, value, suffix = '' }) {
  return (
    <div className="metric">
      <Icon size={18} />
      <div>
        <span>{label}</span>
        <strong>{value === null || value === undefined ? '자료 없음' : `${format.format(value)}${suffix}`}</strong>
      </div>
    </div>
  );
}

export function StatsPanel({ summary, mode }) {
  const rows = mode === 'compare' ? summary : summary.filter((row) => row.area_key === mode);
  return (
    <>
      <section className="stats-grid">
        {rows.map((row) => (
          <article className="area-card" key={row.area_key}>
            <header>
              <h2>{row.label}</h2>
              <span>{row.analysis_date}</span>
            </header>
            <div className="metric-grid">
              <Metric icon={MapPinned} label="구역 면적" value={row.boundary_area_m2 / 1_000_000} suffix=" km²" />
              <Metric icon={UsersRound} label="구역 인구" value={row.allocated_population} suffix="명" />
              <Metric icon={Building2} label="구역 사업체" value={row.allocated_businesses} suffix="개" />
              <Metric icon={TrainFront} label="최근접 역" value={row.nearest_station_m} suffix=" m" />
              <Metric icon={UsersRound} label="60분 통근권 인구" value={row.commuter_population_60min} suffix="명" />
              <Metric icon={Building2} label="60분 통근권 종사자" value={row.commuter_workers_60min} suffix="명" />
            </div>
          </article>
        ))}
      </section>
      <section className="table-panel">
        <h2>비교 통계표</h2>
        <div className="table-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>지표</th>
                {rows.map((row) => (
                  <th key={row.area_key}>{row.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['구역 면적(km²)', (r) => r.boundary_area_m2 / 1_000_000],
                ['구역 총인구(명)', (r) => r.allocated_population],
                ['구역 가구수(가구)', (r) => r.allocated_households],
                ['구역 종사자수(명)', (r) => r.allocated_workers],
                ['구역 사업체수(개)', (r) => r.allocated_businesses],
                ['60분 통근권 총인구(명)', (r) => r.commuter_population_60min],
                ['60분 통근권 가구수(가구)', (r) => r.commuter_households_60min],
                ['60분 통근권 총종사자수(명)', (r) => r.commuter_workers_60min],
                ['용도혼합도', (r) => r.landuse_mix_index],
                ['2km 철도역 수', (r) => r.station_count_2km],
              ].map(([label, getter]) => (
                <tr key={label}>
                  <th>{label}</th>
                  {rows.map((row) => (
                    <td key={row.area_key}>{format.format(getter(row) ?? 0)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
