use std::{env, thread, io::{self, prelude::*}, net::{TcpListener, TcpStream}};

fn handle_client(mut stream: TcpStream) -> thread::JoinHandle<()> {
    // make a thread, echo back to the client
    let handle = thread::spawn(move || {
        eprintln!("got a client: {:?}, started thread", stream);
        let mut buf = [0; 10000];
        let read = stream.read(&mut buf).unwrap();
        eprintln!("read: {}", read);
    });
    handle
}

fn server_proc(port: u32) -> io::Result<()> {
    let listener = TcpListener::bind(format!("127.0.0.1:{}", port))?;

    // accept connections and process them serially
    let mut handles: Vec<thread::JoinHandle<()>> = Vec::new();
    for stream in listener.incoming() {
        handles.push(handle_client(stream?));
    }

    Ok(())
}

fn client_proc(port: u32) -> io::Result<()> {
    let mut client = TcpStream::connect(format!("127.0.0.1:{}", port))?;
    let mut buf = [1; 5000];
    client.write(&buf)?;
    client.flush()?;
    Ok(())
}

fn main() -> io::Result<()> {
    let mut port: u32 = 8001;
    if env::args().len() < 2{
        server_proc(port)?;
    }
    else { 
        client_proc(port)?;
    }
    Ok(())
}