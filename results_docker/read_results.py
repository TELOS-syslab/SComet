import os
import json
import sys
import re
from scipy.stats import gmean

import json
from scipy.stats import gmean
from collections import defaultdict
import pprint

def read_json_lines(path):
    with open(path, 'r') as f:
        return [json.loads(line) for line in f if line.strip()]

result_paths = sys.argv[1]
# LC_task = sys.argv[2]

def parse_results(result_paths):
    dicts = read_json_lines(result_paths)

    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for d in dicts:
        for app, benchmarks in d.items():
            for bench, metrics in benchmarks.items():
                for metric, value in metrics.items():
                    agg[app][bench][metric].append(float(value))

    result = {}
    for app, benchmarks in agg.items():
        result[app] = {}
        for bench, metrics in benchmarks.items():
            result[app][bench] = {}
            for metric, values in metrics.items():
                avg = sum(values) / len(values)
                gmn = gmean(values)
                result[app][bench][metric] = (avg, gmn)

    pprint.pprint(result)
    return result[list(result.keys())[0]]


if result_paths.endswith('.json'):
    parse_results(result_paths)
else:
    total_result = {}
    for root, dirs, files in os.walk(result_paths):
        if root != result_paths:
            continue
        for file in files:
            if file.split('.')[-1] == 'json':
                print(file)
                total_result[file] = parse_results(result_paths + '/' + file)

    for file in sorted(list(total_result.keys())):
        result = [key.ljust(20) for key in total_result[file].keys()]
        print('benchmark' + '\t', ''.join(result))
        break
    for file in sorted(list(total_result.keys())):
        result = [str(total_result[file][key]['99th_latency'][1]).ljust(20) for key in total_result[file].keys()]
        print(file+'\t',''.join(result))






