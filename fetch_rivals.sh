#!/bin/sh
# Copy each teammate's branch into rivals/<Name>/ so tourney.py can use their bot as an opponent
# (rival_bots.py loads them with their own game_engine.py). Read-only snapshots: nothing is
# committed, merged or pushed; rivals/ is in .gitignore.
set -e
git fetch origin
for b in Othmane Ronita Mohamed Harsha; do
  rm -rf "rivals/$b"
  mkdir -p "rivals/$b"
  git archive "origin/$b" | tar -x -C "rivals/$b"
  echo "rivals/$b <- origin/$b ($(git rev-parse --short origin/$b))"
done
