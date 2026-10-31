// Página "Portefólio": KPIs, evolução, nova transação, alocação, posições e transações.
// Todos os valores (em EUR) vêm calculados do backend; aqui só se mostram.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, downloadExport } from '../shared/api.js';
import { useInterval, useStoredState } from '../shared/hooks.js';
import { fmtDate, fmtMoney, fmtNum, fmtPct, SESSION_SHORT, todayISO } from '../shared/format.js';
import { Signed, SymbolSearch } from '../shared/components.jsx';
import LineChart from '../shared/LineChart.jsx';

const DATA_FILE = 'historico/transacoes.json';
const RANGES = [['1H', 3600000], ['1D', 86400000], ['1S', 604800000], ['1M', 2592000000], ['Tudo', 0]];

export default function Portfolio({ active }) {
  const [useExt, setUseExt] = useStoredState('useExt', false);
  const [range, setRange] = useState(0);
  const [data, setData] = useState(null);
  const [hist, setHist] = useState(null);
  const [version, setVersion] = useState(0);   // muda quando as transações mudam
  const changed = () => setVersion((v) => v + 1);

  const loadSummary = useCallback(() => api.portfolio(useExt).then(setData).catch(() => {}), [useExt]);
  const loadHistory = useCallback(() => api.history(range, useExt).then(setHist).catch(() => {}), [range, useExt]);
  useEffect(() => { loadSummary(); }, [loadSummary, version]);
  useEffect(() => { loadHistory(); }, [loadHistory, version]);
  useInterval(loadSummary, 15000);
  useInterval(loadHistory, 60000);

  useEffect(() => {
    window.addEventListener('inv:data-imported', changed);
    return () => window.removeEventListener('inv:data-imported', changed);
  }, []);

  const t = data?.totals;
  const hasPositions = data?.positions.length > 0;

  return (
    <section className={'view' + (active ? ' active' : '')}>
      <div className="kpis">
        <Kpi label="Valor atual">
          {!t ? '—' : !hasPositions ? fmtMoney(0) : t.valueEUR == null ? '…' : fmtMoney(t.valueEUR)}
        </Kpi>
        <Kpi label="Investido">{t ? fmtMoney(t.costEUR) : '—'}</Kpi>
        <Kpi label="Ganho/perda não realizado">
          {hasPositions && t.pnlEUR != null
            ? <Signed v={t.pnlEUR}>{fmtMoney(Math.abs(t.pnlEUR))} <small>{fmtPct(t.pnlPct)}</small></Signed>
            : '—'}
        </Kpi>
        <Kpi label="Ganho/perda realizado">
          {t ? <Signed v={t.realizedEUR}>{fmtMoney(Math.abs(t.realizedEUR))}</Signed> : '—'}
        </Kpi>
      </div>

      <HistoryCard hist={hist} range={range} setRange={setRange} useExt={useExt} setUseExt={setUseExt} />

      <div className="grid-2">
        <div className="card">
          <h2>Nova transação</h2>
          <TransactionForm onAdded={changed} />
        </div>
        <div className="card">
          <h2>Alocação</h2>
          <Allocation items={data?.allocation || []} />
        </div>
      </div>

      <div className="card">
        <h2>Posições</h2>
        <Positions positions={data?.positions || []} />
      </div>

      <TransactionsCard data={data} onChanged={changed} />
    </section>
  );
}

function Kpi({ label, children }) {
  return <div className="kpi"><div className="kpi-label">{label}</div><div className="kpi-value">{children}</div></div>;
}

function HistoryCard({ hist, range, setRange, useExt, setUseExt }) {
  const series = useMemo(() => {
    const pts = hist?.series || [];
    return [
      { label: 'Valor de mercado', kind: 'value', data: pts.map((p) => ({ x: p.t, y: p.v })) },
      { label: 'Montante investido', kind: 'cost', data: pts.map((p) => ({ x: p.t, y: p.c })) },
    ];
  }, [hist]);
  // o eixo mostra sempre a janela inteira do filtro, mesmo que só haja dados no fim
  const windowed = hist?.from != null;

  return (
    <div className="card">
      <div className="card-head">
        <h2>Evolução do portefólio</h2>
        <label className="check" title="Desligado: usa o preço de fecho da sessão regular">
          <input type="checkbox" checked={useExt} onChange={(e) => setUseExt(e.target.checked)} /> Valorizar com pré/pós-mercado
        </label>
        <div className="seg">
          {RANGES.map(([label, ms]) => (
            <button key={label} className={range === ms ? 'active' : ''} onClick={() => setRange(ms)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="legend">
        <span><i className="sw sw-value"></i>Valor de mercado</span>
        <span><i className="sw sw-cost"></i>Montante investido</span>
      </div>
      <LineChart series={series} valueFmt={(v) => fmtMoney(v)} tall
        xMin={windowed ? hist.from : undefined} xMax={windowed ? hist.to : undefined} />
      <p className="hint">Desde a primeira transação: valor ao fecho de cada dia (preços do Yahoo, câmbio do BCE desse dia). Hoje: atualizado ao vivo.</p>
      <p className="hint">{hist?.message}</p>
    </div>
  );
}

function TransactionForm({ onAdded }) {
  const [form, setForm] = useState({ type: 'buy', symbol: '', date: todayISO(), qty: '', price: '', currency: 'EUR' });
  const [msg, setMsg] = useState({ text: '', cls: '' });
  const [busy, setBusy] = useState(false);
  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));
  const setFromEvent = (field) => (e) => set(field)(e.target.value);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setMsg({ text: 'A validar…', cls: '' });
    try {
      const tx = await api.addTransaction(form);
      setMsg({ text: `${tx.type === 'buy' ? 'Compra' : 'Venda'} de ${fmtNum(tx.qty)} ${tx.symbol} adicionada.`, cls: 'ok' });
      setForm((f) => ({ ...f, qty: '', price: '' }));
      onAdded();
    } catch (err) {
      setMsg({ text: err.message, cls: 'err' });
    } finally {
      setBusy(false);
    }
  }

  // Preenche o preço com o valor de mercado atual, convertido para a moeda escolhida
  async function useMarketPrice() {
    const symbol = form.symbol.trim().toUpperCase();
    if (!symbol) return setMsg({ text: 'Indica primeiro o ativo.', cls: 'err' });
    try {
      const p = await api.marketPrice(symbol, form.currency);
      set('price')(String(p.value));
      setMsg({ text: `Preço atual: ${fmtMoney(p.quotePrice, p.quoteCurrency)}`, cls: '' });
    } catch (err) {
      setMsg({ text: err.message, cls: 'err' });
    }
  }

  return (
    <form className="tx-form" onSubmit={submit}>
      <label>Tipo
        <select value={form.type} onChange={setFromEvent('type')}>
          <option value="buy">Compra</option><option value="sell">Venda</option>
        </select>
      </label>
      <label>Ativo
        <SymbolSearch value={form.symbol} onChange={set('symbol')} placeholder="Pesquisar ou escrever o símbolo" />
      </label>
      <label>Data
        <input type="date" value={form.date} max={todayISO()} onChange={setFromEvent('date')} required />
      </label>
      <label>Quantidade
        <input type="number" step="any" min="0" placeholder="10" value={form.qty} onChange={setFromEvent('qty')} required />
      </label>
      <label>Preço por unidade
        <div className="price-row">
          <input type="number" step="any" min="0" placeholder="150.00" value={form.price} onChange={setFromEvent('price')} required />
          <select value={form.currency} onChange={setFromEvent('currency')}>
            <option value="EUR">EUR</option><option value="USD">USD</option>
          </select>
        </div>
      </label>
      <div className="tx-actions">
        <button type="button" className="ghost" onClick={useMarketPrice}>Usar preço atual</button>
        <button type="submit" disabled={busy}>Adicionar transação</button>
      </div>
      <p className={'form-msg ' + msg.cls}>{msg.text}</p>
    </form>
  );
}

function Allocation({ items }) {
  if (!items.length) return <p className="muted">Sem posições com preço disponível.</p>;
  return (
    <div className="alloc">
      {items.map((a) => (
        <div className="alloc-row" key={a.symbol}>
          <span className="sym">{a.symbol}</span>
          <div className="alloc-bar"><span style={{ width: `${a.pct.toFixed(2)}%` }}></span></div>
          <span className="num">{a.pct.toFixed(1)}% · {fmtMoney(a.valueEUR)}</span>
        </div>
      ))}
    </div>
  );
}

function Positions({ positions }) {
  return (
    <div className="tbl-scroll">
      <table className="tbl">
        <thead>
          <tr><th>Ativo</th><th className="num">Qtd.</th><th className="num">Preço médio</th><th className="num">Preço atual</th>
            <th className="num">Valor</th><th className="num">G/P</th><th className="num">G/P %</th></tr>
        </thead>
        <tbody>
          {!positions.length && (
            <tr className="empty"><td colSpan="7">Ainda não há posições. Adiciona uma transação.</td></tr>
          )}
          {positions.map((p) => (
            <tr key={p.symbol}>
              <td className="sym">{p.symbol}<span className="sym-name">{p.name}</span></td>
              <td className="num">{fmtNum(p.qty)}</td>
              <td className="num">{fmtMoney(p.avgCost, p.avgCostCurrency)}</td>
              <td className="num">
                {/* etiqueta "pré"/"pós" quando a posição está valorizada com um preço fora da sessão regular */}
                {p.session && <span className="sess">{SESSION_SHORT[p.session]}</span>}
                {p.price != null ? fmtMoney(p.price, p.currency) : '…'}
              </td>
              <td className="num">{fmtMoney(p.valueEUR)}</td>
              <td className="num"><Signed v={p.pnlEUR}>{fmtMoney(Math.abs(p.pnlEUR))}</Signed></td>
              <td className="num"><Signed v={p.pnlEUR}>{fmtPct(p.pnlPct)}</Signed></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TransactionsCard({ data, onChanged }) {
  const list = data?.transactions || [];

  async function remove(t) {
    if (!confirm(`Apagar ${t.type === 'buy' ? 'compra' : 'venda'} de ${fmtNum(t.qty)} ${t.symbol}?`)) return;
    try {
      await api.deleteTransaction(t.id);
      onChanged();
    } catch (e) {
      alert(e.message);
    }
  }

  async function importFile(e) {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    try {
      const content = JSON.parse(await file.text());
      if (!Array.isArray(content.tx)) throw new Error('Ficheiro sem lista de transações.');
      if (!confirm(`Substituir os dados atuais por ${content.tx.length} transações do ficheiro?`)) return;
      await api.importData(content);
      window.dispatchEvent(new Event('inv:data-imported'));   // a watchlist também pode ter mudado
    } catch (err) {
      alert('Não foi possível importar: ' + err.message);
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Transações</h2>
          <div className="muted small">
            {data?.savedAt
              ? `Guardadas em ${DATA_FILE} (última alteração ${new Date(data.savedAt).toLocaleString('pt-PT')}).`
              : `Guardadas em ${DATA_FILE}.`}
          </div>
        </div>
        <div className="btn-row">
          <button className="ghost" onClick={() => downloadExport().catch((e) => alert(e.message))}>Exportar JSON</button>
          <label className="ghost file-btn">Importar JSON
            <input type="file" accept="application/json" hidden onChange={importFile} />
          </label>
        </div>
      </div>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th>Data</th><th>Tipo</th><th>Ativo</th><th className="num">Qtd.</th><th className="num">Preço</th>
              <th className="num">Total</th><th className="num">EUR/USD</th><th></th></tr>
          </thead>
          <tbody>
            {!list.length && <tr className="empty"><td colSpan="8">Sem transações.</td></tr>}
            {list.map((t) => (
              <tr key={t.id}>
                <td>{fmtDate(t.date)}</td>
                <td>{t.type === 'buy' ? 'Compra' : 'Venda'}</td>
                <td className="sym">{t.symbol}</td>
                <td className="num">{fmtNum(t.qty)}</td>
                <td className="num">{fmtMoney(t.price, t.currency)}</td>
                <td className="num">{fmtMoney(t.total, t.currency)}</td>
                <td className="num">{t.fx.toFixed(4)}</td>
                <td className="num"><button className="icon-btn" title="Apagar" onClick={() => remove(t)}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
