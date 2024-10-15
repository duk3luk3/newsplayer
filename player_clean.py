OFFSET = 0.0
#MIN_PAUSE = 2.0
#MAX_PAUSE = 2.1
PAUSE_LENGTH = 2.0
VOLUME=1.0
#SOUND_DEVICE='USB PnP Sound Device'
SOUND_DEVICE='Bose QC35 II'
PTT_VID = 3568
PTT_PID = 316
PTT_ON_DELAY = 0.1
PTT_OFF_DELAY = 0.25

STARTUP_DELAY = 3.0

from enum import Enum
from dataclasses import dataclass, field
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
PAUSE_LENGTH = config_data['player_config'].get('pause_length', PAUSE_LENGTH)

PTT_VID = config_data['player_config'].get('ptt_dev_vid', PTT_VID)
PTT_PID = config_data['player_config'].get('ptt_dev_pid', PTT_PID)
#silencesfile = 'silences.yml'
silencesfile = config_data['player_config'].get('datafile', 'silences.yml')

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

def init_ptt(vid, pid, state):
    h = None
    try:
      h = hid.Device(vid, pid)
      print(f'Device manufacturer: {h.manufacturer}')
      print(f'Product: {h.product}')
      print(f'Serial Number: {h.serial}')
    except:
      print('No PTT device!')
    state.ptt_dev = h

def ptt_start(state):
    PTT_START = b'\x00\x00\x04\x04\x00'
    state.is_ptt_on = True
    if state.ptt_dev is not None:
        stat.ptt_dev.write(PTT_START)

def ptt_stop(state):
    PTT_STOP = b'\x00\x00\x00\x00\x00'
    state.is_ptt_on = False
    if state.ptt_dev is not None:
        stat.ptt_dev.write(PTT_STOP)

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

@dataclass
class StartingState:
    preinit_done: bool = None
    init_done: bool = None
    start_tick: int = None

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

state = StateContainer()

MUSIC_END = pygame.USEREVENT+1

state.s.init_done = False
state.s.preinit_done = False

if SOUND_DEVICE is not None:
    mixer.pre_init(devicename=SOUND_DEVICE)
pygame.init()

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

            init_ptt(PTT_VID, PTT_PID, state.g)

            state.s.preinit_done = True

        if not state.s.init_done:
            state.s.start_tick = ticks
            state.s.init_done = True

        if ticks > state.s.start_tick + STARTUP_DELAY * 1000.0:
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
        pygame.quit()
        sys.exit()
      elif event.type == MUSIC_END:
        state.current = PlayerState.STARTING
        state.s.init_done = False




    screen = state.g.screen
    screen.fill((0, 0, 0))
    font = state.g.font
    text.append(f'ticks: {ticks:05} time elapsed: {ticks_format(ticks)} state: {state.current.name}')
    text.append(f'Init state: {"done" if state.s.init_done else "pending"}')

    if state.current == PlayerState.STARTING:
        text.append("Waiting to play next file...")
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

