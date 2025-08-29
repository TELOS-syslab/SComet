#!/usr/bin/python3
import time
import sys

sys.path.append('/home/wjy/SComet/')
from config import *


class Container:
    def __init__(self, image_, name_, index_, ip_, cos_):
        self.image = image_
        self.name = name_
        self.index = index_
        self.ip = ip_
        self.benchmark_set = ''
        self.task = ''
        self.running = None
        self.commands = None
        run_on_node(self.ip, f'docker stop {self.name}').wait()
        run_on_node(self.ip, f'docker rm {self.name}').wait()

        command = f'docker run -id -v /home/wjy/SComet:/home/wjy/SComet --privileged --name {self.name} {self.image} /bin/bash'
        proc = run_on_node(self.ip, command)
        out, err = proc.communicate()
        self.id = out.decode().strip()

        out, err = run_on_node(self.ip, f"docker inspect -f '{{{{.State.Pid}}}}' {self.id}").communicate()
        self.pid = int(out.decode().strip())

        print(f"Container {self.name}@{self.ip} ID: {self.id}, PID: {self.pid}")

        self.cos = f"COS{cos_}"
        run_on_node(self.ip, f"sudo mkdir -p /sys/fs/cgroup/cpuset/{self.cos}").wait()
        run_on_node(self.ip, f"echo 0 | sudo tee /sys/fs/cgroup/cpuset/{self.cos}/cpuset.mems").wait()
        run_on_node(self.ip, f"echo 1 | sudo tee /sys/fs/cgroup/cpuset/{self.cos}/cgroup.clone_children").wait()
        run_on_node(self.ip, f"echo {self.pid} | sudo tee /sys/fs/cgroup/cpuset/{self.cos}/tasks").wait()
        run_on_node(self.ip, f"sudo mkdir -p /sys/fs/resctrl/{self.cos}").wait()
        run_on_node(self.ip, f"echo 1 | sudo tee /sys/fs/resctrl/{self.cos}/cgroup.clone_children").wait()
        run_on_node(self.ip, f"echo {self.pid} | sudo tee /sys/fs/resctrl/{self.cos}/tasks").wait()
        print(f"[{self.name}@{self.ip}] bind to COS {self.cos}")

    def __repr__(self):
        return f"[{self.name}@{self.ip}]: {self.task}"

    def remove(self):
        print(f'Container {self.name}@{self.ip} remove')
        run_on_node(self.ip, f'docker stop {self.name}').wait()
        run_on_node(self.ip, f'docker rm {self.name}').wait()

    def copy_from_container(self, src_, dest_):
        os.makedirs(os.path.dirname(dest_), exist_ok=True)
        cmd = f'docker cp "{self.name}:{src_}" "{dest_}"'
        try:
            ret = run_on_node(self.ip, cmd).wait()
            if ret != 0:
                print(f"[Warning] Failed to copy from container: {cmd}, exit code {ret}")
        except Exception as e:
            print(f"[Warning] Exception when copying from container: {cmd}, error: {e}")

    def copy_to_container(self, src_, dest_):
        container_dir = os.path.dirname(dest_)
        mkdir_cmd = f'docker exec {self.name} mkdir -p {container_dir}'
        try:
            run_on_node(self.ip, mkdir_cmd).wait()
        except Exception as e:
            print(f"[Warning] Failed to create directory in container: {mkdir_cmd}, error: {e}")

        cmd = f'docker cp "{src_}" "{self.name}:{dest_}"'
        try:
            ret = run_on_node(self.ip, cmd).wait()
            if ret != 0:
                print(f"[Warning] Failed to copy to container: {cmd}, exit code {ret}")
        except Exception as e:
            print(f"[Warning] Exception when copying to container: {cmd}, error: {e}")
    
    def get_running_benchmark_set(self):
        return self.benchmark_set

    def get_running_task(self):
        return self.task

    def run_task(self, benchmark_set_, task_, commands):
        self.task = task_
        self.benchmark_set = benchmark_set_
        if isinstance(commands, str):
            commands = [commands]
        self.commands = commands

        self.run(commands[0])
        for command in commands[1:]:
            self.run(command, False)

    def run(self, command_, update_running=True):
        print(f'Container {self.name}@{self.ip} run {command_}')
        if update_running:
            self.running = run_on_node(self.ip, f'docker exec {self.name} sh -c "{command_}"')

    def assign_cpu_cores(self, cores):
        core_list = ",".join(map(str, cores))
        run_on_node(self.ip, f"echo {core_list} | sudo tee /sys/fs/cgroup/cpuset/{self.cos}/cpuset.cpus").wait()
        print(f"[{self.name}@{self.ip}] COS {self.cos} CPU allocation: {core_list}")

    def assign_llc_mbw(self, llc_mask, mbw_percent):
        schemata_line = f"L3:{llc_mask} MB:{mbw_percent}"
        run_on_node(self.ip, f"echo {schemata_line} | sudo tee /sys/fs/resctrl/{self.cos}/schemata").wait()
        print(f"[{self.name}@{self.ip}] COS {self.cos} LLC and MBW allocation: LLC={llc_mask}, MBW={mbw_percent}%")


