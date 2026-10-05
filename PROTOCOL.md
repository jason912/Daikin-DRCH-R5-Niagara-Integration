# DRCH-R5 protocol notes (China Telecom / P&T spec #625, "邮电规格")

The DRCH-R5 interface board speaks a master/slave serial protocol derived from the China Telecom / P&T
**#625** monitoring specification (邮电规格 625 号基准). It predates Modbus, is ASCII-hex encoded, and is
documented almost exclusively in Chinese.

The board is used with **Daikin single-split ducted indoor units** (one outdoor : one indoor) — e.g. the
**SkyAir DQ series** medium-static-pressure duct type, **not VRV** — which are common in data rooms. On the Daikin
side it taps the indoor unit's **P1P2** wired-remote (controller) line and re-presents the data as the #625 serial
protocol.

These notes describe what we verified on a live site and cross-checked against the vendor's original
"社外版" (external) specification. **Always confirm against your own vendor document** — variants exist.

---

## 1. Physical layer

| Parameter | Value |
|---|---|
| Electrical | RS-485 (some builds also expose RS-232) |
| Baud / framing | **9600, 8 data bits, no parity, 1 stop bit (8N1)** |
| Duplex | Half-duplex, polled |
| Topology | The board is a **slave**; your gateway/host is the master. One board per bus segment (or address it uniquely) |
| Capacity | 1 board serves up to **3 indoor units**, seen as LINE0 / LINE1 / LINE2 = station **1 / 2 / 3** |

> **The parity trap.** The original manual text says *odd parity*. That is wrong — the working setting is
> **no parity**. With odd parity the board simply never answers, and nothing in the error path hints at parity.

Connection to the Daikin side: the board is wired **in parallel with the indoor unit's wired-remote
(controller) line — the P1P2 two-wire bus** — and acts as a second remote controller. Up to three indoor units
per board, one LINE each.

## 2. Frame layout

All bytes between `SOI` and `EOI` are transmitted as **ASCII hex characters** (two characters per byte value).

```
SOI   VER   ADR   CID1   CID2   LENGTH            INFO    CHKSUM   EOI
7EH   "20"  xx    "60"   xx     LENID(4) LCHKSUM(1) ...    (2)     0DH
```

| Field | Bytes | Meaning |
|---|---|---|
| `SOI` | 1 | Start of information = `0x7E` |
| `VER` | 2 | Protocol version, ASCII `"20"` |
| `ADR` | 2 | Device address (board DIP/ID), ASCII hex |
| `CID1` | 2 | Command class 1 = `"60"` (air-conditioning) |
| `CID2` | 2 | Command code (see §4) |
| `LENID` | 4 | Length of `INFO` in bytes, 4 ASCII hex chars (e.g. `"0000"`) |
| `LCHKSUM` | 1 | Length checksum, 1 ASCII hex char (see §3) |
| `INFO` | 2·n | Payload, ASCII hex |
| `CHKSUM` | 2 | Frame checksum, 2 ASCII hex chars (see §3) |
| `EOI` | 1 | End of information = `0x0D` |

Typical frame length for a short command: **19 ASCII characters**.

## 3. Checksums (the part everyone gets wrong)

**LCHKSUM** — over the four nibbles of `LENID`:

```
nibble_sum = sum of the four hex digits of LENID        # e.g. "0004" -> 0+0+0+4 = 4
LCHKSUM    = (16 - nibble_sum % 16) % 16                # 0 when nibble_sum % 16 == 0
```

**CHKSUM** — two's complement of the ASCII byte sum from `VER` through `INFO` (i.e. everything except
`SOI`, `CHKSUM` itself and `EOI`):

```
s      = sum(ord(c) for c in frame[1:-3])     # "20...INFO"
CHKSUM = (256 - s % 256) % 256
```

Reference implementation: [`examples/drch_r5_poll.py`](examples/drch_r5_poll.py).

### Worked examples (verified byte strings)

| Intent | Frame (ASCII) |
|---|---|
| Read status, station 1, CID2=`43H` | `7E 20 01 60 43 0000 0 80 0D` → `7E2001604300000800D` |
| Read data, station 1, CID2=`44H` | `7E 20 01 60 44 0000 0 7F 0D` → `7E20016044000007F0D` |
| Command, station 1, CID2=`51H` | `7E 20 01 60 51 0000 0 81 0D` → `7E2001605100000810D` |

## 4. Command codes (CID2)

| CID2 | Direction | Purpose |
|---|---|---|
| `43H` | read | Read run/status data |
| `44H` | read | Read measurement data (temperatures, etc.) |
| `47H` | read | Read alarm/accumulated data |
| `49H` | read | Read configuration/limits |
| `51H` | write | Set / control command |

The daisy-chained point table differs per board firmware; take the authoritative list from the vendor's
original specification. Command codes are echoed in the reply's `CID2`; the reply's `INFO` carries the payload.

## 5. Payload and scaling gotchas

- **Alarm and status data are bit fields.** Do not read a status word as a number — decode the individual
  bits, or your alarm points will be nonsense.
- **Return-air temperature arrives as an integer scaled ×100** (e.g. `2200` = 22.00 °C). Watch raw-vs-engineering
  scaling on both the gateway and the Niagara point.
- An **empty LINE reports offline** — this is normal for a board with fewer than three indoor units connected.
  Do not map it as a fault.
- After a **write**, always **read the run state back**. The write acknowledgement alone is not proof the
  indoor unit changed state.

## 6. Variants

Two frame families exist in the wild:

1. **P&T #625** frames: `7E … 0D` (documented above) — what the DRCH-R5 external specification describes.
2. A vendor "**Format2**" frame: `02 … 03` with a BCC XOR checksum.

A board answers **one** of them. If you get silence, confirm which family your board expects before assuming
wiring or parity is at fault.

## 7. Bring-up checklist

- [ ] RS-485 A/B correct, common ground, termination set
- [ ] **9600 8N1, parity NONE**
- [ ] Station number = LINE index (1/2/3), not an arbitrary address
- [ ] Poll one station at a time; allow generous inter-frame delay
- [ ] Verify `CHKSUM` before trusting a reply
- [ ] Decode bit-field alarms; scale temperatures ÷100
- [ ] Prove a write by reading the state back

---

*Part of [Daikin DRCH-R5 → Niagara integration notes](README.md). Shanghai GLINENET.*
