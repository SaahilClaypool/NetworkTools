# Testing a Protocol

This documents the entire process that you can do (using these tools) 
to test some new congestion protocol. 


## 1. Compile a new TCP Congestion control protocol

1. Grab the source code that your current kernel is compiled against.

    I am testing with the raspberry pi B3+ computer. The slightly 
    modified kernel I am using is [here (link)](https://github.com/SaahilClaypool/raspberry-linux)

    Congestion control protocols are defined in the `/net/ipv4` directory. 

2. Modify code as needed

    For example, 
    [this path (link)](https://github.com/SaahilClaypool/raspberry-linux/commit/53212ab7eecea762c4b9021cb34e7a1bf8514042) 
    shows all of the changes I used to add a protocol called  `bbr2`, which uses the source code from the 
    BBR development repository found [here (link)](https://git.kernel.org/pub/scm/linux/kernel/git/davem/net-next.git/commit/?id=0f8782ea14974ce992618b55f0c041ef43ed0b78)

3. Compile the kernel

    Assuming you are compiling for the raspberry pi, you can use use 
    [this docker image](https://cloud.docker.com/u/saahil/repository/docker/saahil/rpi_build) 
    to build your linux source code for the ARM raspberry pi using the command below:
    ```sh 
    docker run --rm \
        -v {SOURCE_CODE_FOLDER}:/linux \
        -v {OUTPUT_FOLDER}:/out \
        -e _UID=`id -u` -e _GID=`id -g` \
        -it saahil/rpi_build sh /root/build_cmd.sh
    ```

    where `SOURCE_CODE_FOLDER` and `OUTPUT_FOLDER` should be directories on your system. 

    Assuming you add your congestion control protocol to `/net/ipv4/new_protocol.c`,
    this should compile a new kernel module in 
    `{OUTPUT_DIRECTORY}/build/ext4/lib/modules/4.19.0-v7+/kernel/net/ipv4/tcp_new_protocol.ko`

4. Copy the new kernel onto the machines that you want to install the module to

5. On each machine, run `sudo insmod ./tcp_new_protocol.ko`

    This will install the new congestion control protocol

6. Test it out

    run `sudo sysctl net.ipv4.tcp_congestion_control=new_protocol`. If there are no errors 
    then the kernel module *should* have installed correctly. 
    Next, you can do some real evaluation. 


## Using the tools to run an experiment (See the readme for details on each tool)

I'll run through an example of creating a new trial comparing bbr against cubic

1. Clone this repository. 

    From now on, I will assume it is in some $TOOLS_REPO

2. Create a directory for an experiment 

    I am going to have a bottleneck of 80mbit with 25ms rtt. So, 
    I will create a new directory "test_80_25". Name this whatever you'd like. 

3. Create a `config.json` in the "test_80_25" directory

    This will control what *flows* are run in this trial. Namely, it will configure
    the congestion control protocol used by each host, and the number of flows created. 

    I will use this file [here](./Trials/example_config.json)

    The important bits to notice are: 

    1. The `cc` key
        This controls the congestion control protocol for each host. 

        For our test, we want one pie to be cubic, one pie to be bbr. So, 
        we want to set the `cc` under "setup>churro1>cc" to `bbr` and the 
        `cc` under "setup>tarta1>cc" to `bbr`. 

        Similarly, we want to set "setup>churro2>cc" to `cubic` and the
        "setup>tarta2>cc" to `cubic`. 

        Note: the server and client protocols should match. This is used for naming
        purposes in the graphs. 

    2. The client connections

        In the "run" section, we will start each flow. 
        For example, if we want to *only* run two flows from 
        the churro1 to tarta1 and from churro2 to tarta2, we would
        using the following block: 

        ```json
        "run": {
            "pi@churro1": {
                "commands": [
                    "./ServerSender client tarta1 5201 {T} 1 1 &"
                ]
            },
            "pi@churro2": {
                "commands": [
                    "sleep 2; ./ServerSender client tarta2 5201 {T} 1 1 &"
                ]
            }
        }
        ```

        The {T} will be replaced with the time in the next step. 
    
4. Create a `tbf.sh` file in the same directory

    This file will contain the setup for the queueing disciplines to limit
    the throughput and round trip time accordingly. 

    Here is an example tbf.sh file: 
    ```sh
    sudo tc qdisc del dev enp3s0 root
    sleep 5
    sudo tc qdisc add dev enp3s0 root handle 1:0 netem delay 24ms limit 5000
    sudo tc qdisc add dev enp3s0 parent 1:1 handle 10: tbf rate 80mbit buffer 1mbit limit 10000mbit
    sudo tc qdisc add dev enp3s0 parent 10:1 handle 100: tbf rate 80mbit burst .05mbit limit 1000000b
    sudo tc -s qdisc ls dev enp3s0
    ```

    Note that the minimum rtt in my network in 1ms. So, I only add 24 ms to get to the desired 25ms. 

    Also, there are *two* token bucket filters. These are used to reduce the "burst" caused by token bucket
    filters. These lines shouldn't require too much tuning - just remember to keep the two `rate 80mbit` values
    the same.

5. Edit the "run.py" file 

    Note: this should be modified to work better with environment variables... but for now follow this: 

    Modify the `TOOLS_DIR` variable at the top of the file to be the absolute path of this
    directory

6. Run

    run `$TOOLS_REPO/Trials/run.py test_plots --directory test_80_25 --rerun --time 180` to run 
    your trial for 3 minutes. 

    Add a --show to show the graphs as they are plotted in real time. 



     