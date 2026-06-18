const jsonCache = new Map();
const BASE = import.meta.env.BASE_URL;

export async function loadJson(path, fallback = null) {
  if (jsonCache.has(path)) return jsonCache.get(path);
  try {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    jsonCache.set(path, data);
    return data;
  } catch (error) {
    console.warn(`Failed to load ${path}`, error);
    return fallback;
  }
}

export async function loadAnalytics() {
  const [summary, landuse, accessibility, industry, bonus, validation] = await Promise.all([
    loadJson(dataPath('analytics/summary.json'), []),
    loadJson(dataPath('analytics/landuse_mix.json'), []),
    loadJson(dataPath('analytics/accessibility.json'), []),
    loadJson(dataPath('analytics/industry.json'), []),
    loadJson(dataPath('analytics/bonus_indicators.json'), []),
    loadJson(dataPath('reports/validation_report.json'), {}),
  ]);
  return { summary, landuse, accessibility, industry, bonus, validation };
}

export function dataPath(path) {
  return `${BASE}data/${path}`;
}
