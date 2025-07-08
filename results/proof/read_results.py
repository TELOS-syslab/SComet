import os
import json
import sys
import re
from scipy.stats import gmean

def read_results(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            dicts = re.findall(r'\{.*?\}', f.read())
            parsed_data = []
            for d in dicts:
                data = json.loads(d)
                broken = False
                for key, value in data.items():
                    for v in value:
                        if v[-1] >= 10:
                            broken = True
                            break
                if not broken:
                    parsed_data.append(data)
            return parsed_data
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False
    return False

result_paths = sys.argv[1]
# print(result_paths)

result = {}

if result_paths.endswith('.json'):
    dicts = read_results(result_paths)
    for key in dicts[0]:
        list_groups = [d[key] for d in dicts]
        averaged = [
            [(sum(values) / len(values),gmean(values)) for values in zip(*lists)]
            for lists in zip(*list_groups)
        ]
        result[key] = averaged
    for item in result.items():
        print(item[0], item[1])
else:
    for root, dirs, files in os.walk(result_paths):
        if root != result_paths:
            continue
        for file in files:
            result[file] = {}
            if file.split('.')[-1] == 'json':
                # print(file)
                dicts = read_results(result_paths + '/' + file)
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
              '\t','\t'.join(result20), '\t','\t'.join(result21))






