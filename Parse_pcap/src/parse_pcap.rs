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

    fn calculate_throughput_between(pkts: &[Rc<Pkts>]) -> i64 {
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

    fn packet_len(pkt: &Pkts) -> u32 {
        //     return ip_p.len - ip_p.hl * 4- tcp_p.data_offset
        pkt.ip_p.get_total_length() as u32
        // - pkt.ip_p.get_header_length() as u32
        // - 4 * pkt.tcp_p.get_data_offset() as u32
    }
}
impl<'a> ParserEntry<'a> for ThroughputState<'a> {
    /// just keep track of all the data in this window for each flow we see
    fn on_packet(&mut self, flow_label: u16, packet: Rc<Pkts<'a>>, granularity: i64) {
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
            * 8.;

        self.intermediate_flows.remove(&flow_label);
        self.intermediate_flows
            .insert(flow_label, Vec::with_capacity(1000));
        return throughput as i64;
    }

    fn get_label(&self) -> &'static str {
        "Throughput"
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
