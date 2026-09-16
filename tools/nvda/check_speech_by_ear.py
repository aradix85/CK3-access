"""Speech layer checked by ear. It announces itself; you need not read along.
Start it with check_speech_by_ear.bat in the same folder.

**Not a pytest test, and the name says so on purpose.** It speaks through NVDA and sleeps for a
minute; under the old name `test_speech.py` pytest would collect it, importing it would run it,
and a test run would start talking. What it proves needs ears, which is exactly what the
automatic suite in tests\\ cannot do.

Three rounds, each testing exactly one thing: 1 queue, 2 replace, 3 braille."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speech

COUNT = 'one, two, three, four, five, six, seven, eight, nine, ten.'

print('nvda reachable:', speech.nvda_running())

speech.output('Round one, queue. The message joins the back of the line, so the count runs '
              'all the way to the end first.')
time.sleep(9)
speech.output(COUNT, speech.QUEUE)
time.sleep(2)
speech.output('Message of round one.', speech.QUEUE)
time.sleep(10)

speech.output('Round two, replace. The message throws the count away. You hear the count '
              'break off and it does not come back.')
time.sleep(9)
speech.output(COUNT, speech.QUEUE)
time.sleep(2)
speech.output('Message of round two.', speech.REPLACE)
time.sleep(6)

speech.output('Round three, braille. Three lines follow with four counts between them. The first '
              'two reach the braille display with exactly the words you hear; the third is the '
              'exception this seam allows, and it reads there differently from how it sounds.')
time.sleep(13)
speech.output('Line one.', speech.QUEUE)
time.sleep(4)
speech.output('Line two.', speech.QUEUE)
time.sleep(4)
speech.output('Line three, end.', speech.QUEUE, braille='line three end 123')
time.sleep(4)

speech.output('End of the test.', speech.QUEUE)
print('test finished without an error code')
