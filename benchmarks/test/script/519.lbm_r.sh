cd /home/wjy/spec2017/benchspec/CPU/519.lbm_r/run/run_base_refrate_mytest-m64.0000

num_threads=${1:-1}
core_ids_string=${2:-}
IFS=',' read -ra core_ids <<< "$core_ids_string"
total_cores=${#core_ids[@]}

# 计算每个线程应分配多少个 core（尽量平均）
base=$((total_cores / num_threads))
extra=$((total_cores % num_threads))

start_idx=0

for i in $(seq 0 $((num_threads - 1))); do
    # 计算当前线程应该分配几个 core
    count=$base
    if [ $i -lt $extra ]; then
        count=$((count + 1))
    fi

    # 提取对应的 core ID 子数组
    cores=("${core_ids[@]:start_idx:count}")
    core_str=$(IFS=','; echo "${cores[*]}")
    start_idx=$((start_idx + count))

    if [ -n "$core_str" ]; then
        cmd="taskset -c $core_str ./lbm_r_base.mytest-m64 3000 reference.dat 0 0 100_100_130_ldc.of"
    else
        cmd="./lbm_r_base.mytest-m64 3000 reference.dat 0 0 100_100_130_ldc.of"
    fi

    eval "$cmd" > lbm_${i}.out  2>> lbm_${i}.err  &
done

wait
