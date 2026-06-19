import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const colors = ['#2563eb', '#0f766e', '#f97316', '#7c3aed', '#dc2626', '#64748b'];

function shortName(label = '') {
  return label.replace('제1', '').replace('테크노밸리', 'TV').replace('국제업무지구', '업무지구');
}

function metricRows(summary, key, fallback = 0) {
  return summary.map((row) => ({
    name: shortName(row.label),
    value: row[key] ?? fallback,
  }));
}

export function Charts({ summary, landuse, accessibility, industry }) {
  const scaleRows = summary.map((row) => ({
    name: shortName(row.label),
    사업체수: row.display_businesses ?? 0,
    종사자수: row.display_workers ?? 0,
  }));

  const curveRows = [15, 30, 45, 60].map((minutes) => {
    const row = { minutes };
    accessibility.forEach((area) => {
      const item = area.cumulative_accessibility?.find((d) => d.minutes === minutes);
      row[`${shortName(area.label)} 인구`] = Math.round(item?.allocated_population ?? 0);
      row[`${shortName(area.label)} 종사자`] = Math.round(item?.allocated_workers ?? 0);
    });
    return row;
  });

  const commuteRows = summary.map((row) => ({
    name: shortName(row.label),
    '30분 인구': row.commuter_population_30min ?? 0,
    '60분 인구': row.commuter_population_60min ?? 0,
    '30분 종사자': row.commuter_workers_30min ?? 0,
    '60분 종사자': row.commuter_workers_60min ?? 0,
  }));

  const spatialDensityRows = summary.map((row) => ({
    name: shortName(row.label),
    '정류장 밀도': row.bus_stop_density_per_km2 ?? 0,
    '도로망 밀도': row.road_network_density_km_per_km2 ?? 0,
  }));

  const icRows = summary.map((row) => ({
    name: shortName(row.label),
    '최근접 IC 거리': row.nearest_highway_ic_km ?? 0,
  }));

  const stationCatchmentRows = summary.map((row) => ({
    name: shortName(row.label),
    '500m 역세권': row.station_area_ratio_500m ?? 0,
    '1km 역세권': row.station_area_ratio_1km ?? 0,
  }));

  const industryNames = Array.from(
    new Set(
      industry.flatMap((area) =>
        (area.industry_composition || [])
          .slice()
          .sort((a, b) => (b.workers || 0) - (a.workers || 0))
          .slice(0, 5)
          .map((item) => item.industry),
      ),
    ),
  ).slice(0, 8);

  const industryRows = industryNames.map((name) => {
    const row = { industry: name };
    industry.forEach((area) => {
      const item = (area.industry_composition || []).find((entry) => entry.industry === name);
      row[shortName(area.label)] = Math.round(item?.workers || 0);
    });
    return row;
  });

  return (
    <section className="chart-grid">
      <MetricChart title="LUM" data={metricRows(summary, 'landuse_mix_index')} unit="" color="#2563eb" />
      <MetricChart title="직주비" data={metricRows(summary, 'job_housing_ratio')} unit="" color="#0f766e" />
      <MetricChart title="평균 용적률" data={metricRows(summary, 'avg_floor_area_ratio', 0)} unit="%" color="#f97316" />

      <Chart title="공간접근성 밀도">
        <BarChart data={spatialDensityRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="정류장 밀도" fill="#2563eb" radius={[3, 3, 0, 0]} />
          <Bar dataKey="도로망 밀도" fill="#0f766e" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>

      <MetricChart title="최근접 IC 거리" data={icRows.map((row) => ({ name: row.name, value: row['최근접 IC 거리'] }))} unit="km" color="#dc2626" />

      <Chart title="역세권 면적 비율">
        <BarChart data={stationCatchmentRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} />
          <Legend />
          <Bar dataKey="500m 역세권" fill="#7c3aed" radius={[3, 3, 0, 0]} />
          <Bar dataKey="1km 역세권" fill="#f97316" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>

      <Chart title="사업체 · 종사자 규모">
        <BarChart data={scaleRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="사업체수" fill="#7c3aed" radius={[3, 3, 0, 0]} />
          <Bar dataKey="종사자수" fill="#dc2626" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>

      <Chart title="30·60분 통근권">
        <BarChart data={commuteRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="30분 인구" fill="#2563eb" radius={[3, 3, 0, 0]} />
          <Bar dataKey="60분 인구" fill="#93c5fd" radius={[3, 3, 0, 0]} />
          <Bar dataKey="30분 종사자" fill="#0f766e" radius={[3, 3, 0, 0]} />
          <Bar dataKey="60분 종사자" fill="#5eead4" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>

      <Chart title="누적 접근성 곡선">
        <LineChart data={curveRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="minutes" unit="분" />
          <YAxis />
          <Tooltip />
          <Legend />
          {accessibility.flatMap((area, index) => [
            <Line key={`${area.area_key}-pop`} type="monotone" dataKey={`${shortName(area.label)} 인구`} stroke={colors[index]} strokeWidth={2} dot={false} />,
            <Line key={`${area.area_key}-work`} type="monotone" dataKey={`${shortName(area.label)} 종사자`} stroke={colors[index + 2]} strokeWidth={2} strokeDasharray="5 4" dot={false} />,
          ])}
        </LineChart>
      </Chart>

      {landuse.map((row, index) => (
        <Chart title={`${row.label} 용도지역 구성비`} key={row.area_key}>
          <PieChart>
            <Pie data={row.classes} dataKey="share" nameKey="class" innerRadius={42} outerRadius={78} paddingAngle={1}>
              {row.classes.map((entry, idx) => (
                <Cell key={entry.class} fill={colors[(idx + index) % colors.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`} />
            <Legend />
          </PieChart>
        </Chart>
      ))}

      {landuse
        .filter((row) => row.building_use_classes?.length)
        .map((row, index) => (
          <Chart title={`${row.label} 건축물 주용도 구성비`} key={`${row.area_key}-building`}>
            <PieChart>
              <Pie data={row.building_use_classes} dataKey="share" nameKey="class" innerRadius={42} outerRadius={78} paddingAngle={1}>
                {row.building_use_classes.map((entry, idx) => (
                  <Cell key={entry.class} fill={colors[(idx + index + 2) % colors.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`} />
              <Legend />
            </PieChart>
          </Chart>
        ))}

      <Chart title="주요 업종 종사자 구성">
        <BarChart data={industryRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="industry" hide />
          <YAxis />
          <Tooltip />
          <Legend />
          {summary.map((row, idx) => (
            <Bar key={row.area_key} dataKey={shortName(row.label)} fill={colors[idx]} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      </Chart>
    </section>
  );
}

function MetricChart({ title, data, unit, color }) {
  return (
    <Chart title={title}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip formatter={(value) => `${value}${unit}`} />
        <Bar dataKey="value" name={title} fill={color} radius={[3, 3, 0, 0]} />
      </BarChart>
    </Chart>
  );
}

function Chart({ title, children }) {
  return (
    <article className="chart-panel">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={230}>
        {children}
      </ResponsiveContainer>
    </article>
  );
}
