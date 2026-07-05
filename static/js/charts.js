/**
 * charts.js — Shared utilities for Nepal Student Visa Analytics Dashboard
 * Design: MoonRow × Australian palette
 * Colors: Deep navy · Violet · AUS Gold (#FFCD00) · AUS Green (#00843D)
 */

// ── Palette ──────────────────────────────────────────────────────────────────
const PALETTE = {
  violet:     '#7c5cfc',
  violetLight:'#a78bfa',
  ausGold:    '#FFCD00',
  ausGreen:   '#00843D',
  red:        '#f43f5e',
  cyan:       '#06b6d4',
  amber:      '#f59e0b',
  blue:       '#3b82f6',
  slate:      '#4a5880',
};

// Chart color sequences
const CHART_COLORS = [
  '#7c5cfc', '#FFCD00', '#00843D', '#06b6d4',
  '#f43f5e', '#f59e0b', '#a78bfa', '#10b981',
];

// ── Number formatter ─────────────────────────────────────────────────────────
function fmt(n) {
  if (n == null) return '—';
  return Math.round(n).toLocaleString();
}

// ── Shorten long sector names ─────────────────────────────────────────────────
function shortSector(name) {
  if (!name) return '—';
  const MAX = 28;
  return name.length > MAX ? name.slice(0, MAX) + '…' : name;
}

// ── Fetch JSON ────────────────────────────────────────────────────────────────
async function fetchJSON(url) {
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const data = await res.json();
  return data.results !== undefined ? data.results : data;
}

// ── Fetch ALL paginated pages ─────────────────────────────────────────────────
async function fetchAllPages(baseUrl) {
  let url = baseUrl;
  let all = [];
  while (url) {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!res.ok) break;
    const data = await res.json();
    if (data.results !== undefined) {
      all = all.concat(data.results);
      url = data.next ? data.next.replace(/^https?:\/\/[^/]+/, '') : null;
    } else {
      all = all.concat(data);
      url = null;
    }
  }
  return all;
}

// ── Shared tooltip style ──────────────────────────────────────────────────────
const TOOLTIP = {
  backgroundColor: '#0e1425',
  borderColor: 'rgba(124,92,252,0.35)',
  borderWidth: 1,
  titleFont:  { family: "'JetBrains Mono', monospace", size: 11 },
  bodyFont:   { family: "'JetBrains Mono', monospace", size: 11 },
  padding: 12,
  cornerRadius: 8,
  titleColor: '#f0f4ff',
  bodyColor:  '#8899bb',
};

const LEGEND = {
  position: 'top',
  labels: {
    font: { family: "'JetBrains Mono', monospace", size: 10 },
    boxWidth: 10,
    boxHeight: 10,
    borderRadius: 3,
    padding: 14,
    color: '#8899bb',
  }
};

// ── Line chart options ────────────────────────────────────────────────────────
function lineOptions(yLabel = '') {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: LEGEND,
      tooltip: TOOLTIP,
    },
    scales: {
      x: {
        grid: { color: 'rgba(124,92,252,0.06)' },
        ticks: {
          color: '#4a5880',
          font: { family: "'JetBrains Mono', monospace", size: 10 },
          maxRotation: 45,
          autoSkip: true,
          maxTicksLimit: 14,
        }
      },
      y: {
        grid: { color: 'rgba(124,92,252,0.06)' },
        ticks: {
          color: '#4a5880',
          font: { family: "'JetBrains Mono', monospace", size: 10 },
        },
        title: yLabel ? {
          display: true,
          text: yLabel,
          color: '#4a5880',
          font: { family: "'JetBrains Mono', monospace", size: 10 }
        } : undefined,
      }
    }
  };
}

// ── Bar chart options ─────────────────────────────────────────────────────────
function barOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: LEGEND,
      tooltip: TOOLTIP,
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: '#4a5880',
          font: { family: "'JetBrains Mono', monospace", size: 10 },
          maxRotation: 40,
          autoSkip: true,
          maxTicksLimit: 12,
        }
      },
      y: {
        grid: { color: 'rgba(124,92,252,0.06)' },
        ticks: {
          color: '#4a5880',
          font: { family: "'JetBrains Mono', monospace", size: 10 },
        }
      }
    }
  };
}

