#!/bin/bash

t_values=("0,32,8")
r_values=("15400")
c_values=("0,14,1")
m_values=("0,100,10")

num_loops=2
benchmark_set=spec2017
test_time=120

for ((i=0; i<num_loops; i++)); do
    for t in "${t_values[@]}"; do
        for r in "${r_values[@]}"; do
            for c in "${c_values[@]}"; do
                for m in "${m_values[@]}"; do
                    sudo rm -rf /var/lock/libpqos
                    sudo pkill -f 'python|memcached|nginx|mutated|wrk|lbm|mttest|_r_base'
                    sudo python3 bandwidth_monitor.py "$benchmark_set" -T ${test_time} -t $t -r $r -c $c -m $m --lc masstree
                done
            done
        done
    done
done

