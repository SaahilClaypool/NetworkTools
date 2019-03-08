#!/usr/bin/python3
import os
import argparse
import time

CUR_DIR = os.getcwd()
TOOLS_DIR = f"/home/saahil/Documents/rpi/NetworkTools"
PARSE_PCAP = f"{TOOLS_DIR}/Parse_pcap/target/release/parse_pcap"
PLOT_PCAP = f"{TOOLS_DIR}/Parse_pcap/plot.py"

START_TRIAL = f"{TOOLS_DIR}/Trials/start_trial.py"
RECORD_LOCAL = f"{TOOLS_DIR}/Trials/record_local.py"



def main():
    parser = argparse.ArgumentParser(description="Orchestrate a set of experiments")
    parser.add_argument("name", help="name of ouput")
    parser.add_argument("--directory", "-d", required=True)
    parser.add_argument("--build", "-b", action='store_true', default=False)
    parser.add_argument("--parse", "-p", action='store_true', default=False)
    parser.add_argument("--rerun", "-r", action='store_true', default=False)
    parser.add_argument("--granularity", "-g", default="")
    parser.add_argument("--show", "-s", action='store_const', const="show", default="false")
    parser.add_argument("--time", "-T", default="0")
    
    args = parser.parse_args()
    print(args)

    if (args.build):
        os.system(f"cd {TOOLS_DIR}/Parse_pcap; cargo build --release; cd -;" )

    local_time = 60
    if (int(args.time) != 0):
        local_time = int(args.time)

    if (args.rerun):
        trial_cmd = f"""\
        cd {args.directory};
        mkdir Results;
        rm Results/*;
        {RECORD_LOCAL} {local_time} Results/queue_length.csv 10 &
        {START_TRIAL} config.json {args.name} {args.time};
        """

        os.system(trial_cmd)

        off_cmd = f"""\
        sudo tc qdisc del dev enp3s0 root
        sudo tc -s qdisc ls dev enp3s0
        """
        os.system(off_cmd)
        time.sleep(10)

    parse_cmd = f"""\
    cd {args.directory}/Results;
    rm .*@*.csv; {PARSE_PCAP} '.*' '.' '.' {args.granularity};
    cd -;
    """
    if (args.parse or args.rerun):
        os.system(parse_cmd)

    plot_cmd = f"""\
    cd {args.directory}/Results;
    {PLOT_PCAP} . . {args.name}.svg {args.show}
    mv *svg ..;
    cd -;
    """
    os.system(plot_cmd)



    

if __name__ == "__main__":
    main()
