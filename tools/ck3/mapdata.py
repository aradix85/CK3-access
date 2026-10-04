"""The static map layer: where a county is, what it borders, and how far away things are.

Disk only. It never opens a save and never talks to the game, which is the whole point: this is
the half of the answer that is the same for every player and can be worked out before anything is
running. Everything it needs is read the way the engine merges it, mods included, so a tester with
a different set of mods gets his own map rather than this one.

Nothing here is cached. The province centres and the adjacency come out of `provinces.png` in a
few seconds, and a cached copy would be a file that quietly disagrees with the player's own map
after a patch or a new mod. Derive rather than write down.

The three constants below carry decisions and each was measured.
Distance is deliberately approximate: for playing, the
difference that matters is between the next county, the far side of your realm and the far side of
the world.
"""
import collections
import math
import os
import pathlib
import re
from typing import Required, TypedDict

import numpy
from numpy.typing import NDArray
from PIL import Image

from tools import paths, terminal
from tools.ck3 import database, guimap

Image.MAX_IMAGE_PIXELS = None

# 1.509 km per pixel, the median over seven pairs whose real distance is known. The spread is a
# third, because the map stretches with latitude; a fitted projection was tried and is not better.
KM_PER_PIXEL = 1.509

# 2.5 pixels a day, the median over 234 travel plans a save had in flight. The spread is about a
# factor two, from terrain, sea crossings and the fifteen days an embarkation costs.
PIXELS_PER_DAY = 2.5

# Within a fifth, a bearing counts as diagonal. It belongs in data
# rather than in this line as soon as there is a settings file.
DIAGONAL_MARGIN = 0.20

COMPASS = {(0, 1): 'north', (0, -1): 'south', (1, 0): 'east', (-1, 0): 'west',
           (1, 1): 'northeast', (-1, 1): 'northwest', (1, -1): 'southeast',
           (-1, -1): 'southwest'}


def _map_file(name: str) -> str:
    return os.path.join(paths.require('GAME'), 'game', 'map_data', name)


def province_colours() -> dict[int, int]:
    """Colour -> province number, from `definition.csv`. The colour is the only link between the
    image and a number, so a province whose colour is missing here cannot exist on the map."""
    out: dict[int, int] = {}
    with open(_map_file('definition.csv'), encoding='utf-8', errors='replace') as file:
        for line in file:
            parts = line.strip().split(';')
            if len(parts) >= 5 and parts[0].isdigit() and int(parts[0]) > 0:
                red, green, blue = (int(p) for p in parts[1:4])
                out[(red << 16) | (green << 8) | blue] = int(parts[0])
    return out


def province_image() -> NDArray[numpy.int32]:
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
    numbers: NDArray[numpy.int32] = lookup[packed]
    unknown = int((numbers == 0).sum())
    if unknown:
        raise AssertionError(f'{int(unknown)} pixels carry a colour definition.csv does not list; the image '
                             'and the definitions have come apart')
    return numbers


def centres(numbers: NDArray[numpy.int32] | None = None) -> dict[int, tuple[float, float]]:
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


def touching(numbers: NDArray[numpy.int32] | None = None) -> set[tuple[int, int]]:
    """Every pair of provinces whose pixels lie next to each other.

    Four-neighbour, because a diagonal touch is a corner and not a border. Packed into one integer
    per pair so that `unique` does the counting; a Python loop over the differing pixels is minutes
    where this is seconds.
    """
    numbers = province_image() if numbers is None else numbers
    out: set[tuple[int, int]] = set()
    for left, right in ((numbers[:, :-1], numbers[:, 1:]), (numbers[:-1, :], numbers[1:, :])):
        differ = left != right
        low = numpy.minimum(left[differ], right[differ]).astype(numpy.int64)
        high = numpy.maximum(left[differ], right[differ]).astype(numpy.int64)
        for packed in numpy.unique(low * SPREAD + high).tolist():
            out.add((packed // SPREAD, packed % SPREAD))
    return out


def special_links() -> list[tuple[int, int, str]]:
    """The connections the image cannot show: straits and ferries from `adjacencies.csv`."""
    out: list[tuple[int, int, str]] = []
    with open(_map_file('adjacencies.csv'), encoding='utf-8', errors='replace') as file:
        for line in file:
            parts = line.strip().split(';')
            if len(parts) > 3 and parts[0].isdigit() and parts[1].isdigit():
                out.append((int(parts[0]), int(parts[1]), parts[2]))
    return out


def province_kinds() -> dict[int, str]:
    """Province number -> what it is, from `default.map`: sea, lake, river, impassable.

    Only the kinds `default.map` names are in here. A province it does not name is ordinary land,
    and that is an absence rather than a finding.
    """
    out: dict[int, str] = {}
    text = pathlib.Path(_map_file('default.map')).read_text(encoding='utf-8', errors='replace')
    for kind in ('sea_zones', 'river_provinces', 'lakes', 'impassable_mountains',
                 'impassable_seas', 'wasteland'):
        for found in re.finditer(rf'{kind}\s*=\s*(RANGE\s*)?\{{([^}}]*)\}}', text):
            numbers = [int(n) for n in found.group(2).split() if n.isdigit()]
            if found.group(1) and len(numbers) == 2:
                numbers = list(range(numbers[0], numbers[1] + 1))
            for number in numbers:
                out[number] = kind
    return out


TIERS = {'e': 'empire', 'k': 'kingdom', 'd': 'duchy', 'c': 'county', 'b': 'barony'}


class Title(TypedDict, total=False):
    """One landed title. `tier`, `chain`, `name` and `chain_names` are on every title `titles`
    returns; `capital` only where the files name one, `province` only on a barony that has one,
    and `provinces` only on a county."""
    tier: Required[str]
    chain: list[str]
    capital: str
    province: int
    provinces: list[int]
    name: str
    chain_names: list[str]


def _value(block: guimap.Entry, key: str) -> str | None:
    for child in block.get('body') or []:
        if child['key'] == key:
            return child.get('value')
    return None


def titles() -> dict[str, Title]:
    """Title key -> what it is, what land sits under it, which title it calls its capital, the de
    jure titles above it, and its name.

    The de jure chain is not a field: it is where the title sits in the nesting of
    `landed_titles`, so it comes out of the walk for free. Measured 1 September 2026: 17620 titles,
    of which 11297 baronies carry a province, 3476 counties carry baronies and none of them lacks a
    chain. 2804 titles name a capital and every one of those capitals is a county, so the way from
    a title to a place is one hop rather than a walk.

    **A later file that names a county without baronies does not empty it.** Mods do that to add a
    single line, and overwriting on every mention cost 1228 counties their provinces before this
    rule was here.
    """
    out: dict[str, Title] = {}

    def walk(blocks: list[guimap.Entry], chain: list[str]) -> None:
        for block in blocks:
            key = block.get('key') or ''
            body = block['body'] or []
            tier = TIERS.get(key[:1]) if key[1:2] == '_' else None
            below = chain + [key] if tier else chain
            if tier:
                row = out.setdefault(key, {'tier': tier})
                row['chain'] = chain
                capital = _value(block, 'capital')
                if capital:
                    row['capital'] = capital
                if tier == 'barony':
                    number = _value(block, 'province')
                    if number and number.isdigit():
                        row['province'] = int(number)
                if tier == 'county':
                    provinces = []
                    for child in body:
                        if (child.get('key') or '').startswith('b_'):
                            number = _value(child, 'province')
                            if number and number.isdigit():
                                provinces.append(int(number))
                    if provinces or 'provinces' not in row:
                        row['provinces'] = provinces
            if body:
                walk(body, below)

    for _, _, full in database.files('landed_titles'):
        walk(guimap.parse(pathlib.Path(full).read_text(encoding='utf-8-sig', errors='replace')), [])
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

    def __init__(self) -> None:
        numbers = province_image()
        self.centres = centres(numbers)
        self.kinds = province_kinds()
        self.titles = titles()
        self.counties = {key: row for key, row in self.titles.items()
                         if row['tier'] == 'county'}
        self.county_of: dict[int, str] = {}
        for key, row in self.counties.items():
            for province in row.get('provinces') or []:
                self.county_of[province] = key
        self.neighbours: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
        self.water: collections.defaultdict[str, collections.Counter[str]] = (
            collections.defaultdict(collections.Counter))
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

    def name(self, county: str) -> str:
        row = self.counties.get(county)
        return (row.get('name') if row else None) or county

    def county_for(self, title: str) -> str | None:
        """The county a title stands on, which is what turns a title held in the game into a place.

        A barony sits in one, a county with land is one, and everything above names a capital on
        disk - and every capital in the files is a county, so this is one hop and not a walk.
        Measured 1 September 2026: 17577 of the 17620 titles land on a county. The 43 that do not
        are titular duchies, kingdoms and empires that name no capital, k_ottoman and the beyliks
        among them; a title with no land under it has no place, and that is an answer rather than
        a gap.
        """
        row = self.titles.get(title)
        if row is None:
            return None
        if 'province' in row:
            return self.county_of.get(row['province'])
        if row.get('provinces'):
            return title
        return row.get('capital')

    def where(self, county: str) -> tuple[float, float] | None:
        """The point of a county: the mean of its capital barony's province."""
        row = self.counties.get(county)
        provinces = row.get('provinces') if row else None
        if not provinces or provinces[0] not in self.centres:
            return None
        x, y = self.centres[provinces[0]]
        return float(x), float(y)          # plain floats: numpy booleans do not subtract

    def apart(self, one: str, two: str) -> tuple[float, float, float] | None:
        """(pixels, kilometres, days) between two counties, all three approximate."""
        here, there = self.where(one), self.where(two)
        if here is None or there is None:
            return None
        pixels = math.hypot(here[0] - there[0], here[1] - there[1])
        return pixels, pixels * KM_PER_PIXEL, pixels / PIXELS_PER_DAY

    def bearing(self, one: str, two: str) -> str | None:
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

    def rings(self, county: str, depth: int = 3) -> list[set[str]]:
        """Neighbours, neighbours of neighbours, and so on - each ring without the ones before."""
        seen, edge = {county}, {county}
        out: list[set[str]] = []
        for _ in range(depth):
            further: set[str] = set()
            for member in edge:
                further |= self.neighbours.get(member, set())
            further -= seen
            out.append(further)
            seen |= further
            edge = further
        return out

    def describe(self, county: str) -> list[str]:
        """One county in sentences,: what it is, then
        where it sits, then what it touches. Not the reading order of the product - that is layer
        three - but enough for the user to judge the numbers against what she knows."""
        row = self.counties.get(county)
        if not row:
            return [f'{county} is not a county in this installation.']
        lines = [f"{self.name(county)}, {len(row.get('provinces') or [])} baronies."]
        if row.get('chain_names'):
            lines.append('De jure in {}.'.format(', then '.join(reversed(row['chain_names']))))
        rings = self.rings(county)
        if rings[0]:
            lines.append(f"{len(rings[0])} neighbours: {', '.join(sorted(self.name(n) for n in rings[0]))}.")
            lines.append(f'{len(rings[1])} counties in the second ring, {len(rings[2])} in the third.')
        else:
            lines.append('No land neighbours.')
        if self.water.get(county):
            lines.append('Borders {}.'.format(', '.join(f"{int(count)} {kind.replace('_', ' ')}"
                                     for kind, count in self.water[county].most_common())))
        return lines

    def between(self, one: str, two: str) -> str:
        """The three numbers a player asked for a place wants: how far, how long, which way."""
        far = self.apart(one, two)
        if far is None:
            return f'{one} or {two} has no place on the map.'
        _pixels, km, days = far
        return (f'{self.name(two)} lies {self.bearing(one, two)} of {self.name(one)}, roughly {int(round(km, -1))} kilometres, about {round(days)} days of travel.')


def main() -> None:
    terminal.utf8()
    world = Map()
    print(f'{len(world.centres)} provinces on the map, {len(world.county_of and set(world.county_of.values()))} counties with land, {len(world.neighbours)} with neighbours, {len(world.titles)} titles')
    placed = sum(1 for title in world.titles if world.county_for(title))
    print(f'{int(placed)} of {len(world.titles)} titles land on a county')
    for title in ('b_praha', 'd_bohemia', 'k_bohemia', 'e_west_slavia', 'k_ottoman'):
        print(f'   {title} sits on {world.county_for(title)}')
    for county in ('c_praha', 'c_roma'):
        print()
        for line in world.describe(county):
            print(f'   {line}')
    print()
    for one, two in (('c_praha', 'c_roma'), ('c_praha', 'c_middlesex'), ('c_roma', 'c_toledo')):
        print(f'   {world.between(one, two)}')


if __name__ == '__main__':
    main()
