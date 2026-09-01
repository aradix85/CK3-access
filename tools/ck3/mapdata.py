"""The static map layer: where a county is, what it borders, and how far away things are.

Disk only. It never opens a save and never talks to the game, which is the whole point: this is
the half of the answer that is the same for every player and can be worked out before anything is
running. Everything it needs is read the way the engine merges it, mods included, so a tester with
a different set of mods gets his own map rather than this one.

Nothing here is cached. The province centres and the adjacency come out of `provinces.png` in a
few seconds, and a cached copy would be a file that quietly disagrees with the player's own map
after a patch or a new mod. Derive rather than write down.

The three constants below carry decisions and each was measured; the counting rules are in
`brief\\meetwerk.md`, where a province lies. Distance is deliberately approximate: for playing, the
difference that matters is between the next county, the far side of your realm and the far side of
the world.
"""
import collections
import math
import os
import re
import sys

import numpy
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import database
import guimap
import paths

Image.MAX_IMAGE_PIXELS = None

# 1.509 km per pixel, the median over seven pairs whose real distance is known. The spread is a
# third, because the map stretches with latitude; a fitted projection was tried and is not better.
KM_PER_PIXEL = 1.509

# 2.5 pixels a day, the median over 234 travel plans a save had in flight. The spread is about a
# factor two, from terrain, sea crossings and the fifteen days an embarkation costs.
PIXELS_PER_DAY = 2.5

# Within a fifth, a bearing counts as diagonal. From `brief\\schermen.md`, and it belongs in data
# rather than in this line as soon as there is a settings file.
DIAGONAL_MARGIN = 0.20

COMPASS = {(0, 1): 'north', (0, -1): 'south', (1, 0): 'east', (-1, 0): 'west',
           (1, 1): 'northeast', (-1, 1): 'northwest', (1, -1): 'southeast',
           (-1, -1): 'southwest'}


def _map_file(name):
    return os.path.join(paths.GAME, 'game', 'map_data', name)


def province_colours():
    """Colour -> province number, from `definition.csv`. The colour is the only link between the
    image and a number, so a province whose colour is missing here cannot exist on the map."""
    out = {}
    for line in open(_map_file('definition.csv'), encoding='utf-8', errors='replace'):
        parts = line.strip().split(';')
        if len(parts) >= 5 and parts[0].isdigit() and int(parts[0]) > 0:
            red, green, blue = (int(p) for p in parts[1:4])
            out[(red << 16) | (green << 8) | blue] = int(parts[0])
    return out


def province_image():
    """The map as province numbers, one per pixel.

    The check that can fail is that every pixel resolves: measured 1 September 2026, zero of the
    42467328 pixels carried a colour the definitions do not list. If that ever stops holding, the
    image and the definitions have come apart and nothing below this line means anything.
    """
    lookup = numpy.zeros(1 << 24, dtype=numpy.int32)
    for colour, number in province_colours().items():
        lookup[colour] = number
    image = numpy.asarray(Image.open(_map_file('provinces.png')), dtype=numpy.uint8)
    packed = ((image[:, :, 0].astype(numpy.int32) << 16)
              | (image[:, :, 1].astype(numpy.int32) << 8) | image[:, :, 2].astype(numpy.int32))
    numbers = lookup[packed]
    unknown = int((numbers == 0).sum())
    if unknown:
        raise AssertionError('%d pixels carry a colour definition.csv does not list; the image '
                             'and the definitions have come apart' % unknown)
    return numbers


def centres(numbers=None):
    """Province number -> (x, y), the mean of its pixels.

    The mean of a concave shape can fall outside it, and for a bearing and a rough distance that
    does not matter. Do not use this to decide whether a point is inside a province.
    """
    numbers = province_image() if numbers is None else numbers
    height, width = numbers.shape
    highest = int(numbers.max())
    count = numpy.bincount(numbers.ravel(), minlength=highest + 1)
    columns = numpy.tile(numpy.arange(width, dtype=numpy.float64), height)
    rows = numpy.repeat(numpy.arange(height, dtype=numpy.float64), width)
    sum_x = numpy.bincount(numbers.ravel(), weights=columns, minlength=highest + 1)
    sum_y = numpy.bincount(numbers.ravel(), weights=rows, minlength=highest + 1)
    return {number: (sum_x[number] / count[number], sum_y[number] / count[number])
            for number in range(1, highest + 1) if count[number]}


SPREAD = 20000          # bigger than the highest province number, so a pair packs into one int


def touching(numbers=None):
    """Every pair of provinces whose pixels lie next to each other.

    Four-neighbour, because a diagonal touch is a corner and not a border. Packed into one integer
    per pair so that `unique` does the counting; a Python loop over the differing pixels is minutes
    where this is seconds.
    """
    numbers = province_image() if numbers is None else numbers
    out = set()
    for left, right in ((numbers[:, :-1], numbers[:, 1:]), (numbers[:-1, :], numbers[1:, :])):
        differ = left != right
        low = numpy.minimum(left[differ], right[differ]).astype(numpy.int64)
        high = numpy.maximum(left[differ], right[differ]).astype(numpy.int64)
        for packed in numpy.unique(low * SPREAD + high).tolist():
            out.add((packed // SPREAD, packed % SPREAD))
    return out


def special_links():
    """The connections the image cannot show: straits and ferries from `adjacencies.csv`."""
    out = []
    for line in open(_map_file('adjacencies.csv'), encoding='utf-8', errors='replace'):
        parts = line.strip().split(';')
        if len(parts) > 3 and parts[0].isdigit() and parts[1].isdigit():
            out.append((int(parts[0]), int(parts[1]), parts[2]))
    return out


def province_kinds():
    """Province number -> what it is, from `default.map`: sea, lake, river, impassable.

    Only the kinds `default.map` names are in here. A province it does not name is ordinary land,
    and that is an absence rather than a finding.
    """
    out = {}
    text = open(_map_file('default.map'), encoding='utf-8', errors='replace').read()
    for kind in ('sea_zones', 'river_provinces', 'lakes', 'impassable_mountains',
                 'impassable_seas', 'wasteland'):
        for found in re.finditer(r'%s\s*=\s*(RANGE\s*)?\{([^}]*)\}' % kind, text):
            numbers = [int(n) for n in found.group(2).split() if n.isdigit()]
            if found.group(1) and len(numbers) == 2:
                numbers = list(range(numbers[0], numbers[1] + 1))
            for number in numbers:
                out[number] = kind
    return out


TIERS = {'e': 'empire', 'k': 'kingdom', 'd': 'duchy', 'c': 'county', 'b': 'barony'}


def _value(block, key):
    for child in block.get('body') or []:
        if child['key'] == key:
            return child.get('value')
    return None


def counties():
    """County key -> its baronies' provinces, the de jure titles above it, and its name.

    The de jure chain is not a field: it is where the county sits in the nesting of
    `landed_titles`, so it comes out of the walk for free. Measured 1 September 2026: 3476 counties
    carry provinces, 11297 baronies between them, and none of them lacks a chain.

    **A later file that names a county without baronies does not empty it.** Mods do that to add a
    single line, and overwriting on every mention cost 1228 counties their provinces before this
    rule was here.
    """
    out = {}

    def walk(blocks, chain):
        for block in blocks:
            key = block.get('key') or ''
            tier = TIERS.get(key[:1]) if key[1:2] == '_' else None
            below = chain + [key] if tier else chain
            if tier == 'county':
                provinces = []
                for child in block.get('body') or []:
                    if (child.get('key') or '').startswith('b_'):
                        number = _value(child, 'province')
                        if number and number.isdigit():
                            provinces.append(int(number))
                row = out.setdefault(key, {})
                if provinces or 'provinces' not in row:
                    row['provinces'] = provinces
                row['chain'] = chain
            if block.get('body'):
                walk(block['body'], below)

    for _, _, full in database.files('landed_titles'):
        walk(guimap.parse(open(full, encoding='utf-8-sig', errors='replace').read()), [])
    names = guimap.localization()
    for key, row in out.items():
        row['name'] = names.get(key, key)
        row['chain_names'] = [names.get(title, title) for title in row.get('chain', [])]
    return out


class Map:
    """Everything the static layer knows, built once and asked many times.

    Building walks the province image twice and the title files once, a few seconds in all. Hold on
    to one of these rather than calling the functions above per question.
    """

    def __init__(self):
        numbers = province_image()
        self.centres = centres(numbers)
        self.kinds = province_kinds()
        self.counties = counties()
        self.county_of = {}
        for key, row in self.counties.items():
            for province in row.get('provinces') or []:
                self.county_of[province] = key
        self.neighbours = collections.defaultdict(set)
        self.water = collections.defaultdict(collections.Counter)
        pairs = touching(numbers) | {(a, b) for a, b, _ in special_links()}
        for one, two in pairs:
            for own, other, number in ((self.county_of.get(one), self.county_of.get(two), two),
                                       (self.county_of.get(two), self.county_of.get(one), one)):
                if own is None:
                    continue
                if other is not None and other != own:
                    self.neighbours[own].add(other)
                elif other is None:
                    self.water[own][self.kinds.get(number, 'unnamed')] += 1

    def name(self, county):
        return self.counties.get(county, {}).get('name') or county

    def where(self, county):
        """The point of a county: the mean of its capital barony's province."""
        provinces = self.counties.get(county, {}).get('provinces') or []
        if not provinces or provinces[0] not in self.centres:
            return None
        x, y = self.centres[provinces[0]]
        return float(x), float(y)          # plain floats: numpy booleans do not subtract

    def apart(self, one, two):
        """(pixels, kilometres, days) between two counties, all three approximate."""
        here, there = self.where(one), self.where(two)
        if here is None or there is None:
            return None
        pixels = math.hypot(here[0] - there[0], here[1] - there[1])
        return pixels, pixels * KM_PER_PIXEL, pixels / PIXELS_PER_DAY

    def bearing(self, one, two):
        """Eight points. North is up, so y runs the other way round."""
        here, there = self.where(one), self.where(two)
        if here is None or there is None:
            return None
        east, north = there[0] - here[0], here[1] - there[1]
        if abs(east) < DIAGONAL_MARGIN * abs(north):
            east = 0
        elif abs(north) < DIAGONAL_MARGIN * abs(east):
            north = 0
        sign = ((east > 0) - (east < 0), (north > 0) - (north < 0))
        return COMPASS.get(sign)

    def rings(self, county, depth=3):
        """Neighbours, neighbours of neighbours, and so on - each ring without the ones before."""
        seen, edge, out = {county}, {county}, []
        for _ in range(depth):
            further = set()
            for member in edge:
                further |= self.neighbours.get(member, set())
            further -= seen
            out.append(further)
            seen |= further
            edge = further
        return out

    def describe(self, county):
        """One county in sentences, in the order `brief\\schermen.md` asks for: what it is, then
        where it sits, then what it touches. Not the reading order of the product - that is layer
        three - but enough for the user to judge the numbers against what she knows."""
        row = self.counties.get(county)
        if not row:
            return ['%s is not a county in this installation.' % county]
        lines = ['%s, %d baronies.' % (self.name(county), len(row.get('provinces') or []))]
        if row.get('chain_names'):
            lines.append('De jure in %s.' % ', then '.join(reversed(row['chain_names'])))
        rings = self.rings(county)
        if rings[0]:
            lines.append('%d neighbours: %s.'
                         % (len(rings[0]), ', '.join(sorted(self.name(n) for n in rings[0]))))
            lines.append('%d counties in the second ring, %d in the third.'
                         % (len(rings[1]), len(rings[2])))
        else:
            lines.append('No land neighbours.')
        if self.water.get(county):
            lines.append('Borders %s.'
                         % ', '.join('%d %s' % (count, kind.replace('_', ' '))
                                     for kind, count in self.water[county].most_common()))
        return lines

    def between(self, one, two):
        """The three numbers a player asked for a place wants: how far, how long, which way."""
        far = self.apart(one, two)
        if far is None:
            return '%s or %s has no place on the map.' % (one, two)
        pixels, km, days = far
        return ('%s lies %s of %s, roughly %d kilometres, about %d days of travel.'
                % (self.name(two), self.bearing(one, two), self.name(one),
                   round(km, -1), round(days)))


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    world = Map()
    print('%d provinces on the map, %d counties with land, %d with neighbours'
          % (len(world.centres), len(world.county_of and set(world.county_of.values())),
             len(world.neighbours)))
    for county in ('c_praha', 'c_roma'):
        print()
        for line in world.describe(county):
            print('   %s' % line)
    print()
    for one, two in (('c_praha', 'c_roma'), ('c_praha', 'c_middlesex'), ('c_roma', 'c_toledo')):
        print('   %s' % world.between(one, two))


if __name__ == '__main__':
    main()
