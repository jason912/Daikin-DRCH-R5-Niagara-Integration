#!/usr/bin/env python3
"""
drch_r5_poll.py — minimal reference for the Daikin DRCH-R5 (P-board, China Telecom / P&T spec #625) serial protocol.

Reference skeleton, NOT production software. It shows:
  * how a frame is assembled (SOI / VER / ADR / CID1 / CID2 / LENGTH / INFO / CHKSUM / EOI)
  * how LENID + LCHKSUM and CHKSUM are computed
  * how to poll one station and parse the reply

Physical layer: RS-485, 9600 8N1, NO parity (the manual's "odd parity" is wrong).
Requires: pyserial  (pip install pyserial)

Usage:
    python drch_r5_poll.py /dev/ttyUSB0 1 0x44      # read measurement data from station 1
    python drch_r5_poll.py COM3 2 0x43              # Windows, station 2, read status

Run with no arguments to just print example frames (no hardware needed).
"""

import sys

SOI = 0x7E
EOI = 0x0D
VER = "20"          # protocol version, as ASCII
CID1 = "60"         # command class: air-conditioning

# CID2 command codes (verify against your vendor specification)
CID2_READ_STATUS = "43"
CID2_READ_DATA = "44"
CID2_READ_ALARM = "47"
CID2_READ_LIMITS = "49"
CID2_WRITE = "51"

# Hidden writable control registers (start/stop) found on a live site — the only
# writable control path we ship. Setpoints / fan speed are effectively locked.
CTRL_ADDR = {"start_stop": 2000}   # 2000/2001 -> FC06 0/1


def lchksum(lenid_hex: str) -> str:
    """LCHKSUM: (16 - sum(nibbles of LENID) % 16) % 16, as one hex char."""
    return format((16 - (sum(int(c, 16) for c in lenid_hex) % 16)) % 16, "X")


def build_frame(adr: str, cid2: str, info: str = "") -> bytes:
    """Build a full request frame. adr/cid2/info are ASCII-hex strings."""
    lenid = format(len(info) // 2, "04X")           # INFO length in BYTES, 4 hex chars
    body = VER + adr.upper() + CID1 + cid2.upper() + lenid + lchksum(lenid) + info.upper()
    s = sum(ord(c) for c in body) % 256
    chk = format((256 - s) % 256, "02X")
    return (format(SOI, "02X") + body + chk + format(EOI, "02X")).encode("ascii")


def parse_reply(raw: bytes):
    """Sanity-check a reply and return (adr, cid2, info_ascii) or raise ValueError."""
    text = raw.decode("ascii", "ignore").strip()
    if len(text) < 19 or text[0:2].upper() != format(SOI, "02X"):
        raise ValueError("no SOI / too short: %r" % text)
    if text[-2:].upper() != format(EOI, "02X"):
        raise ValueError("no EOI: %r" % text)
    body, chk = text[2:-4], text[-4:-2]
    if format((256 - sum(ord(c) for c in body) % 256) % 256, "02X") != chk.upper():
        raise ValueError("bad CHKSUM: %r" % text)
    adr, cid2, info = text[2:4], text[8:10], text[14:-4]
    return adr, cid2, info


def poll(port: str, station: int, cid2: str, timeout: float = 2.0):
    """One poll/response cycle. Returns parsed reply; raises on timeout."""
    import serial  # pyserial

    adr = format(station, "02X")                    # station = LINE index (1/2/3)
    req = build_frame(adr, cid2)
    with serial.Serial(port, 9600, bytesize=8, parity=serial.PARITY_NONE,
                       stopbits=1, timeout=timeout) as ser:
        ser.reset_input_buffer()
        ser.write(req)
        ser.flush()
        raw = ser.read(64)                          # replies are short
    if not raw:
        raise TimeoutError("no reply from station %d (check parity=NONE, A/B, station id)" % station)
    return parse_reply(raw)


def main() -> int:
    if len(sys.argv) < 4:
        print("example frames (no hardware):")
        for cid2 in (CID2_READ_STATUS, CID2_READ_DATA, CID2_READ_ALARM, CID2_WRITE):
            print("  CID2=%s station 1 -> %s" % (cid2, build_frame("01", cid2).decode()))
        print("\nusage: %s <serial-port> <station 1-3> <cid2 hex>" % sys.argv[0])
        return 0

    port, station, cid2 = sys.argv[1], int(sys.argv[2]), sys.argv[3].replace("0x", "")
    adr, rc, info = poll(port, station, cid2)
    print("reply adr=%s cid2=%s info=%s" % (adr, rc, info))
    print("note: alarm/status payloads are BIT FIELDS; temperatures are scaled x100.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
