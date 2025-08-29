#!/bin/bash

# if [[ -z "${NTHREADS}" ]]; then NTHREADS=32; fi

NTHREADS=${1:-1}
QPS=${2:-2000}
duration=${3:-600}
core_ids_string=${4:-}
IFS=',' read -ra core_ids <<< "$core_ids_string"
MAXREQS=$((QPS * duration))
WARMUPREQS=$((QPS * 7))

cd /home/wjy/SComet/benchmarks/Tailbench/tailbench/masstree
# sudo bash kill_networked.sh
# sudo pkill -f mttest
bash kill_networked.sh
pkill -f mttest
sleep 1

if [ -n "${core_ids[0]}" ]; then
    cmd="TBENCH_MAXREQS=${MAXREQS} TBENCH_WARMUPREQS=${WARMUPREQS} \
    taskset -c $core_ids_string ./mttest_server_networked -j${NTHREADS} mycsba masstree"
else
    cmd="TBENCH_MAXREQS=${MAXREQS} TBENCH_WARMUPREQS=${WARMUPREQS} \
    ./mttest_server_networked -j${NTHREADS} mycsba masstree"
fi
echo $cmd 
# sudo bash -c "$cmd"
bash -c "$cmd"
