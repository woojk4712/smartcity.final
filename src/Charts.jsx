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

export function Charts({ summary, landuse, accessibility }) {
  const landuseRows = landuse.map((row) => ({
    name: row.label.replace(' 1테크노밸리', ''),
    LUM: row.landuse_mix_index,
  }));
  const accessRows = accessibility.map((row) => ({
    name: row.label.replace(' 1테크노밸리', ''),
    '2km 역 수': row.station_count_2km,
    '20km 역 수': row.active_station_count_20km,
  }));
  const curveRows = [15, 30, 45, 60].map((minutes) => {
    const row = { minutes };
    accessibility.forEach((area) => {
      const item = area.cumulative_accessibility?.find((d) => d.minutes === minutes);
      row[`${area.label} 인구`] = item?.allocated_population ?? 0;
      row[`${area.label} 종사자`] = item?.allocated_workers ?? 0;
    });
    return row;
  });
  const densityRows = summary.map((row) => ({
    name: row.label.replace(' 1테크노밸리', ''),
    '인구밀도': row.population_density_per_km2,
    '종사자': row.allocated_workers,
  }));

  return (
    <section className="chart-grid">
      <Chart title="공간 집약도">
        <BarChart data={densityRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="인구밀도" fill="#2563eb" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>
      <Chart title="용도혼합도">
        <BarChart data={landuseRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis domain={[0, 1]} />
          <Tooltip />
          <Bar dataKey="LUM" fill="#0f766e" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>
      <Chart title="철도 접근성">
        <BarChart data={accessRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="2km 역 수" fill="#f97316" radius={[3, 3, 0, 0]} />
          <Bar dataKey="20km 역 수" fill="#7c3aed" radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>
      <Chart title="등시간권 누적 접근성">
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
        <Chart title={`${row.label} 용도지역 비율`} key={row.area_key}>
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
