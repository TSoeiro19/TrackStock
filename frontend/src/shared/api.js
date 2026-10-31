// Pedidos ao backend Python. Todos os cálculos são feitos lá; aqui só se pedem e mostram os resultados.
const APP_HEADERS = { 'X-App': 'investimentos' };   // identifica a app perante o servidor

// Estado da ligação ao servidor (barra do topo e aviso "app desligada")
let status = { ok: true, at: 0 };
const listeners = new Set();

export function onServerStatus(fn) {
  listeners.add(fn);
  fn(status);
  return () => listeners.delete(fn);
}

function setStatus(ok) {
  status = { ok, at: ok ? Date.now() : status.at };
  listeners.forEach((fn) => fn(status));
}

async function request(path, { method = 'GET', body } = {}) {
  let r;
  try {
    r = await fetch('/api' + path, {
      method,
      headers: body ? { ...APP_HEADERS, 'Content-Type': 'application/json' } : APP_HEADERS,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    setStatus(false);
    throw new Error('A app está desligada (abre-a pelo atalho "TrackStock")');
  }
  setStatus(true);
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.error || 'HTTP ' + r.status);
  return j;
}

const enc = encodeURIComponent;

export const api = {
  // mercado
  quote: (symbol, bars = false) => request(`/market/quote?symbol=${enc(symbol)}${bars ? '&bars=1' : ''}`),
  search: (term) => request(`/market/search?q=${enc(term)}`),
  watchlist: () => request('/market/watchlist'),
  addWatch: (symbol) => request('/market/watchlist', { method: 'POST', body: { symbol } }),
  removeWatch: (symbol) => request(`/market/watchlist/${enc(symbol)}`, { method: 'DELETE' }),
  // câmbio
  fx: () => request('/fx'),
  // portefólio
  portfolio: (ext) => request(`/portfolio?ext=${ext ? 1 : 0}`),
  history: (range, ext) => request(`/portfolio/history?range=${range}&ext=${ext ? 1 : 0}`),
  addTransaction: (tx) => request('/portfolio/transactions', { method: 'POST', body: tx }),
  deleteTransaction: (id) => request(`/portfolio/transactions/${enc(id)}`, { method: 'DELETE' }),
  marketPrice: (symbol, currency) => request(`/portfolio/price?symbol=${enc(symbol)}&currency=${currency}`),
  importData: (data) => request('/portfolio/import', { method: 'POST', body: data }),
  // daily briefing
  briefings: () => request('/briefing/list'),
  briefing: (date) => request(`/briefing?date=${enc(date)}`),
  generateBriefing: () => request('/briefing/generate', { method: 'POST' }),
};

// Descarrega a cópia das transações e da watchlist (o pedido precisa do cabeçalho da app)
export async function downloadExport() {
  const r = await fetch('/api/portfolio/export', { headers: APP_HEADERS });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const name = /filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '')?.[1] || 'portefolio.json';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(await r.blob());
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

// Avisa o servidor de que esta janela está aberta; ao fechar a última, o servidor (--auto-stop) desliga-se
export function startPresence() {
  const id = crypto.randomUUID();
  const ping = () => fetch(`/api/ping?id=${id}`, { method: 'POST' }).catch(() => {});
  ping();
  const timer = setInterval(ping, 20000);
  // janelas em segundo plano têm os temporizadores abrandados: avisa logo que volta a ficar visível
  const onVisible = () => document.visibilityState === 'visible' && ping();
  const onHide = () => navigator.sendBeacon(`/api/bye?id=${id}`);
  document.addEventListener('visibilitychange', onVisible);
  window.addEventListener('pagehide', onHide);
  return () => {
    clearInterval(timer);
    document.removeEventListener('visibilitychange', onVisible);
    window.removeEventListener('pagehide', onHide);
    onHide();
  };
}

// Versões anteriores guardavam as transações no browser: se o servidor ainda não as tiver, envia-as uma vez
export async function migrateBrowserData() {
  let tx;
  try { tx = JSON.parse(localStorage.getItem('inv.tx') || 'null'); } catch { return; }
  if (!Array.isArray(tx)) return;
  const { transactions } = await api.portfolio(false);
  if (!transactions.length && tx.length) {
    const watchlist = JSON.parse(localStorage.getItem('inv.watchlist') || 'null');
    await api.importData({ tx, ...(Array.isArray(watchlist) && { watchlist }) });
  }
  ['tx', 'watchlist', 'history', 'rates'].forEach((k) => localStorage.removeItem('inv.' + k));
}
