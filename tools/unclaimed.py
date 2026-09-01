"""Sentences that count something and then claim the count is complete, and constants in code.

`check.py` verifies: is what this document says still true against the disk? It cannot ask the
other question - did anyone finish looking? A sentence like "five places open that view and none
of them is usable" is true about five places and wrong as a total, and a missing sixth leaves no
trace. Nothing recomputes prose.

**Both failures this was written for happened on 1 September 2026, within an hour.** The five
places were eight. "Nine shortcuts" was the number that had been tried, against the 229 the game
binds. Both were written in words rather than digits, so a sweep over numbers would have missed
them; what they had in common was a count standing next to a claim of completeness.

This decides nothing. It hands over candidates, because the judgement - is this a total or an
observation - belongs to a reader who knows what was measured. Run it after a session that
changed what is known, and after a game update.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
SKIP_DIRS = ('.git', '.git-notes', '__pycache__', 'naslag', 'harvest')

# Dutch number words, because the working documents are Dutch and both misses were spelled out.
WORDS = ('twee', 'drie', 'vier', 'vijf', 'zes', 'zeven', 'acht', 'negen', 'tien', 'elf',
         'twaalf', 'dertien', 'veertien', 'vijftien', 'zestien', 'zeventien', 'achttien',
         'negentien', 'twintig', 'dertig', 'veertig', 'vijftig')
COUNT = re.compile(r'\b(?:%s)\b|\b\d{1,6}\b' % '|'.join(WORDS), re.I)
CLOSED = re.compile(
    r'geen enkele|geen ervan|geen van de|geen van die|geen van deze|geen van beide|'
    r'de enige|het enige|enige route|enige weg|enige manier|nergens|er is geen|er zijn geen|'
    r'alle vijf|alle vier|alle drie|alle twee|alle zes|alle zeven|alle acht|alle negen|'
    r'stuk voor stuk|uitputtend|uitgemeten|allemaal|zonder uitzondering|'
    r'no route|none of them|not one|nowhere|the only', re.I)


def files(suffixes):
    for root, dirs, names in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(names):
            if name.endswith(suffixes):
                yield os.path.join(root, name)


def sentences(text):
    """Rough split. A claim rarely spans a blank line, and that is all this needs."""
    for block in re.split(r'\n\s*\n', text):
        flat = ' '.join(block.split())
        for piece in re.split(r'(?<=[.!?])\s+(?=[A-Z*`])', flat):
            yield piece


def closing_counts():
    """Per document, the sentences that count and then close a door."""
    found = {}
    for path in files(('.md',)):
        short = os.path.relpath(path, PROJECT)
        text = open(path, encoding='utf-8', errors='replace').read()
        for piece in sentences(text):
            if 25 <= len(piece) <= 400 and COUNT.search(piece) and CLOSED.search(piece):
                found.setdefault(short, []).append(piece)
    return found


def literals():
    """Numbers in code outside comments and docstrings: a measurement, or an assumption?

    This is the other half of the same failure. 1600 and 900 stood in `openers.on_screen` as the
    edges of the screen and turned down 8995 widgets once the drawing area became 1920x1200, and
    the header field at +40 was read as a block size it is not. Both looked like code and were
    really a measurement someone wrote down.
    """
    found = {}
    for path in files(('.py', '.cpp', '.h')):
        short = os.path.relpath(path, PROJECT)
        if short == os.path.join('tools', 'unclaimed.py'):
            continue
        inside_doc = False
        for number, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
            stripped = line.strip()
            if stripped.count('"""') % 2:
                inside_doc = not inside_doc
                continue
            if inside_doc or stripped.startswith(('#', '//', '*')):
                continue
            code = re.sub(r'#.*|//.*', '', line)
            hits = re.findall(r'0x[0-9A-Fa-f]+|(?<![\w.])\d{3,}(?![\w.])', code)
            if hits:
                found.setdefault(short, []).append((number, hits, stripped[:96]))
    return found


def main(show_all):
    counts = closing_counts()
    total = sum(len(v) for v in counts.values())
    print('Sentences that count and then close a door: %d' % total)
    for short in sorted(counts, key=lambda s: -len(counts[s])):
        print('  %-30s %3d' % (short, len(counts[short])))
    if show_all:
        for short in sorted(counts):
            print('')
            print('=== %s ===' % short)
            for piece in counts[short]:
                print('  - %s' % piece[:230])

    code = literals()
    print('')
    print('Numbers in code outside comments and docstrings: %d'
          % sum(len(v) for v in code.values()))
    for short in sorted(code, key=lambda s: -len(code[s])):
        print('  %-34s %3d' % (short, len(code[short])))
    if show_all:
        for short in sorted(code):
            print('')
            print('=== %s ===' % short)
            for number, hits, line in code[short]:
                print('  %5d  %-22s %s' % (number, ','.join(hits)[:22], line))

    print('')
    print('None of this is a defect by itself. A count is a candidate; ask whether it is a total')
    print('or an observation, and whether it belongs in reports\\claims.json with its rule.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main('--all' in sys.argv)
