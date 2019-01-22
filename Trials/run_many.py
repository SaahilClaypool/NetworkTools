#!/usr/bin/python3
""" 
Run an trial with an increasing buffer size
Layout:
- Dynamic Buffers
    - python script
    - notes
    - Data
        - ExperimentConfigA
            - config.json
            - Trial_byte_number
                - tbf.sh: generated for each trial
"""
import os
import argparse
import csv
import matplotlib as mpl
import json 
from collections import defaultdict

should_show = False

colors = {
    "bbr": "blue",
    "bbrshallow": "blue",
    "cubic": "orange"
}

min_bytes = 100000
max_bytes = 500000
steps = 40
trial_time = 300
trial_number = 2
throughput_mbit = 80
delay_ms = 10


executable = "/home/saahil/raspberry/rpi/Experiments/run.py "

tbf_string = """\
sudo tc qdisc del dev enp3s0 root
sleep 5
sudo tc qdisc add dev enp3s0 root handle 1:0 netem delay {delay}ms limit 5000
sudo tc qdisc add dev enp3s0 parent 1:1 handle 10: tbf rate {throughput}mbit buffer 1mbit limit 10000mbit
sudo tc qdisc add dev enp3s0 parent 10:1 handle 100: tbf rate {throughput}mbit burst .05mbit limit {buffer}b
sudo tc -s qdisc ls dev enp3s0
"""

sub_folders = [
    # "40_BBR_vs_Cubic_2",
    # "80_BBR_vs_Cubic_2",
    # "120_BBR_vs_Cubic_2",
    # "40_BBR_vs_Cubic_4",
    # "80_BBR_vs_Cubic_4",
    # "120_BBR_vs_Cubic_4",
    # "40_BBR_vs_Cubic_8",
    # "80_BBR_vs_Cubic_8",
    # "120_BBR_vs_Cubic_8",
    # "40_BBR_2",
    # "80_BBR_2",
    # "120_BBR_2",
    # "40_BBR_4",
    # "80_BBR_4",
    # "120_BBR_4",
    # "40_BBR_8",
    # "80_BBR_8",
    # "120_BBR_8",
    # "40_BBR_shallow_4",
    # "80_BBR_shallow_4",
    # "120_BBR_shallow_4",
    "40_BBR_vs_Cubic_shallow_4",
    "80_BBR_vs_Cubic_shallow_4",
    "120_BBR_vs_Cubic_shallow_4",
]
# sub_folders = ["BBR", "Cubic", "BBR_vs_Cubic"]
# sub_folders = ["BBR"]


def bytes_to_mbits(b):
    return b / 125000


def bytes_to_mbytes(b):
    return b / 1000000


def mbits_to_bytes(b):
    return b * 125000


def mbytes_to_bytes(b):
    return b * 1000000


def get_bytes(min_bytes=min_bytes, max_bytes=max_bytes, steps=steps):
    for bytes in [min_bytes + i * (max_bytes - min_bytes) / steps
                  for i in range(steps + 1)]:
        yield int(bytes)

def frac_bdp_to_bytes(point):
    print(f"point: {point}")
    # bdp = calc_bdp --> bdp in mbytes / second
    bdp_m_s = calc_bdp(delay_ms + 1)
    bdp_bytes_s = mbytes_to_bytes(bdp_m_s)
    return int(bdp_bytes_s * point)


def generate_sub_experiments(folders=sub_folders, remove=False):
    """
    for each given folder, make a new experiment by copying the config.json
    in that folder into a new sub_folder suffixed with the byte amount
    and a token bucket filter file with the given byte config

    yeild a bunch of experiment folders (full paths)
    """
    global trial_number, trial_time, throughput_mbit, delay_ms, max_bytes, min_bytes
    counter = 0
    all_folders = []
    byte_steps = [i for i in get_bytes()]
    for folder in folders:
        experiment_folders = []
        folder = "/".join(["Data", folder])
        config = "/".join([folder, "config.json"])
        byte_steps = load_config(folder)
        if (remove):
            remove_cmd = f"rm -rf {folder}/Trial*"
            print(remove_cmd)
            os.system(remove_cmd)

        print("byte steps", byte_steps)
        for byte in byte_steps:
            for trial in range(trial_number):
                new_folder = "/".join([folder, f"Trial_{byte}_{trial}"])
                counter = counter + 1
                print("on folder: ", new_folder, counter)
                if (os.path.isdir(new_folder)):
                    if (remove):
                        os.system(f"rm -rf {new_folder}")
                        os.mkdir(new_folder)
                else:
                    os.mkdir(new_folder)

                os.system(f"cp {config} {new_folder}")
                tbf = tbf_string.format(
                    buffer=byte, throughput=throughput_mbit, delay=delay_ms)
                tbf_file = "/".join([new_folder, "tbf.sh"])
                with open(tbf_file, 'w') as f:
                    print(tbf, file=f)
                experiment_folders.append(new_folder)
        all_folders.append((folder, experiment_folders))
    return all_folders


def run_sub_experiments(experiment_folders, parse=False, plot=False):
    global executable, trial_time
    for experiment_folder in experiment_folders:
        run_cmd = f"{executable} result --directory {experiment_folder} --time {trial_time} --rerun"
        if (parse):
            run_cmd = f"{executable} result --directory {experiment_folder} --time {trial_time} --parse"
        if (plot):
            run_cmd = f"{executable} result --directory {experiment_folder} --time {trial_time}"
        os.system(run_cmd)


def get_drop_rate(queue_file):
    """
    get the drop rate from the given queue file.
    """
    with open(queue_file) as csvfile:
        reader = csv.DictReader(csvfile, skipinitialspace=True)
        rows = [row for row in reader]
        startup_cutoff = int(0.50 * len(rows))
        end_cutoff = int(0.85 * len(rows))
        sent = float(rows[end_cutoff]['sent']) - \
            float(rows[startup_cutoff]['sent'])
        drops = float(rows[end_cutoff]['drops']) - \
            float(rows[startup_cutoff]['drops'])
        drop_rate = drops / sent
        return drop_rate * 100


def get_average_throughput(tp_file, start=.5, end=.8):
    """
    get the average, q1, q3 throughput of the flow between start and end percent
    """
    with open(tp_file) as csvfile:
        reader = csv.DictReader(csvfile, skipinitialspace=True)
        rows = [row for row in reader]
        rows = rows[int(len(rows) * start): int(len(rows) * end)]
        tps = list(map(lambda el: int(el['throughput']), rows))
        q1 = percentile(tps, 25)
        q3 = percentile(tps, 75)
        total = sum(tps) / len(rows)

    return total, q1, q3


def plot_experiments(folder, experiment_folders):
    """
    For each folder,
    get the drop rate (dropped / sent) at 99\% - 1\% to cut off
    the startup
    """
    print(f"Loading config from {folder}")
    load_config(folder)
    queue_size = []
    drop_rates = []
    throughputs = {}
    t_q1 = {}
    t_q3 = {}

    for experiment_folder in experiment_folders:
        basename = os.path.basename(experiment_folder)
        _, byte, trial = basename.split("_")
        queue_file = "/".join([experiment_folder, "Results/queue_length.csv"])
        queue_size.append(int(byte))

        # Drop Rate
        drop_rate = get_drop_rate(queue_file)
        drop_rates.append(drop_rate)
        # Relative Throughput
        # Find all csv files ignoring queue length
        result_directory = "/".join([experiment_folder, "Results"])
        current_throughputs = {}
        for tp_file in os.listdir(result_directory):
            if tp_file.endswith(".csv") and tp_file != "queue_length.csv" and "tarta" in tp_file:
                protocol, machine, _ = tp_file.split("_")
                tp = (os.path.join(result_directory, tp_file))
                if not protocol in current_throughputs.keys():
                    current_throughputs[protocol] = []
                current_throughputs[protocol].append(
                    get_average_throughput(tp))

        for protocol, values in current_throughputs.items():
            tps, s_q1, s_q3 = [], [], []
            for tp, q1, q3 in values:
                tps.append(tp)
                s_q1.append(q1)
                s_q3.append(q3)
            total = sum(tps)  # / len(tps)
            total_q1 = sum(s_q1)  # / len(tps)
            total_q3 = sum(s_q3)  # / len(tps)

            if not protocol in throughputs.keys():
                throughputs[protocol] = []
            throughputs[protocol].append(total)

            if not protocol in t_q1.keys():
                t_q1[protocol] = []
            t_q1[protocol].append(total_q1)

            if not protocol in t_q3.keys():
                t_q3[protocol] = []
            t_q3[protocol].append(total_q3)

    queue_size = list(map(bytes_to_mbytes, queue_size))
    protocol_map = average_over_trials(queue_size, throughputs, t_q1, t_q3, drop_rates)
    throughputs = defaultdict(list)
    t_q1 = defaultdict(list)
    t_q3 = defaultdict(list)
    queue_size = []
    drop_rates = []
    for protocol, results in protocol_map.items():
        queue_size = []
        drop_rates = []
        for result in results:
            queue_size.append(result[0])
            throughputs[protocol].append(result[1])
            t_q1[protocol].append(result[2])
            t_q3[protocol].append(result[3])
            drop_rates.append(result[4])
    # need to group and average over the buffer size
    print(f"len queue: {len(queue_size)}, dr: {len(drop_rates)}, tp: {len(throughputs)}")
    plot_drop_rate(queue_size, drop_rates)
    plot_throughput(queue_size, throughputs)
    plot_throughput(queue_size, throughputs, t_q1, t_q3)


def average_over_trials(queue_size, throughputs, t_q1, t_q3, drop_rates):
    """
    given the list of queue sizes, and the dictionaries for prot: values for the above,
    return (qsize, dict {prot: (mean, q1, a3)})
    """
    gr_values = {}
    for prot in throughputs.keys():
        gr_values[prot] = {}
        for qsize, tp, q1, q3, drop_rate in zip(queue_size, throughputs[prot], t_q1[prot], t_q3[prot], drop_rates):
            if qsize not in gr_values[prot]:
                gr_values[prot][qsize] = []
            gr_values[prot][qsize].append((tp, q1, q3, drop_rate))
    # gr values maps each prot to queue_
    result = {}
    for prot, values in gr_values.items():
        tps, q1s, q3s = [], [], []
        result[prot] = []
        for queue, trial_results in values.items():
            avg_tp, avg_q1, avg_q3, avg_dr = 0, 0, 0, 0
            for tp, q1, q3, dr in trial_results:
                avg_tp += tp
                avg_q1 += q1
                avg_q3 += q3
                avg_dr += dr
            avg_tp /= len(trial_results)
            avg_q1 /= len(trial_results)
            avg_q3 /= len(trial_results)
            avg_dr /= len(trial_results)
            result[prot].append((queue, avg_tp, avg_q1, avg_q3, avg_dr))

    return result


def percentile(numbers, percentile=50):
    idx = int(percentile / 100 * len(numbers))
    return sorted(numbers)[idx]


def plot_drop_rate(queue_size, drop_rates):
    """
    Takes in queue size in terms of mbytes
    """
    # plot drop rate
    bdp = plot_bdp()
    old_queue_size = queue_size
    queue_size = list(map(lambda v: v / bdp, queue_size))
    for old, new in zip(old_queue_size, queue_size):
        print(f"old: {old}, new: {new}")
    plt.plot(queue_size, drop_rates)
    plt.title(folder)
    plt.xlabel("queue size (multiples of BDP)")
    plt.ylabel("drop_rate (percent)")
    # plt.ticklabel_format(style='sci', axis='x', scilimits=(0,0))
    plt.ticklabel_format(style='sci', axis='x')
    plt.legend()
    plt.ylim(bottom=0)
    # plt.xlim(left=bytes_to_mbytes(min_bytes), right=bytes_to_mbytes(max_bytes))
    plt.xlim(left=bytes_to_mbytes(min_bytes) / bdp,
             right=bytes_to_mbytes(max_bytes) / bdp)
    plt.tight_layout()
    plt.savefig(f"{folder}/drop_rate.svg")
    if (should_show):
        plt.show()
    plt.close()


def plot_bdp():
    bdp = calc_bdp(delay_ms + 1)
    bdp_1_5 = bdp * 1.5
    # plt.axvline(x = bdp, label="BDP", color="orange", linestyle="--")
    plt.axvline(x=1, label="BDP", color="red", linestyle="--")
    # plt.axvline(x = bdp_1_5, label="1.5 * BDP", color="green", linestyle="--")
    plt.axvline(x=1.5, label="1.5 * BDP", color="green", linestyle="--")
    return bdp


def calc_bdp(min_rtt=delay_ms + 1):
    print(f"calculating bdp with delay = {min_rtt}")
    throughput_mbyte = mbits_to_bytes(bytes_to_mbytes(throughput_mbit))
    bdp = throughput_mbyte * min_rtt / 1000
    return bdp


def plot_throughput(queue_size, throughputs, q1=None, q3=None):
    bdp = plot_bdp()
    # remove duplicates from trials... this could be moved to average_over_trials
    queue_size = list(map(lambda v: v / bdp, queue_size))
    for protocol, rates in throughputs.items():
        # rates = list(map(bytes_to_mbits, rates))
        plt.plot(queue_size, rates, label=protocol, color=colors[protocol])
    # Plot Quartiles
    if q1 is not None and q3 is not None:
        alpha = 0.3
        for protocol, rates in q1.items():
            # rates = list(map(bytes_to_mbits, rates))
            plt.plot(queue_size, rates,
                     label=f"{protocol} Q1", color=colors[protocol], alpha=alpha)
            plt.fill_between(
                queue_size, throughputs[protocol], rates, color=colors[protocol], alpha=alpha / 3)
        for protocol, rates in q3.items():
            # rates = list(map(bytes_to_mbits, rates))
            plt.plot(queue_size, rates,
                     label=f"{protocol} Q3", color=colors[protocol], alpha=alpha)
            plt.fill_between(
                queue_size, throughputs[protocol], rates, color=colors[protocol], alpha=alpha / 3)

    # plot the total throughput
    # x_data = list(map(bytes_to_mbytes, [min_bytes, max_bytes]))
    # y_data = [throughput_mbit, throughput_mbit]
    # plt.plot(x_data, y_data, label="Max Bandwidth")

    plt.title(folder)
    plt.ylim(bottom=0, top=throughput_mbit + 10)
    # plt.xlim(left=bytes_to_mbytes(min_bytes), right=bytes_to_mbytes(max_bytes))
    plt.xlim(left=bytes_to_mbytes(min_bytes) / bdp,
             right=bytes_to_mbytes(max_bytes) / bdp)
    plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
    # plt.xlabel("queue size (mega bytes)")
    plt.xlabel("queue size (multiples of BDP)")
    plt.ylabel("total throughput (mbits / second)")
    # plt.ticklabel_format(style='sci', axis='x', scilimits=(0,0))
    plt.ticklabel_format(style='sci', axis='x')
    plt.tight_layout()
    if q1 is None:
        plt.savefig(f"{folder}/throughput.svg")
    else:
        plt.savefig(f"{folder}/q_throughput.svg")

    if (should_show):
        plt.show()
    plt.close()

def load_config(folder):
    global trial_number, trial_time, throughput_mbit, delay_ms, max_bytes, min_bytes
    trials_config = "/".join([folder, "trials_config.json"])
    if os.path.isfile(trials_config):
        json_input = open(trials_config).read()
        print(json_input)
        params = json.loads(json_input)
        print(params)
        trial_number = params["trials"]
        trial_time = params["time"]
        throughput_mbit = params["tp"]
        delay_ms = params["delay"]
        byte_steps = [i for i in map(frac_bdp_to_bytes, params["points"])]
        min_bytes = byte_steps[0]
        max_bytes = byte_steps[-1]
        return byte_steps

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Orchestrate a set of experiments")
    parser.add_argument("--rerun", "-r", action='store_true', default=False)
    parser.add_argument("--reparse", "-p", action='store_true', default=False)
    parser.add_argument("--replot", action='store_true', default=False)
    parser.add_argument("--show", "-s", action='store_true', default=False)
    parser.add_argument("--clean", "-c", action='store_true', default=False)
    args = parser.parse_args()
    print(args)

    if (args.show):
        should_show = True
        import matplotlib.pyplot as plt
    else:
        print("turning off interactive")
        mpl.use('Agg')
        import matplotlib.pyplot as plt
        plt.ioff()

    experiments = generate_sub_experiments(remove=args.rerun or args.clean)
    for exp, sub_exp in experiments:
        print(exp)
        print(len(sub_exp))

    if (args.rerun):
        for _folder, experiment_folders in experiments:
            run_sub_experiments(experiment_folders)
    if (args.reparse):
        for _folder, experiment_folders in experiments:
            run_sub_experiments(experiment_folders, parse=True)
    if (args.replot):
        for _folder, experiment_folders in experiments:
            run_sub_experiments(experiment_folders, plot=True)

    for folder, experiment_folders in experiments:
        print(f"\n\n{folder}")
        plot_experiments(folder, experiment_folders)
