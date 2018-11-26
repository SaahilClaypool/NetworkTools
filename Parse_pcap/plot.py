#!/usr/bin/python3
import csv
import sys
import re
from os import listdir
from os.path import isfile, join

import matplotlib.pyplot as plt

sender = "churro"
receiver = "tarta"
percent_shown = .9

def main():
    if (len(sys.argv) < 4):
        print("enter more args")
        print("""\
1: directory
2: name part
3. name
4. should_show (blank if false)
""")
        exit(1)
    print(sys.argv)
    dirname = sys.argv[1]
    r_pattern = re.compile(".*{}.*csv".format(sys.argv[2]))
    name = sys.argv[3]
    print(r_pattern)


    expected_points = 50
    if (len(sys.argv) > 5):
        expected_points = int(sys.argv[5])



    files = []
    header = ["time", "throughput", "inflight", "rtt"]
    iheader = dict(map(lambda x: (x[1], x[0] - 1), enumerate(header)))
    fig, axes = plt.subplots(nrows = len(header) - 1, ncols=1)
    for f in listdir(dirname):
        if (isfile(join(dirname, f)) and r_pattern.search(str(f))):
            cheader = ["inflight", "rtt"]
            if (sender in f):
                cheader = ["inflight", "rtt"]
            else:
                cheader = ["throughput"]
            plot_one(f, cheader, iheader, fig, axes, expected_points)
            f = join(dirname, f)
            print(f)
    
    for idx, h in enumerate(header[1:]):
        axes[idx].set_ylabel(h)
        print("setting label to ", h)
    axes[-1].set_xlabel("time (seconds)")
    fig.suptitle(name)
    # plt.ylabel("throughput (mbps)")
    # if (len(sys.argv) > 5):
    #     plt.ylabel(sys.argv[5])
    # plt.xlabel("time (s)")
    # if (len(sys.argv) > 6):
    #     plt.xlabel(sys.argv[6])
    # plt.title(name)
    # plt.ylim(ymin=0)
    fig.savefig(name, dpi='figure')
    if (len(sys.argv) > 4 and sys.argv[4] == "show"):
        plt.show()

def plot_one(filename, header, plot_indexs, fig, plots, expected_points):
    time = []
    outputs = {}
    for h in header:
        outputs[h] = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            time.append(float(row["time"]) / 1000)
            for idx, h in enumerate(header):
                outputs[h].append(float(row[h]))
        if (len(time) < expected_points):
            return
        for h in header:
            o = outputs[h]
            last = int(len(o) * percent_shown)
            o = o[:last]
            t = time[:last]
            plots[plot_indexs[h]].plot(t, o)

if __name__ == '__main__':
    main()
