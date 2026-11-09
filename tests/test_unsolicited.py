"""The script reader of `tools.ck3.unsolicited`: the first level of an entry, as the game writes it."""
from tools.ck3 import unsolicited

SCRIPT = '''
namespace = birth
# a comment with = and { in it
birth.0001 = {
\ttype = letter_event
\twindow = "fullscreen_event"
\thidden = no
\ttrigger = { age >= 16 type = alert }
\tai_targets = { ai_recipients = vassals }
\tflags = { one two }
}
plain = { display = toast }
'''


def test_first_level_only() -> None:
    found = {key: (pairs, blocks) for key, pairs, blocks in unsolicited.entries(SCRIPT)}
    assert set(found) == {'birth.0001', 'plain'}
    pairs, blocks = found['birth.0001']
    assert pairs == {'type': 'letter_event', 'window': 'fullscreen_event', 'hidden': 'no'}
    assert blocks == {'trigger', 'ai_targets', 'flags'}
    assert found['plain'] == ({'display': 'toast'}, set())
