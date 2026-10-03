# Credits

This project stands on other people's work and ideas.

- **rashad** (`github.com/rashadnaqeeb`) described the non-OCR approach for CK3 publicly in June 2026: a
  DLL that reads the widget classes through the RTTI the game ships, with addresses re-derived after
  each patch. The idea is his; the code here is not.
- **tfigment** — the Crusader Kings III cheat table on FearLess Cheat Engine (thread 13576): the first
  public map of where this game keeps things in memory, and the technique of reaching a global through
  a wildcard instruction search. Nothing from the table is copied.
- **KeinNiemand** — LargePageInjectorMods (`github.com/KeinNiemand/LargePageInjectorMods`): loading a
  DLL into a Paradox game through `launcher-settings.json`.
- **The CK3 Wiki**, the Interface page for modders (`ck3.paradoxwikis.com/Interface`): draw order,
  layers, and what `alwaystransparent` and `allow_outside` do to a click.
- **noxsidereum** (skyretk) and **d3dev** (`d3_tooltips`) — worked examples of reading RTTI and
  tooltip text from memory.
- **Agami** (`github.com/Agamidae`) — the CK3 OCR-Support mod. Her choices about what each screen reads
  out, in what order, are the design reference here. Her mod carries no licence, so none of her code is
  used.
- **NVDA** (`github.com/nvaccess/nvda`) and its controller client, LGPL 2.1; loaded, not
  redistributed. The licence is in `tools/nvda/license_nvda_controllerclient.txt`.
- **Paradox Interactive** — Crusader Kings III and its engine. No Paradox files are included.
- **The Accessible Crusades Discord** and `github.com/Molitvan/blind-accessible-games-list`, where this
  work is found, tested and argued about — and where the line "read the game, never rebuild it" comes
  from.
- Built with **Claude** (Anthropic) as a working partner throughout.
