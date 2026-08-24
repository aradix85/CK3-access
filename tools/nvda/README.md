# NVDA controller client

`speech.py` speaks and writes braille through NVDA's official controller client. That DLL is **not
included in this repository**, to keep third-party binaries out of the source tree.

## Getting it

Download `nvda_<version>_controllerClient.zip` from `download.nvaccess.org/releases/stable/` and
put the 64-bit `nvdaControllerClient.dll` next to `speech.py`, together with its licence file.

The client is licensed LGPL 2.1. If you ship it in a release, ship its licence text with it.

## Functions used

`speakText`, `brailleMessage`, `cancelSpeech`, `testIfRunning`.

`speakSsml` exists but is not used: its fourth parameter is `asynchronous`, and passing false
blocks until the speech finishes and then returns error 1223.

## One seam

Everything above this layer calls a single function that takes text, braille text and a mode.
Swapping NVDA for an abstraction layer such as Prism or SRAL means replacing the inside of that
function and nothing else — see `CONTRIBUTING.md`.
