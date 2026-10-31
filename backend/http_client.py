# Pedidos HTTP a serviços externos (Yahoo Finance, BCE) com cache curta em memória
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import HTTP_TIMEOUT, USER_AGENT


class UpstreamError(Exception):
    """O serviço externo falhou ou respondeu com erro. status/body vêm da resposta, se houver."""

    def __init__(self, message, status=502, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


_cache = {}   # url -> (expira, dados)
_lock = threading.Lock()


def get_json(url, ttl=0, params=None):
    if params:
        url += '?' + urllib.parse.urlencode(params)
    now = time.monotonic()
    if ttl:
        with _lock:
            hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except ValueError:
            body = None
        raise UpstreamError(f'HTTP {e.code}', e.code, body) from e
    except (OSError, ValueError) as e:
        raise UpstreamError('Falha a contactar o serviço externo') from e
    if ttl:
        with _lock:
            if len(_cache) > 500:   # limpa as entradas expiradas
                for k in [k for k, (exp, _) in _cache.items() if exp <= now]:
                    del _cache[k]
            _cache[url] = (now + ttl, data)
    return data
