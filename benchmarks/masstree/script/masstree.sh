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
rm -rf lats.bin
rm -rf lats.txt
pkill -f mttest

if [ -n "${core_ids[0]}" ]; then
    cmd="TBENCH_QPS=${QPS} \
	TBENCH_MAXREQS=${MAXREQS} \
	TBENCH_WARMUPREQS=${WARMUPREQS} \
    	TBENCH_MINSLEEPNS=10000 \
	taskset -c $core_ids_string ./mttest_integrated \
	-j${NTHREADS} mycsba masstree"
else
    cmd="TBENCH_QPS=${QPS} \
	TBENCH_MAXREQS=${MAXREQS} \
	TBENCH_WARMUPREQS=${WARMUPREQS} \
    	TBENCH_MINSLEEPNS=10000 \
	./mttest_integrated \
	-j${NTHREADS} mycsba masstree"
fi
echo $cmd

bash -c "$cmd" 1> /home/wjy/SComet/benchmarks/masstree/QoS/masstree.log 2>&1
python3 ../utilities/parselats.py lats.bin > /home/wjy/SComet/benchmarks/masstree/QoS/masstree_0.log

for ((i = 1; i < NTHREADS; i++)); do
    cp /home/wjy/SComet/benchmarks/masstree/QoS/masstree_0.log /home/wjy/SComet/benchmarks/masstree/QoS/masstree_$i.log
done


