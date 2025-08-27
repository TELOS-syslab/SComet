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

parse_results(result_paths)
'''
else:
    for root, dirs, files in os.walk(result_paths):
        if root != result_paths:
            continue
        for file in files:
            result[file] = {}
            if file.split('.')[-1] == 'json':
                # print(file)
                dicts = read_json_lines(result_paths + '/' + file)
                for key in dicts[0]:
                    list_groups = [d[key] for d in dicts]
                    averaged = [
                        [(sum(values) / len(values),gmean(values)) for values in zip(*lists)]
                        for lists in zip(*list_groups)
                    ]
                    result[file][key] = averaged
    print("filename\t", '\t'.join(list(result.values())[0].keys()), '\t', '\t'.join(list(result.values())[0].keys()))
    for file in sorted(list(result.keys())):
        result00 = [str(result[file][key][0][0][0]) for key in result[file].keys()]
        result01 = [str(result[file][key][0][0][1]) for key in result[file].keys()]
        result10 = [str(result[file][key][0][1][0]) for key in result[file].keys()]
        result11 = [str(result[file][key][0][1][1]) for key in result[file].keys()]
        result20 = [str(result[file][key][0][2][0]) for key in result[file].keys()]
        result21 = [str(result[file][key][0][2][1]) for key in result[file].keys()]
        print(file+'\t', '\t'.join(result00), '\t', '\t'.join(result01),
              '\t','\t'.join(result10), '\t','\t'.join(result11),
              '\t','\t'.join(result20), '\t','\t'.join(result21))'''






