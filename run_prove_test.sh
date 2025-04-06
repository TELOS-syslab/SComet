#!/bin/bash

# t_values=(8)
# r_values=(50000 60000 70000)
# c_values=(2 4 6 8 10 12 14)
# m_values=(10 30 50 70 90)

LC_task="nginx"
t_values=(8)
r_values=(8000 12000 16000)
c_values=(2 6 10 14)
m_values=(10 30 50 70 90)

num_loops=3

for t in "${t_values[@]}"; do
    for r in "${r_values[@]}"; do
        for c in "${c_values[@]}"; do
            for m in "${m_values[@]}"; do
                echo "Executing: sudo python3 prove_row_buffer_interference.py -t $t -r $r -c $c -m $m --lc ${LC_task}"
                for ((i=1; i<=num_loops; i++)); do
                    echo "========== loop $i =========="
                    sudo python3 prove_row_buffer_interference.py -t "$t" -r "$r" -c "$c" -m "$m" --lc "${LC_task}"
                done
            done
        done
    done
done
