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
import os
import winreg


def _from_env(name):
    value = os.environ.get(name)
    return value if value and os.path.isdir(value) else None


def _steam_libraries():
    """The Steam folders from the registry and from `libraryfolders.vdf`; a player may use
    more than one drive."""
    folders = []
    for branch, build_key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                         (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
        try:
            with winreg.OpenKey(branch, build_key) as k:
                for field in ('SteamPath', 'InstallPath'):
                    try:
                        folders.append(winreg.QueryValueEx(k, field)[0])
                    except OSError:
                        pass
        except OSError:
            pass
    out = []
    for base in folders:
        out.append(base)
        vdf = os.path.join(base, 'steamapps', 'libraryfolders.vdf')
        if os.path.exists(vdf):
            for line in open(vdf, encoding='utf-8', errors='replace'):
                if '"path"' in line:
                    part = line.split('"')
                    if len(part) > 3:
                        out.append(part[3].replace('\\\\', '\\'))
    return out


def _find_game():
    candidates = [os.path.join(b, 'steamapps', 'common', 'Crusader Kings III')
                  for b in _steam_libraries()]
    candidates += [r'C:\steam\steamapps\common\Crusader Kings III',
                   r'C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III']
    for path in candidates:
        if os.path.exists(os.path.join(path, 'binaries', 'ck3.exe')):
            return path
    return None


def _find_docs():
    """The Documents folder comes from the registry, because it can be moved or redirected
    (OneDrive) and is named differently on a non-English Windows."""
    base = None
    try:
        build_key = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, build_key) as k:
            base = os.path.expandvars(winreg.QueryValueEx(k, 'Personal')[0])
    except OSError:
        pass
    for candidate in (base, os.path.join(os.path.expanduser('~'), 'Documents'),
                      os.path.join(os.path.expanduser('~'), 'Documenten')):
        if candidate:
            path = os.path.join(candidate, 'Paradox Interactive', 'Crusader Kings III')
            if os.path.isdir(path):
                return path
    return None


GAME = _from_env('CK3_GAME') or _find_game()
DOCS = _from_env('CK3_DOCS') or _find_docs()
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get('CK3_WORK') or os.path.join(os.environ.get('TEMP', os.path.expanduser('~')),
                                                  'ck3')

EXE = os.path.join(GAME, 'binaries', 'ck3.exe') if GAME else None
SETTINGS = os.path.join(DOCS, 'pdx_settings.txt') if DOCS else None
SAVES = os.path.join(DOCS, 'save games') if DOCS else None
ERROR_LOG = os.path.join(DOCS, 'logs', 'error.log') if DOCS else None
REPORTS = os.path.join(PROJECT, 'reports')
DLL = os.path.join(PROJECT, 'dll', 'channel.dll')


def require(name):
    """Return a path, or stop with a sentence saying what needs to happen.

    Stop hard at the site of the problem: a missing path that travels on as an empty string
    produces an error three layers away that has nothing to do with the cause.
    """
    value = globals().get(name)
    if not value or not os.path.exists(value):
        raise SystemExit(
            '%s not found (%r). Set the environment variable CK3_GAME or CK3_DOCS, '
            'or check whether the game and the saves are on this machine.' % (name, value))
    return value


if __name__ == '__main__':
    for name in ('GAME', 'DOCS', 'PROJECT', 'WORK', 'EXE', 'SETTINGS', 'SAVES', 'ERROR_LOG'):
        print('%-13s %s' % (name, globals()[name]))
