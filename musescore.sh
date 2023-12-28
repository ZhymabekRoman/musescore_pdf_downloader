#!/bin/bash
# set -euo pipefail

sudo -S test

# Find all appimage files starting with MuseScore-4
files=$(find $(pwd) -type f -name 'MuseScore-4*.AppImage')

# Convert files into an array
files_array=($files)

# Check the number of files found
num_files=${#files_array[@]}

if [ $num_files -eq 0 ]; then
  echo "No files found"
elif [ $num_files -eq 1 ]; then
  # If only one file found, execute it
  chmod +x ${files_array[0]}
  ./${files_array[0]} &
else
  # If multiple files found, prompt user to select one
  echo "Multiple files found. Please select one to execute:"
  
  # Print all files with their corresponding indices
  for index in "${!files_array[@]}"; do
    echo "$index) ${files_array[$index]}"
  done
  
  # Prompt user for input
  read -p "Enter number: " file_num
  
  # Check if input is a valid number
  if [[ $file_num =~ ^[0-9]+$ ]] && [ $file_num -ge 0 ] && [ $file_num -lt $num_files ]; then
    # If valid, execute the selected file
    chmod +x ${files_array[$file_num]}
    echo "Executing - ${files_array[$file_num]}"
    ${files_array[$file_num]} &
  else
    echo "Invalid input"
    exit 1
  fi
fi

main_proc_pid=$!
echo ${main_proc_pid}

sleep 15
pulse_proc_pid=$(pgrep pulseeffects)

muse_score_proc_pids=$(pgrep mscore4portable)
for muse_score_proc_pid in $muse_score_proc_pids; do
	ls /proc/$muse_score_proc_pid/task | sudo xargs renice -n -18 -p
	ls /proc/$muse_score_proc_pid/task | sudo xargs ionice -c 2 -n 5 -p
done

ls /proc/$pulse_proc_pid/task | sudo xargs renice -n -19 -p
ls /proc/$pulse_proc_pid/task | sudo xargs ionice -c 2 -n 3 -p
