"""The single place paths come from.

Every path belonged here once and nowhere else. With the save folder in `check.py` and in
`memory.py` and in the working documents, moving it is always half done - and on another machine
it simply does not work. This is the same idea as the field offsets, one layer up: derive instead
of write down.

Anything can be overridden with an environment variable, for anyone whose game lives elsewhere:

    CK3_GAME        the install folder of Crusader Kings III
    CK3_DOCS        the folder under Documents with saves, settings and logs
    CK3_WORK        scratch work (defaults to %TEMP%\\ck3)
"""
import json
import os
import pathlib
import re
import winreg


def registry_value(branch: int, key: str, field: str, view: int = 0) -> str | None:
    """One value from the registry, or None when the key or the value is not there.

    The registry is outside input, and there absence is an answer: Steam may not be installed, and
    an uninstall entry may lack a field. Any other refusal still breaks.
    """
    try:
        with winreg.OpenKey(branch, key, 0, winreg.KEY_READ | view) as k:
            value: str = winreg.QueryValueEx(k, field)[0]
            return value
    except FileNotFoundError:
        return None


def _find_game() -> str | None:
    """The install folder, through the Steam client: its own folder from the registry, its libraries
    from `libraryfolders.vdf`, which lists that folder too; a player may use more than one drive.

    Measured 21 October 2026: the client writes `SteamPath` under the user's key, and that is where
    it is read; the installer's `InstallPath` under the machine's names the same folder.
    """
    steam = registry_value(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath')
    vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf') if steam else None
    if vdf is None or not os.path.exists(vdf):
        return None
    for library in re.findall(r'"path"\s+"([^"]+)"', pathlib.Path(vdf).read_text(encoding='utf-8')):
        path = os.path.join(library.replace('\\\\', '\\'), 'steamapps', 'common', 'Crusader Kings III')
        if os.path.exists(os.path.join(path, 'binaries', 'ck3.exe')):
            return path
    return None


def _find_docs() -> str | None:
    """The Documents folder comes from the registry, because it can be moved or redirected to
    OneDrive. A Dutch Windows shows it as Documenten, but the folder keeps its name."""
    personal = registry_value(winreg.HKEY_CURRENT_USER,
                              r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders',
                              'Personal')
    if personal is None:
        return None
    return os.path.join(os.path.expandvars(personal), 'Paradox Interactive', 'Crusader Kings III')


# An override is taken as given: one that points nowhere stops at `require` with its own path in
# the sentence, rather than quietly giving way to another copy of the game.
GAME = os.environ.get('CK3_GAME') or _find_game()
DOCS = os.environ.get('CK3_DOCS') or _find_docs()
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get('CK3_WORK') or os.path.join(os.environ['TEMP'], 'ck3')

EXE = os.path.join(GAME, 'binaries', 'ck3.exe') if GAME else None
SETTINGS = os.path.join(DOCS, 'pdx_settings.txt') if DOCS else None
SAVES = os.path.join(DOCS, 'save games') if DOCS else None
ERROR_LOG = os.path.join(DOCS, 'logs', 'error.log') if DOCS else None
REPORTS = os.path.join(PROJECT, 'reports')
DLL = os.path.join(PROJECT, 'dll', 'channel.dll')


def mod_folders() -> list[str]:
    """The folders of the mods that are switched on, in load order.

    The engine merges these over its own files, so anything reading game files off disk has to
    read the same set or it is looking at a game nobody is running. Which mods are on sits in
    `dlc_load.json`; each entry names a `.mod` file, and that file points at the workshop folder.

    Do not read the launcher database for this: it holds zero mods on this machine, which is
    exactly how it wiped `dlc_load.json` once.
    """
    if not DOCS:
        return []
    listing = os.path.join(DOCS, 'dlc_load.json')
    if not os.path.exists(listing):
        return []
    out = []
    with open(listing, encoding='utf-8-sig') as file:
        enabled = json.load(file)['enabled_mods']
    for entry in enabled:
        descriptor = os.path.join(DOCS, entry.replace('/', os.sep))
        if not os.path.exists(descriptor):
            continue
        with open(descriptor, encoding='utf-8-sig', errors='replace') as file:
            lines = file.readlines()
        for line in lines:
            if line.strip().startswith('path='):
                folder = line.split('=', 1)[1].strip().strip('"').replace('/', os.sep)
                if os.path.isdir(folder):
                    out.append(folder)
    return out


def require(name: str) -> str:
    """Return a path, or stop with a sentence saying what needs to happen.

    Stop hard at the site of the problem: a missing path that travels on as an empty string
    produces an error three layers away that has nothing to do with the cause.
    """
    value: str | None = globals()[name]
    if not value or not os.path.exists(value):
        raise SystemExit(
            f'{name} not found ({value!r}). Set the environment variable CK3_GAME or CK3_DOCS, '
            'or check whether the game and the saves are on this machine.')
    return value


if __name__ == '__main__':
    for name in ('GAME', 'DOCS', 'PROJECT', 'WORK', 'EXE', 'SETTINGS', 'SAVES', 'ERROR_LOG'):
        print(f'{name!s:<13} {globals()[name]}')
