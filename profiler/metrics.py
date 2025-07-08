import re
import json
import sys
import glob
import os

def calculate_metric(formula, events, constants):
    try:
        return eval(formula, {**events, **constants})
    except Exception as e:
        # print("Error calculating formula {}: {}".format(formula, e))
        return None


log_dir = '/home/wjy/SComet/benchmarks/spec2017/log'
metrics_path = "/home/wjy/SComet/profiler/pmu-events/sapphirerapids_metrics.json"

if len(sys.argv) > 1:
    log_dir = sys.argv[1]

log_files = glob.glob(os.path.join(log_dir, '*.log'))

for log_path in log_files:
    if 'metric' in log_path or 'dummy' in log_path or 'analysis' in log_path:
        continue
    print(log_path)
    raw_events = {}
    metrics = []
    with open(log_path, 'r') as log_f:
        for line in log_f:
            raw_events[line.split()[0]] = float(line.split()[1])
    with open(metrics_path, 'r') as metrics_f:
        data = json.load(metrics_f)
        metrics = data.get("Metrics", [])

    constants = {
        "SYSTEM_TSC_FREQ": 2000000000,
        "20": 20,
        "CORES_PER_SOCKET": 	56,
        "SOCKET_COUNT": 1,
        "HYPERTHREADING_ON": 0,
        "THREADS_PER_CORE": 1,
        "DURATIONTIMEINMILLISECONDS": 5000,
        "system.sockets[0].cpus.count * system.socket_count": 56,
    }

    None_event = []
    None_constant = []

    with open(log_path.split('.log')[0] + '_metrics.log', 'w') as log_f:
        for metric in metrics:
            metric_events = {}
            for event in metric["Events"]:
                event_name = event.get("Name", "").split(":")[0]
                if 'UNC_IIO_PAYLOAD_BYTES_IN.MEM_READ.PART' in event_name or 'UNC_IIO_PAYLOAD_BYTES_IN.MEM_WRITE.PART' in event_name:
                    event_name = event_name.replace('UNC_IIO_PAYLOAD_BYTES_IN', 'UNC_IIO_DATA_REQ_OF_CPU')
                alias = event.get("Alias", "")
                metric_events[alias] = raw_events.get(event_name)
                if not metric_events[alias] and (event_name.lower().replace('.','_') + '_0') in raw_events.keys():
                    metric_events[alias] = 0
                    for i in range(100):
                        metric_events[alias] += raw_events.get(event_name.lower().replace('.','_') + '_%d' % i, 0)
                if metric_events[alias] == None and event_name not in None_event:
                    None_event.append(event_name)

            metric_constants = {}
            for constant in metric["Constants"]:
                constant_name = constant.get("Name", "")
                alias = constant.get("Alias", "")
                metric_constants[alias] = constants.get(constant_name)
                if not metric_constants[alias] and constant_name not in None_constant:
                    None_constant.append(constant_name)

            formula = metric["Formula"]
            result = calculate_metric(formula, metric_events, metric_constants)
            if result != None:
                # print("{} {}".format(metric['MetricName'], result))
                log_f.write(f"{metric['MetricName']} {result}\n")

# if None_event:
#    print(metric['MetricName'], None_event)

