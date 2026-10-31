// Estrutura da app: barra do topo com os separadores, uma página por separador e rodapé
import { useEffect, useState } from 'react';
import { api, migrateBrowserData, onServerStatus, startPresence } from './shared/api.js';
import { useInterval } from './shared/hooks.js';
import Market from './pages/Market.jsx';
import Portfolio from './pages/Portfolio.jsx';
import Briefing from './pages/Briefing.jsx';

const PAGES = [
  { id: 'market', label: 'Mercado', Page: Market },
  { id: 'portfolio', label: 'Portefólio', Page: Portfolio },
  { id: 'briefing', label: 'Daily briefing', Page: Briefing },
];

export default function App() {
  const [page, setPage] = useState('market');

  useEffect(() => {
    migrateBrowserData().catch(() => {});
    return startPresence();
  }, []);

  return (
    <>
      <header className="topbar">
        <div className="brand">TrackStock</div>
        <nav className="tabs" role="tablist">
          {PAGES.map(({ id, label }) => (
            <button key={id} role="tab" className={'tab' + (page === id ? ' active' : '')} onClick={() => setPage(id)}>
              {label}
            </button>
          ))}
        </nav>
        <ConnectionStatus />
      </header>
      <ServerBanner />

      {/* todas as páginas ficam montadas (continuam a atualizar); só a ativa é visível */}
      <main>
        {PAGES.map(({ id, Page }) => <Page key={id} active={page === id} />)}
      </main>

      <footer className="mainFooter">
        TrackStock <span>·</span> Cotações: Yahoo Finance <span>·</span> Câmbio: Banco Central Europeu
      </footer>
      <BackToTop />
    </>
  );
}

function useServerStatus() {
  const [status, setStatus] = useState({ ok: true, at: 0 });
  useEffect(() => onServerStatus(setStatus), []);
  return status;
}

// Ponto de ligação, hora da última resposta e câmbio EUR/USD
function ConnectionStatus() {
  const { ok, at } = useServerStatus();
  const [usd, setUsd] = useState(null);
  useInterval(() => api.fx().then((f) => setUsd(f.usd)).catch(() => {}), 60 * 60 * 1000, true);

  const cls = !ok ? 'err' : at ? 'on' : '';
  const text = !ok ? 'app desligada' : at ? 'Yahoo Finance · ' + new Date(at).toLocaleTimeString('pt-PT') : 'a ligar…';
  return (
    <div className="status">
      <span className={'dot ' + cls} title="Ligação"></span>
      <span>{text}</span>
      <span className="sep">·</span>
      <span>{usd ? `EUR/USD ${usd.toFixed(4)}` : 'EUR/USD —'}</span>
    </div>
  );
}

function ServerBanner() {
  const { ok } = useServerStatus();
  if (ok) return null;
  return (
    <div className="banner">
      A app está desligada. Abre-a pelo atalho <strong>TrackStock</strong> no ambiente de trabalho.
    </div>
  );
}

function BackToTop() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 300);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return (
    <button id="myBtn" className={show ? 'show' : ''} title="Voltar ao topo" aria-label="Voltar ao topo"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>▲</button>
  );
}
