# Getting a DRCH-R5 P-board into Niagara

Once the board's serial protocol is tamed (see [`PROTOCOL.md`](PROTOCOL.md)), the Niagara side should be the easy
part. These are the choices and the two mapping rules that cost us time.

## The three routes

| Route | What it is | Trade-off |
|---|---|---|
| 1. Vendor protocol gateway | A configuration box with a `DAIKIN_DRCH-R5` plugin; exposes **Modbus TCP :502** | Fast to deploy; you inherit the vendor's point table and its limits |
| 2. Daikin's own gateway (IRACC) | Native Daikin interface | Fixed point set, limited flexibility, vendor lead times |
| 3. **Custom edge gateway** | Small Linux IPC: serial poller + Modbus TCP server | Most work up front; **full control** of timing, retries and writable points |

We shipped **route 3** because the site needed **write** capability that the off-the-shelf boxes would not expose.

## A working edge-gateway shape

```
Daikin indoor units (×3)
        │  remote-controller line (parallel)
   DRCH-R5 P-board
        │  RS-485, 9600 8N1, no parity
   Edge IPC (Linux)
     ├─ serial poller        → builds/parses #625 frames
     ├─ Modbus TCP server    → :502
        │
   Niagara (N4)
     └─ Modbus TCP driver → device → points
```

Keep the poller and the Modbus server as separate concerns: the poller owns the timing of the serial bus
(that bus is slow and unforgiving), while the Modbus server is a cache in front of it.

## Niagara setup

1. Add a **Modbus TCP** network in Niagara; point it at the edge gateway's IP, port **502**, unit ID as configured.
2. Create the device, then add points per the point table.
3. Set poll frequency to something sane for a 9600-baud bus — do not let the supervisor's poll rate drive the
   serial poll rate.
4. Watch **byte/word order** on any scaled (float) point. Little-endian is common but not universal; if a
   temperature reads as zero, swap the words before blaming the gateway.

## Two address-mapping rules that cost us time

Where the gateway presents a legacy BACnet-style register numbering but Niagara reads raw Modbus addresses:

- **Analog points:** `Modbus address = BACnet register × 2 + 1`
- **Digital points:** `Modbus address = BACnet register + 1`

These are easy to get "almost right" — a point that is off by one reads a neighbour's value and looks plausible.

## The write-control gotcha

Read is easy. **Write** is where this board humbles people.

- Temperature **setpoints** and **fan speed** are effectively **locked** on this interface — writes do not take.
- What *does* work is **start/stop** via the board's **hidden control addresses**:

  | Control | Address | Function code | Value |
  |---|---|---|---|
  | Start / Stop | **2000 / 2001** | `FC06` (write single register) | `0` / `1` |

  The vendor documentation does not advertise these clearly. We found them, verified them on site, and that is the
  only writable control path we ship.

- Always **read the run state back** after a write. The acknowledgement alone proves nothing.

## Commissioning checklist

- [ ] Serial params **9600 8N1, parity none**; station = LINE index
- [ ] One indoor unit per LINE; empty LINE offline is normal
- [ ] Alarms decoded as **bit fields**, not values
- [ ] Return-air temperature **÷100**
- [ ] Analog/digital address offsets applied (×2+1 / +1)
- [ ] Start/stop proven by read-back on the real unit
- [ ] Poll rates matched to bus bandwidth

---

*Part of [Daikin DRCH-R5 → Niagara integration notes](README.md). Shanghai GLINENET.*
