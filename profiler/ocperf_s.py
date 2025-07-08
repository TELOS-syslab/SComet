import os
import json
import sys
import subprocess
import time
import signal
import re

# Use ocperf to calulate all pmu event of a benchmark set
# Benchmark set should in ../benchmark with log and script dir
# PMU event list is stored in ./events/pmu-events

EVENT_DIR = "./pmu-events"
EVENT_NUM_PER_TEST = 50

if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
else:
    print('Microbench name needed')
    exit(0)

test_time = 10
if '-t' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-t') + 1])

event_list = []

for filename in os.listdir(EVENT_DIR):
    if filename.endswith(".json") and "metrics" not in filename and 'experimental' not in filename:
        filepath = os.path.join(EVENT_DIR, filename)
        with open(filepath, 'r') as file:
            try:
                data = json.load(file)
                if "Events" in data.keys():
                    event_list += data["Events"]
            except json.JSONDecodeError as e:
                print("Error reading {}: {}".format(filepath, e))

event_list = [e for e in event_list if e.get("Deprecated") == "0"]
# event_list = [e for e in event_list if 'GE' in e["EventName"]]
print(event_list)
print(len(event_list))

benchmark_list = []
benchmark_path = '../benchmarks/' + benchmark_set
for root, dirs, files in os.walk(benchmark_path + '/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_list.append('.'.join(file.split('.')[0:-1]))
benchmark_list.sort()
print('benchmark list:')
print(benchmark_list)

'''row_miss_list = [
    '500.perlbench_r',
    '505.mcf_r',
    '507.cactuBSSN_r',
    '508.namd_r',
    '510.parest_r',
    '519.lbm_r',
    '520.omnetpp_r',
    '521.wrf_r',
    '523.xalancbmk_r',
    '526.blender_r',
    '527.cam4_r',
    '538.imagick_r',
    '541.leela_r',
    '548.exchange2_r',
]
benchmark_list = [benchmark for benchmark in benchmark_list if benchmark not in row_miss_list]'''

dummy_dict = {}
with open('/home/wjy/SComet/benchmarks/spec2017/log/dummy.log', mode='r') as dummy_f:
    dummy = dummy_f.readlines()
    for line in dummy:
        dummy_dict[line.split()[0]] = int(line.split()[-1])

for benchmark in benchmark_list:
    not_test = [1] * len(event_list)
    result = {}
    output_log = '%s/log/%s.log' % (benchmark_path, benchmark)
    subprocess.Popen('touch %s' % output_log, shell=True).wait()
    subprocess.Popen('rm -rf %s' % output_log, shell=True).wait()
    while any(not_test):
        print(f"remain: {sum(not_test)}")
        subprocess.Popen('touch temp.log', shell=True).wait()
        subprocess.Popen('rm -rf temp.log', shell=True).wait()

        instr = 'HOME=/home/wjy /home/wjy/pmu-tools/ocperf stat -I %d' % ((test_time - 1) * 1000)
        instr_print = 'HOME=/home/wjy /home/wjy/pmu-tools/ocperf stat --print '
        events = []
        msr_used = []
        for n in range(len(event_list)):
            if len(events) >= 50:
                break
            if not_test[n] == 0:
                continue
            if event_list[n].get("TakenAlone") == "0":
                if event_list[n].get("MSRIndex") == "0" or event_list[n].get("MSRIndex") == "0x00" or event_list[n].get("MSRIndex") == None:
                    not_test[n] = 0
                    events.append(event_list[n])
                elif event_list[n].get("MSRIndex") not in msr_used:
                    not_test[n] = 0
                    events.append(event_list[n])
                    msr_used.append(event_list[n].get("MSRIndex"))
                else:
                    continue
            elif len(events) == 0:
                not_test[n] = 0
                events.append(event_list[n])
                break
            else:
                break

        for event in events:
            instr = instr + " -e " + event.get("EventName")
            instr_print = instr_print + " -e " + event.get("EventName")
        instr = instr + " -o temp.log bash %s/script/%s.sh" % (benchmark_path, benchmark)


        process = subprocess.run(instr_print, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        result = process.stdout
        perf_events = []
        for full_event in result.strip().split('-e'):
            perf_events += re.split(r'name=|/', full_event.strip())
        result = {}
        for event in perf_events:
            if event in dummy_dict.keys():
                result[event] = dummy_dict[event]
        
        if len(result.values()) and sum(result.values()) == 0:
            print(f"All 0, jump {instr}")
            # print(result)
            continue

        cmd_result = subprocess.Popen(instr, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        try:
            stdout_data, stderr_data = cmd_result.communicate(timeout=1)
            if 'event syntax error' in stderr_data:
                print(f"event error, jump {instr}")
                continue
        except subprocess.TimeoutExpired:
            pass

        print(instr)
        print("waiting for perf...")
        if test_time <= 0:
            cmd_result.wait()
        else:
            time.sleep(test_time)
            print("%d second passed..." % test_time)

        os.killpg(os.getpgid(cmd_result.pid), signal.SIGTERM)
        cmd_result.wait()

        try:
            with open("temp.log", mode='r') as log_f:
                logs = log_f.readlines()
                if len(logs) - 3 == len(events):
                    for i in range(3, len(logs)):
                        if 'not' in logs[i]:
                            result[events[i - 3].get("EventName")] = 0
                        else:
                            result[events[i-3].get("EventName")] = int(logs[i].split()[1].replace(',',''))
                else:
                    for i in range(3, len(logs)):
                        if 'not supported' in logs[i]:
                            result[logs[i].split()[2]] = 0
                        else:
                            result[logs[i].split()[2]] = int(logs[i].split()[1].replace(',',''))
                subprocess.Popen('rm -rf temp.log', shell=True).wait()
        except (FileNotFoundError, IOError):
            pass
        
        with open(output_log, mode='a') as output_f:
            for r in result.keys():
                output_f.write("{:<50} {:<50}\n".format(r, result[r]))
