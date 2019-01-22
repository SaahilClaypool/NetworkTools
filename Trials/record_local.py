#!/usr/bin/python3

import time
import os
import re
import sys
import time

# pattern = re.compile(b"backlog.*b")
pattern  = (r"backlog (?P<num>\d*)b")
patternK = (r"backlog (?P<num>\d*)Kb")
patternM = (r"backlog (?P<num>\d*)Mb")

q_pattern = (r"bytes (?P<sent>\d*) pkt \(dropped (?P<dropped>\d*)")

def main():
    t = 60
    out = sys.stdout
    raw_output = open("raw.txt", 'w')
    if (len(sys.argv) > 1):
        t = int(sys.argv[1]) # seconds
    if (len(sys.argv) > 2):
        print("writing to: ", sys.argv[2])
        out = open(sys.argv[2], 'w')
    if (len(sys.argv) > 3):
        print("waiting for : ", sys.argv[3])
        time.sleep(int(sys.argv[3]))
    print("time,buffer_len,sent,drops", file=out)
    for i in range(int(t / .1)):
        (buffer_len, sent, drops) = get_current_buffer(raw_output)
        print(time.time(), ",", buffer_len, ",", sent, ",", drops, file=out)
        time.sleep(.1)
    if (len(sys.argv) > 2):
        print("Finished writing to ", sys.argv[2], "after time", t)
        out.close()
    raw_output.close()

def get_current_drops(output):
    """
    return current (sent, dropped) packets from the given tc command output
    """
    has_skipped_netem = False
    for line in output.split("\n"):
        # it looks like the tbf share a buffer
        # So, the we only need to recor the first one seen
        # break after the second one
        match = re.search(q_pattern, line)
        if (match):
            if (not has_skipped_netem):
                has_skipped_netem = True
                continue
            sent = int(match.group("sent"))
            dropped = int(match.group("dropped"))
            return (sent, dropped)

def get_current_queue(output):
    has_skipped_netem = False

    for line in output.split("\n"):
        # it looks like the tbf share a buffer
        # So, the we only need to recor the first one seen
        # break after the second one
        match = re.search(pattern, line)
        matchK = re.search(patternK, line)
        matchM = re.search(patternM, line)
        if (match):
            if (not has_skipped_netem):
                has_skipped_netem = True
                continue
            bytes_in_buffer = int(match.group("num"))
            return bytes_in_buffer
        elif (matchK):
            if (not has_skipped_netem):
                has_skipped_netem = True
                continue
            bytes_in_buffer = 1024 * int(matchK.group("num"))
            return  bytes_in_buffer
        elif (matchM):
            if (not has_skipped_netem):
                has_skipped_netem = True
                continue
            bytes_in_buffer = 1000000 * int(matchM.group("num"))
            return bytes_in_buffer

def get_current_buffer(raw_output):
    """
    return the current number of bytes in the tbf
    ignore the duplicate tbf and the netem queue
    output is always in bytes
    """

    # get the ouptut from the system call
    output = os.popen("sudo tc -s qdisc ls dev enp3s0").read()
    has_skipped_netem = False
    print(output, file=raw_output)
    queue = get_current_queue(output)
    (sent, drops) = get_current_drops(output)
    return (queue, sent, drops)


if __name__ == "__main__":
    main()
