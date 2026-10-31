# Aplicação Flask: junta os módulos de cada funcionalidade, protege a API e serve o frontend compilado
from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import briefing, fx, market, portfolio, presence
from .config import APP_HEADER, FRONTEND_DIST, MAX_BODY
from .http_client import UpstreamError

# Pedidos sem o cabeçalho X-App: só o sinal de presença (o navigator.sendBeacon não envia cabeçalhos)
PUBLIC_API = {'/api/ping', '/api/bye'}


def create_app(port):
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = MAX_BODY
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    for module in (market, fx, portfolio, briefing, presence):
        app.register_blueprint(module.bp)

    allowed_hosts = {f'localhost:{port}', f'127.0.0.1:{port}', f'[::1]:{port}'}

    @app.before_request
    def guard():
        # Só aceita pedidos dirigidos a localhost (protege contra DNS rebinding)
        if request.host not in allowed_hosts:
            return jsonify(error='Pedido recusado'), 400
        # A API só responde à própria app: exige o cabeçalho X-App (outros sites não o conseguem enviar
        # sem autorização CORS, que este servidor nunca dá) e, se houver Origin, tem de ser esta app.
        if request.path.startswith('/api/') and request.path not in PUBLIC_API:
            origin = request.headers.get('Origin')
            if request.headers.get('X-App') != APP_HEADER or (origin and origin != f'http://localhost:{port}'):
                return jsonify(error='Pedido recusado'), 403

    @app.after_request
    def no_cache(resp):
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    # Erros com mensagem para mostrar na interface
    @app.errorhandler(ValueError)
    def bad_request(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(UpstreamError)
    def upstream(e):
        return jsonify(error=str(e)), e.status if e.status in (404,) else 502

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.description), e.code

    @app.errorhandler(Exception)
    def internal(e):
        app.logger.exception(e)
        return jsonify(error='Erro interno'), 500

    # ---------- frontend (frontend/dist, gerado por "npm run build") ----------
    @app.get('/')
    def index():
        if not (FRONTEND_DIST / 'index.html').exists():
            return ('<h1>Falta compilar o frontend</h1><p>Corre <code>npm install</code> e '
                    '<code>npm run build</code> na pasta <code>frontend</code>.</p>', 503)
        return send_from_directory(FRONTEND_DIST, 'index.html')

    @app.get('/<path:path>')
    def static_files(path):
        if path.startswith('api/'):
            abort(404, 'Não encontrado')
        return send_from_directory(FRONTEND_DIST, path)   # recusa caminhos fora da pasta

    return app
