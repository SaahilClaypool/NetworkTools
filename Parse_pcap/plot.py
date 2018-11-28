#!/usr/bin/python3
import csv
import sys
import re
from os import listdir
from os.path import isfile, join

import matplotlib as mpl
should_show = False
if (len(sys.argv) > 4 and sys.argv[4] == "show"):
    should_show = True
else:
    mpl.use('Agg')
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



    print(f"Searching {dirname} for csv files")
    header = ["time", "throughput", "inflight", "rtt"]
    has_queue = has_router_queue(dirname)
    if (has_queue):
        header.append("queue (bytes)")
    iheader = dict(map(lambda x: (x[1], x[0] - 1), enumerate(header)))
    fig, axes = plt.subplots(nrows = len(header) - 1, ncols=1, sharex=True)
    for f in listdir(dirname):
        if (isfile(join(dirname, f)) \
                and r_pattern.search(str(f))
                and str(f) != "queue_length.csv"):
            cheader = ["inflight", "rtt"]
            if (sender in f):
                cheader = ["inflight", "rtt"]
            else:
                cheader = ["throughput"]
            plot_one(f, cheader, iheader, fig, axes, expected_points)
            f = join(dirname, f)
            print(f)
    if (has_queue):
        plot_queue("queue_length.csv", fig, axes, -1)

    for idx, h in enumerate(header[1:]):
        axes[idx].set_ylabel(h)
    axes[-1].set_xlabel("time (seconds)")
    fig.suptitle(name.replace(".png", ""), fontsize=16)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(name, dpi='figure')
    if (should_show):
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

def plot_queue(filename, fig, plots, idx):
    x = []
    y = []
    # there should be a start_time.txt file in the results
    start_time = 0
    if (isfile("start_time.txt")):
        start_time = int(open("start_time.txt", 'r').read().strip())
        print("start time: ", start_time)
    with open(filename, 'r') as csvfile:
        for line in csvfile:
            t, v = line.split(",")
            t = (float(t) * 1000 - start_time) / 1000
            v = v.strip()
            v = int(v)
            x.append(t)
            y.append(v)

    last = int(len(x) * percent_shown)
    print("x[0]", x[0])
    plots[idx].plot(x[:last], y[:last])

def has_router_queue(dirname, filename="queue_length.csv"):
    for f in listdir(dirname):
        if (isfile(join(dirname, f)) and filename == str(f)):
            return True
    return False

if __name__ == '__main__':
    main()
