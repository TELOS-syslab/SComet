import json
import os
import sys
import time
import docker
import subprocess
from config import *  # 导入配置

class Container:
    # 类级别的常量配置
    client = docker.from_env()
    HOST_WORK_DIR = ROOT
    CONTAINER_WORK_DIR = ROOT
    SPEC2017_HOST_DIR = "/home/wjy/spec2017"
    SPEC2017_CONTAINER_DIR = "/home/wjy/spec2017"
    VOLUMES = {
        HOST_WORK_DIR: {'bind': CONTAINER_WORK_DIR, 'mode': 'rw'},
        SPEC2017_HOST_DIR: {'bind': SPEC2017_CONTAINER_DIR, 'mode': 'rw'}
    }
    TASK_PORTS = {
        "memcached": 11211,
        "nginx": 80,
        "masstree": None,
        "xapian": None
    }
    available_benchmark_set = ['parsec-benchmark', 'stream', 'iperf', 'spec2017', 'ecp']
    LC_tasks = ["memcached", "nginx", "masstree", "xapian"]

    def __init__(self):
        # 初始化测试参数
        self.test_time = 60
        self.threads = [8, 8, 24]
        self.core = []
        self.LC_rps = [59000]
        self.cache_ways = [7, 7, 1]
        self.memory_bandwidth_ratio = [50, 40, 10]
        self.use_palloc = False
        self.cos_llc_masks = []
        self.latency_dict = {}
        self.be_containers = []  # 存储后台容器引用
        self.palloc_base_path = "/sys/fs/cgroup/palloc"
        self.benchmark_set = "spec2017"
        self.benchmark_list = ["519.lbm_r", "baseline"]
        
        # 解析命令行参数并初始化
        self._parse_cli_args()
        self._initialize_core_allocation()
        self.cos_llc_masks = self.initialize_hardware_isolation()

    def _parse_cli_args(self):
        """解析命令行参数"""
        print("=== 命令行参数 ===")
        print(sys.argv)

        # 处理--lc参数
        if '--lc' in sys.argv:
            try:
                idx = sys.argv.index('--lc')
                lc_task_arg = sys.argv[idx + 1]
                print(f"检测到 --lc 参数: {lc_task_arg}")
                if lc_task_arg in self.LC_tasks:
                    self.LC_tasks = [lc_task_arg]
                else:
                    print(f"错误：任务 '{lc_task_arg}' 不在支持列表中")
                    sys.exit(1)
            except IndexError:
                print("--lc 参数缺少任务名称")
                sys.exit(1)
        else:
            self.LC_tasks = [self.LC_tasks[0]]
        print(f"LC任务列表: {self.LC_tasks}")

        # 处理-T参数（测试时间）
        if '-T' in sys.argv:
            self.test_time = int(sys.argv[sys.argv.index('-T') + 1])

        # 处理-t参数（线程数）
        if '-t' in sys.argv:
            self.threads = list(map(int, sys.argv[sys.argv.index('-t') + 1].split(',')))
        
        self.LC_threads = self.threads[:-1]
        self.BE_threads = self.threads[-1]

        # 处理-r参数（请求率）
        if '-r' in sys.argv:
            self.LC_rps = list(map(int, sys.argv[sys.argv.index('-r') + 1].split(',')))
            if len(self.LC_rps) != 1:
                print("错误：-r 参数应提供单个值")
                sys.exit(1)

        # 处理-c参数（缓存路数）
        if '-c' in sys.argv:
            self.cache_ways = list(map(int, sys.argv[sys.argv.index('-c') + 1].split(',')))

        # 处理-m参数（内存带宽比例）
        if '-m' in sys.argv:
            self.memory_bandwidth_ratio = list(map(int, sys.argv[sys.argv.index('-m') + 1].split(',')))

        # 处理--palloc参数
        if '--palloc' in sys.argv:
            self.use_palloc = True
            self._initialize_palloc()

        # 处理--be-core参数
        if '--be-core' in sys.argv:
            start = sum(self.threads[0:-1])
            end = start + int(sys.argv[sys.argv.index('--be-core') + 1])
            self.core[-1] = ','.join(CPU_cores['NUMA0'][start:end])

    def _initialize_core_allocation(self):
        """初始化CPU核心分配"""
        for i in range(len(self.threads)):
            start = sum(self.threads[0:i])
            end = sum(self.threads[0:i+1])
            core_str = ','.join(CPU_cores['NUMA0'][start:end])
            print(f"分配核心 {i}: {core_str}")
            self.core.append(core_str)

    def _initialize_palloc(self):
        """初始化palloc配置"""
        try:
            subprocess.run("echo 1 | sudo tee /sys/kernel/debug/palloc/use_palloc", 
                          shell=True, check=True)
            subprocess.run("echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled", 
                          shell=True, check=True)
            subprocess.run("echo 0x0000F000 | sudo tee /sys/kernel/debug/palloc/palloc_mask > /dev/null", 
                          shell=True, check=True)
            
            # 清理现有palloc分区
            if os.path.exists(self.palloc_base_path):
                for name in os.listdir(self.palloc_base_path):
                    full_path = os.path.join(self.palloc_base_path, name)
                    if name.startswith("part") and os.path.isdir(full_path):
                        try:
                            with open(os.path.join(full_path, "tasks")) as f:
                                for pid in f:
                                    pid = pid.strip()
                                    subprocess.run(f"echo {pid} | sudo tee {self.palloc_base_path}/tasks", 
                                                  shell=True, check=True)
                            subprocess.run(f"sudo rmdir {full_path}", shell=True, check=True)
                            print(f"已删除 {full_path}")
                        except Exception as e:
                            print(f"删除 {full_path} 失败: {e}")
        except Exception as e:
            print(f"palloc初始化失败: {e}")


    def initialize_hardware_isolation(self):
        """初始化硬件资源隔离（PQoS配置）"""
        print("初始化硬件资源隔离...")
        try:
            subprocess.run('sudo rm -rf /var/lock/libpqos', shell=True, check=True)
            subprocess.run("sudo pqos -R", shell=True, check=True)
            
            # 终止现有pqos进程
            check_cmd = "ps aux | grep pqos | grep -v grep"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                subprocess.run("sudo pkill -f pqos", shell=True, check=True)
                print("pqos 进程已终止")

            total_ways = self.get_cache_ways()
            print(f"系统 LLC 总路数: {total_ways}")
            
            cos_llc_masks = []
            start_bit = 0
            for ways in self.cache_ways:
                if ways:
                    mask = ((1 << ways) - 1) << start_bit
                    cos_llc_masks.append(f'0x{mask:0{total_ways//4}x}')
                    start_bit += ways
                else:
                    cos_llc_masks.append('0x0')
            
            # 应用PQoS配置
            for i in range(len(cos_llc_masks)):
                if cos_llc_masks[i] != '0x0':
                    print(f"COS{i} LLC Mask: {cos_llc_masks[i]}, MBA: {self.memory_bandwidth_ratio[i]}%")
                    cos_cmd = f'sudo pqos -e "llc:{i}={cos_llc_masks[i]};mba:{i}={self.memory_bandwidth_ratio[i]}"'
                    print(f"执行: {cos_cmd}")
                    subprocess.run(cos_cmd, shell=True, check=True)
            
            return cos_llc_masks
        except Exception as e:
            print(f"硬件隔离失败: {e}")
            return [None]*len(self.cache_ways)

    def wait_for_running(self, container, timeout=30):
        """等待容器进入运行状态"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                container.reload()
                if container.status == 'running':
                    time.sleep(2)  # 额外等待进程初始化
                    return True
            except Exception as e:
                print(f"检查容器状态错误: {e}")
            time.sleep(1)
        return False

    def assign_to_cos(self, container_id, cos_id):
        """将容器分配到指定的COS"""
        if self.use_palloc:
            try:
                part_name = f"part_{container_id}"
                palloc_path = os.path.join(self.palloc_base_path, part_name)
                palloc_bins_file = os.path.join(palloc_path, "palloc.bins")

                if not os.path.exists(palloc_path):
                    subprocess.run(f"sudo mkdir -p {palloc_path}", shell=True, check=True)

                # 分配palloc bins（LC用0-14，BE用15）
                bins_to_assign = "0-14" if cos_id == 0 else "15"
                subprocess.run(f"echo {bins_to_assign} | sudo tee {palloc_bins_file} > /dev/null", 
                              shell=True, check=True)

                # 绑定进程
                pid = self.client.api.inspect_container(container_id)['State']['Pid']
                tasks_file = os.path.join(palloc_path, "tasks")
                subprocess.run(f"echo {pid} | sudo tee -a {tasks_file} > /dev/null", 
                              shell=True, check=True)
                print(f"容器 {container_id} 分配 palloc bins {bins_to_assign}")
            except Exception as e:
                print(f"palloc分配失败: {e}")

        if cos_id >= len(self.cos_llc_masks) or self.cos_llc_masks[cos_id] is None:
            print(f"警告：无法分配 COS{cos_id} 给容器 {container_id}")
            return False

        try:
            # 方法1：直接使用PID分配
            pid = self.client.api.inspect_container(container_id)['State']['Pid']
            pid_cmd = f"sudo pqos -a 'pid:{cos_id}={pid}'"
            print(f"执行PID分配: {pid_cmd}")
            subprocess.run(pid_cmd, shell=True, check=True)
            return True

        except subprocess.CalledProcessError:
            print("PID分配失败，尝试其他方法")

        # 尝试其他分配方法
        try:
            # 方法2：获取容器内所有进程PID并逐个分配
            pids_output = subprocess.check_output(
                f"docker exec {container_id} ps -eo pid --no-headers", 
                shell=True, 
                text=True
            ).strip()
            
            container_pids = []
            for line in pids_output.split('\n'):
                if line.strip():
                    container_pids.append(line.strip())
            
            print(f"容器内进程PIDs: {container_pids}")
            
            success_count = 0
            for container_pid in container_pids:
                try:
                    pid_assign_cmd = f"sudo pqos -a 'pid:{cos_id}={container_pid}'"
                    subprocess.run(pid_assign_cmd, shell=True, check=True)
                    success_count += 1
                except Exception as inner_e:
                    print(f"为PID {container_pid} 分配COS失败: {inner_e}")
                    continue
            
            if success_count > 0:
                print(f"成功为 {success_count} 个进程分配了 COS{cos_id}")
                return True
                
        except Exception as e:
            print(f"批量PID分配失败: {e}")
        
        print(f"所有COS分配方法失败，容器 {container_id} 不受COS限制")
        return False

    def start(self, image, command, core, cos_id=None, detach=True, **kwargs):
        """启动容器并返回容器对象"""
        container_config = {
            'image': image,
            'command': command,
            'volumes': self.VOLUMES,
            'cpuset_cpus': core,
            'detach': detach,
            'network_mode': "host",
            'privileged': True,** kwargs
        }

        print(f"启动容器命令: {command}")
        try:
            container = self.client.containers.run(**container_config)
            print(f"容器 {container.short_id} 已启动")

            if detach and cos_id is not None:
                if self.wait_for_running(container):
                    print(f"容器就绪，分配COS{cos_id}...")
                    self.assign_to_cos(container.id, cos_id)
                else:
                    print(f"容器 {container.short_id} 启动超时")
            return container
        except docker.errors.ContainerError as e:
            print(f"容器错误（退出码 {e.exit_status}）: {e.stderr.decode('utf-8') if e.stderr else '无输出'}")
            return False
        except Exception as e:
            print(f"启动容器失败: {e}")
            return False

    def safe_remove(self, container):
        """安全停止并删除容器"""
        try:
            if container:
                container.stop(timeout=10)
                container.remove(force=True)
                print(f"容器 {container.short_id} 已清理")
        except Exception as e:
            print(f"清理容器错误: {e}")

    def cleanup_be_containers(self):
        """清理所有后台BE容器"""
        for container in self.be_containers:
            self.safe_remove(container)
        self.be_containers = []

    def run_tailbench_task(self, lc_task, benchmark):
        """运行Tailbench类型任务（masstree、xapian等）"""
        mt_threads = self.LC_threads[0]
        mt_rps = self.LC_rps[0]
        mt_duration = self.test_time
        core_ids = self.core[0].replace(",", " ")
        be_core = self.core[2]

        # 启动BE任务
        if benchmark != "baseline" and self.BE_threads > 0:
            be_cmd = f"bash {self.CONTAINER_WORK_DIR}/benchmarks/{self.benchmark_set}/script/{benchmark}.sh {self.BE_threads} {be_core}"
            be_container = self.start(
                "be_container:v1",
                be_cmd,
                be_core,
                cos_id=2,
                detach=True,
                mem_limit="16g",
                cpu_shares=512
            )
            if be_container:
                self.be_containers.append(be_container)

        # 启动LC任务
        lc_cmd = f"bash {self.CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/{lc_task}.sh {mt_threads} {mt_rps} {mt_duration} {core_ids}"
        lc_result = self.start(
            "lc_container:v1",
            lc_cmd,
            self.core[0],
            cos_id=0,
            detach=False,
            mem_limit="8g",
            cpu_shares=2048
        )

        # 清理BE容器
        self.cleanup_be_containers()
        return lc_result

    def run_standard_task(self, lc_task, benchmark):
        """运行标准任务（memcached、nginx等）"""
        lc_server_threads = self.LC_threads[0]
        lc_client_threads = self.LC_threads[1]
        lc_rps = self.LC_rps[0]
        server_core = self.core[0]
        client_core = self.core[1]
        be_core = self.core[2]
        lc_combined_core = f"{server_core},{client_core}"

        # 构建LC任务命令
        lc_cmd = f"""bash -c '
            {self.CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/server.sh {lc_server_threads} {lc_rps} {self.test_time} {server_core} &
            SERVER_PID=$!
            
            if [ {self.TASK_PORTS[lc_task]} ]; then
                timeout 60 bash -c "until nc -z 127.0.0.1 {self.TASK_PORTS[lc_task]}; do sleep 1; done"
                if [ $? -ne 0 ]; then
                    echo "服务端启动失败" >&2
                    exit 1
                fi
            fi
            
            {self.CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/client.sh {lc_client_threads} {lc_rps} {self.test_time} {len(client_core.split(','))} {client_core}
            wait $SERVER_PID
        '"""

        # 启动BE任务
        if benchmark != "baseline" and self.BE_threads > 0:
            be_cmd = f"bash {self.CONTAINER_WORK_DIR}/benchmarks/{self.benchmark_set}/script/{benchmark}.sh {self.BE_threads} {be_core}"
            be_container = self.start(
                "be_container:v1",
                be_cmd,
                be_core,
                cos_id=2,
                detach=True,
                mem_limit="16g",
                cpu_shares=512
            )
            if be_container:
                self.be_containers.append(be_container)

        # 启动LC任务
        lc_result = self.start(
            "lc_container:v1",
            lc_cmd,
            lc_combined_core,
            detach=False,
            mem_limit="8g",
            cpu_shares=2048
        )

        # 清理BE容器
        self.cleanup_be_containers()
        return lc_result

    def read_latency_metrics(self, lc_task):
        """读取并计算延迟指标"""
        latency_list_95 = []
        latency_list_99 = []
        violate_list = []
        
        # 确定线程数量
        if lc_task not in ["memcached", "nginx"]:
            thread_count = self.LC_threads[0]  # Tailbench使用第一个线程配置
        else:
            thread_count = self.LC_threads[1]  # 其他任务使用客户端线程数
        
        for n in range(thread_count):
            log_file = f"{self.HOST_WORK_DIR}/benchmarks/{lc_task}/QoS/{lc_task}_{n}.log"
            if not os.path.exists(log_file):
                print(f"警告: 日志文件 {log_file} 不存在")
                continue
            
            # 读取延迟指标（假设这些函数在config.py中定义）
            latency_95 = read_LC_latency_95(log_file)
            latency_99 = read_LC_latency_99(log_file)
            violate = read_LC_latency_violate_QoS(log_file, QoS[lc_task])
            
            latency_list_95.append(latency_95)
            latency_list_99.append(latency_99)
            violate_list.append(violate)
        
        # 计算平均值
        avg_95 = sum(latency_list_95) / len(latency_list_95) if latency_list_95 else 0.0
        avg_99 = sum(latency_list_99) / len(latency_list_99) if latency_list_99 else 0.0
        avg_violate = sum(violate_list) / len(violate_list) if violate_list else 0.0
        
        return {
            "95th_latency": avg_95,
            "99th_latency": avg_99,
            "violate_rate": avg_violate,
            "throughput": self.LC_rps[0]
        }

    def save_results(self):
        """保存测试结果到JSON文件"""
        output_filename = f"{self.HOST_WORK_DIR}/results_docker/proof/{self.LC_tasks[0]}_t{self.threads}_r{self.LC_rps[0]}_c{self.cache_ways}_m{self.memory_bandwidth_ratio}.json"
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        with open(output_filename, 'a') as f:
            json.dump(self.latency_dict, f)
            f.write('\n')  # 按行分隔JSON条目
        print(f"结果已追加至: {output_filename}")

    def run_all_tests(self):
        """运行所有配置的测试"""
        try:
            for lc_task in self.LC_tasks:
                print(f"\n=== 测试 LC 任务: {lc_task} ===")
                self.latency_dict[lc_task] = {}
                
                for benchmark in self.benchmark_list:
                    print(f"\n--- 测试组合: {lc_task} + {benchmark} ---")
                    time.sleep(5)
                    
                    # 根据任务类型选择不同的运行方法
                    if lc_task not in ["memcached", "nginx"]:
                        # 运行Tailbench类型任务
                        result = self.run_tailbench_task(lc_task, benchmark)
                    else:
                        # 运行标准任务
                        result = self.run_standard_task(lc_task, benchmark)
                    
                    if not result:
                        print("LC任务执行失败，跳过后续测试...")
                        continue
                    
                    # 读取并存储延迟指标
                    metrics = self.read_latency_metrics(lc_task)
                    self.latency_dict[lc_task][benchmark] = metrics
                    print(f"测试组合 {lc_task} + {benchmark} 完成，95th延迟: {metrics['95th_latency']:.2f} us")
            
            # 保存测试结果
            self.save_results()
            
        except KeyboardInterrupt:
            print("\n用户中断，清理容器...")
            self.cleanup_be_containers()
            for container in self.client.containers.list(all=True):
                try:
                    container.stop(timeout=10)
                    container.remove(force=True)
                except:
                    pass
            sys.exit(0)
        except Exception as e:
            print(f"致命错误: {e}", file=sys.stderr)
            self.cleanup_be_containers()
            sys.exit(1)


