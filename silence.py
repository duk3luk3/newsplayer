from functools import total_ordering
from datetime import timedelta as TD
import yaml
import sys

mp3filename = sys.argv[1]

#MAX_DIST = 60.0*3 - 5
#WANT_DIST = 60.0*2
MAX_DIST = 60.0*1 - 5
WANT_DIST = 0
WANT_DURATIONS = [2.0, 1.5, 1.0, 0.5, 0.3]


silence_half_text = open('silences.txt').readlines()
#silence_one_text = open('silence_half_sec.txt').readlines()

def format_sec(seconds):
  if not seconds or seconds == float('inf'):
    return None
  full_minutes = int(seconds / 60)
  remainder_secs = (seconds - full_minutes * 60)
  return f"{full_minutes:02}:{remainder_secs:01.3f}"

@total_ordering
class Silence:
  def __init__(self, start, end, duration):
    self.start = start
    self.end = end or start
    self.duration = duration or float('inf')

  def __repr__(self):
    fs = format_sec(self.start)
    fe = format_sec(self.end)
    
    return f"{fs} - {fe} ({self.duration})"

  def __lt__(self, other):
    return self.start < other.start

  def __eq__(self, other):
    return self.start == other.start

start = None
end = None
duration = None

silences = []

for line in silence_half_text:
  if line.startswith('lavfi.silence'):
    components = line.strip().split('=')
    if components[0] == 'lavfi.silence_start':
      start = float(components[1])
    elif components[0] == 'lavfi.silence_end':
      end = float(components[1])
    elif components[0] == 'lavfi.silence_duration':
      duration = float(components[1])
      s = Silence(start, end, duration)
      silences.append(s)
      start = end = duration = None

if start and not end:
  silences.append(Silence(start, end, duration))
  
silences = sorted(silences)

for s in silences:
  print(s)

print("====")

candidates = [s for s in silences]
selected = []

curr_end = 0.0

while True:
  this_candidates = [s for s in candidates if s.start > curr_end and s.start < curr_end + MAX_DIST]
 
  if len(this_candidates) == 0:
    break

  d_candidates = None

  for wd in WANT_DURATIONS:
    d_candidates = [s for s in this_candidates if s.duration > wd and s.start > curr_end + WANT_DIST]
    if d_candidates:
      break

  if len(d_candidates) > 0:
    selected.append(d_candidates[-1])
  else:
    selected.append(this_candidates[-1])

  if selected[-1].end is None:
    break

  last_end = curr_end
  curr_end = selected[-1].end
  candidates = [s for s in candidates if s.start > curr_end]

with(open('labels.txt','w') as lf):
  for idx in range(len(selected)):
    if idx > 0:
      prev_end = selected[idx-1].end
      this_sta = selected[idx].start
      duration = format_sec(this_sta - prev_end)
      print(f">> {duration} >>")

    lf.write(f"{selected[idx].start}\t{selected[idx].end}\t{selected[idx]}\n")
    print(selected[idx])


selected_list = [ {'start': s.start, 'end': s.end, 'duration': s.duration} for s in selected ]

wrapped_list = [ { 'name': mp3filename, 'silences': selected_list } ]

with open('silences.yml', 'w') as yf:
  yaml.dump(wrapped_list, yf)
