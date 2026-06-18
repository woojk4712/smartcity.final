import { Building2, ClipboardCheck, MapPinned, TrainFront, UsersRound } from 'lucide-react';

const format = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });

function Metric({ icon: Icon, label, value, suffix = '' }) {
  const missing = value === null || value === undefined || Number.isNaN(value);
  return (
    <div className="metric">
      <Icon size={18} />
      <div>
        <span>{label}</span>
        <strong>{missing ? '자료 없음' : `${format.format(value)}${suffix}`}</strong>
      </div>
    </div>
  );
}

export function StatsPanel({ summary, validation, mode }) {
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
            <p className="source-line">{row.boundary_source}</p>
            <div className="metric-grid">
              <Metric icon={MapPinned} label="구역 면적" value={row.boundary_area_m2 / 1_000_000} suffix=" km²" />
              <Metric icon={UsersRound} label="구역 인구" value={row.display_population} suffix="명" />
              <Metric icon={Building2} label="구역 사업체" value={row.display_businesses} suffix="개" />
              <Metric icon={UsersRound} label="구역 종사자" value={row.display_workers} suffix="명" />
              <Metric icon={TrainFront} label="30분 통근권 인구" value={row.commuter_population_30min} suffix="명" />
              <Metric icon={TrainFront} label="60분 통근권 인구" value={row.commuter_population_60min} suffix="명" />
              <Metric icon={Building2} label="30분 통근권 종사자" value={row.commuter_workers_30min} suffix="명" />
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
                ['구역 면적(km²)', (r) => decimal.format(r.boundary_area_m2 / 1_000_000)],
                ['총인구(명)', (r) => format.format(r.display_population)],
                ['가구수(가구)', (r) => format.format(r.display_households)],
                ['종사자수(명)', (r) => format.format(r.display_workers)],
                ['사업체수(개)', (r) => format.format(r.display_businesses)],
                ['직주비(종사자/인구)', (r) => decimal.format(r.job_housing_ratio ?? 0)],
                ['LUM', (r) => decimal.format(r.landuse_mix_index ?? 0)],
                ['평균 용적률(%)', (r) => r.avg_floor_area_ratio ?? '자료 없음'],
                ['30분 통근권 인구(명)', (r) => format.format(r.commuter_population_30min)],
                ['60분 통근권 인구(명)', (r) => format.format(r.commuter_population_60min)],
                ['30분 통근권 종사자(명)', (r) => format.format(r.commuter_workers_30min)],
                ['60분 통근권 종사자(명)', (r) => format.format(r.commuter_workers_60min)],
              ].map(([label, getter]) => (
                <tr key={label}>
                  <th>{label}</th>
                  {rows.map((row) => (
                    <td key={row.area_key}>{getter(row)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="table-panel">
        <h2><ClipboardCheck size={16} /> 데이터 검증</h2>
        <div className="validation-grid">
          {rows.map((row) => {
            const item = validation?.[row.area_key] || {};
            return (
              <div className="validation-card" key={row.area_key}>
                <strong>{row.label}</strong>
                <span>필지 {format.format(item.parcel_count || 0)}개</span>
                <span>건축물 {format.format(item.building_count || 0)}개</span>
                <span>집계구 {format.format(item.aggregation_count_population || 0)}개</span>
                <span>인구 {format.format(item.total_population || 0)}명</span>
                <span>사업체 {format.format(item.total_businesses || 0)}개</span>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
