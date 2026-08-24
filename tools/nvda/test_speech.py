"""Standalone test of the speech layer. It announces itself; you need not read along.
Start it with test_speech.bat in the same folder.

Three rounds, each testing exactly one thing:
  1 queue, 2 replace, 3 braille."""
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speech

COUNT = 'one, two, three, four, five, six, seven, eight, nine, ten.'

print('nvda reachable:', speech.nvda_running())

speech.speak('Round one, queue. The message joins the back of the line, so the count runs '
              'all the way to the end first.')
time.sleep(9)
speech.speak(COUNT, speech.QUEUE)
time.sleep(2)
speech.speak('Message of round one.', speech.QUEUE)
time.sleep(10)

speech.speak('Round two, replace. The message throws the count away. You hear the count '
              'break off and it does not come back.')
time.sleep(9)
speech.speak(COUNT, speech.QUEUE)
time.sleep(2)
speech.speak('Message of round two.', speech.REPLACE)
time.sleep(6)

speech.speak('Round three, braille. Three braille lines follow with four counts between them. '
              'Every line is spoken as well.')
time.sleep(9)
speech.speak('Line one.', speech.QUEUE, braille='line one')
time.sleep(4)
speech.speak('Line two.', speech.QUEUE, braille='line two 123')
time.sleep(4)
speech.speak('Line three.', speech.QUEUE, braille='line three end')
time.sleep(4)

speech.speak('End of the test.', speech.QUEUE)
print('test finished without an error code')
