# Cria o atalho "Investimentos" no ambiente de trabalho (abre a app sem janelas de consola)
import sys
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parent.parent


def main():
    shell = win32com.client.Dispatch('WScript.Shell')
    lnk_path = Path(shell.SpecialFolders('Desktop')) / 'TrackStock.lnk'
    pythonw = Path(sys.executable).with_name('pythonw.exe')

    lnk = shell.CreateShortCut(str(lnk_path))
    lnk.TargetPath = str(pythonw if pythonw.exists() else sys.executable)
    lnk.Arguments = f'"{ROOT / "scripts" / "abrir.py"}"'
    lnk.WorkingDirectory = str(ROOT)
    lnk.IconLocation = f'{ROOT / "frontend" / "public" / "icons" / "icon.ico"},0'
    lnk.Description = 'TrackStock'
    lnk.Save()
    print(f'Atalho criado: {lnk_path}')


if __name__ == '__main__':
    main()
