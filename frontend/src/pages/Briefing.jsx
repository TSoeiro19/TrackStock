// Página "Daily briefing": mostra o briefing do dia (ou de dias anteriores) e permite gerá-lo de novo
import { useEffect, useMemo, useRef, useState } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { api } from '../shared/api.js';
import { fmtClockIso, fmtDate } from '../shared/format.js';

const POLL_MS = 10000;

// Markdown -> HTML limpo (o texto vem de páginas da web, por isso passa pelo DOMPurify)
function renderMarkdown(md) {
  const tpl = document.createElement('template');
  tpl.innerHTML = DOMPurify.sanitize(marked.parse(md));
  tpl.content.querySelectorAll('a').forEach((a) => { a.target = '_blank'; a.rel = 'noopener'; });
  tpl.content.querySelectorAll('table').forEach((t) => {
    const wrap = document.createElement('div');
    wrap.className = 'tbl-scroll';
    t.replaceWith(wrap);
    wrap.appendChild(t);
  });
  return tpl.innerHTML;
}

export default function Briefing({ active }) {
  const [today, setToday] = useState(null);
  const [dates, setDates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [briefing, setBriefing] = useState(null);
  const [error, setError] = useState('');
  const pollTimer = useRef(null);

  async function refreshDates() {
    const list = await api.briefings();
    setToday(list.today);
    setDates(list.dates.includes(list.today) ? list.dates : [list.today, ...list.dates]);
    return list.today;
  }

  function show(b) {
    setBriefing(b);
    setError('');
    clearTimeout(pollTimer.current);
    if (b.status === 'running') pollTimer.current = setTimeout(() => load(b.date), POLL_MS);
    // quando um briefing acaba de ficar pronto, aparece na lista de dias
    if (b.status === 'ready') refreshDates().catch(() => {});
  }

  async function load(date) {
    setSelected(date);
    try { show(await api.briefing(date)); } catch (e) { setError(e.message); }
  }

  async function runToday() {
    setSelected(today);
    try { show(await api.generateBriefing()); } catch (e) { setError(e.message); }
  }

  // Ao abrir a app: carrega a lista e, se ainda não houver briefing de hoje, começa a gerá-lo
  useEffect(() => {
    (async () => {
      try {
        const t = await refreshDates();
        setSelected(t);
        const b = await api.briefing(t);
        show(b.status === 'missing' ? await api.generateBriefing() : b);
      } catch (e) {
        setError(e.message);
      }
    })();
    return () => clearTimeout(pollTimer.current);
  }, []);

  const b = briefing?.date === selected ? briefing : null;
  const isToday = selected === today;
  const html = useMemo(() => (b?.status === 'ready' ? renderMarkdown(b.markdown) : ''), [b]);

  let status = null;
  if (error) status = <span className="down">{error}</span>;
  else if (b?.status === 'running') {
    status = <><span className="spinner"></span> A preparar o briefing de hoje (começou às {fmtClockIso(b.since)}).
      Costuma demorar 3–8 minutos: o Claude está a pesquisar as notícias.</>;
  } else if (b?.status === 'error') {
    status = <><span className="down">Não foi possível gerar o briefing.</span> <span className="muted">{b.error}</span></>;
  } else if (b?.status === 'missing') {
    status = isToday ? 'Ainda não há briefing de hoje.' : 'Não há briefing para este dia.';
  }

  return (
    <section className={'view' + (active ? ' active' : '')}>
      <div className="card briefing-card">
        <div className="card-head">
          <div>
            <h2>Daily briefing</h2>
            <div className="muted small">
              {selected && fmtDate(selected)}{b?.generatedAt && ` · gerado às ${fmtClockIso(b.generatedAt)}`}
            </div>
          </div>
          <div className="btn-row">
            <select title="Briefings anteriores" value={selected || ''} onChange={(e) => load(e.target.value)}>
              {dates.map((d) => <option key={d} value={d}>{d === today ? 'Hoje' : fmtDate(d)}</option>)}
            </select>
            {isToday && b && b.status !== 'running' && (
              <button className="ghost" onClick={runToday}>Gerar de novo</button>
            )}
          </div>
        </div>
        <div className="briefing-status">{status}</div>
        <article className="md" dangerouslySetInnerHTML={{ __html: html }} />
        <p className="hint">Gerado pelo Claude no teu PC com a prompt de <code>historico/briefings/prompt.md</code>; cada briefing
          fica guardado na mesma pasta. O de hoje é gerado automaticamente na primeira vez que abres a app no dia.</p>
      </div>
    </section>
  );
}
