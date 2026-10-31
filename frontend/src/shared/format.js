// Formatação de valores e textos para a interface (pt-PT)

const moneyFmt = {};
export function fmtMoney(v, currency = 'EUR') {
  if (!Number.isFinite(v)) return '—';
  const digits = Math.abs(v) > 0 && Math.abs(v) < 1 ? 6 : 2;
  const key = currency + digits;
  try {
    moneyFmt[key] ??= new Intl.NumberFormat('pt-PT', {
      style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: digits,
    });
  } catch {
    moneyFmt[key] = { format: (x) => `${x.toLocaleString('pt-PT', { maximumFractionDigits: digits })} ${currency}` };
  }
  return moneyFmt[key].format(v);
}

export function fmtNum(v, max = 6) {
  if (!Number.isFinite(v)) return '—';
  return v.toLocaleString('pt-PT', { maximumFractionDigits: max });
}

export function fmtPct(v) {
  if (!Number.isFinite(v)) return '—';
  return (v > 0 ? '+' : '') + v.toLocaleString('pt-PT', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
}

// Etiqueta de tempo para eixos, com a precisão adequada ao intervalo mostrado
export function fmtTime(ts, span) {
  const d = new Date(ts);
  if (span <= 10 * 60000) return d.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  if (span <= 2 * 86400000) return d.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit' });
}

export const fmtClock = (sec) => new Date(sec * 1000).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' });
export const fmtClockIso = (iso) => new Date(iso).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' });
export const fmtDate = (iso) => new Date(iso + 'T00:00').toLocaleDateString('pt-PT');

export function todayISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

// Sessões e estado das bolsas (o estado vem calculado do backend)
export const SESSION_LABEL = { pre: 'Pré-abertura', post: 'Pós-fecho' };
export const SESSION_SHORT = { pre: 'pré', post: 'pós' };
export const STATE_LABEL = { open24: '24h', regular: 'aberta', pre: 'pré-abertura', post: 'pós-fecho', closed: 'fechada' };

export function sessionHoursTitle(q) {
  const { pre, regular, post } = q?.sessions || {};
  if (!regular || q.crypto) return '';
  let s = `Sessão regular: ${fmtClock(regular.start)}–${fmtClock(regular.end)} (hora local)`;
  if (q.hasExt && pre && post) s += `\nPré: ${fmtClock(pre.start)} · Pós até ${fmtClock(post.end)}`;
  return s;
}
