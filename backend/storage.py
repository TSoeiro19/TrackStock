# Transações e watchlist em historico/transacoes.json (o mesmo formato do "Exportar JSON")
import json
import os
import re
import threading
from datetime import datetime, timezone

from .config import DATA_DIR, DATA_FILE, DEFAULT_WATCHLIST

_lock = threading.RLock()


def migrate_symbol(s):
    """Símbolos da versão Finnhub (BINANCE:BTCUSDT) passam a ser os do Yahoo (BTC-USD)."""
    return re.sub(r'^BINANCE:([A-Z0-9]+)USDT$', r'\1-USD', s)


def _normalize(data):
    tx = [{**t, 'symbol': migrate_symbol(t['symbol'])} for t in data.get('tx') or []]
    watchlist = list(dict.fromkeys(migrate_symbol(s) for s in data.get('watchlist', DEFAULT_WATCHLIST)))
    return {'tx': tx, 'watchlist': watchlist}


def load():
    with _lock:
        if not DATA_FILE.exists():
            return _normalize({})
        return _normalize(json.loads(DATA_FILE.read_text(encoding='utf-8')))


def save(data):
    with _lock:
        DATA_DIR.mkdir(exist_ok=True)
        content = {
            'version': 3,
            'savedAt': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'tx': data['tx'],
            'watchlist': data['watchlist'],
        }
        # escreve primeiro num ficheiro temporário para nunca deixar o ficheiro a meio
        tmp = DATA_FILE.with_name(DATA_FILE.name + '.tmp')
        tmp.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, DATA_FILE)
        return content


def update(fn):
    """Lê, aplica fn(data) e grava, sem outro pedido pelo meio. fn pode lançar ValueError para cancelar."""
    with _lock:
        data = load()
        fn(data)
        return save(data)

def saved_at():
    return datetime.fromtimestamp(DATA_FILE.stat().st_mtime).astimezone().isoformat() if DATA_FILE.exists() else None
