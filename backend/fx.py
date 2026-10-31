# Câmbio: BCE (Frankfurter) para as moedas principais, Yahoo para as restantes. Taxas = unidades por 1 EUR.
import bisect
import threading
import time
from datetime import date, timedelta

from flask import Blueprint, jsonify

from .http_client import UpstreamError, get_json

bp = Blueprint('fx', __name__, url_prefix='/api/fx')

FRANKFURTER = 'https://api.frankfurter.dev/v1'
RATES_TTL = 3600

_lock = threading.Lock()
_rates = {'EUR': 1.0}      # câmbio atual do BCE
_rates_at = None           # quando foi atualizado (time.monotonic)
_extra = {}                # moedas que o BCE não publica, via Yahoo (None = sem câmbio)
_hist = None               # {'from': 'AAAA-MM-DD', 'dates': [...], 'rates': {data: {moeda: taxa}}}


def current_rates():
    """Câmbio atual do BCE (atualizado no máximo a cada hora; se falhar, mantém o último)."""
    global _rates, _rates_at
    if _rates_at is None or time.monotonic() - _rates_at > RATES_TTL:
        try:
            j = get_json(f'{FRANKFURTER}/latest', params={'base': 'EUR'})
            with _lock:
                _rates = {**j['rates'], 'EUR': 1.0}
                _rates_at = time.monotonic()
        except (UpstreamError, KeyError):
            _rates_at = time.monotonic() - RATES_TTL + 60   # sem ligação: tenta de novo daqui a 1 min
    return _rates


def per_eur(cur):
    """Unidades de `cur` por 1 EUR (None se não houver câmbio)."""
    if cur == 'EUR':
        return 1.0
    rate = current_rates().get(cur)
    if rate:
        return rate
    if cur not in _extra:
        from .market import fetch_chart   # importação local: market não depende de fx
        try:
            _extra[cur] = fetch_chart(f'EUR{cur}=X', '5d', '1d')['meta']['regularMarketPrice']
        except (UpstreamError, ValueError, KeyError):
            _extra[cur] = None
    return _extra[cur]


def to_eur(amount, cur):
    rate = per_eur(cur)
    return amount / rate if rate and amount is not None else None


def usd_on(day):
    """EUR/USD do BCE numa data (último publicado até esse dia), para registar o câmbio de cada transação."""
    if day >= date.today().isoformat():
        return per_eur('USD')
    try:
        return get_json(f'{FRANKFURTER}/{day}', ttl=86400, params={'base': 'EUR', 'symbols': 'USD'})['rates']['USD']
    except (UpstreamError, KeyError):
        return per_eur('USD')


# ---------- câmbio histórico (reconstrução do histórico do portefólio) ----------

def load_history(start):
    """Garante o câmbio diário desde `start` (AAAA-MM-DD) até hoje."""
    global _hist
    today = date.today().isoformat()
    if _hist and _hist['from'] <= start and _hist['to'] == today:
        return
    j = get_json(f'{FRANKFURTER}/{start}..{today}', params={'base': 'EUR'})
    rates = j.get('rates')
    if not isinstance(rates, dict) or 'USD' in rates:
        raise UpstreamError('resposta inesperada do câmbio histórico')
    with _lock:
        _hist = {'from': start, 'to': today, 'dates': sorted(rates), 'rates': rates}


def per_eur_on(cur, day):
    """Unidades de `cur` por 1 EUR num dia (último câmbio publicado até esse dia; senão, o atual)."""
    if cur == 'EUR':
        return 1.0
    if _hist:
        i = bisect.bisect_right(_hist['dates'], day) - 1
        if i >= 0 and _hist['rates'][_hist['dates'][i]].get(cur):
            return _hist['rates'][_hist['dates'][i]][cur]
    return per_eur(cur)


def days_before(day, n):
    return (date.fromisoformat(day) - timedelta(days=n)).isoformat()


@bp.get('')
def rates_route():
    rates = current_rates()
    return jsonify({'usd': rates.get('USD'), 'rates': rates})
