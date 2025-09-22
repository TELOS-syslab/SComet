#!/usr/bin/python3
import time
import sys
sys.path.append('/home/wjy/SComet/')
from config import *

class Container:
    image = ''
    name = ''
    ip = ''
    task = ''
    running = None
    command = None
    def __init__(self, image_, name_, ip_ = '172.17.1.119'):
        self.image = image_
        self.name = name_
        self.ip = ip_
        print(f'Container {self.name}@{self.ip} init')
        run_on_node(self.ip, f'docker stop {self.name}').wait()
        run_on_node(self.ip, f'docker rm {self.name}').wait()
        run_on_node('%s docker run -id -v /home/wjy/SComet:/home/wjy/SComet --privileged --name %s %s /bin/bash' % (self.ssh_pre(), self.name, self.image)).wait()
       
    def __repr__(self):
        return self.name + '-' + self.task

    def remove(self):
        print(f'Container {self.name}@{self.ip} remove')
        run_on_node(self.ip, f'docker stop {self.name}').wait()
        run_on_node(self.ip, f'docker rm {self.name}').wait()

    def copy_file(self, src_, dest_):
        run_on_node(self.ip, f"docker cp {self.name}:{src_} {dest_}").wait()

    def get_running_benchmark_set(self):
        return self.command.split('/')[-3]

    def get_running_task(self):
        return '.'.join(self.command.split('/')[-1].split('.')[0:-1])
    
    def get_id(self):
        process = run_on_node(f'docker ps -a | grep {self.name}')
        process.wait()
        output = process.stdout.readlines()
        return output[0].decode('utf-8').split()[0]

    def run_task(self, benchmark_set_, task_, arg_=''):
        self.task = task_
        self.run('sh /home/wjy/SComet/benchmarks/%s/script/%s.sh %s' % (benchmark_set_, task_, arg_))

    def run_accompany_task(self, benchmark_set_, task_, arg_=''):
        self.run('sh /home/wjy/SComet/benchmarks/%s/script/%s.sh %s' % (benchmark_set_, task_, arg_))

    def run(self, command_):
        self.command = command_
        print(f'Container {self.name}@{self.ip} run {self.command}')
        self.running = run_on_node(f'docker exec {self.name} sh -c "{self.command}"')




