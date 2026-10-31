# Daily briefing: a prompt de historico/briefings/prompt.md corre no Claude Code e o resultado fica em historico/briefings/AAAA-MM-DD.md
# Ficheiros por dia: .md (resultado), .tmp/.err (durante a geração), .pid (geração a decorrer),
# .failed (erro), .input.md (prompt enviada)
import ctypes
import os
import re
import shutil
import subprocess
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request

from .config import BRIEF_DIR, BRIEF_KEEP_DAYS, BRIEF_PROMPT

bp = Blueprint('briefing', __name__, url_prefix='/api/briefing')

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)   # o claude.exe corre sem abrir consola
_lock = threading.Lock()


def find_claude():
    """claude.exe: CLI instalado à parte, no PATH, ou o que vem com a extensão do VS Code (a mais recente)."""
    for p in (Path.home() / '.local' / 'bin' / 'claude.exe', shutil.which('claude.exe')):
        if p and Path(p).is_file():
            return Path(p)
    ext = sorted((Path.home() / '.vscode' / 'extensions').glob('anthropic.claude-code-*/resources/native-binary/claude.exe'),
                 key=lambda p: p.stat().st_mtime, reverse=True)
    return ext[0] if ext else None


def process_name(pid):
    """Nome do executável do processo, se ainda estiver a correr (Windows)."""
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.restype = ctypes.c_void_p
    h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    h = ctypes.c_void_p(h)
    try:
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:   # STILL_ACTIVE
            return None
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(len(buf))
        if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return None
        return Path(buf.value).stem.lower()
    finally:
        k.CloseHandle(h)


def _file(day, ext):
    return BRIEF_DIR / f'{day}.{ext}'


def _mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()


def _read(path):
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''


def _remove(*paths):
    for p in paths:
        p.unlink(missing_ok=True)


def status(day):
    """{date, status: ready|running|missing|error, markdown?, generatedAt?, since?, error?}"""
    pid_file, tmp, err, failed, md = (_file(day, e) for e in ('pid', 'tmp', 'err', 'failed', 'md'))
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().split()[0])
        except (ValueError, IndexError):
            pid = 0
        if pid and process_name(pid) == 'claude':
            return {'date': day, 'status': 'running', 'since': _mtime(pid_file)}
        # a geração terminou: guarda o resultado ou o erro
        _remove(pid_file)
        out = _read(tmp).strip()
        if len(out) >= 200:
            os.replace(tmp, md)
            _remove(failed)
        else:
            msg = '\n'.join(s for s in (_read(err).strip(), out) if s) or 'O Claude terminou sem devolver o briefing.'
            failed.write_text(msg, encoding='utf-8')
            _remove(tmp)
        _remove(err, _file(day, 'input.md'))
    if md.exists():
        return {'date': day, 'status': 'ready', 'markdown': _read(md), 'generatedAt': _mtime(md)}
    if failed.exists():
        return {'date': day, 'status': 'error', 'error': _read(failed)}
    return {'date': day, 'status': 'missing'}


def start(day):
    st = status(day)
    if st['status'] == 'running':
        return st
    claude = find_claude()
    if not claude:
        return {'date': day, 'status': 'error', 'error': 'Claude Code CLI não encontrado (claude.exe).'}
    if not BRIEF_PROMPT.exists():
        return {'date': day, 'status': 'error', 'error': 'Falta o ficheiro historico\\briefings\\prompt.md.'}

    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    _remove(_file(day, 'failed'))
    extra = ('\n\n---\n## Instruções desta execução\n'
             f'- Data de hoje: {day} (Europe/Lisbon).\n'
             '- Esta execução foi pedida agora pela app; ignora as indicações sobre agendamento.\n'
             '- Responde apenas com o briefing final em Markdown, sem comentários sobre o processo nem perguntas.')
    input_file = _file(day, 'input.md')
    input_file.write_text(_read(BRIEF_PROMPT) + extra, encoding='utf-8')

    with open(input_file, 'rb') as fin, open(_file(day, 'tmp'), 'wb') as fout, open(_file(day, 'err'), 'wb') as ferr:
        p = subprocess.Popen([str(claude), '-p', '--allowedTools', 'WebSearch,WebFetch'],
                             stdin=fin, stdout=fout, stderr=ferr, cwd=BRIEF_DIR, creationflags=NO_WINDOW)
    _file(day, 'pid').write_text(str(p.pid))
    return status(day)


def cleanup(keep_days=BRIEF_KEEP_DAYS):
    """Apaga os ficheiros de briefings com mais de keep_days dias (pela data no nome). Não toca no prompt.md."""
    if not BRIEF_DIR.exists():
        return []
    limit = (date.today() - timedelta(days=keep_days)).isoformat()
    removed = []
    for f in BRIEF_DIR.iterdir():
        m = re.match(r'^(\d{4}-\d{2}-\d{2})\.', f.name)
        if m and m[1] < limit and f.is_file():
            f.unlink(missing_ok=True)
            removed.append(f.name)
    return removed


def list_dates():
    dates = sorted((f.stem for f in BRIEF_DIR.glob('*.md') if DATE_RE.match(f.stem)), reverse=True)[:90] \
        if BRIEF_DIR.exists() else []
    return {'today': date.today().isoformat(), 'dates': dates}


@bp.get('/list')
def list_route():
    with _lock:
        cleanup()   # a lista é pedida sempre que a app abre
        return jsonify(list_dates())


@bp.get('')
def status_route():
    day = request.args.get('date', '')
    if not DATE_RE.match(day):
        raise ValueError('Data inválida')
    with _lock:
        return jsonify(status(day))


@bp.post('/generate')
def generate_route():
    with _lock:
        return jsonify(start(date.today().isoformat()))   # só se gera o briefing do próprio dia
