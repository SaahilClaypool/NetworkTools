use std::{
    env,
    error::Error,
    io::{self, prelude::*},
    net::{TcpListener, TcpStream},
    thread,
    time::SystemTime,
};

fn handle_client(mut stream: TcpStream) -> thread::JoinHandle<()> {
    // make a thread, echo back to the client
    let handle = thread::spawn(move || {
        eprintln!("got a client: {:?}, started thread", stream);
        let mut buf = [0; 10000];
        while stream.read(&mut buf).is_ok() {}
    });
    handle
}

fn server_proc(port: u32) -> io::Result<()> {
    let bind_to = format!("127.0.0.1:{}", port);
    eprintln!("binding to {}", bind_to);
    let listener = TcpListener::bind(bind_to)?;

    // accept connections and process them serially
    let mut handles: Vec<thread::JoinHandle<()>> = Vec::new();
    for stream in listener.incoming() {
        handles.push(handle_client(stream?));
    }

    Ok(())
}

fn client_proc(port: u32, secs: u64, flows: u32, flow_offset: u64) -> Result<(), Box<dyn Error>> {
    let connect_to = format!("127.0.0.1:{}", port);
    eprintln!(
        "Connecting {} flows to {} offset {} for {} seconds",
        flows, connect_to, flow_offset, secs
    );
    let mut join_handles = Vec::<thread::JoinHandle<u32>>::new();
    for i in 0..flows {
        let connect_to = connect_to.clone();
        let handle = thread::spawn(move || {
            let mut client = TcpStream::connect(connect_to).expect("failed to connect");
            let start = SystemTime::now();
            let buf = [1; 5000];
            while SystemTime::now().duration_since(start).unwrap().as_secs() < secs {
                client.write(&buf).unwrap();
                client.flush().unwrap();
            }
            0
        });
        join_handles.push(handle);
    }

    for join_handle in join_handles.into_iter() {
        join_handle.join().expect("Thread finished already - no worries");
    }

    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    eprintln!("usage: ServerSender [server] [port] [seconds] [flows] [flow_offset]");
    let mut port: u32 = 8001;
    let mut is_server = false;
    let mut secs = 15; // seconds
    let mut flows = 1; // client only - server uses as many threads as client makes
    let mut flow_offset = 2; // client only - server uses as many threads as client makes
    for (i, arg) in env::args().enumerate() {
        match i {
            1 => is_server = "server" == &arg[..],
            2 => port = arg.parse::<u32>()?,
            3 => secs = arg.parse::<u64>()?,
            4 => flows = arg.parse::<u32>()?,
            5 => flow_offset = arg.parse::<u64>()?,
            _ => eprintln!("args {} is {}", i, arg),
        }
    }

    if is_server {
        server_proc(port)?;
    } else {
        client_proc(port, secs, flows, flow_offset)?;
    }
    Ok(())
}
