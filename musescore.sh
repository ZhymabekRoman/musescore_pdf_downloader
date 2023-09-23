#!/bin/bash
# set -euo pipefail

sudo -S test

./MuseScore4.AppImage &

main_proc_pid=$!
echo ${main_proc_pid}

sleep 15
pulse_proc_pid=$(pgrep pulseeffects)

# while true
# do
muse_score_proc_pids=$(pgrep mscore4portable)
for muse_score_proc_pid in $muse_score_proc_pids; do
	ls /proc/$muse_score_proc_pid/task | sudo xargs renice -n -18 -p
	ls /proc/$muse_score_proc_pid/task | sudo xargs ionice -c 2 -n 5 -p
done

# if [ -z "${muse_score_proc_pids}" ]; then
#   echo "PROCESS EXIT"
#  exit 1
# fi

ls /proc/$pulse_proc_pid/task | sudo xargs renice -n -19 -p
ls /proc/$pulse_proc_pid/task | sudo xargs ionice -c 2 -n 3 -p
# sleep 15
# done
