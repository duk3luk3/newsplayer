from functools import total_ordering
from datetime import timedelta as TD, datetime, date
import calendar
import yaml
import sys
import subprocess
import requests
import os.path
import os

template_pre = [
        {
            'name': 'sample_files/warning.mp3',
            'silences': []
            },
        {
            'name': 'sample_files/welcome.mp3',
            'silences': [],
            'pause_before': 270
            }
        ]

template_post = [
        {
            'name': 'sample_files/thankyou.mp3',
            'silences': []
            }
        ]

DAY_INDEXES = { name: num for num, name in enumerate(calendar.day_name)}

MAX_DIST = 2.5
WANT_DIST = 2
#MAX_DIST = 60.0*1 - 5
#WANT_DIST = 0
WANT_DURATIONS = [2.0, 1.5, 1.0, 0.5, 0.3]

DOWNLOAD_BASE = 'https://www.wia-files.com/podcast/wianews-{date}.mp3'
DOWNLOAD_DAY = 'Sunday'

if len(sys.argv) > 1:
  configfile = sys.argv[1]
  config_data = yaml.safe_load(open(configfile).read())
  silence_config = config_data.get('silences',{})
  MAX_DIST = silence_config.get('max_dist', MAX_DIST)
  WANT_DIST = silence_config.get('want_dist', WANT_DIST)
  WANT_DURATIONS = silence_config.get('want_durations', WANT_DURATIONS)
  DOWNLOAD_BASE = silence_config.get('download', {}).get('base_url', DOWNLOAD_BASE)
  DOWNLOAD_DAY = silence_config.get('download', {}).get('dat', DOWNLOAD_DAY)

MAX_DIST = MAX_DIST * 60.0
WANT_DIST = WANT_DIST * 60.0

is_latest = False
mp3filename = None
if len(sys.argv) > 2:
  mp3filename = sys.argv[2]
else:
  is_latest = True
  today = date.today()
  dl_day_index = DAY_INDEXES[DOWNLOAD_DAY]
  day_gap = dl_day_index - today.weekday()
  if day_gap > 2:
      day_gap -= 7
  download_date = today + TD(days=day_gap)
  download_date_str = download_date.strftime('%Y-%m-%d')
  download_url = DOWNLOAD_BASE.format(date=download_date_str)
  mp3filename = download_url.split("/")[-1]

  if os.path.isfile(mp3filename) and os.path.getsize(mp3filename) > 10*1024*1024:
      print(f'File exists: {mp3filename}')
  else:

    print(f'download url: {download_url}')

    r_headers = {
            'User-Agent': 'VK3UKW Download 0.1',
            }

    print('Downloading...')
    r = requests.get(download_url, headers=r_headers, allow_redirects=True, stream=True)
    r.raise_for_status()
    bs = 1024**4
    with open(mp3filename, 'wb') as mf:
        for data in r.iter_content(bs):
            sys.stdout.write('.')
            sys.stdout.flush()
            mf.write(data)
    print(' done')

silencename = f'{mp3filename}_silences.txt'
outputname = f'{mp3filename}_cbr.mp3'

if not os.path.isfile(outputname) or os.path.getsize(outputname) < 1000*1000:
    silence_cmd = f'ffmpeg -y -i {mp3filename} -af silencedetect=noise=-35dB:d=0.3,ametadata=mode=print:file={silencename},dynaudnorm=p=0.9 -b:a 256k {outputname}'

    print(f'Running {silence_cmd}')
    subprocess.run(silence_cmd.split(' '))

length_cmd = f'ffprobe -i {outputname} -show_entries format=duration -v quiet -of csv=p=0'
print(f'Running {length_cmd}')
length_result = subprocess.run(length_cmd.split(' '), capture_output=True)

length_out = length_result.stdout.decode().strip()

print(f'length_out: {length_out}')

length_out_min = float(length_out) / 60.0

print(f'length_out mins: {length_out_min}')

if length_out_min < 28.0:
    print('Less than 28 minutes!')
    os.remove(mp3filename)
    sys.exit(1)


silence_text = open(silencename).readlines()

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

for line in silence_text:
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

with open(f'silences_{mp3filename}.yml', 'w') as yf:
  yaml.dump(wrapped_list, yf)

if is_latest:
    templated = template_pre + wrapped_list + template_post

    with open(f'silences_latest.yml', 'w') as yf:
      yaml.dump(templated, yf)
