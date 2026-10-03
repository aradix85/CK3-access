"""What a script prints, readable whatever the game holds."""
import io
import sys


def utf8() -> None:
    """UTF-8 out, an unprintable character replaced rather than fatal, and a line at a time.

    The console's own code page turns a name with an accent into noise or an exception, and output
    that waits for the end of a long round cannot be read while it runs. One place, so every script
    makes the same choice.
    """
    assert isinstance(sys.stdout, io.TextIOWrapper), f'stdout is {sys.stdout!r}, not a text stream'
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
