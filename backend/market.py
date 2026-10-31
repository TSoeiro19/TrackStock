# Mercado: cotações do Yahoo Finance, sessões das bolsas, pré/pós-mercado, pesquisa e watchlist
import re
import time

from flask import Blueprint, jsonify, request

from . import storage
from .http_client import UpstreamError, get_json

bp = Blueprint('market', __name__, url_prefix='/api/market')

CHART_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/{}'
SEARCH_URL = 'https://query2.finance.yahoo.com/v1/finance/search'
SYMBOL_RE = re.compile(r'^[A-Za-z0-9.\-^=]{1,25}$')
RANGES = {'1d', '5d', '1mo', '3mo', '6mo', '1y', '5y', 'max'}
INTERVALS = {'1m', '2m', '5m', '15m', '30m', '60m', '1d', '1wk'}
# Tempo de cache por intervalo: o intradiário muda a cada minuto, os fechos diários uma vez por dia
CHART_TTL = {'1m': 8, '2m': 15, '5m': 50, '15m': 120, '30m': 300, '60m': 300, '1d': 3 * 3600, '1wk': 6 * 3600}

# Algumas bolsas cotam em subunidades (Londres em pence, Joanesburgo em cêntimos…)
SUBUNITS = {'GBp': ('GBP', 100), 'GBX': ('GBP', 100), 'ZAc': ('ZAR', 100), 'ILA': ('ILS', 100)}


def norm_currency(cur):
    """(moeda, divisor) — ex.: GBp -> ('GBP', 100)."""
    return SUBUNITS.get(cur) or ((cur or 'USD').upper(), 1)


def valid_symbol(sym):
    return bool(sym) and bool(SYMBOL_RE.match(sym))


def fetch_chart(symbol, rng='1d', interval='1m'):
    """Resposta 'chart' do Yahoo para um símbolo (lança UpstreamError se não existir)."""
    if not valid_symbol(symbol) or rng not in RANGES or interval not in INTERVALS:
        raise ValueError('Parâmetros inválidos')
    try:
        j = get_json(CHART_URL.format(symbol), ttl=CHART_TTL[interval],
                     params={'range': rng, 'interval': interval, 'includePrePost': 'true'})
    except UpstreamError as e:
        desc = ((e.body or {}).get('chart') or {}).get('error') or {}
        if desc.get('description'):
            raise UpstreamError(f'"{symbol}" não foi encontrado', 404) from e
        raise
    res = ((j.get('chart') or {}).get('result') or [None])[0]
    if not res:
        raise UpstreamError(f'"{symbol}" não foi encontrado', 404)
    return res


def series(res):
    """[(timestamp s, preço)] com os preços já na moeda principal (sem subunidades)."""
    _, div = norm_currency(res['meta'].get('currency'))
    ts = res.get('timestamp') or []
    closes = (((res.get('indicators') or {}).get('quote') or [{}])[0].get('close')) or []
    return [(t, c / div) for t, c in zip(ts, closes) if c is not None]


# ---------- sessões (o Yahoo dá o horário de cada bolsa, já com as mudanças de hora) ----------

def _sessions(meta):
    ctp = meta.get('currentTradingPeriod') or {}
    return {k: {'start': ctp[k]['start'], 'end': ctp[k]['end']} for k in ('pre', 'regular', 'post') if ctp.get(k)}


def market_state(sessions, crypto, has_ext, now=None):
    """open24 | regular | pre | post | closed"""
    if crypto:
        return 'open24'
    now = now or time.time()
    inside = lambda s: s and s['start'] <= now < s['end']
    if inside(sessions.get('regular')):
        return 'regular'
    if has_ext and inside(sessions.get('pre')):
        return 'pre'
    if has_ext and inside(sessions.get('post')):
        return 'post'
    return 'closed'


def next_change(sessions, crypto, now=None):
    """Próximo instante (ms) em que o estado da bolsa muda, para a interface voltar a pedir a cotação."""
    if crypto:
        return None
    now = now or time.time()
    edges = [t for s in sessions.values() for t in (s['start'], s['end']) if t > now]
    return min(edges) * 1000 if edges else None


# ---------- TradingView ----------
# Sufixo do Yahoo -> bolsa no TradingView
TV_EXCHANGE = {
    'LS': 'EURONEXT', 'AS': 'EURONEXT', 'PA': 'EURONEXT', 'BR': 'EURONEXT', 'IR': 'EURONEXT',
    'DE': 'XETR', 'F': 'FWB', 'MI': 'MIL', 'MC': 'BME', 'L': 'LSE', 'SW': 'SIX', 'VI': 'VIE',
    'ST': 'OMXSTO', 'HE': 'OMXHEX', 'CO': 'OMXCOP', 'OL': 'OSL', 'WA': 'GPW',
    'TO': 'TSX', 'V': 'TSXV', 'SA': 'BMFBOVESPA', 'MX': 'BMV',
    'AX': 'ASX', 'NZ': 'NZX', 'T': 'TSE', 'HK': 'HKEX', 'SS': 'SSE', 'SZ': 'SZSE', 'KS': 'KRX',
    'NS': 'NSE', 'BO': 'BSE', 'TW': 'TWSE', 'SI': 'SGX', 'JO': 'JSE',
}
# Os índices "oficiais" (SP:SPX, …) não têm dados no widget gratuito: usam-se os CFD equivalentes
TV_INDEX = {
    '^GSPC': 'FOREXCOM:SPXUSD', '^DJI': 'FOREXCOM:DJI', '^IXIC': 'NASDAQ:IXIC', '^NDX': 'FOREXCOM:NSXUSD',
    '^RUT': 'FOREXCOM:US2000', '^VIX': 'TVC:VIX', '^STOXX50E': 'FOREXCOM:EU50', '^GDAXI': 'FOREXCOM:GRXEUR',
    '^FTSE': 'FOREXCOM:UKXGBP', '^FCHI': 'FOREXCOM:FRXEUR', '^IBEX': 'FOREXCOM:ESPEUR', '^N225': 'FOREXCOM:JPXJPY',
    '^HSI': 'FOREXCOM:HKXHKD', 'PSI20.LS': 'EURONEXT:PSI20',
}


def tradingview_symbol(sym, exchange=''):
    if sym in TV_INDEX:
        return TV_INDEX[sym]
    if m := re.match(r'^([A-Z0-9]+)-(USD|EUR|GBP|USDT)$', sym):
        return f'BINANCE:{m[1]}USDT' if m[2] in ('USD', 'USDT') else f'COINBASE:{m[1]}{m[2]}'
    if m := re.match(r'^([A-Z]{6})=X$', sym):
        return f'FX_IDC:{m[1]}'
    if m := re.match(r'^([A-Z]{3})=X$', sym):
        return f'FX_IDC:USD{m[1]}'
    if (m := re.match(r'^(.+)\.([A-Z]{1,2})$', sym)) and m[2] in TV_EXCHANGE:
        return f"{TV_EXCHANGE[m[2]]}:{m[1].replace('-', '_')}"
    # EUA: a bolsa vem dos dados do Yahoo; BRK-B no Yahoo é BRK.B no TradingView
    base = sym.replace('-', '.')
    if re.match(r'^Nasdaq', exchange, re.I):
        return f'NASDAQ:{base}'
    if re.match(r'^NYSE ?Arca|NYSE American', exchange, re.I):
        return f'AMEX:{base}'
    if re.match(r'^NYSE', exchange, re.I):
        return f'NYSE:{base}'
    return base.lstrip('^')


# ---------- cotação ----------

def _change(price, ref):
    if not ref or price is None:
        return None, None
    return price - ref, (price - ref) / ref * 100


def get_quote(symbol, with_bars=False):
    """Cotação normalizada: preço regular, variação, pré/pós-mercado, estado da bolsa e (opcional) o gráfico de hoje."""
    res = fetch_chart(symbol)
    m = res['meta']
    cur, div = norm_currency(m.get('currency'))
    crypto = m.get('instrumentType') == 'CRYPTOCURRENCY'
    sessions = _sessions(m)
    reg = sessions.get('regular')
    has_ext = bool(m.get('hasPrePostMarketData')) and not crypto

    def session_at(t):
        if not has_ext or not reg:
            return None
        return 'pre' if t < reg['start'] else 'post' if t >= reg['end'] else None

    bars = [{'t': t * 1000, 'y': y, 'e': session_at(t)} for t, y in series(res)]
    prev_raw = m.get('chartPreviousClose', m.get('previousClose'))
    prev = prev_raw / div if prev_raw else None
    price = m['regularMarketPrice'] / div
    reg_t = m['regularMarketTime'] * 1000
    change, change_pct = _change(price, prev)

    # há um preço de pré/pós-mercado mais recente do que o da sessão regular?
    last = bars[-1] if bars else None
    ext = None
    if last and last['e'] and last['t'] > reg_t:
        ext_change, ext_pct = _change(last['y'], price)
        ext = {'price': last['y'], 't': last['t'], 'session': last['e'], 'change': ext_change, 'changePct': ext_pct}

    exchange = m.get('fullExchangeName') or m.get('exchangeName') or ''
    q = {
        'symbol': symbol,
        'name': m.get('longName') or m.get('shortName') or symbol,
        'exchange': exchange,
        'currency': cur,
        'type': m.get('instrumentType'),
        'crypto': crypto,
        'hasExt': has_ext,
        'sessions': sessions,
        'state': market_state(sessions, crypto, has_ext),
        'nextChange': next_change(sessions, crypto),
        'price': price,
        'time': reg_t,
        'prev': prev,
        'change': change,
        'changePct': change_pct,
        'ext': ext,
        'tradingView': tradingview_symbol(symbol, exchange),
    }
    if with_bars:
        q['bars'] = bars
    return q


def effective_price(q, use_ext):
    """Preço para valorizar posições: o de pré/pós-mercado se pedido e mais recente, senão o da sessão regular."""
    if use_ext and q.get('ext'):
        return q['ext']['price'], q['ext']['session']
    return q['price'], None


def search(term):
    j = get_json(SEARCH_URL, ttl=300, params={'q': term, 'quotesCount': 10, 'newsCount': 0, 'listsCount': 0})
    return [{
        'symbol': it['symbol'],
        'name': it.get('longname') or it.get('shortname') or '',
        'type': it.get('typeDisp') or it.get('quoteType') or '',
        'exchange': it.get('exchDisp') or '',
    } for it in j.get('quotes') or [] if it.get('symbol')]


# ---------- rotas ----------

@bp.get('/quote')
def quote_route():
    sym = request.args.get('symbol', '').strip().upper()
    return jsonify(get_quote(sym, with_bars=request.args.get('bars') == '1'))


@bp.get('/search')
def search_route():
    term = request.args.get('q', '').strip()
    if not term or len(term) > 60:
        raise ValueError('Pesquisa inválida')
    return jsonify(search(term))


@bp.get('/watchlist')
def watchlist_get():
    return jsonify(storage.load()['watchlist'])


@bp.post('/watchlist')
def watchlist_add():
    sym = str((request.get_json(silent=True) or {}).get('symbol', '')).strip().upper()
    get_quote(sym)   # confirma que o símbolo existe

    def add(data):
        if sym not in data['watchlist']:
            data['watchlist'].append(sym)
    return jsonify(storage.update(add)['watchlist'])


@bp.delete('/watchlist/<path:symbol>')
def watchlist_remove(symbol):
    def remove(data):
        data['watchlist'] = [s for s in data['watchlist'] if s != symbol]
    return jsonify(storage.update(remove)['watchlist'])
