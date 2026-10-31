// Componentes pequenos usados em mais do que uma página
import { useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { STATE_LABEL, sessionHoursTitle } from './format.js';

// Texto com cor e seta conforme o sinal de v
export function Signed({ v, children }) {
  if (!Number.isFinite(v)) return <span>—</span>;
  const cls = v > 0 ? 'up' : v < 0 ? 'down' : '';
  const arrow = v > 0 ? '▲ ' : v < 0 ? '▼ ' : '';
  return <span className={cls}>{arrow}{children}</span>;
}

// Estado da bolsa (aberta, fechada…) com o horário ao passar o rato
export function MarketState({ quote, children }) {
  return (
    <span className={`state ${quote.state}`} title={sessionHoursTitle(quote)}>
      {children ?? STATE_LABEL[quote.state]}
    </span>
  );
}

// Campo de pesquisa de ativos com lista de sugestões
export function SymbolSearch({ value, onChange, onPick, placeholder, id }) {
  const [items, setItems] = useState(null);   // null = lista fechada
  const [error, setError] = useState('');
  const [active, setActive] = useState(-1);
  const seq = useRef(0);
  const picked = useRef(false);   // o valor mudou por se ter escolhido uma sugestão: não pesquisa de novo

  useEffect(() => {
    if (picked.current) { picked.current = false; return; }
    const term = value.trim();
    if (term.length < 2) { setItems(null); return; }
    const my = ++seq.current;
    const timer = setTimeout(async () => {
      try {
        const res = await api.search(term);
        if (my !== seq.current) return;
        setItems(res.slice(0, 10));
        setError('');
      } catch (e) {
        if (my === seq.current) { setItems([]); setError(e.message); }
      }
      setActive(-1);
    }, 250);
    return () => clearTimeout(timer);
  }, [value]);

  const close = () => { seq.current++; setItems(null); setActive(-1); };
  const pick = (it) => { picked.current = true; onChange(it.symbol); close(); onPick?.(it.symbol); };

  const onKeyDown = (e) => {
    if (!items?.length) return;
    if (e.key === 'ArrowDown') { setActive((active + 1) % items.length); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { setActive((active - 1 + items.length) % items.length); e.preventDefault(); }
    else if (e.key === 'Enter' && active >= 0) { pick(items[active]); e.preventDefault(); }
    else if (e.key === 'Escape') close();
  };

  return (
    <div className="search-wrap">
      <input id={id} value={value} placeholder={placeholder} autoComplete="off" required
        onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} onBlur={() => setTimeout(close, 150)} />
      {items && (
        <ul className="search-list">
          {items.length ? items.map((it, i) => (
            <li key={it.symbol} className={i === active ? 'active' : ''}
              onMouseDown={(e) => { e.preventDefault(); pick(it); }}>
              <span className="s-sym">{it.symbol}</span>
              <span className="s-name">{it.name}</span>
              <span className="s-exch">{[it.type, it.exchange].filter(Boolean).join(' · ')}</span>
            </li>
          )) : <li className="s-empty">{error || 'Sem resultados'}</li>}
        </ul>
      )}
    </div>
  );
}
