use pnet_packet::{ethernet, ipv4, tcp, FromPacket, Packet};
use regex::Regex;
use std::collections::HashMap;
use std::rc::Rc;

lazy_static! {
    static ref SENDER_SRC: regex::Regex = Regex::new("192.168.2..").unwrap();
    static ref SENDER_DST: regex::Regex = Regex::new("192.168.1..").unwrap();
}

pub trait ParserEntry<'a> {
    /// called for each packet to update state
    fn on_packet(&mut self, flow_label: u16, packet: Rc<Pkts<'a>>, granularity: i64);
    /// called every window, get the data for that window
    /// returns the value computed for that window
    fn on_window(&mut self, flow_label: u16, granularity: i64) -> i64;
    fn get_label(&self) -> &'static str;
}

pub struct ThroughputState<'a> {
    intermediate_flows: HashMap<u16, Vec<Rc<Pkts<'a>>>>,
}

impl<'a> ThroughputState<'a> {
    pub fn new() -> Self {
        Self {
            intermediate_flows: HashMap::new(),
        }
    }

    fn calculate_throughput_between(pkts: &[Rc<Pkts<'_>>]) -> i64 {
        let mut data_size: i64 = 0;
        for idx in 0..pkts.len() {
            let p = &pkts[idx];

            let dst: String = p.ip_p.get_destination().to_string();
            if SENDER_DST.is_match(&dst) {
                data_size += Self::packet_len(p) as i64;
            }
        }
        data_size
    }

    fn packet_len(pkt: &Pkts<'_>) -> u32 {
        //     return ip_p.len - ip_p.hl * 4- tcp_p.data_offset
        pkt.ip_p.get_total_length() as u32
        // - pkt.ip_p.get_header_length() as u32
        // - 4 * pkt.tcp_p.get_data_offset() as u32
    }
}
impl<'a> ParserEntry<'a> for ThroughputState<'a> {
    /// just keep track of all the data in this window for each flow we see
    fn on_packet(&mut self, flow_label: u16, packet: Rc<Pkts<'a>>, _granularity: i64) {
        if !self.intermediate_flows.contains_key(&flow_label) {
            self.intermediate_flows
                .insert(flow_label, Vec::with_capacity(1000));
        }
        self.intermediate_flows
            .get_mut(&flow_label)
            .unwrap()
            .push(packet);
    }

    fn on_window(&mut self, flow_label: u16, granularity: i64) -> i64 {
        let window = self.intermediate_flows.get(&flow_label).unwrap();
        let throughput = (Self::calculate_throughput_between(window) as i64) as f64
            / (granularity as f64 / 1000.)
            * 8.
            / 1000000.; // bytes to megabits

        self.intermediate_flows.remove(&flow_label);
        self.intermediate_flows
            .insert(flow_label, Vec::with_capacity(1000));
        return throughput as i64;
    }

    fn get_label(&self) -> &'static str {
        "throughput"
    }
}

pub struct InflightState {
    intermediate_flows: HashMap<u16, (u32, u32)>,
    start_flows: HashMap<u16, (u32, u32)>,
}

impl InflightState {
    pub fn new() -> Self {
        InflightState {
            intermediate_flows: HashMap::new(),
            start_flows: HashMap::new(),
        }
    }
}

impl<'a> ParserEntry<'a> for InflightState {
    /// called for each packet to update state
    fn on_packet(&mut self, flow_label: u16, packet: Rc<Pkts<'a>>, _granularity: i64) {
        if !self.intermediate_flows.contains_key(&flow_label) {
            self.intermediate_flows.insert(flow_label, (0, 0));
            self.start_flows.insert(flow_label, (0, 0));
        }
        let (last_sent, last_acked) = *self.intermediate_flows.get(&flow_label).unwrap();
        let (first_sent, first_acked) = *self.start_flows.get(&flow_label).unwrap();

        let dst = packet.ip_p.get_destination().to_string();
        if SENDER_DST.is_match(&dst) {
            let sent = packet.tcp_p.get_sequence();
            if first_sent == 0 {
                *self.start_flows.get_mut(&flow_label).unwrap() = (sent, first_acked);
                println!("first sent , first ackd {} {}", sent, first_acked);
            }
            // handle wrapping seq numbers.
            if sent > last_sent
                || (sent < first_sent
                    && (last_sent > first_sent || first_sent - sent < first_sent - last_sent))
            {
                *self.intermediate_flows.get_mut(&flow_label).unwrap() = (sent, last_acked);
            }
        } else {
            let acked = packet.tcp_p.get_acknowledgement();
            if first_acked == 0 {
                *self.start_flows.get_mut(&flow_label).unwrap() = (first_sent, acked);
                println!("first sent , first ackd {} {}", first_sent, acked);
            }

            // handle wrapping seq numbers.
            if acked > last_acked
                || (acked < first_acked
                    && (last_acked > first_acked || first_acked - acked < first_acked - last_acked))
            {
                *self.intermediate_flows.get_mut(&flow_label).unwrap() = (last_sent, acked);
            }
        }
    }
    /// called every window, get the data for that window
    /// returns the value computed for that window
    fn on_window(&mut self, flow_label: u16, _granularity: i64) -> i64 {
        let (last_sent, last_acked) = self.intermediate_flows.get(&flow_label).unwrap();
        let mut inflight = 0;
        if last_sent > last_acked {
            inflight = last_sent - last_acked
        }
        inflight as i64
    }

    fn get_label(&self) -> &'static str {
        "inflight"
    }
}

struct PacketTime {
    seq_num: u32,
    sent_time: i64,
    ack_time: i64,
}

pub struct RTTState {
    intermediate_flows: HashMap<u16, Vec<PacketTime>>,
    last_rtt: i64,
}

impl RTTState {
    pub fn new() -> Self {
        Self {
            intermediate_flows: HashMap::new(),
            last_rtt: 0,
        }
    }
}

impl<'a> ParserEntry<'a> for RTTState {
    /// each packet, update the time of the last
    fn on_packet(&mut self, flow_label: u16, packet: Rc<Pkts<'a>>, _granularity: i64) {
        if !self.intermediate_flows.contains_key(&flow_label) {
            self.intermediate_flows.insert(flow_label, Vec::new());
        }
        let window = self.intermediate_flows.get_mut(&flow_label).unwrap();
        let dst = packet.ip_p.get_destination().to_string();
        if SENDER_DST.is_match(&dst) {
            // for each sent, add it to the list of packets sent and unacked
            window.push(PacketTime {
                seq_num: packet.tcp_p.get_sequence(),
                sent_time: packet.time,
                ack_time: -1,
            });
        } else {
            let ack_num = packet.tcp_p.get_acknowledgement();
            for p in window.iter_mut() {
                if p.seq_num <= ack_num && p.ack_time == -1 {
                    p.ack_time = packet.time
                }
            }
        }
    }
    /// called every window, get the data for that window
    /// returns the value computed for that window
    fn on_window(&mut self, flow_label: u16, _granularity: i64) -> i64 {
        let window = self.intermediate_flows.get_mut(&flow_label).unwrap();
        let mut sum = 0;
        let mut count = 0;
        for pkt in window.iter() {
            if pkt.ack_time == -1 {
                continue;
            }
            count += 1;
            if pkt.ack_time > pkt.sent_time {
                let cur_rtt = pkt.ack_time - pkt.sent_time;
                if cur_rtt > 500 {
                    // if greater half a second, there is a problem probably
                    println!(
                        "That's odd... {} {} rtt {}, throwing away",
                        pkt.sent_time, pkt.ack_time, cur_rtt
                    );
                    count -= 1;
                } else {
                    sum += cur_rtt;
                }
            }
        }
        // clear the list up to the last acked packet
        *window = window.split_off(count);
        if count == 0 {
        } else {
            self.last_rtt = (sum as f64 / count as f64) as i64;
        }
        return self.last_rtt;
    }

    fn get_label(&self) -> &'static str {
        "rtt"
    }
}

#[derive(Debug)]
pub struct Pkts<'a> {
    /// millisecond time
    pub time: i64,
    pub eth_p: ethernet::EthernetPacket<'a>,
    pub ip_p: ipv4::Ipv4Packet<'a>,
    pub tcp_p: tcp::TcpPacket<'a>,
}
