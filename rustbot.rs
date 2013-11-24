#[feature(managed_boxes)]

extern mod extra;

use extra::serialize::Decodable;
use extra::serialize::Encodable;
use extra::json::{Encoder, Decoder};

pub struct Protocol {
    writer: @Writer,
    encoder: @mut Encoder,
    reader: @Reader
}

impl Protocol {
    fn new(writer: @Writer, reader: @Reader) -> Protocol {
        return Protocol {
            writer: writer,
            encoder: @mut Encoder(writer),
            reader: reader
        };
    }
    
    fn send<T: Encodable<Encoder>>(&self, v: T) {
        v.encode(self.encoder);
        self.writer.write_char('\n');
    }
    
    fn recv<T: Decodable<Decoder>>(&self) -> T {
        let line = self.reader.read_line();
        let jsonobject = extra::json::from_str(line);
        let mut decoder = Decoder(jsonobject.unwrap());
        return Decodable::decode(&mut decoder);
    }
}

#[deriving(Decodable, Encodable)]
pub struct WorldInfo {
    width: uint,
    height: uint
}

#[deriving(Decodable, Encodable)]
pub struct RobotInfo {
    location: (uint, uint),
    hp: uint,
    player_id: uint,
    robot_id: uint
}

#[deriving(Decodable, Encodable)]
pub struct WorldState {
    turn: uint,
    robots: ~[RobotInfo],
    local: RobotInfo
}

pub enum Action {
    Move(uint, uint),
    Attack(uint, uint),
    Guard,
    Suicide
}

impl<S: extra::serialize::Encoder> Encodable<S> for Action {
    fn encode(&self, s: &mut S) {
        match *self {
            Move(a, b) => do s.emit_seq(2) |s| {
                s.emit_seq_elt(0, |s| "move".encode(s));
                s.emit_seq_elt(1, |s| (a, b).encode(s));
            },
            Attack(a, b) => do s.emit_seq(2) |s| {
                s.emit_seq_elt(0, |s| "attack".encode(s));
                s.emit_seq_elt(1, |s| (a, b).encode(s));
            },
            Guard => s.emit_seq(1, |s| "guard".encode(s)),
            Suicide => s.emit_seq(1, |s| "suicide".encode(s)),
        }
    }
}

trait Robot {
    fn act(&self, info: &WorldInfo, state: &WorldState) -> Action;
}

fn runrobot<T: Robot>(factory: &fn() -> T) {
    let prot = Protocol::new(std::io::stdout(), std::io::stdin());
    let r = factory();
    let info : WorldInfo = prot.recv();
    
    while (true) {
        let state : WorldState = prot.recv();
        prot.send(r.act(&info, &state));
    }    
}

pub struct TestRobot;

impl Robot for TestRobot {
    fn act(&self, info: &WorldInfo, state: &WorldState) -> Action {
        return Guard;
    }
}

fn main() {
    runrobot(|| TestRobot);
}
