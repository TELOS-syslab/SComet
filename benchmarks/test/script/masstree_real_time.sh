# !/bin/bash

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
    cmd="TBENCH_QPS=${QPS} TBENCH_MAXREQS=${MAXREQS} TBENCH_WARMUPREQS=${WARMUPREQS} \
    TBENCH_MINSLEEPNS=10000 realtime=1 taskset -c $core_ids_string ./mttest_integrated -j${NTHREADS} \
    mycsba masstree"
else
    cmd="TBENCH_QPS=${QPS} TBENCH_MAXREQS=${MAXREQS} TBENCH_WARMUPREQS=${WARMUPREQS} \
    TBENCH_MINSLEEPNS=10000 realtime=1 ./mttest_integrated -j${NTHREADS} \
    mycsba masstree"
fi
echo $cmd

# 启动 masstree 服务端（后台运行）
bash -c "$cmd" 1> /home/wjy/SComet/benchmarks/masstree/QoS/masstree.log 2>&1 &
MASSTREE_PID=$!

rm -rf /home/wjy/SComet/benchmarks/masstree/QoS/lc_latency_realtime.log
# 实时解析 lats.bin，每隔1ms追加一行到 lc_latency_realtime.log
phase=0
while kill -0 $MASSTREE_PID 2>/dev/null; do
    if [ -f lats.bin ]; then
        phase=$((phase + 1))
        timestamp=$(date +%s.%N)   # 当前时间（秒.纳秒）
        echo "phase: $phase (t=$timestamp)" >> /home/wjy/SComet/benchmarks/masstree/QoS/lc_latency_realtime.log
        python3 ../utilities/parselats.py lats.bin >> /home/wjy/SComet/benchmarks/masstree/QoS/lc_latency_realtime.log
        echo "" >> /home/wjy/SComet/benchmarks/masstree/QoS/lc_latency_realtime.log   # 可选：分隔空行
    fi
    sleep 0.001
done

wait $MASSTREE_PID

# 最终再解析一次，生成 masstree_0.log
python3 ../utilities/parselats.py lats.bin > /home/wjy/SComet/benchmarks/masstree/QoS/masstree_0.log

for ((i = 1; i < NTHREADS; i++)); do
    cp /home/wjy/SComet/benchmarks/masstree/QoS/masstree_0.log /home/wjy/SComet/benchmarks/masstree/QoS/masstree_$i.log
done


