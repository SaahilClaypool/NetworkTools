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
    header_labels = ["Time\n(sec.)", "Throughput (Mbps)", "Inflight (Kb)", "rtt\n(ms)"]
    header = ["time", "throughput", "inflight", "rtt"]
    has_queue = has_router_queue(dirname)
    if (has_queue):
        header.append("queue (bytes)")
        header_labels.append("queue\n(bytes)")
        header.append("droprate")
        header_labels.append("droprate")
    # Map the header name to the header index
    iheader = dict(map(lambda x: (x[1], x[0] - 1), enumerate(header)))
    # create a figure and axes to SHARE
    fig, axes = plt.subplots(nrows = len(header) - 1, ncols=1, sharex=True)
    # create a map of header: subfigure and axes (ex. "throughput" : (fig, axes))
    sub_figs = {}
    for h in header[1:]:
        sub_header = [h]
        sub_fig, sub_axes = plt.subplots(nrows=len(sub_header), ncols=1, sharex=True)
        sub_figs[h] = (sub_fig, sub_axes)

    all_files = []
    labels = []
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
            label = plot_one(f, cheader, iheader, fig, axes, expected_points, sub_figs)
            labels.append(label)
            f = join(dirname, f)
            print(f)
    if (has_queue):
        plot_queue("queue_length.csv", fig, axes, -2, sub_figs)
        # plot_droprate("queue_length.csv", fig, axes, -1, sub_figs)

    set_titles(all_files, fig, axes, header_labels, name, sub_figs, labels)

def fix_axis(axis, label, legend_labels):
    axis.set_ylim(bottom=0)
    axis.set_ylabel(label)
    # axis.legend(legend_labels, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    # axis.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    # axis.legend(loc="upper right", fontsize="x-small", labelspacing=.01)


def set_titles(all_files, fig, axes, header_labels, name, sub_figs, labels):
    print(f"labels are {labels}")
    plot_throughput(all_files, fig, axes, 0)
    for idx, h in enumerate(header_labels[1:]):
        fix_axis(axes[idx], h, labels)
    axes[-1].set_xlabel("Time (sec.)")
    # axes[-1].set_xlim(0, 45)
    fig.suptitle(name.replace(".png", "").replace(".svg", ""), fontsize=16)
    try:
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    except:
        pass
    fig.savefig(name, dpi='figure')
    fig.set_size_inches(9.5, 5.5)
    for (idx, (sub_header, (sub_fig, sub_plot))) in enumerate(sub_figs.items()):
        label = header_labels[idx + 1]
        fix_axis(sub_plot, label, labels)
        ext = name[-4:]
        sub_name = name.replace(".png", "").replace(".svg", "") + "_" + sub_header
        # sub_fig.suptitle(sub_name.replace("_", " "))
        sub_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        sub_fig.set_size_inches(9.5, 5.5)
        sub_fig.savefig((sub_name + ext).replace(" ", "_"), dpi=500)
        sub_plot.set_xlabel("Time (sec.)")
    if (should_show):
        plt.show()

plot_num = 0
def plot_one(filename, header, plot_indexs, fig, plots, expected_points, sub_figs):
    global plot_num
    plot_num = plot_num + 1
    print(f"plotting n = {plot_num}")
    print(f"plotting one filename is {filename}")
    time = []
    outputs = {}
    for h in header:
        outputs[h] = []

    line, sub_line = None, None
    label = clean_name(filename)
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            time.append(float(row["time"]) / 1000 - 5)
            for idx, h in enumerate(header):
                outputs[h].append(float(row[h]) / 1000)
        if (len(time) < expected_points):
            return
        for h in header:
            o = outputs[h]
            last = int(len(o) * percent_shown)
            o = o[:last]
            t = time[:last]
            line = plots[plot_indexs[h]].plot(t, o, label=label)
            sub_fig, sub_plot = sub_figs[h]
            sub_plot.plot(t, o, label=label)
            # sub_plot.hlines(y=20, xmin=0, xmax=60, colors='gray')
    return label

def plot_queue(filename, fig, plots, idx, sub_figs):
    x = []
    y = []
    # there should be a start_time.txt file in the results
    start_time = 0
    if (isfile("start_time.txt")):
        start_time = int(open("start_time.txt", 'r').read().strip())
        print("start time: ", start_time)
    with open(filename, 'r') as csvfile:
        for line in csvfile:
            parts = list(line.split(","))
            t = parts[0]
            queue_length_bytes = parts[1]
            try:
                float(t)
            except ValueError:
                continue
            t = (float(t) * 1000 - start_time) / 1000
            queue_length_bytes = queue_length_bytes.strip()
            queue_length_bytes = int(queue_length_bytes)
            x.append(t)
            y.append(queue_length_bytes)

    last = int(len(x) * percent_shown)
    plots[idx].plot(x[:last], y[:last], label="queue\nlength")
    # the sub_figs are a dictionary of title : sub_fig, sub_plot
    sub_fig, sub_plot = [i for i in sub_figs.items()][idx][1]
    sub_plot.plot(x[:last], y[:last], label="queue\nlength")


def plot_droprate(filename, fig, plots, idx, sub_figs):
    """
    Plot the drop rate for each rtt window.
    """
    x = []
    y = []
    # there should be a start_time.txt file in the results
    start_time = 0
    if (isfile("start_time.txt")):
        start_time = int(open("start_time.txt", 'r').read().strip())
        print("start time: ", start_time)

    p_sent, p_dropped = 0, 0
    with open(filename, 'r') as csvfile:
        for line in csvfile:
            parts = list(line.split(","))
            t = parts[0]
            sent = parts[2]
            dropped = parts[3]
            try:
                float(t)
            except ValueError:
                continue
            t = (float(t) * 1000 - start_time) / 1000
            sent = sent.strip()
            sent = int(sent)
            dropped = dropped.strip()
            dropped = int(dropped)

            drop_rate = 0
            if p_sent > 0 and sent != p_sent:
                drop_rate = (dropped - p_dropped) / (sent - p_sent)
            x.append(t)
            y.append(drop_rate * 100)

            p_sent, p_dropped = sent, dropped

    last = int(len(x) * percent_shown)
    plots[idx].plot(x[:last], y[:last], label=f"droprate\n percent per 500 ms")
    sub_fig, sub_plot = [i for i in sub_figs.items()][idx][1]
    sub_plot.plot(x[:last], y[:last], label="drop_rate")

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
    plt.hlines(20, xmin=0, xmax=50, colors='gray', label="fair share")
    # plots[idx].plot(time_buckets[:last], val_buckets[:last], label="total\nthroughput")

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
