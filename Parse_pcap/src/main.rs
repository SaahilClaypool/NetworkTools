extern crate pcap;
#[macro_use]
extern crate lazy_static;
extern crate linux_api;
extern crate pnet_packet;
extern crate regex;
extern crate string_error;
extern crate rayon;

use std::env;
use std::error::Error;
use std::collections::HashMap;

use linux_api::time::timeval;

use pcap::{Capture, Offline};
use regex::Regex;
use std::io;
use std::io::Write;
use std::fs::{self, DirEntry};
use std::path::Path;
use rayon::prelude::*;


use pnet_packet::{ethernet, ipv4, tcp, FromPacket, Packet};

/// Usage: cargo run '80.*bbr1_bbr1' '../Results/'  ; python3 plot.py . 80.*bbr_bbr_.*.tarta

fn main() -> Result<(), Box<dyn Error>> {
    let mut files: Vec<String> = vec![];
    let mut reg_string = String::from(".*pcap");
    let mut dir: String = String::from(".");
    let mut output: String;
    let mut granularity: i64 = 500;
    let mut time_step: i64 = 500;

    if env::args().len() < 3 {
        eprintln!("Args: <pcap_regex> <directory> [output_dir] [granularity] [time_step_size]");
        return Result::Err(string_error::new_err("not enough args"));
    }
    else {
        for (i, arg) in env::args().enumerate() {
            match i {
                1 => reg_string = format!(".*{}.*.pcap$", arg),
                2 => dir = arg,
                3 => output = arg,
                4 => granularity = arg.parse::<i64>()?,
                5 => time_step = arg.parse::<i64>()?,
                _ => eprintln!("arg {} is {}", i, arg),
            }
        }
        files = get_files_matching(&reg_string, &dir);
    }


    let parsed_pcaps: Vec<(String, i64, Vec<(u16, Vec<Throughput>)>)> = files.par_iter().map(|file| {
        let stem = Path::new(&file).file_stem().unwrap().to_str().unwrap();
        eprintln!("shortpath: {}", stem);
        let cap = open_capture(&file).unwrap();
        let mut flow_map = parse_capture(cap).unwrap();

        let parsed_flows: Vec<(u16, Vec<Throughput>)> = flow_map.iter_mut().filter_map(|(port, packets)| {
            packets.sort_by(|a, b| a.time.cmp(&b.time));
            let tps = calculate_throughput(&packets, granularity, time_step);

            let non_zero_throughput : Vec<&Throughput> = tps.iter().filter(|tp| {
                tp.value > 200
            }).collect();

            if non_zero_throughput.len() > 100 {
                Some((*port, tps))
            } else {
                None
            }
        }).collect();

        let mut min_start_time = std::i64::MAX;
        for (_, flow) in &parsed_flows {
            if flow[0].time < min_start_time {
                min_start_time = flow[0].time;
            }
        }

        (String::from(stem), min_start_time, parsed_flows)
    }).collect();

    let mut min_start_time = std::i64::MAX;
    for (_, time, _) in &parsed_pcaps {
        if *time < min_start_time {
            min_start_time = *time;
        }
    }

    parsed_pcaps.par_iter().for_each(|(stem, start, flow_map)| {
        flow_map.par_iter().for_each(|(port, flow)|{
            let output_name = &format!("{}_{}.csv", stem, port);
            write_throughput(output_name, flow, min_start_time).unwrap();
        });

    });

    Ok(())
}

fn write_throughput(filename: &str, tps: &Vec<Throughput>, start_time: i64) -> io::Result<()> {
    let mut file = fs::File::create(filename)?;
    eprintln!("writing to: {}", filename);
    for tp in tps {
        file.write_fmt(format_args!("{},{}\n", tp.time - start_time, tp.value))?;
    }
    Ok(())
}

fn get_files_matching(reg_str: &str, dir_str: &str) -> Vec<String> {
    eprintln!("Finding files {} in {} ", reg_str, dir_str);
    let r = regex::Regex::new(reg_str).unwrap();
    let dir = std::path::Path::new(dir_str);
    fs::read_dir(dir).unwrap().filter_map(|entry| {
        let entry = entry.unwrap();
        let path = entry.path();
        if path.is_dir() 
        ||  !r.is_match(entry.file_name().to_str().unwrap()){
            None
        } else {
            Some(String::from(path.canonicalize().unwrap().to_str().unwrap()))
        }
    }).collect()
}

struct Throughput {
    time: i64,
    value: i64,
}

lazy_static! {
    static ref SENDER_SRC: regex::Regex = Regex::new("192.168.2..").unwrap();
    static ref SENDER_DST: regex::Regex = Regex::new("192.168.1..").unwrap();
}

fn packet_len(pkt: &Pkts) -> u32 {
    //     return ip_p.len - ip_p.hl * 4- tcp_p.data_offset
    pkt.ip_p.get_total_length() as u32
    // - pkt.ip_p.get_header_length() as u32
    // - 4 * pkt.tcp_p.get_data_offset() as u32
}

fn calculate_throughput_between(start: usize, end: usize, pkts: &[Pkts]) -> u32 {
    let mut data_size = 0;
    for idx in start..=end {
        let p = &pkts[idx];
        let Pkts {
            time,
            eth_p,
            ip_p,
            tcp_p,
        } = p;

        let dst: String = ip_p.get_destination().to_string();
        if SENDER_DST.is_match(&dst) {
            data_size += packet_len(p);
        }
    }
    data_size
}

/// Takes sorted list of Pkts
fn calculate_throughput(pkts: &[Pkts], granularity: i64, step_size: i64) -> Vec<Throughput> {
    let mut res: Vec<Throughput> = vec![];
    let mut t_bottom = pkts[0].time - granularity;
    let mut t_top = pkts[0].time;
    let mut bottom = 0;
    let mut top = 1;
    'outer: while top < pkts.len() - 1 {
        for idx in top..=pkts.len() {
            // search for first packet past the window
            if idx == pkts.len() {
                top = idx;
                break 'outer;
            }
            if pkts[idx].time > t_top {
                top = idx;
                break;
            }
        }
        for idx in bottom..pkts.len() {
            // search for first packet past the window
            if pkts[idx].time >= t_bottom {
                bottom = idx;
                break;
            }
        }

        let throughput =
            (calculate_throughput_between(bottom, top, pkts) as i64) as f64 / (granularity as f64 / 1000.);
        res.push(Throughput {
            time: t_top,
            value: throughput as i64,
        });
        t_top += step_size;
        t_bottom += step_size;
    }
    res
}

#[derive(Debug)]
struct Pkts {
    /// millisecond time
    time: i64,
    eth_p: ethernet::EthernetPacket<'static>,
    ip_p: ipv4::Ipv4Packet<'static>,
    tcp_p: tcp::TcpPacket<'static>,
}

fn parse(pkt: Vec<u8>, time: i64) -> Pkts {
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

fn parse_capture(mut cap: Capture<Offline>) -> Result<HashMap<u16, Vec<Pkts>>, Box<dyn Error>> {
    let mut flows: HashMap<u16, Vec<Pkts>> = HashMap::new();
    while let Ok(p) = cap.next() {
        let d: Vec<u8> = p.data.iter().cloned().collect();
        let tv = timeval {
            tv_sec: p.header.ts.tv_sec,
            tv_usec: p.header.ts.tv_usec,
        };
        let pkt = parse(d, tv.to_milliseconds());
        let src_port = pkt.tcp_p.get_source() as u16;
        if !flows.contains_key(&src_port) {
            flows.insert(src_port, vec![]);
        }
        flows.get_mut(&src_port).unwrap().push(pkt);
    }
    return Ok(flows);
}

fn open_capture(st: &str) -> Result<Capture<Offline>, Box<dyn Error>> {
    let cap = Capture::from_file(st)?;
    Ok(cap)
}
