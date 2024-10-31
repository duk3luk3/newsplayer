#!/usr/bin/env bash

echo "Newsplayer starting up"

sudo usbreset 0451:2046

while :
do
  today=$(date +%Y-%m-%d)
  echo "The date is $today"
  if [[ $today > '2024-01-01' ]] ; then
	  break
  fi
  sleep 5
done

echo "Starting silence.py"

./.venv/bin/python silence.py

echo "Starting player"


./.venv/bin/python player_clean.py config.yaml | tee -a "newsplayer-$today.log"
#python player_clean.py config.yaml
