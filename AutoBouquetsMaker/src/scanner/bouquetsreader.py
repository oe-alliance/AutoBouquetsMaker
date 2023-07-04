from __future__ import print_function

from .. import log
import re


class BouquetsReader():
	def parseBouquetIndex(self, path, content):
		ret = []
		rows = content.split("\n")
		for row in rows:
			result = re.match("^.*FROM BOUQUET \"(.+)\" ORDER BY.*$", row) or re.match("[#]SERVICE[:] (?:[0-9a-f]+[:])+([^:]+[.](?:tv|radio))$", row, re.IGNORECASE)
			if result is None:
				continue

			filename = result.group(1)

			try:
				bouquet = open(path + "/" + filename, "rb")
			except Exception as e:
				continue

			firstline = bouquet.read().split(b"\n")[0].decode(errors="ignore")
			bouquet.close()

			if firstline[:6] == "#NAME ":
				bouquetname = firstline[6:]
			else:
				bouquetname = "Unknown"

			ret.append({"filename": filename, "name": bouquetname})

		return ret

	def getBouquetsList(self, path):
		ret = {}
		for bouquet_type in ["tv", "radio"]:
			try:
				bouquets = open(path + "/bouquets." + bouquet_type, "r")
			except Exception as e:
				continue

			content = bouquets.read()
			bouquets.close()

			ret[bouquet_type] = self.parseBouquetIndex(path, content)

		return ret

	def readLamedb(self, path):
		print("[ABM-BouquetsReader] Reading lamedb...", file=log)

		transponders = {}

		try:
			lamedb = open(path + "/lamedb", "r")
		except Exception as e:
			return transponders

		content = lamedb.read()
		lamedb.close()

		lamedb_ver = 4
		result = re.match('eDVB services /([45])/', content)
		if result:
			lamedb_ver = int(result.group(1))
			print("[ABM-BouquetsReader] lamedb ver", lamedb_ver, file=log)
		if lamedb_ver == 4:
			transponders = self.parseLamedbV4Content(content)
		elif lamedb_ver == 5:
			transponders = self.parseLamedbV5Content(content)
		return transponders

	def parseLamedbV4Content(self, content):
		transponders = {}
		transponders_count = 0
		services_count = 0

		tp_start = content.find("transponders\n")
		tp_stop = content.find("end\n")

		tp_blocks = content[tp_start + 13:tp_stop].strip().split("/")
		content = content[tp_stop + 4:]

		for block in tp_blocks:
			rows = block.strip().split("\n")
			if len(rows) != 2:
				continue

			first_row = rows[0].strip().split(":")
			if len(first_row) != 3:
				continue

			transponder = {}
			transponder["services"] = {}
			transponder["namespace"] = int(first_row[0], 16)
			transponder["transport_stream_id"] = int(first_row[1], 16)
			transponder["original_network_id"] = int(first_row[2], 16)

			# print>>log, "%x:%x:%x" % (namespace, transport_stream_id, original_network_id)
			second_row = rows[1].strip()
			transponder["dvb_type"] = 'dvb' + second_row[0]
			if transponder["dvb_type"] not in ["dvbs", "dvbt", "dvbc"]:
				continue

			second_row = second_row[2:].split(":")

			if transponder["dvb_type"] == "dvbs" and len(second_row) not in (7, 11, 14, 16):
				continue
			if transponder["dvb_type"] == "dvbt" and len(second_row) != 12:
				continue
			if transponder["dvb_type"] == "dvbc" and len(second_row) != 7:
				continue

			if transponder["dvb_type"] == "dvbs":
				transponder["frequency"] = int(second_row[0])
				transponder["symbol_rate"] = int(second_row[1])
				transponder["polarization"] = int(second_row[2])
				transponder["fec_inner"] = int(second_row[3])
				orbital_position = int(second_row[4])
				if orbital_position < 0:
					transponder["orbital_position"] = orbital_position + 3600
				else:
					transponder["orbital_position"] = orbital_position

				transponder["inversion"] = int(second_row[5])
				transponder["flags"] = int(second_row[6])
				if len(second_row) == 7:  # DVB-S
					transponder["system"] = 0
				else:  # DVB-S2
					transponder["system"] = int(second_row[7])
					transponder["modulation"] = int(second_row[8])
					transponder["roll_off"] = int(second_row[9])
					transponder["pilot"] = int(second_row[10])
					if len(second_row) > 13:  # Multistream
						transponder["is_id"] = int(second_row[11])
						transponder["pls_code"] = int(second_row[12])
						transponder["pls_mode"] = int(second_row[13])
						if len(second_row) > 15:  # T2MI
							if not (second_row[14] and second_row[15]):  # temporary workaround for some broken settings with empty fields (skip the service)
								continue
							transponder["t2mi_plp_id"] = int(second_row[14])
							transponder["t2mi_pid"] = int(second_row[15])
			elif transponder["dvb_type"] == "dvbt":
				transponder["frequency"] = int(second_row[0])
				transponder["bandwidth"] = int(second_row[1])
				transponder["code_rate_hp"] = int(second_row[2])
				transponder["code_rate_lp"] = int(second_row[3])
				transponder["modulation"] = int(second_row[4])
				transponder["transmission_mode"] = int(second_row[5])
				transponder["guard_interval"] = int(second_row[6])
				transponder["hierarchy"] = int(second_row[7])
				transponder["inversion"] = int(second_row[8])
				transponder["flags"] = int(second_row[9])
				transponder["system"] = int(second_row[10])
				transponder["plpid"] = int(second_row[11])
			elif transponder["dvb_type"] == "dvbc":
				transponder["frequency"] = int(second_row[0])
				transponder["symbol_rate"] = int(second_row[1])
				transponder["inversion"] = int(second_row[2])
				transponder["modulation"] = int(second_row[3])
				transponder["fec_inner"] = int(second_row[4])
				transponder["flags"] = int(second_row[5])
				transponder["system"] = int(second_row[6])

			key = "%x:%x:%x" % (transponder["namespace"], transponder["transport_stream_id"], transponder["original_network_id"])
			transponders[key] = transponder
			transponders_count += 1

		srv_start = content.find("services\n")
		srv_stop = content.rfind("end\n")

		srv_blocks = content[srv_start + 9:srv_stop].strip().split("\n")

		for i in list(range(0, len(srv_blocks) // 3)):
			service_reference = srv_blocks[i * 3].strip()
			service_name = srv_blocks[(i * 3) + 1].strip()
			service_provider = srv_blocks[(i * 3) + 2].strip()
			service_reference = service_reference.split(":")

			if len(service_reference) not in (6, 7):
				continue

			service = {}
			service["service_name"] = service_name
			service["service_line"] = service_provider
			service["service_id"] = int(service_reference[0], 16)
			service["namespace"] = int(service_reference[1], 16)
			service["transport_stream_id"] = int(service_reference[2], 16)
			service["original_network_id"] = int(service_reference[3], 16)
			service["service_type"] = int(service_reference[4])
			service["flags"] = int(service_reference[5])
			if len(service_reference) == 7 and int(service_reference[6], 16) != 0:
				service["ATSC_source_id"] = int(service_reference[6], 16)

			key = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
			if key not in transponders:
				continue
			transponders[key]["services"][service["service_id"]] = service
			services_count += 1

		print("[ABM-BouquetsReader] Read %d transponders and %d services" % (transponders_count, services_count), file=log)
		return transponders

	def parseLamedbV5Content(self, content):
		transponders = {}
		transponders_count = 0
		services_count = 0

		lines = content.splitlines()
		for line in lines:
			if line.startswith("t:"):
				first_part = line.strip().split(",")[0][2:].split(":")
				if len(first_part) != 3:
					continue

				transponder = {}
				transponder["services"] = {}
				transponder["namespace"] = int(first_part[0], 16)
				transponder["transport_stream_id"] = int(first_part[1], 16)
				transponder["original_network_id"] = int(first_part[2], 16)

				second_part = line.strip().split(",")[1]
				transponder["dvb_type"] = 'dvb' + second_part[0]
				if transponder["dvb_type"] not in ["dvbs", "dvbt", "dvbc"]:
					continue

				second_part = second_part[2:].split(":")

				if transponder["dvb_type"] == "dvbs" and len(second_part) not in (7, 11):
					continue
				if transponder["dvb_type"] == "dvbt" and len(second_part) != 12:
					continue
				if transponder["dvb_type"] == "dvbc" and len(second_part) != 7:
					continue

				if transponder["dvb_type"] == "dvbs":
					transponder["frequency"] = int(second_part[0])
					transponder["symbol_rate"] = int(second_part[1])
					transponder["polarization"] = int(second_part[2])
					transponder["fec_inner"] = int(second_part[3])
					orbital_position = int(second_part[4])
					if orbital_position < 0:
						transponder["orbital_position"] = orbital_position + 3600
					else:
						transponder["orbital_position"] = orbital_position

					transponder["inversion"] = int(second_part[5])
					transponder["flags"] = int(second_part[6])
					if len(second_part) == 7:  # DVB-S
						transponder["system"] = 0
					else:  # DVB-S2
						transponder["system"] = int(second_part[7])
						transponder["modulation"] = int(second_part[8])
						transponder["roll_off"] = int(second_part[9])
						transponder["pilot"] = int(second_part[10])
						for part in line.strip().split(",")[2:]:  # Multistream/T2MI
							if part.startswith("MIS/PLS:") and len(part[8:].split(":")) == 3:
								transponder["is_id"] = int(part[8:].split(":")[0])
								transponder["pls_code"] = int(part[8:].split(":")[1])
								transponder["pls_mode"] = int(part[8:].split(":")[2])
							elif part.startswith("T2MI:") and len(part[5:].split(":")) == 2:
								if not (part[5:].split(":")[0] and part[5:].split(":")[1]):  # temporary workaround for some broken settings with empty fields (skip the service)
									continue
								transponder["t2mi_plp_id"] = int(part[5:].split(":")[0])
								transponder["t2mi_pid"] = int(part[5:].split(":")[1])
				elif transponder["dvb_type"] == "dvbt":
					transponder["frequency"] = int(second_part[0])
					transponder["bandwidth"] = int(second_part[1])
					transponder["code_rate_hp"] = int(second_part[2])
					transponder["code_rate_lp"] = int(second_part[3])
					transponder["modulation"] = int(second_part[4])
					transponder["transmission_mode"] = int(second_part[5])
					transponder["guard_interval"] = int(second_part[6])
					transponder["hierarchy"] = int(second_part[7])
					transponder["inversion"] = int(second_part[8])
					transponder["flags"] = int(second_part[9])
					transponder["system"] = int(second_part[10])
					transponder["plpid"] = int(second_part[11])
				elif transponder["dvb_type"] == "dvbc":
					transponder["frequency"] = int(second_part[0])
					transponder["symbol_rate"] = int(second_part[1])
					transponder["inversion"] = int(second_part[2])
					transponder["modulation"] = int(second_part[3])
					transponder["fec_inner"] = int(second_part[4])
					transponder["flags"] = int(second_part[5])
					transponder["system"] = int(second_part[6])

				key = "%x:%x:%x" % (transponder["namespace"], transponder["transport_stream_id"], transponder["original_network_id"])
				transponders[key] = transponder
				transponders_count += 1
			elif line.startswith("s:"):
				service_reference = line.strip().split(",")[0][2:]
				service_name = line.strip().split('"', 1)[1].split('"')[0]
				third_part = line.strip().split('"', 2)[2]
				service_provider = ""
				if len(third_part):
					service_provider = third_part[1:]
				service_reference = service_reference.split(":")
				if len(service_reference) != 6 and len(service_reference) != 7:
					continue

				service = {}
				service["service_name"] = service_name
				service["service_line"] = service_provider
				service["service_id"] = int(service_reference[0], 16)
				service["namespace"] = int(service_reference[1], 16)
				service["transport_stream_id"] = int(service_reference[2], 16)
				service["original_network_id"] = int(service_reference[3], 16)
				service["service_type"] = int(service_reference[4])
				service["flags"] = int(service_reference[5])
				if len(service_reference) == 7 and int(service_reference[6], 16) != 0:
					service["ATSC_source_id"] = int(service_reference[6], 16)

				key = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
				if key not in transponders:
					continue
				transponders[key]["services"][service["service_id"]] = service
				services_count += 1

		print("[ABM-BouquetsReader] Read %d transponders and %d services" % (transponders_count, services_count), file=log)
		return transponders
