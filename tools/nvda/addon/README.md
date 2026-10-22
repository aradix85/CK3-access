# CK3 Access: automatic sleep mode

An NVDA add-on with one job: put NVDA in sleep mode while Crusader Kings III has focus. Tested on NVDA
2026.2.

**Why it is needed.** The reader speaks through the NVDA controller client. Without sleep mode NVDA
also reports the game window itself, so everything is said twice, and NVDA keeps the keys the reader
needs to own. Sleep mode silences NVDA's own reporting, not what the reader sends.

## Installing

Copy this folder into your NVDA add-ons directory under the name `ck3Access`, then restart NVDA:

    %APPDATA%\nvda\addons\ck3Access\

A portable NVDA keeps its add-ons in its own `userConfig\addons` folder instead.

## Checking that it works

With CK3 in the foreground NVDA should fall silent about the game window, while the reader is still
spoken and still reaches braille. NVDA+Shift+S switches sleep mode by hand, so pressing it brings
NVDA's own reporting back. If NVDA goes quiet altogether, open an issue and give your NVDA version.
