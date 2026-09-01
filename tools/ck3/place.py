"""From a character in the running game to a place on the map.

Three sources meet here and none of them can answer alone. The character record in memory says
which title a character calls its seat, as a number. The landed-title database in the running
game turns that number into a key. The map files on disk say which county that key stands on.
The chain is only as good as its weakest link, and each of the three proves itself where it
lives: `model.check` against the save, `numbering.keys` against the title files, and
`mapdata.county_for` against every `realm_capital` of three saves.

**Both halves are expensive to build and neither changes while the game runs**, so a caller holds
one `Seats` and asks it many times rather than calling a function per question. Building it reads
18439 keys out of the game and walks the province image once: a few seconds, once.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import mapdata
import model
import numbering


class Seats:
    """Where the characters of this game sit, from the running game and the files together."""

    def __init__(self, pid, world=None):
        self.pid = pid
        self.titles = numbering.keys(pid, 'title')
        self.world = world if world is not None else mapdata.Map()

    def title_of(self, number):
        """The key of a title number, as the running game numbers them right now.

        A number is only meaningful inside the state that is running: titles are created and
        destroyed while playing, so never keep one of these across a load.
        """
        return self.titles.get(number)

    def seat_of(self, handle, records=None):
        """The county a character sits on, or None when it holds no seat.

        None is an answer and not a gap. Three quarters of the characters in a state are dead or
        landless and carry no `realm_capital`, and a titular title names no capital, so it stands
        on no county.
        """
        who = model.character(self.pid, handle, records)
        return self.county_of(who.get('realm_capital'))

    def county_of(self, number):
        """The county a title number stands on: the game names the title, the files place it."""
        if number is None:
            return None
        key = self.title_of(number)
        return self.world.county_for(key) if key else None

    def where(self, handle, records=None):
        """(county key, the name a player reads, the point on the map) of a character's seat."""
        county = self.seat_of(handle, records)
        if county is None:
            return None
        return county, self.world.name(county), self.world.where(county)


def main(pid):
    """Walk the chain and let it fail: the player, the coverage, and what memory holds extra."""
    seats = Seats(pid)
    handle, name = model.player(pid)
    number = model.character(pid, handle).get('realm_capital')
    print('player            : %s, handle %d' % (name, handle))
    print('realm_capital     : %s -> %s' % (number, seats.title_of(number)))
    print('sits on           : %s' % (seats.where(handle),))

    numbers = sorted(seats.titles)
    landed = sum(1 for n in numbers if seats.county_of(n))
    print('title numbers     : %d, standing on a county: %d' % (len(numbers), landed))

    # The test that can fail: every title the files carry has to be reachable from some number.
    # A numbering off by one slot loses the lot, which is what the shifted read showed at 0 of 300.
    on_disk = numbering.on_disk('title')
    reached = {seats.title_of(n) for n in numbers} & on_disk
    print('titles on disk    : %d, reached from a number: %d' % (len(on_disk), len(reached)))
    missed = sorted(on_disk - reached)
    print('not reached       : %d  %s' % (len(missed), missed[:8]))
    extra = sorted({seats.title_of(n) for n in numbers} - on_disk)
    print('held beyond disk  : %d  %s' % (len(extra), extra[:4]))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main(int(sys.argv[1]))
