
OFFSET = 0.0
MIN_PAUSE = 2.0
MAX_PAUSE = 2.1
VOLUME=1.0
#SOUND_DEVICE='USB PnP Sound Device'
SOUND_DEVICE='Bose QC35 II'
PTT_VID = 3568
PTT_PID = 316

import pygame
from pygame import mixer, time, font
from pygame.locals import *
import yaml
from datetime import datetime, timedelta
import sys
import hid

configfile = sys.argv[1]

config_data = yaml.safe_load(open(configfile).read())

OFFSET = config_data['player_config'].get('silence_offset', OFFSET)
VOLUME = config_data['player_config'].get('volume', VOLUME)
SOUND_DEVICE = config_data['player_config'].get('sound_dev', SOUND_DEVICE)

PTT_VID = config_data['player_config'].get('ptt_dev_vid', PTT_VID)
PTT_PID = config_data['player_config'].get('ptt_dev_pid', PTT_PID)
#silencesfile = 'silences.yml'
silencesfile = config_data['player_config'].get('datafile', 'silences.yml')

silence_data = yaml.safe_load(open(silencesfile).read())

soundfile = silence_data[0]['name']
silences = silence_data[0]['silences']

mixer.pre_init(devicename=SOUND_DEVICE)
pygame.init()

#my_font = pygame.font.SysFont('Comic Sans MS', 24)
my_font = pygame.font.SysFont('Courier New', 24)

width, height = 800, 600
screen = pygame.display.set_mode((width, height))

fps = 300
fpsClock = time.Clock()

start = datetime.now()
tick_offset = 0
start_tick = 0


#bus_type : 1
#interface_number : 3
#manufacturer_string : C-Media Electronics Inc.
#path : b'DevSrvsID:4295991877'
#product_id : 316
#product_string : USB PnP Sound Device
#release_number : 256
#serial_number :
#usage : 1
#usage_page : 12
#vendor_id : 3468

#usb_dev: tuple = (0x0D8C, 0x013A)

READ_SIZE = 5

PTT_START = b'\x00\x00\x04\x04\x00'
PTT_STOP = b'\x00\x00\x00\x00\x00'

COR_START = bytearray(b'\x02\x00\x00\x00')
COR_STOP = bytearray(b'\x00\x00\x00\x00')

h = None
try:
  h = hid.Device(PTT_VID, PTT_PID)
  print(f'Device manufacturer: {h.manufacturer}')
  print(f'Product: {h.product}')
  print(f'Serial Number: {h.serial}')
except:
  print('No PTT device!')

is_ptt_on = False

def ptt_start():
  global is_ptt_on
  is_ptt_on = True
  if h:
    h.write(PTT_START)

def ptt_stop():
  global is_ptt_on
  is_ptt_on = False
  if h:
    h.write(PTT_STOP)


MUSIC_END = pygame.USEREVENT+1

for file_block in silence_data:

  soundfile = file_block['name']
  silences = file_block['silences']
  sidx = 0
  
  tick_offset = time.get_ticks()
  sound_delta = 0.0
  #sound = mixer.Sound(soundfile)
  sound = mixer.music.load(soundfile)
  mixer.music.set_endevent(MUSIC_END)
  
  started = False
  finished = False
 
  paused = False
  pause_start = 0.0
 
  while True:
    screen.fill((0, 0, 0))
  
    ticks = time.get_ticks() - tick_offset
  
    if ticks > 2000 and not started:
      ptt_start()
      #sound.set_volume(VOLUME)
      #sound.play()
      mixer.music.set_volume(VOLUME)
      mixer.music.play()
      start = datetime.now()
      start_tick = time.get_ticks() - tick_offset
      started = True

    #if started and not mixer.get_busy():
    #if started and sidx >= len(silences) and len(silences) > 0 :
    #  break

    if finished:
      ptt_stop()
      break
  
    sound_ticks = ticks - start_tick
  
    dt = datetime.now() - start
  
    text = []

    pos = mixer.music.get_pos() / 1000.0
  
    text.append(str(dt))
    text.append(f"global ticks: {ticks}")
    text.append(f"sound  ticks: {sound_ticks} sound pos {pos}:")
    text.append(f"PTT on: {is_ptt_on} Soundfile: {soundfile}")
  
  
    if sidx < len(silences):
  
      #curr_start = (silences[sidx]['start'] + OFFSET + 0.5 * silences[sidx]['duration']) * 1000 + sound_delta
      #curr_duration_s = max(MIN_PAUSE, min(silences[sidx]['duration'], MAX_PAUSE))
      #curr_duration = curr_duration_s * 1000

      curr_silence = silences[sidx]

      sil_start = curr_silence['start']
      sil_dur = curr_silence['duration'] if curr_silence['duration'] != float('inf') else 1.0
      
      curr_start = (sil_start + OFFSET + 0.5 * sil_dur) * 1000
      curr_duration = MIN_PAUSE * 1000
  
      dt_start = timedelta(seconds=curr_start / 1000)
      dt_end = timedelta(seconds=(curr_start+curr_duration)/1000)
  
      #if sound_ticks > curr_start:
      if (mixer.music.get_pos() > curr_start) or paused:
        if (ticks < pause_start + curr_duration) or not paused:
          #sound.set_volume(0.0)
          #mixer.pause()
          if not paused:
            mixer.music.pause()
            mixer.music.rewind()
            time.delay(250)
            paused = True
            pause_start = ticks
            ptt_stop()
          text.append(f"Pause running : {sidx:02} from {dt_start} to {dt_end} ")
        else:
          #sound.set_volume(VOLUME)
          ptt_start()
          time.delay(100)
          paused = False
          #mixer.unpause()
          #mixer.music.play(start=curr_start / 1000.0)
          mixer.music.set_pos(curr_start / 1000.0)
          mixer.music.unpause()
          sound_delta = sound_delta + 250 + 100 + curr_duration
          sidx = sidx + 1
          text.append(f"Pause upcoming: {sidx:02} from {dt_start} to {dt_end} ")
      else:
        text.append(f"Pause upcoming: {sidx:02} from {dt_start} to {dt_end} ")
  
    
    for idx, line in enumerate(text):
      text_surface = my_font.render(line, False, (220, 0, 0))
      screen.blit(text_surface, (0,idx * (my_font.size(line)[1] + 4)))
  
    for event in pygame.event.get():
      if event.type == QUIT:
        ptt_stop()
        pygame.quit()
        sys.exit()
      elif event.type == MUSIC_END:
        print("finished")
        finished = True
  
    pygame.display.flip()
    fpsClock.tick_busy_loop(fps)
