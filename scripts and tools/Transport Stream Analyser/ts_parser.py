#!/usr/bin/env python3
"""
DVB Transport Stream Parser
Extracts NIT, SDT and BAT tables from a raw .ts recording.

Usage: python3 ts_parser.py <file.ts>

Outputs:
  - Network Information Table (NIT) - transponder list and network descriptors
  - Service Description Table (SDT) - service names and types
  - Bouquet Association Table (BAT) - bouquet names and LCN assignments
"""

import sys
import struct
from collections import defaultdict

TS_PACKET_SIZE = 188
SYNC_BYTE = 0x47


def parse_ts_file(filename):
    """Read TS file and collect SI table sections by PID."""
    tables = defaultdict(list)
    sections = {}

    with open(filename, 'rb') as f:
        while True:
            packet = f.read(TS_PACKET_SIZE)
            if len(packet) < TS_PACKET_SIZE:
                break
            if packet[0] != SYNC_BYTE:
                continue

            pid = ((packet[1] & 0x1F) << 8) | packet[2]
            payload_unit_start = (packet[1] >> 6) & 1
            adaptation_field_control = (packet[3] >> 4) & 3

            # Only interested in SI PIDs
            if pid not in (0x00, 0x10, 0x11, 0x12, 0x14):
                continue

            payload_offset = 4
            if adaptation_field_control in (2, 3):
                af_len = packet[4]
                payload_offset = 5 + af_len

            if payload_offset >= TS_PACKET_SIZE:
                continue

            payload = packet[payload_offset:]

            if payload_unit_start:
                pointer = payload[0]
                payload = payload[1 + pointer:]
                sections[pid] = bytearray(payload)
            else:
                if pid in sections:
                    sections[pid].extend(payload)

            if pid in sections and len(sections[pid]) >= 3:
                table_id = sections[pid][0]
                section_length = ((sections[pid][1] & 0x0F) << 8) | sections[pid][2]

                if len(sections[pid]) >= 3 + section_length:
                    tables[pid].append((table_id, bytes(sections[pid][:3 + section_length])))
                    sections[pid] = sections[pid][3 + section_length:]

    return tables


def parse_descriptor(data, offset):
    """Parse a single descriptor."""
    if offset + 2 > len(data):
        return None
    tag = data[offset]
    length = data[offset + 1]
    desc_data = data[offset + 2:offset + 2 + length]
    return tag, length, desc_data, offset + 2 + length


def parse_descriptors(data, offset, end):
    """Parse a list of descriptors."""
    descs = []
    while offset < end:
        result = parse_descriptor(data, offset)
        if not result:
            break
        tag, length, desc_data, offset = result
        descs.append((tag, desc_data))
    return descs


def decode_text(data):
    """Decode DVB text string."""
    try:
        if len(data) > 0 and data[0] < 0x20:
            enc = data[0]
            data = data[1:]
            encodings = {
                0x01: 'iso-8859-5',
                0x02: 'iso-8859-6',
                0x03: 'iso-8859-7',
                0x04: 'iso-8859-8',
                0x05: 'utf-8',
                0x06: 'iso-8859-10',
                0x07: 'iso-8859-11',
                0x09: 'iso-8859-13',
                0x0a: 'iso-8859-14',
                0x0b: 'iso-8859-15',
            }
            return data.decode(encodings.get(enc, 'latin-1'), errors='replace')
        return data.decode('latin-1', errors='replace')
    except Exception:
        return repr(data)


def parse_nit(data):
    """Parse and print Network Information Table."""
    if len(data) < 10:
        return
    table_id = data[0]
    network_id = (data[3] << 8) | data[4]
    network_desc_length = ((data[8] & 0x0F) << 8) | data[9]

    print(f"\n{'='*60}")
    print(f"NIT (table_id=0x{table_id:02x}) Network ID: {network_id} (0x{network_id:04x})")

    offset = 10
    end = 10 + network_desc_length
    descs = parse_descriptors(data, offset, end)
    for tag, ddata in descs:
        if tag == 0x40:  # network_name_descriptor
            print(f"  Network Name: {decode_text(ddata)}")
        elif tag == 0x43:  # satellite_delivery_system_descriptor
            freq = int(f"{ddata[0]:02x}{ddata[1]:02x}{ddata[2]:02x}{ddata[3]:02x}") / 100
            print(f"  Satellite delivery: freq={freq}MHz")
        else:
            print(f"  Descriptor tag=0x{tag:02x}: {ddata[:16].hex()}")

    if end + 2 > len(data):
        return
    ts_loop_length = ((data[end] & 0x0F) << 8) | data[end + 1]
    offset = end + 2
    ts_end = offset + ts_loop_length

    print(f"\n  Transport Streams:")
    while offset + 6 <= ts_end and offset + 6 <= len(data):
        tsid = (data[offset] << 8) | data[offset + 1]
        onid = (data[offset + 2] << 8) | data[offset + 3]
        ts_desc_length = ((data[offset + 4] & 0x0F) << 8) | data[offset + 5]
        offset += 6

        print(f"\n    TSID: {tsid} (0x{tsid:04x}), ONID: {onid} (0x{onid:04x})")

        ts_descs = parse_descriptors(data, offset, offset + ts_desc_length)
        for tag, ddata in ts_descs:
            if tag == 0x43:  # satellite_delivery_system_descriptor
                freq = int(f"{ddata[0]:02x}{ddata[1]:02x}{ddata[2]:02x}{ddata[3]:02x}") / 100
                orb = int(f"{ddata[4]:02x}{ddata[5]:02x}") / 10
                west = (ddata[6] >> 7) & 1
                pol_bits = (ddata[6] >> 5) & 3
                pol = ['H', 'V', 'L', 'R'][pol_bits]
                sr = int(f"{ddata[7]:02x}{ddata[8]:02x}{ddata[9]:02x}{ddata[10] >> 4:01x}") / 10
                print(f"      Satellite: {freq}MHz {pol} SR:{sr} Orbital:{orb}{'W' if west else 'E'}")
            elif tag == 0x41:  # service_list_descriptor
                i = 0
                while i + 3 <= len(ddata):
                    sid = (ddata[i] << 8) | ddata[i + 1]
                    stype = ddata[i + 2]
                    print(f"      Service: SID={sid} (0x{sid:04x}) type=0x{stype:02x}")
                    i += 3
            elif tag == 0x83:  # logical_channel_descriptor
                i = 0
                while i + 4 <= len(ddata):
                    sid = (ddata[i] << 8) | ddata[i + 1]
                    lcn = ((ddata[i + 2] & 0x03) << 8) | ddata[i + 3]
                    print(f"      LCN: SID={sid} (0x{sid:04x}) -> LCN={lcn}")
                    i += 4
            elif tag == 0x88:  # HD simulcast LCN
                i = 0
                while i + 4 <= len(ddata):
                    sid = (ddata[i] << 8) | ddata[i + 1]
                    lcn = ((ddata[i + 2] & 0x03) << 8) | ddata[i + 3]
                    print(f"      HD-LCN: SID={sid} (0x{sid:04x}) -> LCN={lcn}")
                    i += 4
            else:
                print(f"      Descriptor tag=0x{tag:02x} len={len(ddata)}: {ddata[:16].hex()}")

        offset += ts_desc_length


def parse_sdt(data):
    """Parse and print Service Description Table."""
    if len(data) < 11:
        return
    table_id = data[0]
    tsid = (data[3] << 8) | data[4]
    onid = (data[8] << 8) | data[9]

    print(f"\n{'='*60}")
    print(f"SDT (table_id=0x{table_id:02x}) TSID: {tsid} (0x{tsid:04x}), ONID: {onid} (0x{onid:04x})")

    offset = 11
    while offset + 5 <= len(data) - 4:  # -4 for CRC
        sid = (data[offset] << 8) | data[offset + 1]
        desc_length = ((data[offset + 3] & 0x0F) << 8) | data[offset + 4]
        offset += 5

        descs = parse_descriptors(data, offset, offset + desc_length)
        for tag, ddata in descs:
            if tag == 0x48:  # service_descriptor
                stype = ddata[0]
                prov_len = ddata[1]
                provider = decode_text(ddata[2:2 + prov_len])
                name_len = ddata[2 + prov_len]
                name = decode_text(ddata[3 + prov_len:3 + prov_len + name_len])
                print(f"  SID={sid} (0x{sid:04x}) type=0x{stype:02x} provider='{provider}' name='{name}'")

        offset += desc_length


def parse_bat(data):
    """Parse and print Bouquet Association Table."""
    if len(data) < 10:
        return
    table_id = data[0]
    bouquet_id = (data[3] << 8) | data[4]
    bouquet_desc_length = ((data[8] & 0x0F) << 8) | data[9]

    print(f"\n{'='*60}")
    print(f"BAT (table_id=0x{table_id:02x}) Bouquet ID: {bouquet_id} (0x{bouquet_id:04x})")

    offset = 10
    end = 10 + bouquet_desc_length
    descs = parse_descriptors(data, offset, end)
    for tag, ddata in descs:
        if tag == 0x47:  # bouquet_name_descriptor
            print(f"  Bouquet Name: {decode_text(ddata)}")
        else:
            print(f"  Bouquet Descriptor tag=0x{tag:02x}: {ddata[:16].hex()}")

    if end + 2 > len(data):
        return
    ts_loop_length = ((data[end] & 0x0F) << 8) | data[end + 1]
    offset = end + 2
    ts_end = offset + ts_loop_length

    while offset + 6 <= ts_end and offset + 6 <= len(data):
        tsid = (data[offset] << 8) | data[offset + 1]
        onid = (data[offset + 2] << 8) | data[offset + 3]
        ts_desc_length = ((data[offset + 4] & 0x0F) << 8) | data[offset + 5]
        offset += 6

        print(f"\n  TS TSID={tsid} (0x{tsid:04x}) ONID={onid} (0x{onid:04x})")

        ts_descs = parse_descriptors(data, offset, offset + ts_desc_length)
        for tag, ddata in ts_descs:
            if tag == 0x83:  # logical_channel_descriptor
                i = 0
                while i + 4 <= len(ddata):
                    sid = (ddata[i] << 8) | ddata[i + 1]
                    lcn = ((ddata[i + 2] & 0x03) << 8) | ddata[i + 3]
                    visible = (ddata[i + 2] >> 2) & 1
                    print(f"    LCN: SID={sid} (0x{sid:04x}) -> LCN={lcn} visible={visible}")
                    i += 4
            elif tag == 0x88:  # HD simulcast LCN
                i = 0
                while i + 4 <= len(ddata):
                    sid = (ddata[i] << 8) | ddata[i + 1]
                    lcn = ((ddata[i + 2] & 0x03) << 8) | ddata[i + 3]
                    print(f"    HD-LCN: SID={sid} (0x{sid:04x}) -> LCN={lcn}")
                    i += 4
            elif tag == 0x41:  # service_list_descriptor
                i = 0
                while i + 3 <= len(ddata):
                    sid = (ddata[i] << 8) | ddata[i + 1]
                    stype = ddata[i + 2]
                    print(f"    Service: SID={sid} (0x{sid:04x}) type=0x{stype:02x}")
                    i += 3
            else:
                print(f"    Descriptor tag=0x{tag:02x} len={len(ddata)}: {ddata[:32].hex()}")

        offset += ts_desc_length


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.ts>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Parsing {filename}...")
    tables = parse_ts_file(filename)

    print(f"\nFound tables on PIDs:")
    for pid, entries in sorted(tables.items()):
        table_ids = set(t[0] for t in entries)
        print(f"  PID 0x{pid:04x}: table_ids={[hex(t) for t in sorted(table_ids)]} ({len(entries)} sections)")

    # Parse NIT (PID 0x10, table_id 0x40=actual, 0x41=other)
    seen = set()
    for table_id, data in tables.get(0x10, []):
        key = (table_id, data[3], data[4], data[6])
        if key not in seen:
            seen.add(key)
            if table_id in (0x40, 0x41):
                parse_nit(data)

    # Parse SDT (PID 0x11, table_id 0x42=actual, 0x46=other)
    seen = set()
    for table_id, data in tables.get(0x11, []):
        key = (table_id, data[3], data[4], data[6])
        if key not in seen:
            seen.add(key)
            if table_id in (0x42, 0x46):
                parse_sdt(data)

    # Parse BAT (PID 0x11, table_id 0x4a)
    seen = set()
    for table_id, data in tables.get(0x11, []):
        key = (table_id, data[3], data[4], data[6])
        if key not in seen:
            seen.add(key)
            if table_id == 0x4a:
                parse_bat(data)


if __name__ == '__main__':
    main()
