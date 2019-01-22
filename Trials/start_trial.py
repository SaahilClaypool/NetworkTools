#! /usr/bin/python3
import os
import time
import sys
import json
import threading
from typing import Dict

_TIME = 0

if (not (len(sys.argv) == 2 or len(sys.argv) == 3 or len(sys.argv) == 4)):
    print(f"usage: 1: file 2: name 3: time")
    print(sys.argv)
    exit()

if (len(sys.argv) == 4):
    _TIME = int(sys.argv[3])

def c(host, cmd):
    """
    turn into remote version of command
    """
    cmd = cmd.replace("&", "")
    cmd = cmd.replace("{T}", f"{trial_time}")
    if (host != 'local'):
        cmd_clean = f"ssh {host} "
        cmd_clean += "\"" + cmd + "\""
        return cmd_clean
    return cmd


def exec_cmd(host, cmd):
    new_thread = "&" in cmd
    cmd = c(host, cmd)
    print("command: ", cmd)
    if (new_thread):
        t = threading.Thread(target=lambda : os.system(cmd))
        t.name = f"{host} $ {cmd}"
        t.start()
        return t
    else:
        os.system(cmd)
        return False


def set_cc(host, cc):
    cmd = \
f"""\
sudo sysctl net.core.default_qdisc=fq;
sudo sysctl net.ipv4.tcp_congestion_control={cc};
sudo sysctl net.ipv4.tcp_congestion_control;
"""
    cmd = c(host, cmd);
    print(cmd)
    os.system(cmd)
    pass

config: Dict = json.loads(open(sys.argv[1], 'r').read())
name = config["name"]

trial_time = config["time"]
if (_TIME != 0):
    trial_time = _TIME
if (len(sys.argv) > 2):
    name = sys.argv[2]
print(config)

for host, conf in config["setup"].items():
    print(f"Configuring: {host}\n")
    set_cc(host, conf["cc"])
    for command in conf["commands"]:
        exec_cmd(host, command)

# Sleep to allow threads to start process up etc.
time.sleep(3)

run_handles = []
for host, conf in config["run"].items():
    print(f"Running : {host}\n")
    for command in conf["commands"]:
        join_handle = exec_cmd(host, command)
        run_handles.append(join_handle)
# Block and wait for all tasks started in the run phase
for handle in run_handles:
    handle.join()

off_cmd = f"""\
sudo tc qdisc del dev enp3s0 root
sudo tc qdisc del dev enp2s0 root
sudo tc qdisc del dev enp1s0 root
sudo tc -s qdisc ls dev enp3s0
"""
os.system(off_cmd)

for host, conf in config["finish"].items():
    print(f"Running : {host}\n")
    for command in conf["commands"]:
        exec_cmd(host, command)

# mkdir if it doesn't exist in results
if (not os.path.isdir(f"Results/")):
    os.mkdir(f"Results/")

for host, conf in config["run"].items():
    cc = config["setup"][host]["cc"]
    cmd = f"scp {host}:~/pcap.pcap Results/{cc}_{host}.pcap"
    print("running: ", cmd)
    os.system(cmd)

os.system("sh ./10mbps_enp3_off.sh")
