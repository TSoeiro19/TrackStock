# Janelas da app abertas: cada janela avisa a cada 20 s (/api/ping) e despede-se ao fechar (/api/bye).
# Com --auto-stop, o servidor desliga-se quando não há janelas abertas há tempo suficiente.
import re
import threading
import time

from flask import Blueprint, jsonify, request

bp = Blueprint('presence', __name__, url_prefix='/api')

STALE_AFTER = 10 * 60      # janela que deixou de dar sinal (ex.: o Chrome fechou à força)
GRACE_CLOSED = 8           # após fechar a última janela (dá tempo a um F5)
GRACE_NEVER_OPEN = 2 * 60  # a app nunca chegou a abrir
ID_RE = re.compile(r'^[a-f0-9-]{8,40}$')

_clients = {}              # id -> último sinal
_had_client = False
_empty_since = time.monotonic()
_lock = threading.Lock()


def _update(client_id, alive):
    global _had_client
    if not client_id or not ID_RE.match(client_id):
        return
    with _lock:
        if alive:
            _clients[client_id] = time.monotonic()
            _had_client = True
        else:
            _clients.pop(client_id, None)


def should_stop():
    """Sem janelas abertas há tempo suficiente?"""
    global _empty_since
    now = time.monotonic()
    with _lock:
        for cid, seen in list(_clients.items()):
            if now - seen > STALE_AFTER:
                del _clients[cid]
        if _clients:
            _empty_since = None
            return False
        if _empty_since is None:
            _empty_since = now
        grace = GRACE_CLOSED if _had_client else GRACE_NEVER_OPEN
        return now - _empty_since > grace


@bp.route('/ping', methods=['GET', 'POST'])
def ping():
    _update(request.args.get('id'), True)
    return jsonify({'ok': True})


@bp.route('/bye', methods=['GET', 'POST'])
def bye():
    _update(request.args.get('id'), False)
    return jsonify({'ok': True})
