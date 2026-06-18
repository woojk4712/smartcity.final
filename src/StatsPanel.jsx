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

function methodLabel(method) {
  if (method === 'building_main_use_gross_floor_area') return '건축물 주용도 연면적 기준';
  if (method === 'zoning_area') return '용도지역 면적 기준';
  return method || '자료 없음';
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
            <p className="source-line">{row.boundary_definition}</p>
            <dl className="definition-list">
              <div>
                <dt>경계 기준</dt>
                <dd>{row.boundary_basis}</dd>
              </div>
              <div>
                <dt>출처</dt>
                <dd>{row.boundary_source}</dd>
              </div>
              <div>
                <dt>면적 산출</dt>
                <dd>{row.boundary_area_calculation_method}</dd>
              </div>
            </dl>
            <div className="metric-grid">
              <Metric icon={MapPinned} label="구역 면적" value={row.boundary_area_km2 ?? row.boundary_area_m2 / 1_000_000} suffix=" km²" />
              <Metric icon={UsersRound} label="구역 인구" value={row.display_population} suffix="명" />
              <Metric icon={Building2} label="구역 사업체" value={row.display_businesses} suffix="개" />
              <Metric icon={UsersRound} label="구역 종사자" value={row.display_workers} suffix="명" />
              <Metric icon={Building2} label="건축물 수" value={row.building_count} suffix="개" />
              <Metric icon={Building2} label="평균 용적률" value={row.avg_floor_area_ratio} suffix="%" />
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
                ['구역 면적(km²)', (r) => decimal.format(r.boundary_area_km2 ?? r.boundary_area_m2 / 1_000_000)],
                ['총인구(명)', (r) => format.format(r.display_population)],
                ['가구수(가구)', (r) => format.format(r.display_households)],
                ['종사자수(명)', (r) => format.format(r.display_workers)],
                ['사업체수(개)', (r) => format.format(r.display_businesses)],
                ['건축물 수(개)', (r) => format.format(r.building_count ?? 0)],
                ['건축물 연면적 합계(m²)', (r) => format.format(r.building_gross_floor_area_m2 ?? 0)],
                ['직주비(종사자/인구)', (r) => decimal.format(r.job_housing_ratio ?? 0)],
                ['LUM', (r) => decimal.format(r.landuse_mix_index ?? 0)],
                ['LUM 기준', (r) => methodLabel(r.lum_method)],
                ['평균 용적률(%)', (r) => (r.avg_floor_area_ratio === null || r.avg_floor_area_ratio === undefined ? '자료 없음' : decimal.format(r.avg_floor_area_ratio))],
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
        <h2>구역계 정의 및 출처</h2>
        <div className="table-scroll">
          <table className="comparison-table boundary-table">
            <thead>
              <tr>
                <th>지역명</th>
                <th>비교 대상 정의</th>
                <th>경계 기준</th>
                <th>출처</th>
                <th>면적(km²)</th>
                <th>면적 산출 방식</th>
                <th>비고</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.area_key}>
                  <th>{row.label}</th>
                  <td>{row.boundary_definition}</td>
                  <td>{row.boundary_basis}</td>
                  <td>{row.boundary_source}</td>
                  <td>{decimal.format(row.boundary_area_km2 ?? row.boundary_area_m2 / 1_000_000)}</td>
                  <td>{row.boundary_area_calculation_method}</td>
                  <td>{row.boundary_note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="table-panel">
        <h2>
          <ClipboardCheck size={16} /> 데이터 검증
        </h2>
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
                <span>30분 도달 역 {format.format(item.reachable_station_30_count || 0)}개</span>
                <span>60분 도달 역 {format.format(item.reachable_station_60_count || 0)}개</span>
                <span>60분-30분 인구 증가 {format.format(item.commuter_population_delta_60_30 || 0)}명</span>
                <span>60분-30분 종사자 증가 {format.format(item.commuter_workers_delta_60_30 || 0)}명</span>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
