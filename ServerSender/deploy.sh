cargo build --target=armv7-unknown-linux-gnueabihf --release;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@churro1:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@churro2:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@churro3:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@churro4:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@tarta1:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@tarta2:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@tarta3:~;
scp ./target/armv7-unknown-linux-gnueabihf/release/ServerSender pi@tarta4:~;

