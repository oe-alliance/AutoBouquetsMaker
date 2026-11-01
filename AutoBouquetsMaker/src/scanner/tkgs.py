# -*- coding: utf-8 -*-
# Turksat TKGS support for AutoBouquetsMaker. Reads the TKGS table (private table 0xA7 on PID 0x1FF5, broadcast on 42.0E) and
# turns it into the services and positions the other protocols get from the NIT, BAT and SDT.
# The TKGS table decoding is based on MSTKGS by Murat SEVER.
from __future__ import print_function

import errno
import fcntl
import os
import platform
import struct
import time
from types import SimpleNamespace

from enigma import eDVBFrontendParametersSatellite as Sat

from Components.config import config
from Components.NimManager import nimmanager

from .. import log
from .dvbscanner import DvbScanner, skipper

PID, TABLE = 0x1FF5, 0xA7
DUMP = "/tmp/tkgs_table.bin"  # the raw sections of the last read, saved when extra debug is on
NO_DATA, GIVE_UP = 45, 60  # seconds without any section, before a stalled read is abandoned
TOLERANCE = 3000  # kHz, how far an existing transponder may be from the TKGS one and still be the same


class NoData(Exception):
	"""Nothing arrived, this is probably not a TKGS transponder."""


def say(*args):
	print("[ABM-TKGS]", *args, file=log)


# ---- decoding the table -------------------------------------------------------------------------------------

def dvb_text(raw):
	data = bytearray(raw)
	if not data:
		return ""
	lead, codec = data[0], "iso-8859-9"
	if lead == 0x15:
		codec, data = "utf-8", data[1:]
	elif lead == 0x11:
		codec, data = "utf-16-be", data[1:]
	elif lead == 0x10:
		if len(data) < 3 or data[1] or data[2] in (0, 12) or data[2] > 15:
			return ""
		codec, data = "iso-8859-%d" % data[2], data[3:]
	elif 1 <= lead <= 0x0B:
		if lead == 8:
			return ""
		codec, data = "iso-8859-%d" % (lead + 4), data[1:]
	elif lead < 0x20:
		return ""
	try:
		text = bytes(data).decode(codec, "replace")
	except LookupError:
		text = bytes(data).decode("latin-1")
	return text[:120]


def bcd(chunk):
	total = 0
	for byte in chunk:
		if byte >> 4 > 9 or byte & 15 > 9:
			return None
		total = total * 100 + (byte >> 4) * 10 + (byte & 15)
	return total


def carrier(index, body, tsid, onid):
	if len(body) != 11:
		return None
	freq, orb, rate, tail = bcd(body[0:4]), bcd(body[4:6]), bcd(body[7:10]), body[10]
	if None in (freq, orb, rate) or tail >> 4 > 9 or orb > 1800 or tail & 15 > 10 and tail & 15 != 15:
		return None
	khz, baud, flags = freq * 10, (rate * 10 + (tail >> 4)) * 100, body[6]
	if not (3000000 <= khz <= 13000000 and 1000000 <= baud <= 50000000):
		return None
	return SimpleNamespace(rank=index, khz=khz, baud=baud, fec=tail & 15, orbit=orb if flags & 0x80 else (3600 - orb) % 3600,
		plane=flags >> 5 & 3, roll=flags >> 3 & 3, s2=flags >> 2 & 1, mod=flags & 3, tsid=tsid, onid=onid)


class Table:
	"""The decoded TKGS table: carriers, programs (one per TKGS channel number) and the HD / SD orders."""

	def __init__(self, data):
		self.b = bytearray(data)
		self.n = len(self.b)
		self.title, self.carriers, self.programs, self.orders = "", [], [], {}
		try:
			at = 2 + self.word(0)
			for tag, body in self.tags(2, at):
				if tag == 0x90 and len(body) >= 4:
					self.title = dvb_text(body[4:4 + body[3]])
			self.orders_at(self.carriers_at(self.first_carrier(at)))
		except IndexError:
			raise ValueError("table ended early")
		self.programs.sort(key=lambda p: p.chno)

	def word(self, at):
		if at + 2 > self.n:
			raise ValueError("table ended early @%d" % at)
		return self.b[at] << 8 | self.b[at + 1]

	def span(self, at):
		return (self.b[at] & 15) << 8 | self.b[at + 1]

	def tags(self, start, stop):
		out, at = [], start
		while at < stop:
			if at + 2 > stop or at + 2 + self.b[at + 1] > stop:
				raise ValueError("bad descriptor loop @%d" % at)
			out.append((self.b[at], self.b[at + 2:at + 2 + self.b[at + 1]]))
			at += 2 + self.b[at + 1]
		return out

	def first_carrier(self, at):
		for i in range(at, min(self.n, at + 512)):
			size = self.b[i]
			if size >= 13 and i + 1 + size < self.n and self.b[i + 1 + size] == 0x42:
				try:
					if any(tag == 0x43 for tag, body in self.tags(i + 1, i + 1 + size)):
						return i
				except ValueError:
					pass
		raise ValueError("no transponder loop")

	def carriers_at(self, at):
		while at < self.n and self.b[at]:
			size, car = self.b[at], None
			head = at + 1 + size
			tsid, onid = self.word(head + 3), self.word(head + 8)
			for tag, body in self.tags(at + 1, head):
				if tag == 0x43:
					car = carrier(len(self.carriers), body, tsid, onid)
			if car is None:
				raise ValueError("bad transponder @%d" % at)
			self.carriers.append(car)
			services, at = self.services_at(head)
			at = self.lineup_at(at, services, car)
		return at + 1

	def services_at(self, at):
		b, found = self.b, {}
		while True:
			if b[at] != 0x42:
				raise ValueError("SDT expected @%d" % at)
			stop = at + 3 + self.span(at + 1)
			if stop > self.n:
				raise ValueError("SDT overflows @%d" % at)
			cursor = at + 11
			while cursor < stop - 4:
				sid, size = self.word(cursor), self.span(cursor + 3)
				if cursor + 5 + size > stop - 4:
					raise ValueError("service overflows @%d" % cursor)
				info = SimpleNamespace(kind=None, name="", brand="", scrambled=bool(b[cursor + 3] & 0x10))
				for tag, body in self.tags(cursor + 5, cursor + 5 + size):
					if tag == 0x48 and len(body) >= 3:
						plen = body[1]
						info.kind, info.brand = body[0], dvb_text(body[2:2 + plen])
						if 2 + plen < len(body):
							info.name = dvb_text(body[3 + plen:3 + plen + body[2 + plen]])
				found[sid] = info
				cursor += 5 + size
			if b[at + 6] >= b[at + 7]:
				return found, stop
			at = stop

	def lineup_at(self, at, services, car):
		stop = at + 2 + self.word(at)
		if stop > self.n:
			raise ValueError("lineup overflows @%d" % at)
		cursor = at + 2
		while cursor < stop:
			lcn = self.word(cursor)
			if self.b[cursor + 2] != 0x02:
				raise ValueError("PMT expected @%d" % cursor)
			sid = self.word(cursor + 5)
			info = services.get(sid)
			if info is not None:
				self.programs.append(SimpleNamespace(chno=lcn, sid=sid, name=info.name, kind=info.kind, brand=info.brand, scrambled=info.scrambled, car=car))
			cursor += 5 + self.span(cursor + 3)
		return stop

	def orders_at(self, at):
		if at + 2 > self.n:
			return
		stop, cursor = min(self.n, at + 2 + self.word(at)), at + 2
		while cursor + 2 <= stop:
			size, name, rows = self.word(cursor) & 0x0FFF, None, []
			for tag, body in self.tags(cursor + 2, min(stop, cursor + 2 + size)):
				if tag == 0x93 and len(body) >= 4:
					name = dvb_text(body[4:4 + body[3]])
				elif tag == 0x94 and len(body) >= 4:
					rows.append((body[0] << 8 | body[1], body[2] << 8 | body[3]))
			self.orders[name or "List %d" % (len(self.orders) + 1)] = rows
			cursor += 2 + size


# ---- collecting the sections --------------------------------------------------------------------------------

CRC_TABLE = []
for _byte in range(256):
	_acc = _byte << 24
	for _bit in range(8):
		_acc = (_acc << 1 ^ 0x04C11DB7 if _acc & 0x80000000 else _acc << 1) & 0xFFFFFFFF
	CRC_TABLE.append(_acc)


def crc(data):
	acc = 0xFFFFFFFF
	for byte in data:
		acc = (acc << 8 & 0xFFFFFFFF) ^ CRC_TABLE[(acc >> 24) ^ byte]
	return acc  # 0 for a section with a valid CRC


class Sections:
	"""Collects the TKGS sections. Sections with a bad or missing CRC (some drivers strip it) count after two identical copies."""

	def __init__(self):
		self.parts = {}  # table id extension -> [version, last section number, {section number: bytes}]
		self.votes = {}
		self.fresh = self.grew = 0.0

	def offer(self, raw):
		b = bytearray(raw)
		if len(b) < 12 or b[0] != TABLE or not b[1] & 0x80:
			return
		size = 3 + ((b[1] & 15) << 8 | b[2])
		if len(b) == size - 4:
			b += bytes(4)
		if len(b) != size or not b[5] & 1 or b[6] > b[7]:
			return
		raw, ext, ver, seq, last = bytes(b), b[3] << 8 | b[4], b[5] >> 1 & 31, b[6], b[7]
		if crc(raw):
			key = (ext, ver, seq, last, raw)
			if len(self.votes) > 2000:  # a noisy stream, don't keep it all
				self.votes.clear()
			self.votes[key] = self.votes.get(key, 0) + 1
			if self.votes[key] < 2:
				return
		part, now = self.parts.get(ext), time.monotonic()
		if part is None:
			part = self.parts[ext] = [ver, last, {}]
			self.fresh = now
		elif part[0] != ver:
			if (ver - part[0]) % 32 >= 16:
				return  # an older version
			part[:] = [ver, last, {}]
		elif part[1] != last:
			return
		if seq not in part[2]:
			part[2][seq] = raw
			self.grew = now

	def progress(self):
		return sum(len(p[2]) for p in self.parts.values()), sum(p[1] + 1 for p in self.parts.values())

	def done(self):
		return bool(self.parts) and all(len(p[2]) == p[1] + 1 for p in self.parts.values())

	def raw(self):
		return b"".join(p[2][i] for _, p in sorted(self.parts.items()) for i in sorted(p[2]))

	def data(self):
		return b"".join(p[2][i][8:-4] for _, p in sorted(self.parts.items()) for i in sorted(p[2]))


class TsSections:
	"""Cuts sections out of the TS packets of the TKGS PID."""

	def __init__(self):
		self.raw, self.part, self.cc = bytearray(), None, None

	def push(self, chunk):
		out, buf, pos = [], self.raw, 0
		buf += chunk
		while len(buf) - pos >= 188:
			if buf[pos] != 0x47:
				pos += 1
				continue
			self.packet(buf[pos:pos + 188], out)
			pos += 188
		del buf[:pos]
		return out

	def packet(self, p, out):
		if (p[1] & 0x1F) << 8 | p[2] != PID:
			return
		if p[1] & 0x80:
			self.part = None
			return
		control, cc = p[3] >> 4 & 3, p[3] & 15
		if control in (0, 2):
			return
		start = 5 + p[4] if control == 3 else 4
		if start >= 188:
			return
		if self.cc is not None:
			if cc == self.cc:
				return  # repeated packet
			if cc != (self.cc + 1) % 16:
				self.part = None  # a packet was lost
		self.cc = cc
		body = p[start:]
		if p[1] & 0x40:
			pointer, body = body[0], body[1:]
			if self.part is not None:
				self.part += body[:pointer]
				self.harvest(out)
			self.part = bytearray(body[pointer:])
		elif self.part is None:
			return
		else:
			self.part += body
		self.harvest(out)

	def harvest(self, out):
		part = self.part
		while part is not None and len(part) >= 3:
			if part[0] == 0xFF:
				part = None
				break
			size = 3 + ((part[1] & 15) << 8 | part[2])
			if len(part) < size:
				break
			if part[0] == TABLE:
				out.append(bytes(part[:size]))
			part = part[size:]
		self.part = part or None


class Demux:
	"""A raw demux tap on the TKGS PID, or a section filter if the driver refuses the tap."""
	FILTER = struct.Struct("=H16s16s16s2xII")
	PES = struct.Struct("=H2xIIII")

	def __init__(self, path, frontend):
		try:
			self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
		except OSError:
			self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
		legacy = platform.machine().lower().startswith(("mips", "ppc", "powerpc", "sparc", "parisc", "alpha"))
		self.bits, self.none, self.write = (13, 1, 4) if legacy else (14, 0, 1)
		self.ts = None
		self.ioctl(42)
		self.ioctl(49, struct.pack("=I", frontend), 4)  # DMX_SET_SOURCE, the frontend the demux reads from
		for size in (1 << 20, 1 << 19, 1 << 18, 1 << 17):
			if self.ioctl(45, size) is not None:
				break
		if not self.tap() and self.ioctl(43, self.FILTER.pack(PID, bytes([TABLE]), b"\xff", b"", 0, 4), self.FILTER.size) is None:  # the tap first, as the section filter of some drivers drops the large sections. 4 = start immediately
			say("neither the TS tap nor the section filter could be started")

	def ioctl(self, nr, arg=0, size=0):
		request = ((self.write if size else self.none) << (16 + self.bits)) | size << 16 | ord("o") << 8 | nr
		try:
			try:
				return fcntl.ioctl(self.fd, request, arg)
			except OverflowError:
				return fcntl.ioctl(self.fd, request - (1 << 32), arg)
		except OSError:
			return None

	def tap(self):
		if self.ioctl(44, self.PES.pack(PID, 0, 3, 20, 4), self.PES.size) is None:  # DMX_OUT_TSDEMUX_TAP, DMX_PES_OTHER
			return False
		self.ts = TsSections()
		return True

	def read(self):
		out = []
		for _ in range(32):
			try:
				data = os.read(self.fd, 188 * 256 if self.ts else 8192)
			except OSError as e:
				if e.errno == errno.EOVERFLOW:
					continue
				break
			if not data:
				break
			out += self.ts.push(data) if self.ts else [data]
		return out

	def close(self):
		self.ioctl(42)
		try:
			os.close(self.fd)
		except OSError:
			pass


# ---- the download -------------------------------------------------------------------------------------------

def read(device, frontend, extra_debug=False):
	"""Reads the TKGS table from the transponder the demuxer is tuned to. Raises NoData if no section arrives, IOError or ValueError if the read fails."""
	demux, sections, start = Demux(device, frontend), Sections(), time.monotonic()
	try:
		seen, shown = {}, 0  # debug: what arrived, by (table id extension, version, section number, length, crc ok)
		while True:
			for raw in demux.read():
				if len(raw) > 7:
					key = (raw[3] << 8 | raw[4], raw[5] >> 1 & 31, raw[6], len(raw), not crc(raw))
					seen[key] = seen.get(key, 0) + 1
				sections.offer(raw)
			now, have = time.monotonic() - start, sections.progress()
			if extra_debug and now >= shown + 5:
				shown += 5
				say("%ds: %d/%d sections, arrived (ext, version, section, bytes, crc ok): count %s" % (now, have[0], have[1], sorted(seen.items())))
			if sections.done() and time.monotonic() - sections.fresh >= 2:
				break
			if not sections.parts and now > NO_DATA:
				raise NoData()
			if now > GIVE_UP and (now > 2 * GIVE_UP or time.monotonic() - sections.grew > 15):
				dump(sections, extra_debug)
				raise IOError("incomplete TKGS table (%d/%d sections)" % have)
			time.sleep(0.1)
	finally:
		demux.close()
	dump(sections, extra_debug)
	return Table(sections.data())


def dump(sections, extra_debug):
	if extra_debug and sections.parts:
		try:
			with open(DUMP, "wb") as f:
				f.write(sections.raw())
			say("saved the %d sections read to %s" % (sections.progress()[0], DUMP))
		except OSError as e:
			say("could not save the sections", e)


# ---- the services -------------------------------------------------------------------------------------------

def services(scanner, table, transponders, servicehacks, order):
	"""{"video": {position: service}, "radio": {position: service}} from the table. Transponders and services are added to transponders.
	The TSID and ONID in the TKGS table are not the real ones, so the transponders and services already in the service list are matched
	by frequency (transponder) and service id (service). What is not there yet is added."""
	new_tps, keys, known_sids = [], {}, {}
	existing = [tp for tp in transponders.values() if tp.get("dvb_type") == "dvbs"]
	configured = set(sat[0] for nim in nimmanager.getNimListOfType("DVB-S") for sat in nimmanager.getSatListForNim(nim)) if config.autobouquetsmaker.skipservices.value else None

	def sids(tp):  # the services we know on a transponder, by service id
		ident = id(tp)
		if ident not in known_sids:
			known_sids[ident] = dict((s["service_id"], s) for s in tp["services"].values())
		return known_sids[ident]

	def make(car, tsid, onid):
		tp = {"dvb_type": "dvbs", "frequency": car.khz, "symbol_rate": car.baud, "polarization": car.plane, "orbital_position": car.orbit,
			"fec_inner": car.fec if car.fec == Sat.FEC_None or car.fec <= Sat.FEC_9_10 else Sat.FEC_Auto, "inversion": Sat.Inversion_Unknown, "flags": 0,
			"system": Sat.System_DVB_S2 if car.s2 else Sat.System_DVB_S, "modulation": car.mod, "roll_off": car.roll, "pilot": Sat.Pilot_Unknown,
			"transport_stream_id": tsid, "original_network_id": onid, "services": {}}
		tp["namespace"] = scanner.buildNamespace(tp)
		return tp

	for car in table.carriers:
		if configured is not None and car.orbit not in configured:
			continue
		progs = [p for p in table.programs if p.car is car and (p.kind in DvbScanner.VIDEO_ALLOWED_TYPES or p.kind in DvbScanner.AUDIO_ALLOWED_TYPES)]
		near = [tp for tp in existing + new_tps if tp["orbital_position"] == car.orbit and tp["polarization"] == car.plane and abs(tp["frequency"] - car.khz) <= TOLERANCE]
		near.sort(key=lambda tp: -sum(1 for p in progs if p.sid in sids(tp)))  # the one that already has most of these services first
		if not near:
			tp = make(car, 0x0F00 + car.rank, 0)  # made up ids, the same ones MSTKGS uses
			transponders["%x:%x:%x" % (tp["namespace"], tp["transport_stream_id"], tp["original_network_id"])] = tp
			new_tps.append(tp)
			near, what = [tp], "new"
		else:
			home, what = near[0], "known"
			if not any(home is tp for tp in new_tps) and (abs(home["symbol_rate"] - car.baud) > 500000 or (home.get("system", 0) != 0) != bool(car.s2)):  # parameters are wrong, correct them
				fixed = make(car, home["transport_stream_id"], home["original_network_id"])
				for field in ("symbol_rate", "fec_inner", "system", "modulation", "roll_off", "pilot"):
					home[field] = fixed[field]
				what = "corrected"
		say("transponder %d %s %d %s: %s, %d services, tsid %d onid %d namespace %x" % (car.khz // 1000, "HVLR"[car.plane], car.baud // 1000, "S2" if car.s2 else "S", what, len(progs), near[0]["transport_stream_id"], near[0]["original_network_id"], near[0]["namespace"]))
		for p in progs:
			service = next((sids(tp)[p.sid] for tp in near if p.sid in sids(tp)), None)
			if service is None:
				home = near[0]
				service = {"service_id": p.sid, "transport_stream_id": home["transport_stream_id"], "original_network_id": home["original_network_id"], "service_type": p.kind,
					"service_name": p.name, "provider_name": p.brand, "free_ca": int(p.scrambled), "flags": 0, "namespace": home["namespace"]}
				home["services"]["%x:%x" % (service["service_type"], service["service_id"])] = service
				sids(home)[p.sid] = service
			service["orbital_position"] = car.orbit
			keys[p.chno] = service
	rows = sorted(table.orders.get(order) or next(iter(table.orders.values()), None) or [(n, n) for n in keys])
	video, radio, skip, taken = {}, {}, skipper(), set()
	for pos, chno in rows:
		service = keys.get(chno)
		if service is None or id(service) in taken:
			continue
		if servicehacks:
			skip.skip = False
			exec(servicehacks)
			if skip.skip:
				continue
		taken.add(id(service))
		service["number"], service["numbers"] = pos, [pos]
		(radio if service["service_type"] in DvbScanner.AUDIO_ALLOWED_TYPES else video)[pos] = service
	say("%s: %d video and %d radio services in the %s list, highest position %d" % (table.title, len(video), len(radio), order, rows[-1][0] if rows else 0))
	return {"video": video, "radio": radio}
