# Caminhos e constantes partilhadas pelo backend
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT / 'frontend' / 'dist'      # frontend compilado (npm run build)
DATA_DIR = ROOT / 'historico'
DATA_FILE = DATA_DIR / 'transacoes.json'        # transações e watchlist (fonte de verdade)
BRIEF_DIR = DATA_DIR / 'briefings'               # um briefing por dia (AAAA-MM-DD.md)
BRIEF_PROMPT = BRIEF_DIR / 'prompt.md'          # prompt do daily briefing
BRIEF_KEEP_DAYS = 30                            # briefings mais antigos são apagados automaticamente

DEFAULT_PORT = 8765
APP_HEADER = 'investimentos'                    # valor do cabeçalho X-App que a app envia
MAX_BODY = 5 * 1024 * 1024
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
HTTP_TIMEOUT = 10

DEFAULT_WATCHLIST = ['^GSPC', 'AAPL', 'NVDA', 'MSFT', 'VWCE.DE', 'EDP.LS', 'GALP.LS', 'ASML.AS', 'BTC-USD']
