#!/usr/bin/env bash

wall "Newsplayer starting up"

sudo usbreset 0451:2046

while :
do
  today=$(date +%Y-%m-%d)
  wall "The date is $today"
  if [[ $today > '2024-01-01' ]] ; then
	  break
  fi
  sleep 5
done

#wall "Starting silence.py"

#./.venv/bin/python silence.py

wall "Starting player"

./.venv/bin/python player_clean.py config.yaml

wall "Done"
