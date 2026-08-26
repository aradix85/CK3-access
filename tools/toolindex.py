"""Writes reports\\toolindex.md: every call a script needs, read from the source.

Why this exists: four calls got the signature wrong on 30 July 2026 - one returning a pair treated
as a single thing, one wanting a dict handed a list, one returning a triple used as a single image,
and a filter that is case sensitive. Each cost a run of tens of seconds plus a game action. This
index is meant to be read before writing, and it keeps itself current: it reads the signature and
the shape of the return value from the source, so it cannot go stale unless the source changes.

Usage: python tools\\toolindex.py
"""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, 'tools')
OUT = os.path.join(ROOT, 'reports', 'toolindex.md')
SKIP = ('test_', 'overzicht.py',
        # Reads the maintainer's working notes only, and .gitignore keeps it out of the repository.
        # Listing it here would describe a tool a reader of this index does not have.
        'docsearch.py')


def first_line(text):
    if not text:
        return ''
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()
    return ''


def signature(node):
    parts = []
    args = node.args
    required = len(args.args) - len(args.defaults)
    for i, name in enumerate([a.arg for a in args.args]):
        if i < required:
            parts.append(name)
        else:
            parts.append('%s=%s' % (name, ast.unparse(args.defaults[i - required])))
    if args.vararg:
        parts.append('*' + args.vararg.arg)
    if args.kwarg:
        parts.append('**' + args.kwarg.arg)
    return '%s(%s)' % (node.name, ', '.join(parts))


def return_shape(node):
    """The shape of what comes out, because that is what the mistakes were about."""
    shapes = []
    for k in ast.walk(node):
        if isinstance(k, ast.FunctionDef) and k is not node:
            continue
        if isinstance(k, ast.Return) and k.value is not None:
            if isinstance(k.value, ast.Tuple):
                shapes.append('%d-tuple' % len(k.value.elts))
            elif isinstance(k.value, (ast.Dict, ast.DictComp)):
                shapes.append('dict')
            elif isinstance(k.value, (ast.List, ast.ListComp)):
                shapes.append('list')
            elif isinstance(k.value, (ast.Set, ast.SetComp)):
                shapes.append('set')
            elif isinstance(k.value, ast.Constant):
                shapes.append(type(k.value.value).__name__)
            else:
                shapes.append('value')
    if not shapes:
        return 'nothing'
    unique = []
    for v in shapes:
        if v not in unique:
            unique.append(v)
    return ' of '.join(unique)


def files():
    for map_, _, names in os.walk(SOURCE):
        for name in sorted(names):
            if not name.endswith('.py'):
                continue
            if any(name.startswith(p) or name == p for p in SKIP):
                continue
            yield os.path.join(map_, name)


lines = ['# Tool index - calls and the shape of what they return', '',
          'Generated from the source by `tools\\toolindex.py`. **Read this before writing a',
          'script**, and generate it again once you have changed the tools.',
          'The *returns* column is here because that is where the mistakes were: a function that',
          'returns a pair, passed on as one thing, costs a run.', '']

for path in files():
    tree = ast.parse(open(path, 'r', encoding='utf-8').read())
    public = [k for k in tree.body
               if isinstance(k, ast.FunctionDef) and not k.name.startswith('_')]
    if not public:
        continue
    lines.append('## %s' % os.path.relpath(path, SOURCE).replace('/', '\\'))
    target = first_line(ast.get_docstring(tree))
    if target:
        lines.append('*%s*' % target)
    lines.append('')
    lines.append('| call | returns | does |')
    lines.append('|---|---|---|')
    for k in public:
        lines.append('| `%s` | %s | %s |'
                      % (signature(k), return_shape(k),
                         first_line(ast.get_docstring(k)) or '-'))
    lines.append('')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('%s written, %d lines' % (OUT, len(lines) + 1))
