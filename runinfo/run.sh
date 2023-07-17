#!/bin/bash

trap "kill -9 $(pgrep -lfa python | grep -e quickstart.py | awk '{print $1}'); kill -9 $(pgrep -lfa bash | grep -e ./run.sh -e srt_reservation | awk '{print $1}'); exit 1" SIGINT

result=1
while [ $result -ne 0 ]
do
    SECONDS=0

    echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
    timeout 1800s bash $(dirname $0)/${1}.sh
    result=$?

    secs=$SECONDS
    hrs=$(( secs/3600 )); mins=$(( (secs-hrs*3600)/60 )); secs=$(( secs-hrs*3600-mins*60 ))
    printf 'Time spent: %02d:%02d:%02d\n' $hrs $mins $secs
done


