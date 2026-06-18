export const areaMeta = {
  pangyo: {
    label: '판교 제1테크노밸리',
    color: '#2563eb',
    fill: '#93c5fd',
    center: [37.4007, 127.1089],
  },
  cheongna: {
    label: '청라국제업무지구',
    color: '#0f766e',
    fill: '#5eead4',
    center: [37.5333, 126.6497],
  },
};

export const buildingUseColors = {
  업무: '#2563eb',
  상업: '#f97316',
  주거: '#16a34a',
  교육연구: '#7c3aed',
  공공: '#dc2626',
  기타: '#64748b',
};

export const zoningColors = {
  일반상업지역: '#f97316',
  중심상업지역: '#dc2626',
  준주거지역: '#16a34a',
  일반주거지역: '#86efac',
  도시지원시설용지: '#2563eb',
  기타: '#94a3b8',
};

export function buildingUseCategory(name = '') {
  if (name.includes('업무') || name.includes('공장') || name.includes('지식산업')) return '업무';
  if (name.includes('판매') || name.includes('근린생활') || name.includes('상가') || name.includes('숙박')) return '상업';
  if (name.includes('주택') || name.includes('공동주택') || name.includes('다가구') || name.includes('아파트')) return '주거';
  if (name.includes('교육') || name.includes('연구') || name.includes('학교')) return '교육연구';
  if (name.includes('공공') || name.includes('문화') || name.includes('의료') || name.includes('운동') || name.includes('종교')) return '공공';
  return '기타';
}

export function boundaryStyle(key) {
  return {
    color: areaMeta[key].color,
    weight: 3,
    fillColor: areaMeta[key].fill,
    fillOpacity: 0.08,
  };
}

export function parcelStyle(key, colorByZoning = false) {
  return (feature) => {
    const category = feature?.properties?.zoning_category || '기타';
    return {
      color: colorByZoning ? '#475569' : areaMeta[key].color,
      weight: colorByZoning ? 0.6 : 0.9,
      fillColor: colorByZoning ? zoningColors[category] || zoningColors.기타 : areaMeta[key].fill,
      fillOpacity: colorByZoning ? 0.58 : 0.03,
    };
  };
}

export function buildingStyle(colorByUse = false) {
  return (feature) => {
    const category = buildingUseCategory(feature?.properties?.main_use || '');
    return {
      color: '#334155',
      weight: colorByUse ? 0.7 : 1,
      fillColor: colorByUse ? buildingUseColors[category] || buildingUseColors.기타 : '#dc2626',
      fillOpacity: colorByUse ? 0.7 : 0.22,
    };
  };
}

export function isoStyle(key, minutes) {
  return {
    color: minutes === 30 ? '#f97316' : '#7c3aed',
    weight: 2,
    dashArray: minutes === 30 ? '8 5' : '3 6',
    fillOpacity: minutes === 30 ? 0.08 : 0.05,
    fillColor: minutes === 30 ? '#fdba74' : '#c4b5fd',
  };
}
