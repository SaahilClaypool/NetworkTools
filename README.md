# Network Tools

This repository contains the tools for testing various TCP networks. 

TODO: add a lock file. This way only a single user can run an experiment on a given machine. 
This should stop collisions (which would ruin a bunch of results).


## Layout

Each directory contains a set of related tools.

1. Parse_pcap

    **Note**: This should be called through `run.py` script described below.

    Contains a `rust` project for parsing pcap files pulled in by the **Trials** script
    The progam `parse_pcap` creates a csv file for each flow, and the 
    The program `plot.py` will parse each csv to create plots.

    `parse_pcap` only requires a directory to search in for pcap files. Here is an example usage:

    ```sh
    parse_pcap '.*' '.' '.' 500
    ```
    The first param, `.*`, matches ALL pcap files (usually what you want). The next param, `.`, searches the current
    directory. The next param, `.`, places the output files in the same directory. The last param, granularity, 
    is the time to average the statistics over. 500ms is half a second, and usually the number I use.
    

2. ServerSender
    Contains a `rust` project to create an arbitrary of tcp flows. 
    The `deploy.sh` script will copy the binary to each of the raspberry pi machines in the cluster. 
    note: this binary must be built for *ARM* to run on the pis. 

3. Trials
    Contains scripts for running trials. 

    - `run.py`: Wrapper for running, parsing and plotting a single trial.

        This should always be used to run the below scripts as it includes proper handling of command line flags.

        **Setup**: To use this script, you need to correctly set the paths for each of the scripts. 
        Currently, these are hard coded to my director setup, but any other user should change this source code 
        to point them to the correct locations.
        ```py
        CUR_DIR = os.getcwd() TOOLS_DIR = f"/home/saahil/raspberry/rpi/NetworkTools"
        PARSE_PCAP = f"{TOOLS_DIR}/Parse_pcap/target/release/parse_pcap"
        PLOT_PCAP = f"{TOOLS_DIR}/Parse_pcap/plot.py"
        EXP_DIR = "/home/saahil/raspberry/rpi/Experiments"
        START_TRIAL = f"{EXP_DIR}/start_trial.py"
        RECORD_LOCAL = f"{EXP_DIR}/record_local.py"
        ```

        **Usage**: The run.py script takes the following flags: 
        - Mandatory parameters:
            - name (positional): 
                this must be the first unnamed parameter. This is the name you want 
                the graphs to be prefixed with.
            - directory (mandatory): relative or absolute directory of containing the "config.json" file.
        - Optional (See run.py for more):
            - (none): without any parameters, this just replots the experiment
            - `--rerun`: re starts or runs the experiment for the first time
            - `--parse`: re runs the parse_pcap file on the results.
            - `--show`: present the graphs. Usually, don't use this over ssh. 
            - `--time`: sets the time for a trial if it is to be rerun. Default 60. 

    - `run_many.py`: Run a series of trials with varying queue sizes.

        (this script is NOT currently very general. Not likely useful for others)

        For each given sub folder, uses the `trials_config.json` to create
        a number of experiment configurations, and runs through them. 
        A `config.json` in the same sub_folder is used to determine what happens during
        each individual trial. Each trial varies the queue size. 

        - Important variables:
            - sub_folders: list of folders to run through
            - tbf_string: used to create the qdiscs for each trial. 
                This will be customized by the `trials_config.json` in each folder.
            - executable: path to the `run.py` script used to run each individual file.
            
    - `start_trial.py`: run a single trial
        This runs and grabs captures from a single trial

        Usage: `start_trial {config_name} {trial_name} {time}`

        Note: should always be called from the `run.py` script

        **Note**: this file contains much redundant information.
        Really, you should only need to change the `cc` field and
        the commands in the `run` section for each trial. 

        A trial is defined by a `config.json` file. An example
        config file is provided in `./Trials/example_config.json`. This file 
        contains 3 sections. Each section must finish before the 
        next session is started. a `&` symbol will be run in the background, 
        similar to a shell. This stops one step from blocking the progress of 
        the run, setup, or finish block.

        1. setup:
            This is used to setup the proper tcp congestion protocols for each host. 
            Additionally, each host should run `sudo tcpdump 'tcp port 5201' -w pcap.pcap -s 96 &`. 
            This will grab *only* the tcp headers for a connection through port 5201 (used
            by both our `ServerSender` tool and iperf). 

            By convention, each `tarta` machine is treated as a `server`. The command 
            `./ServerSender server 0.0.0.0 &` will begin a background process to 
            listen for a connection from the `churro` clients in the *run* step. 
            
        2. run:
            This block is used to start each of the client processes. An example line could be:
            `./ServerSender client tarta1 5201 {T} 1 1 &`. This begins a sender or client application, 
            connecting to host `tarta` port `5201` for some `{T}` seconds. `{T}` will be replaced
            with the time. See the `run.py` wrapper for more details.


        3. finish
            This process should turn off the `tc` settings used for the trial, and kill all of the servers.

        After running each of these steps, all of the `pcap.pcap` files generated by the hosts are copied
        into the `{current_dir}/Results` directory. The naming convention is `{cc}_{user}@{host}.pcap`.

    - `record_local.py`: record queue statistics from tc token bucket filters

        Usage: `record_local.py {local_time} {output_filename} {delay before starting (seconds)} &`

        Note: should always be called from the `run.py`

        This records the buffer size and drop rate of the token bucket filter and outputs this 
        to a csv files (usually queue_length.csv). This is done by polling the tc statistics with
        `sudo tc -s qdisc ls dev enp3s0` each 0.1 seconds. 

## Useful scripts: 

- `sudo tc -s qdisc ls dev enp3s0`: list the active configuration of the given interface
- `sudo tc qdisc del dev enp3s0 root`: remove the custom config for a given interface
- TODO: add more