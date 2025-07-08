#!/bin/bash

t_values=("0,16,1" "0,16,4" "0,16,16")
r_values=("17000")
c_values=("0,14,1")
# c_values=("0,7,1" "0,7,3" "0,7,5" "0,7,7")
# m_values=("0,50,10" "0,50,20" "0,50,30" "0,50,40" "0,50,50")
m_values=("0,100,10")

num_loops=1
test_time=60

for ((i=0; i<num_loops; i++)); do
    for t in "${t_values[@]}"; do
        for r in "${r_values[@]}"; do
            for c in "${c_values[@]}"; do
                for m in "${m_values[@]}"; do
                    sudo rm -rf /var/lock/libpqos
                    sudo pkill -f 'python|memcached|nginx|mutated|wrk|lbm|mttest|_r_base'
                    sudo python3 prove_row_buffer_interference.py -T ${test_time} -t $t -r $r -c $c -m $m --lc masstree
                done
            done
        done
    done
done