# Servidor local da app: python -m backend [--port 8765] [--no-browser] [--auto-stop]
# Só escuta em localhost (IPv4 e IPv6). Com --auto-stop desliga-se quando a última janela da app fecha.
import argparse
import logging
import socket
import sys
import threading
import time

from werkzeug.serving import ThreadedWSGIServer

from .app import create_app
from .config import DEFAULT_PORT
from .desktop import app_running, open_app
from .presence import should_stop


class Server(ThreadedWSGIServer):
    daemon_threads = True
    allow_reuse_address = False   # no Windows permitiria dois servidores na mesma porta

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    ap = argparse.ArgumentParser(prog='python -m backend', description='Servidor local da app de investimentos')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--no-browser', action='store_true', help='não abre a app no browser')
    ap.add_argument('--auto-stop', action='store_true', help='desliga-se quando a última janela da app fecha')
    args = ap.parse_args()
    url = f'http://localhost:{args.port}/'
    logging.getLogger('werkzeug').setLevel(logging.ERROR)   # sem registo de cada pedido

    app = create_app(args.port)
    # "localhost" pode resolver para IPv6 (::1) ou IPv4 (127.0.0.1): escuta nos dois
    try:
        servers = [Server('127.0.0.1', args.port, app)]
    except OSError:
        # A porta está ocupada: se for esta app, basta abrir o browser
        if app_running(url):
            print(f'A app já está a correr em {url}')
            if not args.no_browser:
                open_app(url)
            sys.exit(0)
        print(f'Não foi possível usar a porta {args.port} (ocupada por outro programa).')
        sys.exit(1)
    try:
        servers.append(Server('::1', args.port, app))
    except OSError:
        pass   # sem IPv6 neste PC: basta o IPv4

    print(f'App de investimentos a correr em {url}')
    print('Deixa esta janela aberta. Ctrl+C para parar.')
    if not args.no_browser:
        open_app(url)

    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, kwargs={'poll_interval': 0.5}, daemon=True).start()
    if args.auto_stop:
        def watch():
            while not should_stop():
                time.sleep(0.5)
            servers[0].shutdown()
        threading.Thread(target=watch, daemon=True).start()

    try:
        servers[0].serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.server_close()


if __name__ == '__main__':
    main()
