# CK3 Access: automatic sleep mode

An NVDA add-on with one job: put NVDA in sleep mode while Crusader Kings III has focus.

**Why it is needed.** The reader speaks through the NVDA controller client. Without sleep mode NVDA
also reports the game window itself, so everything is said twice, and NVDA keeps the keys the reader
needs to own.

**Why sleep mode does not silence the reader.** NVDA's speak handler only returns early for
`SLEEP_FULL`. Ordinary sleep mode does not set it, so speech and braille sent through the controller
client keep arriving. This is the same arrangement already running for Cataclysm: Bright Nights.

## Installing

Copy this folder into your NVDA add-ons directory under the name `ck3Access`, then restart NVDA:

    %APPDATA%\nvda\addons\ck3Access\

Restarting NVDA is what loads it; nothing happens until then.

## Checking that it works

With CK3 in the foreground NVDA should fall silent about the game window, while anything sent
through `tools/nvda/speech.py` is still spoken and still reaches braille. If NVDA goes quiet
altogether, that is the wrong kind of silence: check that `sleepMode` is set rather than
`SLEEP_FULL`.
