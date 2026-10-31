// Gráfico de linha (Chart.js) com as cores do tema, eixo temporal e linha vertical no tooltip
import { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import { useDarkTheme } from './hooks.js';
import { fmtTime, SESSION_LABEL } from './format.js';

Chart.defaults.font.family = "'Open Sans', system-ui, sans-serif";

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Linha vertical que acompanha o tooltip
const crosshair = {
  id: 'crosshair',
  afterDraw(chart) {
    const active = chart.tooltip?.getActiveElements?.() || [];
    if (!active.length) return;
    const x = active[0].element.x;
    const { top, bottom } = chart.chartArea;
    const ctx = chart.ctx;
    ctx.save();
    ctx.strokeStyle = cssVar('--axis');
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.restore();
  },
};

// Estilo de cada série: 'value' (linha principal), 'cost' (tracejado discreto), 'live' (pré/pós a tracejado)
function datasetStyle(kind) {
  if (kind === 'cost') {
    return { borderColor: cssVar('--text-2'), borderWidth: 1.5, borderDash: [5, 4], pointRadius: 0, pointHoverRadius: 0, stepped: true };
  }
  const base = { borderColor: cssVar('--series-1'), borderWidth: 2, pointRadius: 0, pointHoverRadius: 4 };
  if (kind === 'live') {
    const ext = cssVar('--series-2');
    const isExt = (ctx) => !!ctx.chart.data.datasets[0].data[ctx.p1DataIndex]?.e;
    return { ...base, tension: 0, segment: { borderColor: (c) => (isExt(c) ? ext : undefined), borderDash: (c) => (isExt(c) ? [5, 4] : undefined) } };
  }
  return { ...base, stepped: true };
}

function options(valueFmt) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    parsing: false,
    normalized: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: cssVar('--surface'),
        titleColor: cssVar('--text'),
        bodyColor: cssVar('--text-2'),
        borderColor: cssVar('--border'),
        borderWidth: 1,
        padding: 10,
        callbacks: {
          title: (items) => (items.length ? new Date(items[0].parsed.x).toLocaleString('pt-PT') : ''),
          label: (item) => {
            const sess = item.raw?.e ? ` (${SESSION_LABEL[item.raw.e]})` : '';
            return ` ${item.dataset.label}${sess}: ${valueFmt.current(item.parsed.y)}`;
          },
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        grid: { display: false },
        border: { color: cssVar('--axis') },
        ticks: {
          color: cssVar('--muted'), maxTicksLimit: 6, maxRotation: 0,
          callback(v) { return fmtTime(v, this.max - this.min); },
        },
      },
      y: {
        grid: { color: cssVar('--grid') },
        border: { display: false },
        ticks: { color: cssVar('--muted'), maxTicksLimit: 6, callback: (v) => valueFmt.current(v) },
      },
    },
  };
}

// series: [{label, kind, data: [{x, y, e?}]}]; xMin/xMax fixam a janela do eixo (opcional)
export default function LineChart({ series, valueFmt, xMin, xMax, tall = false }) {
  const canvas = useRef(null);
  const chart = useRef(null);
  const fmt = useRef(valueFmt);
  fmt.current = valueFmt;
  const dark = useDarkTheme();
  const kinds = series.map((s) => s.kind).join();

  // (re)cria o gráfico quando muda o tema ou o tipo de séries
  useEffect(() => {
    chart.current = new Chart(canvas.current, {
      type: 'line',
      data: { datasets: [] },
      options: options(fmt),
      plugins: [crosshair],
    });
    return () => chart.current.destroy();
  }, [dark, kinds]);

  // dados novos: atualiza sem recriar
  useEffect(() => {
    const c = chart.current;
    c.data.datasets = series.map((s) => ({ label: s.label, data: s.data, ...datasetStyle(s.kind) }));
    c.options.scales.x.min = xMin ?? undefined;
    c.options.scales.x.max = xMax ?? undefined;
    c.update('none');
  }, [series, xMin, xMax, dark, kinds]);

  return <div className={'chart-box' + (tall ? ' tall' : '')}><canvas ref={canvas} /></div>;
}
