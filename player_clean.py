OFFSET = 0.0
#MIN_PAUSE = 2.0
#MAX_PAUSE = 2.1
PAUSE_LENGTH = 2.0
VOLUME=1.0
#SOUND_DEVICE='USB PnP Sound Device'
SOUND_DEVICE='Bose QC35 II'
PTT_METHOD='cm108'
PTT_VID = 3568
PTT_PID = 316
FLDIGI_HOST = '127.0.0.1'
FLDIGI_PORT = 7362
PTT_ON_DELAY = 0.1
PTT_OFF_DELAY = 0.25

PLAY_TIME = None

STARTUP_DELAY = 3.0

from enum import Enum
from dataclasses import dataclass, field
import pygame
from pygame import mixer, time, font
from pygame.locals import *
import yaml
from datetime import date, datetime, timedelta, time as dt_time
import calendar
import sys

configfile = sys.argv[1]
silencesfile = sys.argv[2] if len(sys.argv) > 2 else None

config_data = yaml.safe_load(open(configfile).read())

OFFSET = config_data['player_config'].get('silence_offset', OFFSET)
VOLUME = config_data['player_config'].get('volume', VOLUME)
SOUND_DEVICE = config_data['player_config'].get('sound_dev', SOUND_DEVICE)
PAUSE_LENGTH = config_data['player_config'].get('pause_length', PAUSE_LENGTH)

PTT_METHOD = config_data['player_config'].get('ptt_method', PTT_METHOD)
PTT_VID = config_data['player_config'].get('ptt_dev_vid', PTT_VID)
PTT_PID = config_data['player_config'].get('ptt_dev_pid', PTT_PID)
FLDIGI_HOST = config_data['player_config'].get('fldigi_host', FLDIGI_HOST)
FLDIGI_PORT = config_data['player_config'].get('fldigi_port', FLDIGI_PORT)
#silencesfile = 'silences.yml'
if not silencesfile:
  silencesfile = config_data['player_config'].get('datafile', 'silences.yml')

PLAY_TIME = config_data['player_config'].get('play_time', PLAY_TIME)

silence_data = yaml.safe_load(open(silencesfile).read())

## UTIL functions

def sec_to_ticks(ticks):
    return ticks * 1000.0

def ticks_to_sec(sec):
    return sec / 1000.0

def ticks_format(ticks):
    td = timedelta(milliseconds=ticks)
    return(str(td))

def secs_format(sec):
    td = timedelta(seconds=sec)
    return(str(td))

DAY_INDEXES = { name: num for num, name in enumerate(calendar.day_name)}

def find_next_weekday(day_str):
    today = date.today()
    day_index = DAY_INDEXES[day_str]
    day_gap = day_index - today.weekday()
    if day_gap < 0:
        day_gap += 7
    next_day_date = today + timedelta(days=day_gap)
    return next_day_date

def init_cm108_ptt(vid, pid, state):
    h = None
    try:
      import hid
      h = hid.Device(vid, pid)
      print(f'Device manufacturer: {h.manufacturer}')
      print(f'Product: {h.product}')
      print(f'Serial Number: {h.serial}')
    except:
      print('No PTT device!')
    state.ptt_dev = h

def init_fldigi_ptt(host, port, state):
    client = None
    try:
      import pyfldigi
      client = pyfldigi.Client(hostname=host, port=port)
      print(f'fldigi version: {str(client.version)}')
      client.modem.name = 'NULL'
      print(f'fldigi modem: {client.modem.name}')
      state.ptt_fldigiclient = client
    except Exception as e:
      #print(e)
      print('No pyfldigi connection')

def ptt_start(state):
    PTT_START = b'\x00\x00\x04\x04\x00'
    state.is_ptt_on = True
    if state.ptt_dev is not None:
        state.ptt_dev.write(PTT_START)
    if state.ptt_fldigiclient is not None:
        state.ptt_fldigiclient.main.tx()

def ptt_stop(state):
    PTT_STOP = b'\x00\x00\x00\x00\x00'
    state.is_ptt_on = False
    if state.ptt_dev is not None:
        state.ptt_dev.write(PTT_STOP)
    if state.ptt_fldigiclient is not None:
        state.ptt_fldigiclient.main.rx()

## State storage

class PlayerState(Enum):
  STARTING = 0
  PLAYING = 1
  FINISHED = 3
  GLOBAL = 999

@dataclass
class GlobalState:
    soundfile_idx: int = None
    screen = None
    is_ptt_on = None
    ptt_dev = None
    ptt_fldigiclient = None

@dataclass
class StartingState:
    preinit_done: bool = None
    init_done: bool = None
    start_tick: int = None
    start_play_at: datetime = None

@dataclass
class PlayingState:
    load_done: bool = None
    pause_start_tick: int = None
    silence_idx: int = None

@dataclass
class StateContainer:
    g: GlobalState = field(default_factory=GlobalState)
    s: StartingState = field(default_factory=StartingState)
    p: PlayingState = field(default_factory=PlayingState)
    current: PlayerState = PlayerState.STARTING

## state init

state = StateContainer()

MUSIC_END = pygame.USEREVENT+1

state.s.init_done = False
state.s.preinit_done = False

if SOUND_DEVICE is not None:
    mixer.pre_init(devicename=SOUND_DEVICE)
pygame.init()

## pre-check

if PLAY_TIME:

  now = datetime.now()

  for playtime in PLAY_TIME:
    print(f'checking playtime {playtime}')
    pday = playtime['day']
    ptime = playtime['time']

    next_pday_date = find_next_weekday(pday)
    print(next_pday_date)

    next_play_dt = datetime.combine(next_pday_date, dt_time.fromisoformat(ptime))

    next_play_in = next_play_dt - now

    print(next_play_in)

    if next_play_in.total_seconds() > 0 and next_play_in < timedelta(hours=2.5):
        print(f'set start_play_at: {next_play_dt}')
        state.s.start_play_at = next_play_dt
        break
  if state.s.start_play_at is None:
      print('play time configured but not in time window, exiting')
      sys.exit(0)

## game loop

while True:
    text = []
    ticks = time.get_ticks()

    text.append(f"State: {state.current.name}")

    # Main state machine
    if state.current == PlayerState.STARTING:
        if not state.s.preinit_done:
            width, height = 800, 600
            screen = pygame.display.set_mode((width, height))
            state.g.screen = screen
            fpsClock = time.Clock()
            state.g.fpsclock = fpsClock

            my_font = pygame.font.SysFont('Courier New', 24)
            state.g.font = my_font

            if PTT_METHOD == 'cm108':
                init_cm108_ptt(PTT_VID, PTT_PID, state.g)
                print(f'PTT dev: {state.g.ptt_dev}')
            elif PTT_METHOD == 'fldigi':
                init_fldigi_ptt(FLDIGI_HOST, FLDIGI_PORT, state.g)

            state.s.preinit_done = True

        if not state.s.init_done:
            state.s.start_tick = ticks
            state.s.init_done = True

        can_start = True
        if state.s.start_play_at:
            remaining = state.s.start_play_at - datetime.now()
            if remaining.total_seconds() > 0:
                can_start = False

        if can_start and ticks > state.s.start_tick + STARTUP_DELAY * 1000.0:
            state.current = PlayerState.PLAYING
            state.p.load_done = False

    if state.current == PlayerState.PLAYING:
        if not state.p.load_done:
            soundfile_idx = state.g.soundfile_idx if state.g.soundfile_idx is not None else -1
            soundfile_idx = soundfile_idx + 1
            print(f"Starting sound file {soundfile_idx}")
            soundfile = silence_data[soundfile_idx]['name']
            mixer.music.load(soundfile)
            mixer.music.set_endevent(MUSIC_END)
            mixer.music.set_volume(VOLUME)
            ptt_start(state.g)
            time.delay(int(PTT_OFF_DELAY * 1000))
            mixer.music.play()

            state.g.soundfile_idx = soundfile_idx
            state.p.silence_idx = 0 if len(silence_data[soundfile_idx]['silences']) > 0 else None
            state.p.pause_start_tick = None
            state.p.load_done = True

        soundfile_idx = state.g.soundfile_idx
        silence_idx = state.p.silence_idx
        silence = None
        silence_start_s = None
        if silence_idx is not None and silence_idx < len(silence_data[soundfile_idx]['silences']):
            silence = silence_data[soundfile_idx]['silences'][silence_idx]
            sil_dur = silence['duration'] if silence['duration'] != float('inf') else 1.0
            silence_start_s = (silence['start'] + OFFSET + 0.5 * sil_dur)

        if state.p.pause_start_tick is not None:
            pause_start_tick = state.p.pause_start_tick

            if ticks > pause_start_tick + PAUSE_LENGTH * 1000:
                print("Resuming")
                mixer.music.rewind()
                mixer.music.set_pos(silence_start_s)
                ptt_start(state.g)
                time.delay(int(PTT_ON_DELAY * 1000))
                mixer.music.unpause()

                state.p.silence_idx = state.p.silence_idx+1
                state.p.pause_start_tick = None

        elif silence is not None:
            play_elapsed = mixer.music.get_pos()

            if play_elapsed > silence_start_s * 1000:
                print("Pausing")
                mixer.music.pause()
                time.delay(int(PTT_OFF_DELAY * 1000))
                ptt_stop(state.g)
                state.p.pause_start_tick = ticks


    # Process events
    for event in pygame.event.get():
      if event.type == QUIT:
        #ptt_stop()
        if state.g.is_ptt_on:
            time.delay(int(PTT_OFF_DELAY * 1000))
            ptt_stop(state.g)
        pygame.quit()
        sys.exit()
      elif event.type == MUSIC_END:
        time.delay(int(PTT_OFF_DELAY * 1000))
        ptt_stop(state.g)
        print('Music end')
        if state.g.soundfile_idx >= len(silence_data) - 1:
            state.current = PlayerState.FINISHED
        else:
            state.current = PlayerState.STARTING
            state.s.init_done = False


    if state.current == PlayerState.FINISHED:
        break


    screen = state.g.screen
    screen.fill((0, 0, 0))
    font = state.g.font
    text.append(f'ticks: {ticks:05} time elapsed: {ticks_format(ticks)} state: {state.current.name}')
    text.append(f'Init state: {"done" if state.s.init_done else "pending"}')

    if state.current == PlayerState.STARTING:
        remaining = None
        if state.s.start_play_at:
            remaining = state.s.start_play_at - datetime.now()
            if remaining.total_seconds() < 0:
                remaining = None

        if remaining is not None:
          text.append(f"Waiting until {state.s.start_play_at} to play next file")
          text.append(f"({remaining} remaining)")
        else:
          text.append("Waiting to play next file...")
          text.append("")
    elif state.current == PlayerState.PLAYING:
        soundfile_idx = state.g.soundfile_idx
        playstate = 'Playing' if state.p.pause_start_tick is None else 'Paused'
        pos_sec = ticks_format(mixer.music.get_pos())
        text.append(f"{soundfile_idx:02} {playstate} at {pos_sec}")
        silence_idx = state.p.silence_idx
        if silence_idx is not None and silence_idx < len(silence_data[soundfile_idx]['silences']):
            silence = silence_data[soundfile_idx]['silences'][silence_idx]
            sil_dur = silence['duration'] if silence['duration'] != float('inf') else 1.0
            silence_start_s = (silence['start'] + OFFSET + 0.5 * sil_dur)
            silence_start_f = secs_format(silence_start_s)
            text.append(f"Silence: {silence_idx:02} starting at {silence_start_f}")
        else:
            text.append(f"Silence: No more silence for this file")

    text.append(f"PTT: {'On' if state.g.is_ptt_on else 'Off'}")

    for idx, line in enumerate(text):
      text_surface = my_font.render(line, False, (220, 0, 0))
      screen.blit(text_surface, (0,idx * (my_font.size(line)[1] + 4)))


    pygame.display.flip()
    fpsClock.tick_busy_loop(300)

