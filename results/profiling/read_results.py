import json
import sys
from scipy.stats import gmean

filename = sys.argv[1]

all_dicts = []
with open(filename, "r") as f:
    for line in f:
        line = line.strip()
        if line:
            obj = json.loads(line)
            all_dicts.append(obj)

# print(all_dicts)

def list_unfold(lists):
    result = []
    for l in lists:
        # print(l)
        if isinstance(l, (str, int, float)):
            result.append(l)
        elif isinstance(l, (list)):
            result += list_unfold(l)
        else:
            print('error in unfold, type unknown ', type(l))
            exit(0)
    return result


for dict in all_dicts:
    for bench, val in dict.items():
        dict[bench] = list_unfold(val)

for bench in all_dicts[0].keys():
    print(bench, [dict[bench][2] for dict in all_dicts])

result = {}
for key in all_dicts[0]:
    list_groups = [d[key] for d in all_dicts]
    averaged = [
        [(sum(lists) / len(lists), gmean(lists)) for lists in zip(*list_groups)]
    ]
    result[key] = averaged
for item in result.items():
    print(f"{item[0]:<20} {item[1][0][1][0]:<20} {item[1][0][1][1]:<20} {item[1][0][2][0]:<20} {item[1][0][2][1]:<20} {item[1][0][3][0]:<20} {item[1][0][3][1]:<20}")

    
