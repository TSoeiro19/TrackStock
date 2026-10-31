# Portefólio: transações, posições (método do custo médio), valorização, alocação e histórico. Valores em EUR.
import bisect
import json
import math
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, abort, jsonify, request

from . import fx, storage
from .http_client import UpstreamError
from .market import effective_price, fetch_chart, get_quote, norm_currency, series, valid_symbol

bp = Blueprint('portfolio', __name__, url_prefix='/api/portfolio')

EPS = 1e-9
_pool = ThreadPoolExecutor(max_workers=6)


def fmt_qty(q):
    return f'{q:g}'.replace('.', ',')


def today_iso():
    return date.today().isoformat()


# ---------- posições ----------

def sorted_tx(txs):
    return sorted(txs, key=lambda t: (t['date'], t.get('created', 0)))


def tx_amounts(t):
    """Montante da transação em EUR e USD, com o câmbio do dia da transação."""
    gross = t['qty'] * t['price']
    return {
        'EUR': gross if t['currency'] == 'EUR' else gross / t['fx'],
        'USD': gross if t['currency'] == 'USD' else gross * t['fx'],
    }


def compute_positions(txs):
    """(posições abertas, ganho realizado, primeira venda sem quantidade suficiente ou None)."""
    pos = {}
    realized = {'EUR': 0.0, 'USD': 0.0}
    negative = None
    for t in sorted_tx(txs):
        p = pos.setdefault(t['symbol'], {'symbol': t['symbol'], 'qty': 0.0, 'cost': {'EUR': 0.0, 'USD': 0.0}})
        amt = tx_amounts(t)
        if t['type'] == 'buy':
            p['qty'] += t['qty']
            for c in ('EUR', 'USD'):
                p['cost'][c] += amt[c]
        else:
            if t['qty'] > p['qty'] + EPS and negative is None:
                negative = t
            ratio = min(1.0, t['qty'] / p['qty']) if p['qty'] > 0 else 0.0
            for c in ('EUR', 'USD'):
                realized[c] += amt[c] - p['cost'][c] * ratio
                p['cost'][c] -= p['cost'][c] * ratio
            p['qty'] -= t['qty']
    return [p for p in pos.values() if p['qty'] > EPS], realized, negative


def _safe_quote(sym):
    try:
        return get_quote(sym)
    except (UpstreamError, ValueError):
        return None


def quotes_for(symbols):
    return dict(zip(symbols, _pool.map(_safe_quote, symbols)))


def valuate(open_positions, use_ext):
    """Posições valorizadas ao preço atual (em EUR) e o valor total (None se faltar algum preço)."""
    quotes = quotes_for([p['symbol'] for p in open_positions])
    rows, total, priced = [], 0.0, True
    for p in open_positions:
        q = quotes.get(p['symbol'])
        cost = p['cost']['EUR']
        price, session = effective_price(q, use_ext) if q else (None, None)
        value = fx.to_eur(p['qty'] * price, q['currency']) if q else None
        if value is None:
            priced = False
        else:
            total += value
        pnl = value - cost if value is not None else None
        # preço médio na moeda do ativo (EUR ou USD, as moedas do custo registado), para comparar com o preço atual
        avg_cur = q['currency'] if q and q['currency'] in p['cost'] else 'EUR'
        rows.append({
            'symbol': p['symbol'],
            'name': q['name'] if q else '',
            'qty': p['qty'],
            'avgCost': p['cost'][avg_cur] / p['qty'],
            'avgCostCurrency': avg_cur,
            'avgCostEUR': cost / p['qty'],
            'costEUR': cost,
            'price': price,
            'currency': q['currency'] if q else None,
            'session': session,
            'valueEUR': value,
            'pnlEUR': pnl,
            'pnlPct': pnl / cost * 100 if pnl is not None and cost else None,
        })
    rows.sort(key=lambda r: r['valueEUR'] or 0, reverse=True)
    return rows, (total if priced else None)


def summary(use_ext):
    data = storage.load()
    open_, realized, _ = compute_positions(data['tx'])
    positions, value = valuate(open_, use_ext)
    cost = sum(p['cost']['EUR'] for p in open_)
    if not open_:
        value = 0.0
    pnl = value - cost if value is not None and open_ else None

    priced = [p for p in positions if p['valueEUR'] is not None]
    alloc_total = sum(p['valueEUR'] for p in priced)
    allocation = [{'symbol': p['symbol'], 'valueEUR': p['valueEUR'], 'pct': p['valueEUR'] / alloc_total * 100}
                  for p in priced] if alloc_total > 0 else []

    transactions = [{**t, 'total': t['qty'] * t['price']} for t in reversed(sorted_tx(data['tx']))]
    return {
        'totals': {
            'valueEUR': value,
            'costEUR': cost,
            'pnlEUR': pnl,
            'pnlPct': pnl / cost * 100 if pnl is not None and cost else None,
            'realizedEUR': realized['EUR'],
        },
        'positions': positions,
        'allocation': allocation,
        'transactions': transactions,
        'savedAt': storage.saved_at(),
    }


# ---------- histórico ----------
# Dias anteriores: fecho diário de cada ativo e câmbio do BCE desse dia.
# Hoje: velas de 5 minutos de cada ativo e câmbio atual, terminando no valor atual.

RANGE_STEPS = [('1mo', 28), ('3mo', 88), ('6mo', 180), ('1y', 360), ('5y', 1800), ('max', math.inf)]
_daily_closes = {}   # símbolo -> {rank, day, cur, dates, closes}
_series_cache = {}   # chave -> (expira, resultado)
_cache_lock = threading.Lock()


def _signature(txs):
    return tuple((t['id'], t['date'], t['symbol'], t['type'], t['qty'], t['price'], t['fx']) for t in sorted_tx(txs))


def _cached(key, ttl, fn):
    now = time.monotonic()
    with _cache_lock:
        hit = _series_cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    result = fn()
    with _cache_lock:
        if len(_series_cache) > 50:
            _series_cache.clear()
        _series_cache[key] = (now + ttl, result)
    return result


def _load_daily(sym, first):
    days = (date.today() - date.fromisoformat(first)).days + 7
    rank = next(i for i, (_, max_days) in enumerate(RANGE_STEPS) if days <= max_days)
    cached = _daily_closes.get(sym)
    if cached and cached['rank'] >= rank and cached['day'] == today_iso():
        return cached
    res = fetch_chart(sym, RANGE_STEPS[rank][0], '1d')
    cur, _ = norm_currency(res['meta'].get('currency'))
    off = res['meta'].get('gmtoffset') or 0
    closes = {datetime.fromtimestamp(t + off, timezone.utc).date().isoformat(): px for t, px in series(res)}
    _daily_closes[sym] = {'rank': rank, 'day': today_iso(), 'cur': cur, 'dates': sorted(closes), 'closes': closes}
    return _daily_closes[sym]


def _close_on(c, day):
    i = bisect.bisect_right(c['dates'], day) - 1
    return c['closes'][c['dates'][max(i, 0)]]   # antes do primeiro dia conhecido usa o primeiro fecho


def _end_of_day_ms(day):
    return datetime.fromisoformat(day + 'T23:59:59').timestamp() * 1000


def daily_series(txs):
    """([{t, v, c}] um ponto por dia até ontem, símbolos sem histórico de preços)."""
    txs = sorted_tx(txs)
    first, today = txs[0]['date'], today_iso()
    fx.load_history(fx.days_before(first, 7))
    syms = list(dict.fromkeys(t['symbol'] for t in txs))

    def load(sym):
        try:
            return sym, _load_daily(sym, first)
        except (UpstreamError, ValueError):
            return sym, None
    by_sym = dict(_pool.map(load, syms))
    failed = [s for s, c in by_sym.items() if c is None]

    points = []
    day = first
    while day < today:
        open_, _, _ = compute_positions([t for t in txs if t['date'] <= day])
        value = cost = 0.0
        for p in open_:
            cost += p['cost']['EUR']
            c = by_sym.get(p['symbol'])
            if c:
                value += p['qty'] * _close_on(c, day) / fx.per_eur_on(c['cur'], day)
        points.append({'t': _end_of_day_ms(day), 'v': value, 'c': cost})
        day = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    return points, failed


def intraday_series(txs, use_ext):
    """[{t, v, c}] de hoje, com as velas de 5 minutos (sem pré/pós-mercado, se não for pedido)."""
    open_, _, _ = compute_positions(txs)
    if not open_:
        return []
    midnight = datetime.combine(date.today(), datetime.min.time()).timestamp()
    cost = sum(p['cost']['EUR'] for p in open_)

    def load(p):
        try:
            res = fetch_chart(p['symbol'], '1d', '5m')
        except (UpstreamError, ValueError):
            return None
        m = res['meta']
        cur, div = norm_currency(m.get('currency'))
        rate = fx.per_eur(cur)
        reg = (m.get('currentTradingPeriod') or {}).get('regular')
        only_regular = not use_ext and reg and m.get('instrumentType') != 'CRYPTOCURRENCY'
        pts = [(t, px) for t, px in series(res)
               if t >= midnight and (not only_regular or reg['start'] <= t < reg['end'])]
        prev = m.get('chartPreviousClose', m.get('previousClose'))
        return {'qty': p['qty'], 'rate': rate, 'pts': pts, 'prev': prev / div if prev else None}

    syms = [s for s in _pool.map(load, open_)]
    if any(s is None or not s['rate'] for s in syms):
        return []
    timeline = sorted({t for s in syms for t, _ in s['pts']})
    points = []
    for t in timeline:
        value = 0.0
        for s in syms:
            i = bisect.bisect_right(s['pts'], (t, math.inf)) - 1
            px = s['pts'][i][1] if i >= 0 else s['prev']   # antes da abertura: fecho anterior
            if px is None:
                break
            value += s['qty'] * px / s['rate']
        else:
            points.append({'t': t * 1000, 'v': value, 'c': cost})
    return points


def history(range_ms, use_ext):
    """Série para o gráfico. A linha começa no limite do filtro com o último valor conhecido antes dele."""
    txs = storage.load()['tx']
    now = time.time() * 1000
    if not txs:
        return {'series': [], 'from': now - range_ms if range_ms else None, 'to': now, 'message': ''}
    sig = _signature(txs)
    message = ''
    try:
        daily, failed = _cached(('daily', sig, today_iso()), 3600, lambda: daily_series(txs))
        if failed:
            message = f"Sem histórico de preços para {', '.join(failed)}: esses ativos não entram no valor dos dias anteriores."
    except UpstreamError as e:
        daily, message = [], f'Não foi possível reconstruir o histórico: {e}'
    intraday = _cached(('intraday', sig, use_ext), 50, lambda: intraday_series(txs, use_ext))

    open_, _, _ = compute_positions(txs)
    _, value = valuate(open_, use_ext)
    last_daily = daily[-1]['t'] if daily else 0
    points = daily + [p for p in intraday if p['t'] > last_daily]
    if value is not None:
        points.append({'t': now, 'v': value, 'c': sum(p['cost']['EUR'] for p in open_)})

    start = now - range_ms if range_ms else None
    if start is None:
        shown = points
    else:
        shown = [p for p in points if p['t'] >= start]
        before = [p for p in points if p['t'] < start]
        if before:
            shown.insert(0, {**before[-1], 't': start})
    return {'series': shown, 'from': start, 'to': now, 'message': message}


# ---------- transações ----------

def parse_tx(body):
    """Valida os campos de uma transação vinda do formulário (lança ValueError com a mensagem a mostrar)."""
    try:
        qty, price = float(body.get('qty')), float(body.get('price'))
    except (TypeError, ValueError):
        raise ValueError('Preenche todos os campos com valores positivos.')
    symbol = str(body.get('symbol', '')).strip().upper()
    day = str(body.get('date', ''))
    if not valid_symbol(symbol) or not re.match(r'^\d{4}-\d{2}-\d{2}$', day) or not qty > 0 or not price > 0:
        raise ValueError('Preenche todos os campos com valores positivos.')
    if day > today_iso():
        raise ValueError('A data não pode estar no futuro.')
    if body.get('type') not in ('buy', 'sell') or body.get('currency') not in ('EUR', 'USD'):
        raise ValueError('Tipo ou moeda inválidos.')
    return {'symbol': symbol, 'date': day, 'qty': qty, 'price': price, 'type': body['type'], 'currency': body['currency']}


def import_tx(t):
    """Transação vinda de um ficheiro importado."""
    tx = parse_tx(t)
    fx_rate = float(t.get('fx') or 0)
    if not fx_rate > 0:
        raise ValueError(f"Transação de {tx['symbol']} sem câmbio (fx).")
    return {'id': str(t.get('id') or uuid.uuid4()), 'created': int(t.get('created') or 0), **tx, 'fx': fx_rate}


# ---------- rotas ----------

def _use_ext():
    return request.args.get('ext') == '1'


@bp.get('')
def summary_route():
    return jsonify(summary(_use_ext()))


@bp.get('/history')
def history_route():
    range_ms = max(0, int(request.args.get('range') or 0))
    return jsonify(history(range_ms, _use_ext()))


@bp.post('/transactions')
def add_transaction():
    tx = parse_tx(request.get_json(silent=True) or {})
    get_quote(tx['symbol'])   # confirma que o ativo existe (e há preço para o valorizar)
    rate = fx.usd_on(tx['date'])
    if not rate:
        raise ValueError('Câmbio EUR/USD indisponível, tenta de novo daqui a pouco.')
    tx = {'id': str(uuid.uuid4()), 'created': int(time.time() * 1000), **tx, 'fx': rate}

    def add(data):
        if compute_positions(data['tx'] + [tx])[2]:
            raise ValueError(f"Não tens {tx['symbol']} suficiente nessa data para vender {fmt_qty(tx['qty'])}.")
        data['tx'].append(tx)
    storage.update(add)
    return jsonify(tx)


@bp.delete('/transactions/<tx_id>')
def delete_transaction(tx_id):
    def remove(data):
        remaining = [t for t in data['tx'] if t['id'] != tx_id]
        if len(remaining) == len(data['tx']):
            abort(404, 'Transação não encontrada')
        if compute_positions(remaining)[2]:
            raise ValueError('Não é possível apagar: uma venda posterior ficaria sem quantidade suficiente.')
        data['tx'] = remaining
    storage.update(remove)
    return jsonify({'ok': True})


@bp.get('/price')
def market_price():
    """Preço de mercado atual de um ativo, convertido para EUR ou USD (botão "Usar preço atual")."""
    q = get_quote(request.args.get('symbol', '').strip().upper())
    eur = fx.to_eur(q['price'], q['currency'])
    usd_rate = fx.per_eur('USD')
    value = eur if request.args.get('currency') == 'EUR' else (eur * usd_rate if eur is not None and usd_rate else None)
    if value is None:
        raise ValueError('Câmbio indisponível para converter o preço.')
    return jsonify({'value': round(value, 6 if value < 1 else 4), 'quotePrice': q['price'], 'quoteCurrency': q['currency']})


@bp.get('/export')
def export_route():
    data = storage.load()
    content = {'version': 3, 'savedAt': datetime.now(timezone.utc).isoformat(), **data}
    return Response(json.dumps(content, ensure_ascii=False, indent=2), mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename="portefolio-{today_iso()}.json"'})


@bp.post('/import')
def import_route():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get('tx'), list):
        raise ValueError('Ficheiro sem lista de transações.')
    txs = [import_tx({**t, 'symbol': storage.migrate_symbol(str(t.get('symbol', '')))}) for t in body['tx']]
    if compute_positions(txs)[2]:
        raise ValueError('O ficheiro tem vendas sem quantidade suficiente.')

    def replace(data):
        data['tx'] = txs
        if isinstance(body.get('watchlist'), list):
            data['watchlist'] = list(dict.fromkeys(storage.migrate_symbol(str(s)).upper() for s in body['watchlist']))
    storage.update(replace)
    return jsonify({'ok': True, 'count': len(txs)})
