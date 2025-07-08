#!/bin/bash

# 确保 Docker 服务运行
if ! systemctl is-active --quiet docker; then
    sudo systemctl start docker
fi

t_values=("32,0,1" "32,0,2" "32,0,4" "32,0,8")
# t_values=("32,0,8")
# r_values=("17000" "17200" "17400" "17600" "17800" "18000")
# r_values=("50000" "51000" "52000" "53000" "54000" "55000")
# r_values=("1000" "1500" "2000" "2500" "3000")
r_values=("4000")
# r_values=("1000" "1500")
# r_values=("60000" "70000" "80000" "90000" "100000" "900")
#r_values=("56000" "57000" "58000")
c_values=("14,0,1")
m_values=("100,0,10")

num_loops=10
test_time=120  # 测试持续时间（秒）

mkdir -p /home/wjy/SComet/results1/proof

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
                    sudo python3 /home/wjy/SComet/docker_test.py -T ${test_time} -t ${t} -r ${r} -c ${c} -m ${m} --lc masstree

                    echo "等待 5 秒后继续..."
                    sleep 5
                done
            done
        done
    done
done

echo "所有测试完成！"