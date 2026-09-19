"""A first draft of a screen file, from what the gui files alone can already decide.

Reading a window aloud is two questions. *What is there, and what is it about* - that is on disk,
in the gui files, for every window, including the ones nobody has ever opened. *Which of it
matters, in what order, and in how many words* - that is a judgement, and no measurement answers
it. This writes the first half out in the shape of a screen file, so the judgement is made by
correcting a draft instead of by starting at an empty file two hundred times.

What it proposes, and why each part is mechanical:
  - the reading order is the order of the gui file, which is the designer's own grouping;
  - a repeated container is a list, so it says its size first and its end afterwards;
  - the subject of a text is the data context it inherits, since a widget hardly names its own.
Beside each line it writes what the text will say, or the data function that will fill it, as a
comment - that is the part a human reads to decide.

What it deliberately leaves out: anything a general reading rule can do without being told.
A widget without text is silent on its own, a key the gui file declares can be spoken from the
gui file, and a count belongs to every list. A draft that repeats those would be noise to edit.

Nothing here talks to the game, and it needs no harvest: a window the sweep never opened gets a
draft like any other.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import guimap

TEXT_KEYS = ('text', 'raw_text')


def attribute(node, key):
    for own, value in node['attrs']:
        if own == key:
            return value
    return None


def texts(node, context=(), inside=None, out=None):
    """Every text a window holds, in file order, with its subject and the list it sits in.

    `inside` is the data model of the nearest repeated container above, which is what turns a
    row of a list into one item instead of into as many lines as there are rows.
    """
    if out is None:
        out = []
    if node['type'] == 'tooltipwidget':
        return out                      # a tooltip is for the explain key, not for the order
    own = attribute(node, 'datacontext')
    below = context + ((own,) if own else ())
    model = attribute(node, 'datamodel') or inside
    for key in TEXT_KEYS:
        value = attribute(node, key)
        if value:
            out.append({'text': value, 'context': below, 'list': model,
                        'name': attribute(node, 'name')})
            break
    for child in node['children']:
        texts(child, below, model, out)
    return out


def says(value, localization):
    """What this text will say: the sentence behind a key, or the function that fills it."""
    if '[' in value:
        return value
    if value in localization:
        return guimap.strip_style(localization[value]).strip()
    return value + ' (no sentence on disk)'


def draft(window, table, local, known, localization):
    """One window as a screen file to correct."""
    tree, _ = guimap.window(window, table, local, known)
    found = texts(tree)

    lines = ['# A draft for %s, written from the gui files. None of it is a judgement yet.' % window,
             '#',
             '# %d texts, %d of them rows of a list. The order is the order of the gui file; the'
             % (len(found), sum(1 for one in found if one['list'])),
             '# comment behind a line is what it will say. Cut what does not matter, move what',
             '# matters up, and say it in your own words where the file has none.',
             '',
             'screen = {',
             '\tname = "%s"' % window,
             '\twindow = "%s"' % window,
             '']

    loose = [one for one in found if not one['list']]
    if loose:
        lines.append('\torder = {')
        for one in loose:
            subject = one['context'][-1] if one['context'] else ''
            lines.append('\t\tread = "%s"%s' % (one['text'], comment(says(one['text'], localization),
                                                                    subject)))
        lines += ['\t}', '']

    for model in ordered_models(found):
        rows = [one for one in found if one['list'] == model]
        lines += ['\tlist = {',
                  '\t\tof = "%s"' % model,
                  '\t\tcount = before',
                  '\t\tclose = after',
                  '\t\titem = {']
        for one in rows:
            lines.append('\t\t\tread = "%s"%s' % (one['text'],
                                                  comment(says(one['text'], localization), '')))
        lines += ['\t\t}', '\t}', '']
    lines.append('}')
    return '\n'.join(lines) + '\n', found


def comment(sentence, subject):
    """The part a human reads. One line, so a long sentence is cut rather than wrapped."""
    text = (subject + ': ' if subject else '') + sentence
    text = ' '.join(text.split())
    return '\t# ' + (text[:90] + '...' if len(text) > 90 else text)


def ordered_models(found):
    """The data models in the order they first appear, because a set would shuffle them."""
    out = []
    for one in found:
        if one['list'] and one['list'] not in out:
            out.append(one['list'])
    return out


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ['TEMP'], 'ck3',
                                                                'proposals')
    os.makedirs(folder, exist_ok=True)
    rows = guimap.files()
    table, local = guimap.type_table(rows)
    known = guimap.windows(rows)
    localization = guimap.localization()

    total, listed, empty = 0, 0, []
    for window in sorted(known):
        text, found = draft(window, table, local, known, localization)
        with open(os.path.join(folder, window + '.screen'), 'w', encoding='utf-8') as handle:
            handle.write(text)
        total += len(found)
        listed += sum(1 for one in found if one['list'])
        if not found:
            empty.append(window)

    print('%d windows drafted into %s.' % (len(known), folder))
    print('%d texts in all, %d of them rows of a list.' % (total, listed))
    print('%d windows hold no text at all on disk: %s'
          % (len(empty), ', '.join(empty) if len(empty) < 12 else ', '.join(empty[:12]) + ' ...'))


if __name__ == '__main__':
    main()
