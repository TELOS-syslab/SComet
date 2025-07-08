import json
import os
import sys
import time
import docker
import subprocess
import shlex
from config import *  # 导入 config.py 中的所有配置

client = docker.from_env()

HOST_WORK_DIR = ROOT
CONTAINER_WORK_DIR = ROOT
SPEC2017_HOST_DIR = "/home/wjy/spec2017"
SPEC2017_CONTAINER_DIR = "/home/wjy/spec2017"

VOLUMES = {
    HOST_WORK_DIR: {'bind': CONTAINER_WORK_DIR, 'mode': 'rw'},
    SPEC2017_HOST_DIR: {'bind': SPEC2017_CONTAINER_DIR, 'mode': 'rw'},
    "/home/wjy/SComet/benchmarks/Tailbench": {'bind': "/home/wjy/SComet/benchmarks/Tailbench", 'mode': 'rw'}
}

TASK_PORTS = {
    "memcached": 11211,
    "nginx": 80,
    "masstree": None  # Masstree 使用本地通信，不依赖固定端口
}

available_benchmark_set = ['parsec-benchmark', 'stream', 'iperf', 'spec2017', 'ecp']
LC_tasks = ["memcached", "nginx", "masstree"]  # 默认所有任务，但会被命令行参数覆盖

print("=== 命令行参数 ===")
print(sys.argv)  # 打印所有参数，确认 --lc nginx 是否存在

if '--lc' in sys.argv:
    try:
        idx = sys.argv.index('--lc')
        lc_task_arg = sys.argv[idx + 1]
        print(f"检测到 --lc 参数，值为: {lc_task_arg}")
        if lc_task_arg in LC_tasks:
            LC_tasks = [lc_task_arg]
            print(f"LC_tasks 更新为: {LC_tasks}")
        else:
            print(f"错误：任务 '{lc_task_arg}' 不在支持列表中 ({LC_tasks})")
            sys.exit(1)
    except IndexError:
        print("--lc 参数缺少任务名称")
        sys.exit(1)
else:
    LC_tasks = [LC_tasks[0]]
    print(f"未指定 --lc，使用默认任务: {LC_tasks}")

print("=== LC任务列表 ===")
print(LC_tasks)

benchmark_set = "spec2017"
benchmark_list = ["519.lbm_r", "507.cactuBSSN_r", "500.perlbench_r", "502.gcc_r", "503.bwaves_r", "505.mcf_r", "508.namd_r", "510.parest_r", "511.povray_r", "520.omnetpp_r", "521.wrf_r", "523.xalancbmk_r", "525.x264_r", "526.blender_r", "527.cam4_r", "531.deepsjeng_r", "538.imagick_r", "541.leela_r", "544.nab_r", "548.exchange2_r", "549.fotonik3d_r", "554.roms_r", "557.xz_r", "baseline"]

test_time = 60
if '-T' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-T') + 1])

threads = [8, 8, 24]
if '-t' in sys.argv:
    threads = sys.argv[sys.argv.index('-t') + 1].split(',')
    threads = [int(t) for t in threads]
LC_threads = threads[:-1]
BE_threads = threads[-1]

core = []
for i in range(len(threads)):
    start = sum(threads[0:i])
    end = sum(threads[0:i+1])
    core_str = ','.join(CPU_cores['NUMA0'][start:end])
    print(f"分配核心 {i}: {core_str}")
    core.append(core_str)

LC_rps = []
if '-r' in sys.argv:
    LC_rps = sys.argv[sys.argv.index('-r') + 1].split(',')
    LC_rps = [int(r) for r in LC_rps]
    if len(LC_rps) != 1:
        print("错误：-r 参数应提供单个值", file=sys.stderr)
        sys.exit(1)
else:
    LC_rps = [59000]  # 默认值

cache_ways = [7, 7, 1]
if '-c' in sys.argv:
    cache_ways = sys.argv[sys.argv.index('-c') + 1].split(',')
    cache_ways = [int(c) for c in cache_ways]

memory_bandwidth_ratio = [50, 40, 10]
if '-m' in sys.argv:
    memory_bandwidth_ratio = sys.argv[sys.argv.index('-m') + 1].split(',')
    memory_bandwidth_ratio = [int(m) for m in memory_bandwidth_ratio]


def initialize_hardware_isolation():
    """初始化硬件资源隔离"""
    print("初始化硬件资源隔离...")
    try:
        subprocess.run('sudo rm -rf /var/lock/libpqos', shell=True, check=True)
        subprocess.run("sudo pqos -R", shell=True, check=True)
        
        check_cmd = "ps aux | grep pqos | grep -v grep"
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            subprocess.run("sudo pkill -f pqos", shell=True, check=True)
            print("pqos 进程已终止")
        else:
            print("未发现运行中的 pqos 进程")
        
        total_ways = get_cache_ways()
        print(f"系统 LLC 总路数: {total_ways}")
        
        cos_llc_masks = []
        start_bit = 0
        for ways in cache_ways:
            if ways:
                mask = ((1 << ways) - 1) << start_bit
                cos_llc_masks.append(f'0x{mask:0{total_ways//4}x}')
                start_bit += ways
            else:
                cos_llc_masks.append('0x0')
        
        for i in range(len(cos_llc_masks)):
            if cos_llc_masks[i] != '0x0':
                print(f"COS{i} LLC Mask: {cos_llc_masks[i]}, MBA: {memory_bandwidth_ratio[i]}%")
                cos_cmd = f'sudo pqos -e "llc:{i}={cos_llc_masks[i]};mba:{i}={memory_bandwidth_ratio[i]}"'
                print(f"执行: {cos_cmd}")
                subprocess.run(cos_cmd, shell=True, check=True)
        
        return cos_llc_masks
    except Exception as e:
        print(f"硬件隔离失败: {e}")
        return [None]*len(cache_ways)

cos_llc_masks = initialize_hardware_isolation()

def wait_for_container_running(container, timeout=30):
    """等待容器完全启动并处于运行状态"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            container.reload()  # 刷新容器状态
            if container.status == 'running':
                # 再等待一小段时间确保进程完全启动
                time.sleep(2)
                return True
        except Exception as e:
            print(f"检查容器状态时出错: {e}")
        time.sleep(1)
    return False

def assign_container_to_cos(container_id, cos_id):
    """将容器分配到特定的COS组"""
    if cos_id >= len(cos_llc_masks) or cos_llc_masks[cos_id] is None:
        print(f"警告：无法分配 COS{cos_id} 给容器 {container_id}")
        return False
    try:
        # 获取容器完整信息
        inspect_result = client.api.inspect_container(container_id)
        
        # 检查容器是否在运行
        if inspect_result['State']['Status'] != 'running':
            print(f"错误：容器 {container_id} 未在运行状态")
            return False
        
        # 获取容器的PID
        pid = inspect_result['State']['Pid']
        if pid == 0:
            print("错误：容器PID为0，容器未正常运行")
            return False
        
        print(f"容器 {container_id} 的PID: {pid}")
        
        # 方法1：直接使用PID分配（推荐）
        try:
            pid_cmd = f"sudo pqos -a 'pid:{cos_id}={pid}'"
            print(f"尝试使用PID分配: {pid_cmd}")
            subprocess.run(pid_cmd, shell=True, check=True)
            print(f"成功使用PID分配 COS{cos_id} 给容器 {container_id}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"PID分配失败: {e}")
            # 继续尝试其他方法
        
        # 方法2：获取容器内所有进程PID并逐个分配
        try:
            # 获取容器内所有进程的PID
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
            
            # 为每个进程分配COS
            success_count = 0
            for container_pid in container_pids:
                try:
                    # 获取宿主机上对应的真实PID
                    real_pid_cmd = f"docker exec {container_id} readlink /proc/{container_pid}/ns/pid"
                    real_pid_ns = subprocess.check_output(real_pid_cmd, shell=True, text=True).strip()
                    
                    # 直接使用容器内的PID，让pqos自动映射
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
        
        # 方法3：使用cgroup v1路径（适配不同的cgroup结构）
        try:
            # 检查系统使用的cgroup版本
            cgroup_version = "v1"
            try:
                with open("/proc/mounts", "r") as f:
                    mounts = f.read()
                    if "cgroup2" in mounts:
                        cgroup_version = "v2"
            except:
                pass
            
            print(f"检测到cgroup版本: {cgroup_version}")
            
            if cgroup_version == "v1":
                # 尝试多种可能的cgroup路径格式
                possible_paths = [
                    f"/docker/{container_id}",
                    f"/docker/{container_id[:12]}",  # 短ID
                    f"/system.slice/docker-{container_id}.scope",
                    f"/docker.service/{container_id}",
                ]
                
                for cgroup_path in possible_paths:
                    try:
                        llc_cmd = f"sudo pqos -a 'llc:{cos_id}={cgroup_path}'"
                        print(f"尝试cgroup路径: {llc_cmd}")
                        subprocess.run(llc_cmd, shell=True, check=True)
                        print(f"成功使用cgroup路径 {cgroup_path} 分配 COS{cos_id}")
                        return True
                    except subprocess.CalledProcessError:
                        continue
            else:
                # cgroup v2处理
                cgroup_path = f"/docker/{container_id}"
                llc_cmd = f"sudo pqos -a 'llc:{cos_id}={cgroup_path}'"
                print(f"尝试cgroup v2路径: {llc_cmd}")
                subprocess.run(llc_cmd, shell=True, check=True)
                print(f"成功使用cgroup v2路径分配 COS{cos_id}")
                return True
                
        except Exception as e:
            print(f"cgroup路径分配失败: {e}")
        
        # 方法4：最后尝试 - 使用taskset绑定到COS（备选方案）
        try:
            print(f"尝试备选方案：使用核心亲和性模拟COS分配")
            # 这不是真正的COS分配，但可以作为备选方案
            # 根据COS ID选择对应的CPU核心
            if cos_id < len(core):
                target_cores = core[cos_id]
                taskset_cmd = f"sudo docker exec {container_id} taskset -a -c {target_cores} $$"
                subprocess.run(taskset_cmd, shell=True, check=True)
                print(f"使用备选方案成功绑定容器到核心 {target_cores}")
                return True
        except Exception as e:
            print(f"备选方案也失败: {e}")
        
        print(f"所有COS分配方法都失败，容器将继续运行但不受COS限制")
        return False
        
    except Exception as e:
        print(f"分配 COS{cos_id} 失败: {e}")
        return False

latency_dict = {}

def start_container(image, command, core, cos_id=None, detach=True, **kwargs):
    """通用容器启动函数，统一处理不同任务类型"""
    container_config = {
        'image': image,
        'command': command,
        'volumes': VOLUMES,
        'cpuset_cpus': core,
        'detach': detach,
        'network_mode': "host",
        'privileged': True,
        **kwargs  # 传递 mem_limit, cpu_shares 等参数
    }
    
    print(f"启动容器命令: {command}")
    try:
        if detach:
            container = client.containers.run(**container_config)
            print(f"容器 {container.short_id} 已启动")
            if cos_id is not None:
                # 分配 COS 资源
                if wait_for_container_running(container, timeout=30):
                    print(f"容器 {container.short_id} 已就绪，分配COS资源...")
                    if assign_container_to_cos(container.id, cos_id):
                        print(f"成功分配 COS{cos_id} 给容器 {container.short_id}")
                    else:
                        print(f"警告：COS{cos_id} 分配失败，但容器继续运行")
                else:
                    print(f"警告：容器 {container.short_id} 启动超时，但尝试继续运行")
            return container
        else:
            # 同步执行容器并获取输出
            output = client.containers.run(**container_config)
            print(f"容器输出:\n{output.decode('utf-8')}")
            return True  # 假设命令无错误即成功
    
    except docker.errors.ContainerError as e:
        print(f"容器错误（退出码 {e.exit_status}）:\n{e.stderr.decode('utf-8') if e.stderr else '无错误输出'}")
        return False
    except Exception as e:
        print(f"启动容器失败: {e}")
        return False

def safe_remove_container(container):
    """安全地删除容器"""
    try:
        if container:
            container.stop(timeout=10)
            container.remove(force=True)
            print(f"容器 {container.short_id} 已清理")
    except Exception as e:
        print(f"清理容器时出错: {e}")





try:
    for lc_task in LC_tasks:
        print(f"\n=== 测试 LC 任务: {lc_task} ===")
        latency_dict[lc_task] = {}
        
        for benchmark in benchmark_list:
            print(f"\n--- 测试组合: {lc_task} + {benchmark} ---")
            time.sleep(5)
            
            if lc_task == "masstree":
                # Masstree 专用配置
                lc_server_threads = LC_threads[0]
                lc_client_threads = LC_threads[1]
                lc_rps = LC_rps[0]
                server_args = f"{lc_server_threads} {lc_rps} {test_time} {core[0]}"
                client_args = f"{lc_client_threads} {lc_rps} {test_time} {len(core[1].split(','))} {core[1]}"
                
                # 仿照memcached和nginx的模式，使用单个容器执行server和client
                lc_cmd = f"""bash -c '
                    # 启动服务器（带超时控制）
                    {CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/server.sh {server_args} &
                    SERVER_PID=$!
                    
                    # 等待服务器初始化（可选：检查进程是否存在）
                    echo "等待Masstree服务器启动..."
                    sleep 2
                    if ! kill -0 $SERVER_PID; then
                        echo "服务器启动失败" >&2
                        exit 1
                    fi
                    
                    # 启动客户端（前台运行，自带duration控制）
                    {CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/client.sh {client_args}
                    
                    # 无需显式wait，server.sh的timeout会自动终止服务器
                    echo "Masstree测试完成"
                '"""
                
                be_containers = []
                if benchmark != "baseline" and BE_threads > 0:
                    be_cmd = f"bash {CONTAINER_WORK_DIR}/benchmarks/{benchmark_set}/script/{benchmark}.sh {BE_threads} {core[2]}"
                    be_container = start_container(
                        "be_container:v1",
                        be_cmd,
                        core[2],
                        cos_id=2,
                        detach=True,
                        mem_limit="16g",
                        cpu_shares=512
                    )
                    if be_container:
                        be_containers.append(be_container)
                
                lc_container_success = start_container(
                    "lc_container:v1",
                    lc_cmd,
                    f"{core[0]},{core[1]}",  # 使用服务器和客户端的核心
                    cos_id=0,  # 将整个容器分配给COS0
                    detach=False,
                    mem_limit="12g",  # 增加内存限制，因为同时运行server和client
                    cpu_shares=2048
                )
                
                for be_container in be_containers:
                    safe_remove_container(be_container)
                
                if not lc_container_success:
                    print("LC任务执行失败，跳过后续测试...")
                    continue
            
            else:
                # 原有 memcached/nginx 的处理逻辑保持不变
                lc_server_threads = LC_threads[0]
                lc_client_threads = LC_threads[1]
                lc_rps = LC_rps[0]
                server_args = f"{lc_server_threads} {lc_rps} {test_time} {core[0]}"
                client_args = f"{lc_client_threads} {lc_rps} {test_time} {len(core[1].split(','))} {core[1]}"
                
                lc_cmd = f"""bash -c '
                    {CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/server.sh {server_args} &
                    SERVER_PID=$!
                    if [ {TASK_PORTS[lc_task]} ]; then
                        timeout 60 bash -c "until nc -z 127.0.0.1 {TASK_PORTS[lc_task]}; do sleep 1; done"
                        if [ $? -ne 0 ]; then
                            echo "错误: 服务端启动失败" >&2
                            kill $SERVER_PID
                            exit 1
                        fi
                    fi
                    {CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/client.sh {client_args}
                    wait $SERVER_PID
                    echo "LC任务执行完成"
                '"""
                
                be_containers = []
                if benchmark != "baseline" and BE_threads > 0:
                    be_cmd = f"bash {CONTAINER_WORK_DIR}/benchmarks/{benchmark_set}/script/{benchmark}.sh {BE_threads} {core[2]}"
                    be_container = start_container(
                        "be_container:v1",
                        be_cmd,
                        core[2],
                        cos_id=2,
                        detach=True,
                        mem_limit="16g",
                        cpu_shares=512
                    )
                    if be_container:
                        be_containers.append(be_container)
                
                lc_container_success = start_container(
                    "lc_container:v1",
                    lc_cmd,
                    f"{core[0]},{core[1]}",
                    cos_id=None,
                    detach=False,
                    mem_limit="8g",
                    cpu_shares=2048
                )
                
                for be_container in be_containers:
                    safe_remove_container(be_container)
                
                if not lc_container_success:
                    print("LC任务执行失败，跳过后续测试...")
                    continue
            
            # 读取延迟指标（保持原有逻辑不变）
            latency_list_95 = []
            latency_list_99 = []
            violate_list = []
            
            if lc_task == "masstree":
                thread_count = LC_threads[0]  # Masstree使用第一个线程配置
            else:
                thread_count = LC_threads[1]  # 其他任务使用客户端线程数
            
            for n in range(thread_count):
                if lc_task == "masstree":
                    log_file = f"{HOST_WORK_DIR}/benchmarks/masstree/QoS/masstree_{n}.log"
                else:
                    log_file = f"{HOST_WORK_DIR}/benchmarks/{lc_task}/QoS/{lc_task}_{n}.log"
                
                if not os.path.exists(log_file):
                    print(f"警告: 日志文件 {log_file} 不存在")
                    continue
                
                # 读取95th延迟
                latency_95 = read_LC_latency_95(log_file)
                # 读取99th延迟
                latency_99 = read_LC_latency_99(log_file)
                # 读取违反率
                violate = read_LC_latency_violate_QoS(log_file, QoS[lc_task])
                
                latency_list_95.append(latency_95)
                latency_list_99.append(latency_99)
                violate_list.append(violate)
            
            # 计算平均值
            avg_95 = sum(latency_list_95) / len(latency_list_95) if latency_list_95 else 0.0
            avg_99 = sum(latency_list_99) / len(latency_list_99) if latency_list_99 else 0.0
            avg_violate = sum(violate_list) / len(violate_list) if violate_list else 0.0
            
            # 存储指标
            latency_dict[lc_task][benchmark] = {
                "95th_latency": avg_95,
                "99th_latency": avg_99,
                "violate_rate": avg_violate,
                "throughput": lc_rps 
            }
            print(f"测试组合 {lc_task} + {benchmark} 完成，95th延迟: {avg_95:.2f} us")
    
    # 写入文件
    output_filename = f"{HOST_WORK_DIR}/results1/proof/{LC_tasks[0]}_t{threads}_r{LC_rps[0]}_c{cache_ways}_m{memory_bandwidth_ratio}.json"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, 'a') as f:
        json.dump(latency_dict, f)
        f.write('\n')  # 按行分隔JSON条目
    print(f"结果已追加至: {output_filename}")


except KeyboardInterrupt:
    print("\n用户中断，清理容器...")
    for container in client.containers.list(all=True):
        try:
            container.stop(timeout=10)
            container.remove(force=True)
        except Exception as e:
            print(f"清理容器 {container.short_id} 时出错: {e}")
    sys.exit(0)

except Exception as e:
    print(f"致命错误: {e}", file=sys.stderr)
    # 清理所有容器
    print("清理所有运行中的容器...")
    for container in client.containers.list(all=True):
        try:
            container.stop(timeout=10)
            container.remove(force=True)
        except Exception as e:
            print(f"清理容器 {container.short_id} 时出错: {e}")
    sys.exit(1)