# Abre a app: liga o servidor (escondido, desliga-se sozinho ao fechar a app) e abre o browser predefinido.
# É o que o atalho "TrackStock" do ambiente de trabalho executa, com o pythonw.exe (sem janelas de consola).
import ctypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import DEFAULT_PORT, FRONTEND_DIST  # noqa: E402
from backend.desktop import app_running, open_app  # noqa: E402


def show_error(msg):
    ctypes.windll.user32.MessageBoxW(None, msg, 'TrackStock', 0x10)   # MB_ICONERROR


def main():
    url = f'http://localhost:{DEFAULT_PORT}/'
    if not (FRONTEND_DIST / 'index.html').exists():
        return show_error('Falta compilar o frontend.\nNa pasta frontend, corre: npm install e npm run build')

    if not app_running(url):
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), '-m', 'backend',
                          '--port', str(DEFAULT_PORT), '--no-browser', '--auto-stop'],
                         cwd=ROOT, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        for _ in range(30):
            if app_running(url):
                break
            time.sleep(0.5)

    if app_running(url):
        open_app(url)
    else:
        show_error(f'Não foi possível ligar a app (porta {DEFAULT_PORT}).\n'
                   'Corre "python -m backend" numa consola, na pasta do projeto, para ver o erro.')


if __name__ == '__main__':
    main()
