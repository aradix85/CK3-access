"""From a character in the running game to a place on the map.

Three sources meet here and none of them can answer alone. The character record in memory says
which title a character calls its seat, as a number. The landed-title database in the running
game turns that number into a key. The map files on disk say which county that key stands on.
The chain is only as good as its weakest link, and each of the three proves itself where it
lives: `model.check` against the save, `numbering.keys` against the title files, and
`mapdata.Map.county_for` against every `realm_capital` of three saves.

**Both halves are expensive to build and neither changes while the game runs**, so a caller holds
one `Seats` and asks it many times rather than calling a function per question. Building it reads
18439 keys out of the game and walks the province image once: a few seconds, once.
"""
import sys

from tools import terminal
from tools.ck3 import mapdata, model, numbering


class Seats:
    """Where the characters of this game sit, from the running game and the files together."""

    def __init__(self, pid: int, world: mapdata.Map | None = None) -> None:
        self.pid = pid
        self.titles = numbering.keys(pid, 'title')
        self.world = world if world is not None else mapdata.Map()

    def title_of(self, number: int) -> str | None:
        """The key of a title number, as the running game numbers them right now.

        A number is only meaningful inside the state that is running: titles are created and
        destroyed while playing, so never keep one of these across a load.
        """
        return self.titles.get(number)

    def seat_of(self, handle: int, records: dict[int, bytes] | None = None) -> str | None:
        """The county a character sits on, or None when it holds no seat.

        None is an answer and not a gap. Three quarters of the characters in a state are dead or
        landless and carry no `realm_capital`, and a titular title names no capital, so it stands
        on no county.
        """
        capital = model.character(self.pid, handle, records).get('realm_capital')
        return None if capital is None else self.county_of(int(capital))

    def county_of(self, number: int) -> str | None:
        """The county a title number stands on: the game names the title, the files place it."""
        key = self.title_of(number)
        return self.world.county_for(key) if key else None

    def where(self, handle: int, records: dict[int, bytes] | None = None
              ) -> tuple[str, str, tuple[float, float] | None] | None:
        """(county key, the name a player reads, the point on the map) of a character's seat."""
        county = self.seat_of(handle, records)
        if county is None:
            return None
        return county, self.world.name(county), self.world.where(county)


def main(pid: int) -> None:
    """Walk the chain and let it fail: the player, the coverage, and what memory holds extra."""
    seats = Seats(pid)
    handle, name = model.player(pid)
    capital = model.character(pid, handle).get('realm_capital')
    number = None if capital is None else int(capital)
    print(f'player            : {name}, handle {int(handle)}')
    print(f'realm_capital     : {number} -> {None if number is None else seats.title_of(number)}')
    print(f'sits on           : {seats.where(handle)}')

    numbers = sorted(seats.titles)
    landed = sum(1 for n in numbers if seats.county_of(n))
    print(f'title numbers     : {len(numbers)}, standing on a county: {int(landed)}')

    # The test that can fail: every title the files carry has to be reachable from some number.
    # A numbering off by one slot loses the lot, which is what the shifted read showed at 0 of 300.
    on_disk = numbering.on_disk('title')
    held = set(seats.titles.values())
    reached = held & on_disk
    print(f'titles on disk    : {len(on_disk)}, reached from a number: {len(reached)}')
    missed = sorted(on_disk - reached)
    print(f'not reached       : {len(missed)}  {missed[:8]}')
    extra = sorted(held - on_disk)
    print(f'held beyond disk  : {len(extra)}  {extra[:4]}')


if __name__ == '__main__':
    terminal.utf8()
    main(int(sys.argv[1]))
