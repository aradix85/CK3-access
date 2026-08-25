# Credits

This project stands on other people's work and ideas. None of it is used without saying so.

## The approach

**rashad** (`github.com/rashadnaqeeb`) described the non-OCR approach for CK3 publicly in June 2026:
a hijack DLL that reads the widget classes through the MSVC RTTI tree the game ships, to find a
widget's exact position and drive it. He also named the obvious objection — that the addresses shift
with every patch, and that re-deriving them is scriptable. That is exactly what this project does.
The idea is his; the code here is not.

## Finding things in this game's memory

**tfigment** — the Crusader Kings III cheat table on FearLess Cheat Engine (thread 13576),
maintained through dozens of game versions since 2020. It is not accessibility work and it reads no
screens, but it is the first public map of where this game keeps things in memory: a pointer to the
played character that survives a reload, the selected character, the last selected holding, army and
dynasty house, and a hook on whatever the mouse is over. It also carries the technique this project
still uses to reach a global without a fixed address — search for an instruction pattern with
wildcards, then read the displacement out of the instruction you found. None of the table is copied;
what it gave was a head start on where to look and proof that these things stay findable across
patches.

**KeinNiemand** — LargePageInjectorMods (`github.com/KeinNiemand/LargePageInjectorMods`), C++20 and
open source. The injection skeleton for Paradox titles: get a DLL loaded through
`launcher-settings.json` instead of patching the executable. What that project injects is beside the
point here; the way in is what was taken. Their README's warning that antivirus software sometimes
flags an injector applies to this project too.

**noxsidereum** — skyretk (MIT), a worked example of a DLL that runs during startup and dumps RTTI,
with the reasoning written out in the code. **d3dev** — the `d3_tooltips` wiki, which documents the
pitfall this project has to live with as well: a tooltip pointer that still refers to the previous
thing the mouse was over.

## The design of what a screen says

**Agami** (`github.com/Agamidae`) wrote the CK3 OCR-Support mod, the accessibility mod this
community has actually been playing. Her choices about *what* each screen should read out, in what
order, and what to leave out are the reference used here — not because they are convenient, but
because they were made by someone who plays this game and knows what matters in a council window.

Her mod carries no licence file, so **none of her code is used or copied**. What is taken is design
judgement, and it is taken with attribution.

## Tools and libraries

- **NVDA** (`github.com/nvaccess/nvda`) — the screen reader, and its controller client DLL, which is
  redistributed here under LGPL 2.1. Its licence text ships with it.
- **Paradox Interactive** — Crusader Kings III and the Clausewitz/Jomini engine. No files belonging
  to Paradox are included in this repository or in any release.

## The community

The **Accessible Crusades** Discord, and `github.com/Molitvan/blind-accessible-games-list`, where
this kind of work gets found, tested and argued about. The line this project keeps to — read the
game, never rebuild it — came out of a discussion there, and it is the right line.

## Assistance

Built with Claude (Anthropic) as a working partner throughout: measurement, reverse engineering, and
the maintainer's working notes, which are kept separately and are not part of this repository.

