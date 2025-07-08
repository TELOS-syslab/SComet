#!/bin/bash

sudo rm -rf /var/lock/libpqos
sudo pkill -f 'memcached|nginx|mutated|wrk|lbm'

#t_values=("12,8,12,8,16" "16,8,16,8,8" "18,8,18,8,4"  "19,8,19,8,2")
t_values=("8,8,8,8,24")
r0_values=(90000)
r1_values=(72000)
r_values=()
for r0 in "${r0_values[@]}"; do
    for r1 in "${r1_values[@]}"; do
        r_values+=("${r0},${r1}")
    done
done
c_values=("4,3,4,3,1")
m_values=("30,20,20,20,10")

num_loops=50
test_time=60

for t in "${t_values[@]}"; do
    for r in "${r_values[@]}"; do
        for c in "${c_values[@]}"; do
            for m in "${m_values[@]}"; do
                for ((i=0; i<num_loops; i++)); do
                    sudo python3 prove_row_buffer_interference.py -T ${test_time} -t $t -r $r -c $c -m $m
                done
            done
        done
    done
done

