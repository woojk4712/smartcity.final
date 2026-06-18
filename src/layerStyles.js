export const areaMeta = {
  pangyo: {
    label: '판교 1테크노밸리',
    color: '#2563eb',
    fill: '#93c5fd',
    center: [37.4007, 127.1089],
  },
  cheongna: {
    label: '청라국제도시',
    color: '#0f766e',
    fill: '#5eead4',
    center: [37.5333, 126.6497],
  },
};

export function boundaryStyle(key) {
  return {
    color: areaMeta[key].color,
    weight: 3,
    fillColor: areaMeta[key].fill,
    fillOpacity: 0.22,
  };
}

export function parcelStyle(key) {
  return {
    color: areaMeta[key].color,
    weight: 0.8,
    fillColor: areaMeta[key].fill,
    fillOpacity: 0.12,
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
