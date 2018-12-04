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
    header_labels = ["time\n(seconds)", "throughput\n(mbit / second)", "inflight\n(bytes)", "rtt\n(ms)"]
    header = ["time", "throughput", "inflight", "rtt"]
    has_queue = has_router_queue(dirname)
    if (has_queue):
        header.append("queue (bytes)")
        header_labels.append("queue\n(bytes)")
    iheader = dict(map(lambda x: (x[1], x[0] - 1), enumerate(header)))
    fig, axes = plt.subplots(nrows = len(header) - 1, ncols=1, sharex=True)
    all_files = []
    for f in listdir(dirname):
        if (isfile(join(dirname, f)) \
                and r_pattern.search(str(f))
                and str(f) != "queue_length.csv"):
            all_files.append(f)
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

    plot_throughput(all_files, fig, axes, 0)
    for idx, h in enumerate(header_labels[1:]):
        axes[idx].set_ylabel(h)
        axes[idx].legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    axes[-1].set_xlabel("time (seconds)")
    # axes[-1].set_xlim(0, 45)
    fig.suptitle(name.replace(".png", ""), fontsize=16)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    # fig.savefig(name, dpi='figure')
    fig.set_size_inches(9.5, 5.5)
    fig.savefig(name, dpi=500)
    if (should_show):
        plt.show()

def plot_one(filename, header, plot_indexs, fig, plots, expected_points):
    print(f"plotting one filename is {filename}")
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
            plots[plot_indexs[h]].plot(t, o, label=clean_name(filename))

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
    plots[idx].plot(x[:last], y[:last], label="queue\nlength")

def has_router_queue(dirname, filename="queue_length.csv"):
    for f in listdir(dirname):
        if (isfile(join(dirname, f)) and filename == str(f)):
            return True
    return False

def clean_name(filename):
    # all files are prot_pi@bah_port.csv
    r_pattern = re.compile(r"(?P<prot>.*)_(?P<type>.*)@.*_(?P<port>[0-9]*).csv")
    search = r_pattern.search(filename)
    protocol = search['prot']
    port = search['port']
    cleanname = f"{protocol}-{search['type']}"
    print("matching", filename, "as", cleanname)
    return cleanname

def plot_throughput(files, fig, plots, idx):
    all_tps = [] # list of (times, tps)
    for filename in files:
        if (sender in filename):
            times, tps = [], []
            with open(filename, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                     t = float(row["time"]) / 1000
                     tp = float(row["throughput"])
                     times.append(t)
                     tps.append(tp)
                expected_points = 50
                if (len(times) > expected_points):
                    all_tps.append((times, tps))
    all_tps.sort(key=lambda tps: tps[0][0])
    time_buckets = []
    val_buckets = []
    for t, v in zip(all_tps[0][0], all_tps[0][1]):
        time_buckets.append(t)
        val_buckets.append(v)
    for ts, tps in all_tps[1:]:
        for t, tp in zip(ts, tps):
            if (t > time_buckets[-1]):
                break
            closest_index = closest_time(t, time_buckets)
            val_buckets[closest_index] += tp
    last = int(len(time_buckets) * percent_shown)
    plots[idx].plot(time_buckets[:last], val_buckets[:last], label="total\nthroughput")

def closest_time(time, times):
    """return index of the closest"""
    min_dist = 1000
    min_dist_i = 0
    for i, t in enumerate(times):
        dist = abs(time - t)
        if (dist < min_dist):
            min_dist = dist
            min_dist_i = i
        if t > time:
            break
    return min_dist_i

if __name__ == '__main__':
    main()
