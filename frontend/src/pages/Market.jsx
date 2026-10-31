// Página "Mercado": watchlist, cartão "Ao vivo" do ativo selecionado e gráfico TradingView
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../shared/api.js';
import { useDarkTheme, useInterval, useStoredState } from '../shared/hooks.js';
import { fmtMoney, fmtPct, SESSION_LABEL, SESSION_SHORT } from '../shared/format.js';
import { MarketState, Signed, SymbolSearch } from '../shared/components.jsx';
import LineChart from '../shared/LineChart.jsx';

// Frequência de atualização de cada cotação
const POLL_SELECTED_MS = 10000;
const POLL_OPEN_MS = 15000;
const POLL_CLOSED_MS = 5 * 60 * 1000;
const POLL_ERROR_MS = 60 * 1000;
const MAX_PARALLEL = 3;

export default function Market({ active }) {
  const [watchlist, setWatchlist] = useState(null);
  const [quotes, setQuotes] = useState({});
  const [selected, setSelected] = useState(null);
  const [flash, setFlash] = useState({});
  const [input, setInput] = useState('');

  const loadWatchlist = () => api.watchlist()
    .then((w) => { setWatchlist(w); setSelected((s) => (s && w.includes(s) ? s : w[0] ?? null)); })
    .catch(() => {});
  useEffect(() => {
    loadWatchlist();
    window.addEventListener('inv:data-imported', loadWatchlist);
    return () => window.removeEventListener('inv:data-imported', loadWatchlist);
  }, []);

  /* ---------- atualização periódica das cotações ---------- */
  const nextPoll = useRef({});
  const inflight = useRef(0);
  const latest = useRef({});
  latest.current = { watchlist, selected, quotes };

  function delayFor(sym, q) {
    let d = q.state === 'closed' ? POLL_CLOSED_MS : sym === latest.current.selected ? POLL_SELECTED_MS : POLL_OPEN_MS;
    // a bolsa abre ou fecha antes disso: volta a pedir logo a seguir
    if (q.nextChange) d = Math.min(d, Math.max(1000, q.nextChange - Date.now() + 2000));
    return d;
  }

  function flashRow(sym, dir) {
    setFlash((f) => ({ ...f, [sym]: dir }));
    setTimeout(() => setFlash((f) => ({ ...f, [sym]: null })), 250);
  }

  // A cada segundo pede as cotações que estão na hora (o ativo selecionado primeiro, com o gráfico de hoje)
  useInterval(() => {
    const { watchlist: list, selected: sel } = latest.current;
    if (!list) { loadWatchlist(); return; }
    const now = Date.now();
    const syms = [...list].sort((a, b) => (b === sel) - (a === sel));
    for (const sym of syms) {
      if (inflight.current >= MAX_PARALLEL) break;
      if ((nextPoll.current[sym] || 0) > now) continue;
      nextPoll.current[sym] = Infinity;
      inflight.current++;
      api.quote(sym, sym === sel)
        .then((q) => {
          const old = latest.current.quotes[sym];
          if (old && q.price !== old.price) flashRow(sym, q.price > old.price ? 'up' : 'down');
          setQuotes((qs) => ({ ...qs, [sym]: q }));
          // ficou selecionado entretanto e veio sem gráfico: pede de novo já
          nextPoll.current[sym] = sym === latest.current.selected && !q.bars ? 0 : Date.now() + delayFor(sym, q);
        })
        .catch(() => { nextPoll.current[sym] = Date.now() + POLL_ERROR_MS; })
        .finally(() => { inflight.current--; });
    }
  }, 1000, true);

  function select(sym) {
    setSelected(sym);
    nextPoll.current[sym] = 0;
  }

  async function addWatch(raw) {
    const sym = raw.trim().toUpperCase();
    setInput('');
    if (!sym) return;
    if (watchlist?.includes(sym)) { select(sym); return; }
    try {
      setWatchlist(await api.addWatch(sym));
      select(sym);
    } catch (e) {
      alert(e.message);
    }
  }

  async function removeWatch(sym) {
    try {
      const w = await api.removeWatch(sym);
      setWatchlist(w);
      if (selected === sym) setSelected(w[0] ?? null);
    } catch (e) {
      alert(e.message);
    }
  }

  const q = selected ? quotes[selected] : null;

  return (
    <section className={'view' + (active ? ' active' : '')}>
      <div className="grid-market">
        <div className="card">
          <div className="card-head">
            <h2>Watchlist</h2>
            <form className="inline-form" onSubmit={(e) => { e.preventDefault(); addWatch(input); }}>
              <SymbolSearch value={input} onChange={setInput} onPick={addWatch}
                placeholder="Pesquisar: apple, EDP, VWCE, bitcoin…" />
              <button type="submit">Adicionar</button>
            </form>
          </div>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr><th>Ativo</th><th>Bolsa</th><th className="num">Preço</th><th className="num">Var.</th>
                  <th className="num">Var. %</th><th className="num">Pré/Pós</th><th></th></tr>
              </thead>
              <tbody>
                {watchlist?.length === 0 && (
                  <tr className="empty"><td colSpan="7">Pesquisa um ativo para começar.</td></tr>
                )}
                {watchlist?.map((sym) => (
                  <WatchRow key={sym} sym={sym} q={quotes[sym]} selected={sym === selected} flash={flash[sym]}
                    onSelect={() => select(sym)} onRemove={() => removeWatch(sym)} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint">Dados do Yahoo Finance: ações, ETFs, índices, fundos, câmbio e cripto de todas as bolsas, cada um na sua moeda.
            Atualiza a cada 15 s com a bolsa aberta (incluindo pré/pós-mercado) e a cada 5 min com ela fechada.
            Algumas bolsas chegam com 15–20 min de atraso.</p>
        </div>

        <LiveCard sym={selected} q={q} />
      </div>

      <TradingViewCard sym={selected} q={q} />
    </section>
  );
}

function WatchRow({ sym, q, selected, flash, onSelect, onRemove }) {
  const cur = q?.currency;
  const cls = [selected && 'selected', flash && 'flash-' + flash].filter(Boolean).join(' ');
  return (
    <tr className={cls} onClick={onSelect}>
      <td className="sym">{sym}<span className="sym-name">{q?.name}</span></td>
      <td className="mkt">{q && <MarketState quote={q}>{q.exchange}</MarketState>}</td>
      <td className="num price">{q ? fmtMoney(q.price, cur) : '—'}</td>
      <td className="num chg">{q ? <Signed v={q.change}>{fmtMoney(Math.abs(q.change), cur)}</Signed> : '—'}</td>
      <td className="num pct">{q ? <Signed v={q.changePct}>{fmtPct(q.changePct)}</Signed> : '—'}</td>
      <td className="num ext-cell">
        {q?.ext ? (
          <>
            <span className="sess">{SESSION_SHORT[q.ext.session]}</span>{fmtMoney(q.ext.price, cur)}
            <small><Signed v={q.ext.changePct}>{fmtPct(q.ext.changePct)}</Signed></small>
          </>
        ) : '—'}
      </td>
      <td className="num">
        <button className="icon-btn" title="Remover" onClick={(e) => { e.stopPropagation(); onRemove(); }}>✕</button>
      </td>
    </tr>
  );
}

// Preço, pré/pós-mercado e gráfico de hoje do ativo selecionado
function LiveCard({ sym, q }) {
  const cur = q?.currency;
  const series = useMemo(
    () => [{ label: 'Preço', kind: 'live', data: (q?.bars || []).map((b) => ({ x: b.t, y: b.y, e: b.e })) }],
    [q?.bars],
  );
  const live = q && (q.state === 'regular' || q.state === 'open24');

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>{sym ? `Ao vivo · ${sym}` : 'Ao vivo'}</h2>
          <div className="muted small">{q ? `${q.name} · ${q.exchange} · ${cur}` : ''}</div>
        </div>
        <span className="muted small">{q && <MarketState quote={q} />}</span>
      </div>
      <div className="hero">
        {q ? (
          <>
            {fmtMoney(q.price, cur)}
            <small>
              <Signed v={q.change}>{fmtMoney(Math.abs(q.change), cur)} ({fmtPct(q.changePct)})</Signed>
              {live ? '' : ' · fecho'}
            </small>
          </>
        ) : '—'}
      </div>
      <div className="ext-line">
        {q?.ext && (
          <>
            {SESSION_LABEL[q.ext.session]}: <strong>{fmtMoney(q.ext.price, cur)}</strong>{' '}
            <Signed v={q.ext.change}>{fmtMoney(Math.abs(q.ext.change), cur)} ({fmtPct(q.ext.changePct)})</Signed>
            {' · '}{new Date(q.ext.t).toLocaleTimeString('pt-PT')}
          </>
        )}
      </div>
      <div className="legend">
        <span><i className="sw sw-value"></i>Sessão regular</span>
        <span><i className="sw sw-ext"></i>Pré / pós-mercado</span>
      </div>
      <LineChart series={series} valueFmt={(v) => fmtMoney(v, cur)} />
      <p className="hint">Gráfico de hoje, em velas de 1 minuto. Clica num ativo da watchlist para o ver aqui.</p>
    </div>
  );
}

// Gráfico TradingView (widget tv.js); o símbolo vem do backend e pode ser corrigido à mão
function TradingViewCard({ sym, q }) {
  const [overrides, setOverrides] = useStoredState('tvOverrides', {});
  const [input, setInput] = useState('');
  const dark = useDarkTheme();
  const box = useRef(null);
  // espera pelos dados do Yahoo para saber a bolsa (NASDAQ vs NYSE)
  const tvSym = sym ? overrides[sym] || q?.tradingView || null : null;
  const loaded = typeof window.TradingView !== 'undefined';

  useEffect(() => setInput(tvSym || ''), [tvSym]);

  useEffect(() => {
    if (!tvSym || !loaded) return;
    box.current.innerHTML = '';
    new window.TradingView.widget({
      width: '100%',
      height: 520,
      symbol: tvSym,
      interval: 'D',
      timezone: 'Europe/Lisbon',
      theme: dark ? 'dark' : 'light',
      style: '1',
      locale: 'en',
      enable_publishing: false,
      hide_top_toolbar: false,
      save_image: false,
      container_id: box.current.id,
    });
  }, [tvSym, dark, loaded]);

  // vazio repõe o símbolo automático
  function apply(e) {
    e.preventDefault();
    if (!sym) return;
    const v = input.trim().toUpperCase();
    const next = { ...overrides };
    delete next[sym];
    if (v && v !== q?.tradingView) next[sym] = v;
    setOverrides(next);
  }

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>{sym ? `Gráfico TradingView · ${sym}` : 'Gráfico TradingView'}</h2>
          <div className="muted small">Ativo selecionado na watchlist, com os indicadores e ferramentas do TradingView.</div>
        </div>
        <form className="inline-form tv-form" onSubmit={apply}
          title="Se o gráfico não aparecer, corrige o símbolo (ex: EURONEXT:EDP, XETR:VWCE, FOREXCOM:SPXUSD)">
          <label className="small muted" htmlFor="tvSymbolInput">Símbolo TradingView</label>
          <input id="tvSymbolInput" value={input} onChange={(e) => setInput(e.target.value)} autoComplete="off" spellCheck="false" />
          <button type="submit" className="ghost">Aplicar</button>
          {tvSym && (
            <a className="small" target="_blank" rel="noopener"
              href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSym)}`}>abrir ↗</a>
          )}
        </form>
      </div>
      <div className="tradingview-widget-container">
        {!sym && <div className="tv-msg">Seleciona um ativo na watchlist.</div>}
        {sym && !loaded && <div className="tv-msg">Não foi possível carregar o TradingView (sem ligação à internet?).</div>}
        <div id="tradingview_chart" ref={box} className="tv-box" hidden={!sym || !loaded} />
      </div>
    </div>
  );
}
