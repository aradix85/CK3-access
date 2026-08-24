"""Two things: search by subject, and report where the working document repeats itself.

    python tools\\docsearch.py <word>    says in which files and on which lines it appears
    python tools\\docsearch.py           reports size, plus numbers and sentences that occur
                                        in more than one file

Why the search lives here: a subject is rarely confined to one file, and this project has already
worked something out a second time that was written down all along. Search before you design a test.

Why the duplicate report lives here: a number in two places is a future contradiction - at the next
measurement one of them gets updated and the other does not.
"""
import collections
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = 10
IGNORE = {'2026', '2025', '2024', '2020', '1066', '1178', '867', '1600', '900'}


def files():
    """The maintainer's working notes, which are not part of this repository. On a clone this finds
    nothing, and that is correct: the tool travels with the code, the notes do not."""
    index = os.path.join(ROOT, 'BRIEF.md')
    if os.path.exists(index):
        yield index
    map_ = os.path.join(ROOT, 'brief')
    if not os.path.isdir(map_):
        return
    for name in sorted(os.listdir(map_)):
        if name.endswith('.md'):
            yield os.path.join(map_, name)


def summary(path):
    return os.path.relpath(path, ROOT)


def strip_markup(text):
    text = re.sub(r'`[^`]*`', ' ', text)
    text = re.sub(r'[*_|#\[\]()>]', ' ', text)
    return re.sub(r'\s+', ' ', text.lower()).strip()


if len(sys.argv) > 1:
    word = ' '.join(sys.argv[1:]).lower()
    found = 0
    for path in files():
        lines = open(path, 'r', encoding='utf-8').read().splitlines()
        hits = [(n, r) for n, r in enumerate(lines, 1) if word in r.lower()]
        if not hits:
            continue
        print('%s - %d hit%s' % (summary(path), len(hits), '' if len(hits) == 1 else 's'))
        for n, r in hits[:8]:
            print('   %4d  %s' % (n, r.strip()[:96]))
        if len(hits) > 8:
            print('   ... and %d more' % (len(hits) - 8))
        found += len(hits)
    if not found:
        print('%r does not appear anywhere.' % word)
    raise SystemExit(0)

total = 0
print('size:')
for path in files():
    n = len(open(path, 'r', encoding='utf-8').read().splitlines())
    total += n
    print('   %5d  %s' % (n, summary(path)))
print('   %5d  together' % total)

true_hits = collections.defaultdict(set)
shells = collections.defaultdict(set)
pattern = re.compile(r'0x[0-9A-Fa-f]{2,}|\d+[.,]\d+|\d{3,}')
for path in files():
    text = open(path, 'r', encoding='utf-8').read()
    for number in pattern.findall(text):
        if number not in IGNORE:
            true_hits[number].add(summary(path))
    words = strip_markup(text).split()
    for i in range(len(words) - SHELL):
        shells[' '.join(words[i:i + SHELL])].add(summary(path))

duplicate = {g: h for g, h in true_hits.items() if len(h) > 1}
print()
print('numbers in more than one file: %d' % len(duplicate))
for number, hs in sorted(duplicate.items(), key=lambda p: (-len(p[1]), p[0]))[:20]:
    print('   %-10s %s' % (number, ', '.join(sorted(hs))))

repeated = {s: h for s, h in shells.items() if len(h) > 1}
seen = []
print()
print('word runs in more than one file: %d' % len(repeated))
for run in sorted(repeated, key=len, reverse=True):
    if any(run in earlier for earlier in seen):
        continue
    seen.append(run)
    print('   %s' % run[:96])
    print('      in: %s' % ', '.join(sorted(repeated[run])))
    if len(seen) >= 10:
        break

print()
print('A reference may repeat, a measurement may not. Clean up what your work added.')
