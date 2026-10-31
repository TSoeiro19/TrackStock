# Integração com o Windows: servidor a correr?, abrir a app numa janela própria do browser predefinido
import shlex
import subprocess
import urllib.request
import webbrowser
import winreg
from pathlib import Path

# Browsers baseados em Chromium: aceitam --app= (janela sem separadores nem barra de endereços)
APP_MODE_BROWSERS = {'chrome.exe', 'msedge.exe', 'brave.exe', 'vivaldi.exe', 'chromium.exe'}


def app_running(url):
    try:
        with urllib.request.urlopen(url + 'api/ping', timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def default_prog_id():
    """ProgId do browser predefinido para links http (ex.: ChromeHTML). O Windows 11 recente usa UserChoiceLatest."""
    base = r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http'
    for sub in (r'UserChoiceLatest\ProgId', 'UserChoice'):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf'{base}\{sub}') as key:
                return winreg.QueryValueEx(key, 'ProgId')[0]
        except OSError:
            pass
    return None


def default_browser():
    """Executável do browser predefinido para links http, ou None se não se conseguir ler do registo."""
    prog_id = default_prog_id()
    if not prog_id:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf'{prog_id}\shell\open\command') as key:
            command = winreg.QueryValueEx(key, '')[0]
    except OSError:
        return None
    exe = Path(shlex.split(command, posix=False)[0].strip('"'))
    return exe if exe.is_file() else None


def open_app(url):
    """Abre numa janela de app se o browser predefinido o permitir; senão, num separador normal."""
    browser = default_browser()
    if browser and browser.name.lower() in APP_MODE_BROWSERS:
        subprocess.Popen([str(browser), f'--app={url}'])
    else:
        webbrowser.open(url)
