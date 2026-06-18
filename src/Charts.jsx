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

function shortName(label) {
  return label.replace('제1', '').replace('테크노밸리', 'TV').replace('국제업무지구', '업무지구');
}

export function Charts({ summary, landuse, accessibility, industry }) {
  const indexRows = summary.map((row) => ({
    name: shortName(row.label),
    LUM: row.landuse_mix_index ?? 0,
    '직주비': row.job_housing_ratio ?? 0,
    '평균 용적률': row.avg_floor_area_ratio ?? 0,
  }));

  const scaleRows = summary.map((row) => ({
    name: shortName(row.label),
    '사업체수': row.display_businesses ?? 0,
    '종사자수': row.display_workers ?? 0,
  }));

  const curveRows = [15, 30, 45, 60].map((minutes) => {
    const row = { minutes };
    accessibility.forEach((area) => {
      const item = area.cumulative_accessibility?.find((d) => d.minutes === minutes);
      row[`${area.label} 인구`] = Math.round(item?.allocated_population ?? 0);
      row[`${area.label} 종사자`] = Math.round(item?.allocated_workers ?? 0);
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

  const industryRows = industry.flatMap((area) =>
    (area.industry_composition || [])
      .slice()
      .sort((a, b) => (b.workers || 0) - (a.workers || 0))
      .slice(0, 5)
      .map((item) => ({
        area: shortName(area.label),
        industry: item.industry,
        workers: Math.round(item.workers || 0),
      })),
  );

  return (
    <section className="chart-grid">
      <Chart title="LUM · 직주비 · 용적률">
        <BarChart data={indexRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="LUM" fill="#2563eb" radius={[3, 3, 0, 0]} />
          <Bar dataKey="직주비" fill="#0f766e" radius={[3, 3, 0, 0]} />
          <Bar dataKey="평균 용적률" fill="#f97316" radius={[3, 3, 0, 0]} />
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
            <Line key={`${area.area_key}-pop`} type="monotone" dataKey={`${area.label} 인구`} stroke={colors[index]} strokeWidth={2} dot={false} />,
            <Line key={`${area.area_key}-work`} type="monotone" dataKey={`${area.label} 종사자`} stroke={colors[index + 2]} strokeWidth={2} strokeDasharray="5 4" dot={false} />,
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
            <Tooltip formatter={(value) => `${(value * 100).toFixed(1)}%`} />
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
            <Bar key={row.area_key} dataKey="workers" name={shortName(row.label)} fill={colors[idx]} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      </Chart>
    </section>
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
