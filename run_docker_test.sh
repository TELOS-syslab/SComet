#!/bin/bash

# 确保 Docker 服务运行
if ! systemctl is-active --quiet docker; then
    sudo systemctl start docker
fi

num_loops=10
test_time=120  # 测试持续时间（秒）
mkdir -p /home/wjy/SComet/results_docker/proof

# lc_task="xapian"
# r_values=("600")

lc_task="masstree"
r_values=("1000" "1500" "2000" "2500" "3000" "3500" "4000" "4500"  "5000")

t_values=("8,0,1")
c_values=("14,0,1") 
m_values=("100,0,10")

for ((i=0; i<num_loops; i++)); do
    for t in "${t_values[@]}"; do
        for r in "${r_values[@]}"; do
            for c in "${c_values[@]}"; do
                for m in "${m_values[@]}"; do
                    echo "------------------------"
                    echo "迭代: $i | t=$t | r=$r | c=$c | m=$m"
                    echo "清理旧容器..."
                    docker rm -f $(docker ps -aq) &> /dev/null

                    echo "运行测试..."
                    sudo python3 /home/wjy/SComet/docker_test.py -T ${test_time} -t ${t} -r ${r} -c ${c} -m ${m} --lc ${lc_task}

                    echo "等待 5 秒后继续..."
                    sleep 5
                done
            done
        done
    done
done

echo "所有测试完成！"