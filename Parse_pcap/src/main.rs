extern crate pcap;
#[macro_use]
extern crate lazy_static;
extern crate linux_api;
extern crate pnet_packet;
extern crate rayon;
extern crate regex;
extern crate string_error;

use std::collections::HashMap;
use std::env;
use std::error::Error;
use std::rc::Rc;

use linux_api::time::timeval;

use pcap::{Capture, Offline};
use rayon::prelude::*;
use regex::Regex;
use std::fs::{self, DirEntry};
use std::io;
use std::io::Write;
use std::path::Path;

use pnet_packet::{ethernet, ipv4, tcp, FromPacket, Packet};

mod parse_pcap;

use self::parse_pcap::{ParserEntry, Pkts, ThroughputState};

/// Usage: cargo run '80.*bbr1_bbr1' '../Results/'  ; python3 plot.py . 80.*bbr_bbr_.*.tarta

fn main() -> Result<(), Box<dyn Error>> {
    let mut files: Vec<String> = vec![];
    let mut reg_string = String::from(".*pcap");
    let mut dir: String = String::from(".");
    let mut output: String = String::from("");
    let mut granularity: i64 = 500;
    let mut output_type = String::from("throughput");

    if env::args().len() < 3 {
        eprintln!("Args: <pcap_regex> <directory> [output_dir] [granularity] ");
        return Result::Err(string_error::new_err("not enough args"));
    } else {
        for (i, arg) in env::args().enumerate() {
            match i {
                1 => reg_string = format!(".*{}.*.pcap$", arg),
                2 => dir = arg,
                3 => output = arg,
                4 => granularity = arg.parse::<i64>()?,
                5 => output_type = arg,
                _ => eprintln!("arg {} is {}", i, arg),
            }
        }
        files = get_files_matching(&reg_string, &dir);
    }

    // let tps = calculate_throughput(&mut cap, granularity);
    let mut measure_labels = Vec::new();
    match output_type.as_ref() {
        "throughput" => {
            eprintln!("Calculating throughput");
            measure_labels.push("throughput");
        }
        "inflight" => {
            eprintln!("Calculating inflight");
        }
        _ => {
            eprintln!("No such option. Falling back on all");
        }
    };
    let measure_labels = measure_labels; // take away mut

    let parsed_pcaps: Vec<(String, i64, Vec<(u16, Vec<Vec<i64>>)>)> = files
        .par_iter()
        .map(|file| {
            let stem = Path::new(&file).file_stem().unwrap().to_str().unwrap();
            eprintln!("shortpath: {}", stem);
            let mut cap = open_capture(&file).unwrap();
            let mut measures: Vec<Box<dyn ParserEntry>> = Vec::new();
            for label in measure_labels.iter() {
                match label.as_ref() {
                    "throughput" => {
                        measures.push(Box::new(ThroughputState::new()));
                    }
                    _ => {}
                }
            }

            let tps = calculate_measurements(&mut cap, granularity, measures);
            let mut start_time = std::i64::MAX;
            let vec_tps: Vec<(u16, Vec<Vec<i64>>)> = tps
                .into_iter()
                .map(|(port, tp)| {
                    if tp[0][0] < start_time {
                        start_time = tp[0][0];
                    }
                    (port, tp)
                })
                .collect();

            (String::from(stem), start_time, vec_tps)
        })
        .collect();

    let mut min_start_time = std::i64::MAX;
    for (_, time, _) in &parsed_pcaps {
        if *time < min_start_time {
            min_start_time = *time;
        }
    }

    parsed_pcaps.par_iter().for_each(|(stem, start, flow_map)| {
        flow_map.into_par_iter().for_each(|(port, flow)| {
            let output_name = &format!("{}_{}.csv", stem, port);
            write_throughput(output_name, &measure_labels, flow, min_start_time).unwrap();
        });
    });

    Ok(())
}

fn write_throughput(
    filename: &str,
    labels: &Vec<&str>,
    tps: &Vec<Vec<i64>>,
    start_time: i64,
) -> io::Result<()> {
    let mut file = fs::File::create(filename)?;
    eprintln!("writing to: {}", filename);
    for tp in tps {
        let mut tp: Vec<i64> = tp.iter().map(|v| *v).collect(); // just copy
        let time = tp.remove(0);
        let output = tp
            .iter()
            .map(|measure| measure.to_string())
            .collect::<Vec<String>>()
            .join(",");
        file.write_fmt(format_args!("{},{}\n", time - start_time, output));
    }
    Ok(())
}

fn get_files_matching(reg_str: &str, dir_str: &str) -> Vec<String> {
    eprintln!("Finding files {} in {} ", reg_str, dir_str);
    let r = regex::Regex::new(reg_str).unwrap();
    let dir = std::path::Path::new(dir_str);
    fs::read_dir(dir)
        .unwrap()
        .filter_map(|entry| {
            let entry = entry.unwrap();
            let path = entry.path();
            if path.is_dir() || !r.is_match(entry.file_name().to_str().unwrap()) {
                None
            } else {
                Some(String::from(path.canonicalize().unwrap().to_str().unwrap()))
            }
        })
        .collect()
}

#[derive(Debug)]
struct TimeVal {
    time: i64,
    value: i64,
}

lazy_static! {
    static ref SENDER_SRC: regex::Regex = Regex::new("192.168.2..").unwrap();
    static ref SENDER_DST: regex::Regex = Regex::new("192.168.1..").unwrap();
}

/// calculate the amount of data inflight at each time step
/// this is done by taking the sent - the last ack
fn calculate_inflight(cap: &mut Capture<Offline>, granularity: i64) -> HashMap<u16, Vec<TimeVal>> {
    // pair of last sent, last acked
    let mut intermediate_flows: HashMap<u16, (u32, u32)> = HashMap::new();
    let mut intermediate_t_top: HashMap<u16, i64> = HashMap::new();
    // result
    let mut flows_throughput: HashMap<u16, Vec<TimeVal>> = HashMap::new();

    while let Ok(p) = cap.next() {
        let d: Vec<u8> = p.data.iter().cloned().collect();
        let tv = timeval {
            tv_sec: p.header.ts.tv_sec,
            tv_usec: p.header.ts.tv_usec,
        };

        let pkt = parse(d, tv.to_milliseconds());
        let src_port = pkt.tcp_p.get_source() as u16;
        let dst_port = pkt.tcp_p.get_destination() as u16;
        let mut flow_port = src_port;

        // for each packet, if from sender
        // update the # sent
        // if from the receiver, update the acked
        let dst: String = pkt.ip_p.get_destination().to_string();
        if SENDER_DST.is_match(&dst) {
            // going sender -> client (aka dest is tarta)
            // start flow parsing if the flow hasn't been seen
            if !intermediate_flows.contains_key(&src_port) {
                intermediate_flows.insert(src_port, (0, 0));
                intermediate_t_top.insert(src_port, pkt.time + granularity);
                flows_throughput.insert(src_port, Vec::with_capacity(1000));
            }
            let (last_sent, last_acked) = *intermediate_flows.get(&src_port).unwrap();
            let sent = pkt.tcp_p.get_sequence();
            if sent > last_sent {
                *intermediate_flows.get_mut(&src_port).unwrap() = (sent, last_acked);
            }
        } else {
            // going from client -> source. aka src is 5201, we want to modify the dst port flow
            // start flow parsing if the flow hasn't been seen
            if !intermediate_flows.contains_key(&dst_port) {
                intermediate_flows.insert(src_port, (0, 0));
                intermediate_t_top.insert(src_port, pkt.time + granularity);
                flows_throughput.insert(src_port, Vec::with_capacity(1000));
            }
            let (last_sent, last_acked) = *intermediate_flows.get(&dst_port).unwrap();
            let acked = pkt.tcp_p.get_acknowledgement();
            if acked > last_acked {
                *intermediate_flows.get_mut(&dst_port).unwrap() = (last_sent, acked);
            }
            flow_port = dst_port;
        }

        let t_top = *(intermediate_t_top.get(&flow_port).unwrap());

        if pkt.time > t_top {
            // calculate the throughput for the intermediate window
            let (last_sent, last_acked) = intermediate_flows.get(&flow_port).unwrap();

            let mut inflight = 0;
            if last_acked < last_sent {
                inflight = last_sent - last_acked;
            }
            let tp = TimeVal {
                time: t_top,
                value: inflight as i64,
            };

            intermediate_t_top.remove(&flow_port);
            intermediate_t_top.insert(flow_port, t_top + granularity);

            flows_throughput.get_mut(&flow_port).unwrap().push(tp);
        }
    }
    flows_throughput
}

/// Takes sorted list of Pkts
/// returns a vector of a vector of numbers where the value 1 - n are the values requested
fn calculate_measurements(
    cap: &mut Capture<Offline>,
    granularity: i64,
    mut measurements: Vec<Box<dyn ParserEntry>>,
) -> HashMap<u16, Vec<Vec<i64>>> {
    let mut intermediate_t_top: HashMap<u16, i64> = HashMap::new();
    let mut flows_throughput: HashMap<u16, Vec<Vec<i64>>> = HashMap::new();

    while let Ok(p) = cap.next() {
        let d: Vec<u8> = p.data.iter().cloned().collect();
        let tv = timeval {
            tv_sec: p.header.ts.tv_sec,
            tv_usec: p.header.ts.tv_usec,
        };

        let pkt = parse(d, tv.to_milliseconds());
        let src_port = pkt.tcp_p.get_source() as u16;
        let dst_port = pkt.tcp_p.get_destination() as u16;
        let flow_label;

        let dst: String = pkt.ip_p.get_destination().to_string();
        if SENDER_DST.is_match(&dst) {
            flow_label = src_port;
        } else {
            flow_label = dst_port;
        }

        // start flow parsing if the flow hasn't been seen
        if !intermediate_t_top.contains_key(&flow_label) {
            intermediate_t_top.insert(flow_label, pkt.time + granularity);
            flows_throughput.insert(flow_label, Vec::new());
        }

        let pkt = Rc::new(pkt);

        // update packet tracking
        for measure in measurements.iter_mut() {
            measure.on_packet(flow_label, pkt.clone(), granularity);
        }

        let t_top = *(intermediate_t_top.get(&flow_label).unwrap());

        if pkt.time > t_top {
            // update measurement at end of each window
            let mut all_results = Vec::new();
            all_results.push(t_top);
            for measure in measurements.iter_mut() {
                let res = measure.on_window(flow_label, granularity);
                all_results.push(res);
            }
            flows_throughput
                .get_mut(&flow_label)
                .unwrap()
                .push(all_results);
            *intermediate_t_top.get_mut(&flow_label).unwrap() += granularity;
        }
    }
    flows_throughput
}

fn parse<'a>(pkt: Vec<u8>, time: i64) -> Pkts<'a> {
    let eth_p = ethernet::EthernetPacket::owned(pkt).unwrap();
    let ip_p = ipv4::Ipv4Packet::owned(Vec::from(eth_p.from_packet().payload)).unwrap();
    let tcp_p = tcp::TcpPacket::owned(Vec::from(ip_p.from_packet().payload)).unwrap();

    Pkts {
        time: time,
        eth_p: eth_p,
        ip_p: ip_p,
        tcp_p: tcp_p,
    }
}

fn open_capture(st: &str) -> Result<Capture<Offline>, Box<dyn Error>> {
    let cap = Capture::from_file(st)?;
    Ok(cap)
}
