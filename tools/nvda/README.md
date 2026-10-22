# NVDA controller client

`speech.py` speaks and writes braille through NVDA's official controller client. That DLL is **not
included in this repository**, to keep third-party binaries out of the source tree.

## Getting it

Download `nvda_<version>_controllerClient.zip` from `download.nvaccess.org/releases/stable/` and
put the 64-bit `nvdaControllerClient.dll` next to `speech.py`; its licence is already there
(`CREDITS.md`). `check_speech_by_ear.bat` then checks by ear that it speaks.

## Functions used

`speakText`, `brailleMessage`, `cancelSpeech`, `testIfRunning`. `speakSsml` is not used: called
synchronously it blocks until the speech ends and then fails.

## One seam

Everything above this layer goes through `output` and `failure` (`ARCHITECTURE.md`, section 7); another
screen reader goes behind them (`CONTRIBUTING.md`).
