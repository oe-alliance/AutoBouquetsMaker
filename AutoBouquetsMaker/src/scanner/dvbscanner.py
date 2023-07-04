from __future__ import print_function

from .. import log

import dvbreader
import datetime
import time
import os
from Components.config import config


class DvbScanner():
	TIMEOUT_SEC = 20
	SDT_TIMEOUT = 20

	VIDEO_ALLOWED_TYPES = [1, 4, 5, 17, 22, 24, 25, 27, 31, 135]
	AUDIO_ALLOWED_TYPES = [2, 10]
	INTERACTIVE_ALLOWED_TYPES = [133]
	EPG_ALLOWED_TYPES = [131]
	HD_ALLOWED_TYPES = [17, 25, 27, 135]
	HEVC_ALLOWED_TYPES = [31]

	def __init__(self):
		self.adapter = 0
		self.demuxer = 0
		self.demuxer_device = "/dev/dvb/adapter0/demux0"
		self.frontend = 0
		self.nit_pid = 0x10
		self.nit_current_table_id = 0x40
		self.nit_other_table_id = 0x41
		self.sdt_pid = 0x11
		self.sdt_current_table_id = 0x42
		self.sdt_other_table_id = 0x46
		self.bat_pid = 0x11
		self.bat_table_id = 0x4a
		self.fastscan_pid = 0x00
		self.fastscan_table_id = 0x00
		self.ignore_visible_service_flag = 0
		self.extra_debug = config.autobouquetsmaker.level.value == "expert" and config.autobouquetsmaker.extra_debug.value
		self.namespace_complete = not (config.usage.subnetwork.value if hasattr(config.usage, "subnetwork") else True)  # config.usage.subnetwork not available in all images
		self.namespace_complete_cable = not (config.usage.subnetwork_cable.value if hasattr(config.usage, "subnetwork_cable") else True)  # config.usage.subnetwork not available in all images
		self.namespace_complete_terrestrial = not (config.usage.subnetwork_terrestrial.value if hasattr(config.usage, "subnetwork_terrestrial") else True)  # config.usage.subnetwork not available in all images

	def isValidOnidTsid(self, orbital_position, onid, tsid):
		if onid == 0 or onid == 1 and tsid < 2 or onid >= 0xff00:
			return False
		return True

	def setAdapter(self, id):
		self.adapter = id
		self.demuxer_device = "/dev/dvb/adapter%d/demux%d" % (self.adapter, self.demuxer)
		print("[ABM-DvbScanner] Adapter %d" % self.adapter, file=log)

	def setDemuxer(self, id):
		self.demuxer = id
		self.demuxer_device = "/dev/dvb/adapter%d/demux%d" % (self.adapter, self.demuxer)
		print("[ABM-DvbScanner] Demuxer %d" % self.demuxer, file=log)

	def setFrontend(self, id):
		self.frontend = id
		print("[ABM-DvbScanner] Frontend %d" % self.frontend, file=log)

	def setDVBType(self, id):
		self.dvbtype = id
		print("[ABM-DvbScanner] DVBType %s" % self.dvbtype, file=log)

	def setNitPid(self, value):
		self.nit_pid = value
		print("[ABM-DvbScanner] NIT pid: 0x%x" % self.nit_pid, file=log)

	def setNitCurrentTableId(self, value):
		self.nit_current_table_id = value
		print("[ABM-DvbScanner] NIT current table id: 0x%x" % self.nit_current_table_id, file=log)

	def setNitOtherTableId(self, value):
		self.nit_other_table_id = value
		print("[ABM-DvbScanner] NIT other table id: 0x%x" % self.nit_other_table_id, file=log)

	def setSdtPid(self, value):
		self.sdt_pid = value
		print("[ABM-DvbScanner] SDT pid: 0x%x" % self.sdt_pid, file=log)

	def setSdtCurrentTableId(self, value):
		self.sdt_current_table_id = value
		print("[ABM-DvbScanner] SDT current table id: 0x%x" % self.sdt_current_table_id, file=log)

	def setSdtOtherTableId(self, value):
		self.sdt_other_table_id = value
		print("[ABM-DvbScanner] SDT other table id: 0x%x" % self.sdt_other_table_id, file=log)

	def setBatPid(self, value):
		self.bat_pid = value
		print("[ABM-DvbScanner] BAT pid: 0x%x" % self.bat_pid, file=log)

	def setBatTableId(self, value):
		self.bat_table_id = value
		print("[ABM-DvbScanner] BAT table id: 0x%x" % self.bat_table_id, file=log)

	def setFastscanPid(self, value):
		self.fastscan_pid = value
		print("[ABM-DvbScanner] Fastscan pid: 0x%x" % self.fastscan_pid, file=log)

	def setFastscanTableId(self, value):
		self.fastscan_table_id = value
		print("[ABM-DvbScanner] Fastscan table id: 0x%x" % self.fastscan_table_id, file=log)

	def setVisibleServiceFlagIgnore(self, value):
		self.ignore_visible_service_flag = value
		print("[ABM-DvbScanner] Ignore visible service flag: %d" % self.ignore_visible_service_flag, file=log)

	def buildNamespace(self, transponder):
		if transponder["dvb_type"] == 'dvbc':
			namespace = 0xFFFF0000
			if self.namespace_complete_cable:
				namespace |= (transponder['frequency'] // 1000) & 0xFFFF
		elif transponder["dvb_type"] == 'dvbt':
			namespace = 0xEEEE0000
			if self.namespace_complete_terrestrial:
				namespace |= (transponder['frequency'] // 1000000) & 0xFFFF
		elif transponder["dvb_type"] == 'dvbs':
			orbital_position = transponder['orbital_position']
			namespace = orbital_position << 16
			if self.namespace_complete or not self.isValidOnidTsid(orbital_position, transponder['original_network_id'], transponder['transport_stream_id']):
				namespace |= ((transponder['frequency'] // 1000) & 0xFFFF) | ((transponder['polarization'] & 1) << 15)
		return namespace

	def tsidOnidTest(self, onid, tsid):
		# This just grabs the tsid and onid of the current transponder.
		# Used to confirm motorised dishes have arrived at the correct satellite before starting the download.
		print("[ABM-DvbScanner] tsid onid test...", file=log)

		sdt_pid = 0x11
		sdt_current_table_id = 0x42
		mask = 0xff
		tsidOnidTestTimeout = 90
		passed_test = False

		fd = dvbreader.open(self.demuxer_device, sdt_pid, sdt_current_table_id, mask, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, tsidOnidTestTimeout)

		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out checking tsid onid", file=log)
				break

			section = dvbreader.read_sdt(fd, sdt_current_table_id, 0x00)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if section["header"]["table_id"] == sdt_current_table_id:
				passed_test = (onid is None or onid == section["header"]["original_network_id"]) and (tsid is None or tsid == section["header"]["transport_stream_id"])
				print("[ABM-DvbScanner][tsidOnidTest] tsid: %d, onid: %d" % (section["header"]["transport_stream_id"], section["header"]["original_network_id"]), file=log)
				if passed_test:
					break

		dvbreader.close(fd)

		return passed_test

	def updateTransponders(self, transponders, read_other_section=False, customtransponders=None, netid=None, bouquettype=None, bouquet_id=-1, tune_freq=0):
		print("[ABM-DvbScanner] Reading transponders...", file=log)

		if customtransponders is None:
			customtransponders = []

		if self.nit_other_table_id == 0x00:
			mask = 0xff
		else:
			mask = self.nit_current_table_id ^ self.nit_other_table_id ^ 0xff

		fd = dvbreader.open(self.demuxer_device, self.nit_pid, self.nit_current_table_id, mask, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			print("[ABM-DvbScanner] demuxer_device", str(self.demuxer_device), file=log)
			print("[ABM-DvbScanner] nit_pid", str(self.nit_pid), file=log)
			print("[ABM-DvbScanner] nit_current_table_id", str(self.nit_current_table_id), file=log)
			print("[ABM-DvbScanner] mask", str(mask), file=log)
			print("[ABM-DvbScanner] frontend", str(self.frontend), file=log)
			return None

		nit_current_section_version = -1
		nit_current_section_network_id = -1
		nit_current_sections_read = []
		nit_current_sections_count = 0
		nit_current_content = []
		nit_current_completed = False

		nit_other_section_version = {}
		nit_other_sections_read = {}
		nit_other_sections_count = {}
		nit_other_content = {}
		nit_other_completed = {}
		all_nit_others_completed = not read_other_section or self.nit_other_table_id == 0x00

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.TIMEOUT_SEC)
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading NIT", file=log)
				if self.nit_other_table_id != 0x00:
					print("[ABM-DvbScanner] No nit_other found - set nit_other_table_id=\"0x00\" for faster scanning?", file=log)
				break

			section = dvbreader.read_nit(fd, self.nit_current_table_id, self.nit_other_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] NIT raw section header", section["header"])
				print("[ABM-DvbScanner] NIT raw section content", section["content"])

			if (section["header"]["table_id"] == self.nit_current_table_id
				and self.dvbtype != 'dvbc' and not nit_current_completed):
				if self.extra_debug:
					print("[ABM-DvbScanner] raw section above is from NIT actual table.")

				if (section["header"]["version_number"] != nit_current_section_version or section["header"]["network_id"] != nit_current_section_network_id):
					nit_current_section_version = section["header"]["version_number"]
					nit_current_section_network_id = section["header"]["network_id"]
					nit_current_sections_read = []
					nit_current_content = []
					nit_current_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in nit_current_sections_read:
					nit_current_sections_read.append(section["header"]["section_number"])
					nit_current_content += section["content"]

					if len(nit_current_sections_read) == nit_current_sections_count:
						nit_current_completed = True

			elif (str(section["header"]["network_id"]) == str(netid) and self.dvbtype == 'dvbc' and not nit_current_completed):
				if self.extra_debug:
					print("[ABM-DvbScanner] raw section above is from NIT actual table.")

				if (section["header"]["version_number"] != nit_current_section_version or section["header"]["network_id"] != nit_current_section_network_id):
					nit_current_section_version = section["header"]["version_number"]
					nit_current_section_network_id = section["header"]["network_id"]
					nit_current_sections_read = []
					nit_current_content = []
					nit_current_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in nit_current_sections_read:
					nit_current_sections_read.append(section["header"]["section_number"])
					nit_current_content += section["content"]

					if len(nit_current_sections_read) == nit_current_sections_count:
						nit_current_completed = True
						all_nit_others_completed = True

			elif section["header"]["table_id"] == self.nit_other_table_id and not all_nit_others_completed and (self.dvbtype != 'dvbc' or str(section["header"]["network_id"]) == str(netid)):
				if self.extra_debug:
					print("[ABM-DvbScanner] raw section above is from NIT other table.")
				network_id = section["header"]["network_id"]

				if network_id in nit_other_section_version and nit_other_section_version[network_id] == section["header"]["version_number"] and all(completed == True for completed in list(nit_other_completed.values())):
					all_nit_others_completed = True
				else:

					if network_id not in nit_other_section_version or section["header"]["version_number"] != nit_other_section_version[network_id]:
						nit_other_section_version[network_id] = section["header"]["version_number"]
						nit_other_sections_read[network_id] = []
						nit_other_content[network_id] = []
						nit_other_sections_count[network_id] = section["header"]["last_section_number"] + 1
						nit_other_completed[network_id] = False

					if section["header"]["section_number"] not in nit_other_sections_read[network_id]:
						nit_other_sections_read[network_id].append(section["header"]["section_number"])
						nit_other_content[network_id] += section["content"]

						if len(nit_other_sections_read[network_id]) == nit_other_sections_count[network_id]:
							nit_other_completed[network_id] = True

			elif self.extra_debug:
				print("[ABM-DvbScanner] raw section above skipped. Either duplicate output or ID mismatch.")

			if nit_current_completed and all_nit_others_completed:
				print("[ABM-DvbScanner] Scan complete, netid: ", str(netid), file=log)
				break

		dvbreader.close(fd)

		nit_content = nit_current_content
		for network_id in nit_other_content:
			nit_content += nit_other_content[network_id]

		logical_channel_number_dict = {}
		logical_channel_number_dict_tmp = {}
		hd_logical_channel_number_dict_tmp = {}
		service_dict_tmp = {}
		transponders_count = 0
		self.namespace_dict = {}

		for transponder in nit_content:
			if self.extra_debug:
				print("[ABM-DvbScanner] NIT content", transponder)
			if "descriptor_tag" in transponder and transponder["descriptor_tag"] == 0x41:  # service
				key = "%x:%x:%x" % (transponder["transport_stream_id"], transponder["original_network_id"], transponder["service_id"])
				service_dict_tmp[key] = transponder
				continue
			if "descriptor_tag" in transponder and transponder["descriptor_tag"] in {0x82, 0x83}:  # lcn
				key = "%x:%x:%x" % (transponder["transport_stream_id"], transponder["original_network_id"], transponder["service_id"])
				logical_channel_number_dict_tmp[key] = transponder
				continue
			if "descriptor_tag" in transponder and transponder["descriptor_tag"] == 0x87:  # LCN V2
				if transponder["channel_list_id"] == bouquet_id:
					key = "%x:%x:%x" % (transponder["transport_stream_id"], transponder["original_network_id"], transponder["service_id"])
					logical_channel_number_dict_tmp[key] = transponder
				continue
			if "descriptor_tag" in transponder and transponder["descriptor_tag"] == 0x88:  # HD lcn
				key = "%x:%x:%x" % (transponder["transport_stream_id"], transponder["original_network_id"], transponder["service_id"])
				hd_logical_channel_number_dict_tmp[key] = transponder
				continue
			customtransponder = {}
			if len(customtransponders) > 0 and self.dvbtype == 'dvbt':  # Only for DVB-T/T2 transponder override.
				for key in list(range(0, len(customtransponders))):
					if customtransponders[key]["transport_stream_id"] == transponder["transport_stream_id"]:
						customtransponder = customtransponders[key]
						break
			if "descriptor_tag" in transponder and transponder["descriptor_tag"] == 0x7f and len(customtransponder) == 0:  # DVB-T2
				# if no custom transponer information is available look in lamedb just in case it is already there
				key = "%x:%x:%x" % (0xEEEE0000, transponder["transport_stream_id"], transponder["original_network_id"])
				if key not in transponders:
					continue
				customtransponder = transponders[key]
			transponder["services"] = {}
			transponder["dvb_type"] = self.dvbtype
			transponder["bouquet_type"] = bouquettype

			if transponder["dvb_type"] == 'dvbc':  # DVB-C
				transponder["symbol_rate"] = transponder["symbol_rate"] * 100
				transponder["flags"] = 0
				if transponder["fec_inner"] != 15 and transponder["fec_inner"] > 9:
					transponder["fec_inner"] = 0
				transponder["frequency"] = transponder["frequency"] // 10
				transponder["namespace"] = self.buildNamespace(transponder)
				transponder["inversion"] = transponder["fec_outer"]
				transponder["system"] = 0
			elif transponder["dvb_type"] == 'dvbt':  # DVB-T
				if len(customtransponder) == 0:  # no override or DVB-T2 transponder
					transponder["frequency"] = transponder["frequency"] * 10
					transponder["namespace"] = self.buildNamespace(transponder)
					transponder["inversion"] = 0
					transponder["plpid"] = 0
					transponder["flags"] = 0
					transponder["system"] = 0
				else:
					transponder["frequency"] = customtransponder["frequency"]
					transponder["namespace"] = self.buildNamespace(transponder)
					transponder["bandwidth"] = customtransponder["bandwidth"]
					transponder["code_rate_hp"] = customtransponder["code_rate_hp"]
					transponder["code_rate_lp"] = customtransponder["code_rate_lp"]
					transponder["modulation"] = customtransponder["modulation"]
					transponder["transmission_mode"] = customtransponder["transmission_mode"]
					transponder["guard_interval"] = customtransponder["guard_interval"]
					transponder["hierarchy"] = customtransponder["hierarchy"]
					transponder["inversion"] = customtransponder["inversion"]
					transponder["flags"] = customtransponder["flags"]
					transponder["system"] = customtransponder["system"]
					transponder["plpid"] = customtransponder["plpid"]
			elif transponder["dvb_type"] == 'dvbs':  # DVB-S
				if transponder["descriptor_tag"] != 0x43:  # Confirm DVB SI data is DVB-S
					continue
				transponder["symbol_rate"] = transponder["symbol_rate"] * 100
				transponder["flags"] = 0
				if transponder["fec_inner"] != 15 and transponder["fec_inner"] > 9:
					transponder["fec_inner"] = 0
				transponder["frequency"] = transponder["frequency"] * 10
				orbital_position = ((transponder["orbital_position"] >> 12) & 0x0F) * 1000
				orbital_position += ((transponder["orbital_position"] >> 8) & 0x0F) * 100
				orbital_position += ((transponder["orbital_position"] >> 4) & 0x0F) * 10
				orbital_position += transponder["orbital_position"] & 0x0F
				# shift Ka-band transponders to correspond with Ka positions in satellites.xml
				if transponder["frequency"] > 12999000:
					orbital_position += 2
				if orbital_position != 0 and transponder["west_east_flag"] == 0:  # 0 == west, 1 == east
					orbital_position = 3600 - orbital_position
				transponder["orbital_position"] = orbital_position
				transponder["pilot"] = 2

				if transponder["system"] == 0 and transponder["modulation"] == 2:
					transponder["modulation"] = 1
				transponder["inversion"] = 2
				# shift 5.0E and 1.0W positions to correspond with satellites.xml
				if transponder["orbital_position"] in (50, 3590):
					if transponder["orbital_position"] == 50:
						transponder["orbital_position"] -= 2
					elif transponder["orbital_position"] == 3590:
						transponder["orbital_position"] += 2
				transponder["namespace"] = self.buildNamespace(transponder)

			transponder_key = "%x:%x:%x" % (transponder["namespace"],
				transponder["transport_stream_id"],
				transponder["original_network_id"])

			if transponder_key in transponders:
				transponder["services"] = transponders[transponder_key]["services"]
			transponders[transponder_key] = transponder
			transponders_count += 1

			namespace_key = "%x:%x" % (transponder["transport_stream_id"], transponder["original_network_id"])
			if namespace_key not in self.namespace_dict:
				self.namespace_dict[namespace_key] = transponder["namespace"]

			if self.extra_debug:
				print("[ABM-DvbScanner] transponder", transponder)

		# Fix DVB-T frequency when 1 transponder found at the NIT table and the frequency is different from tune frequency
		if transponders_count == 1 and len(customtransponder) == 0 and tune_freq > 0 and transponders[transponder_key]["frequency"] != tune_freq:
			print("[ABM-DvbScanner] Fix transponder frequency from NIT frequency %d to %d" % (transponders[transponder_key]["frequency"], tune_freq), file=log)
			transponders[transponder_key]["frequency"] = tune_freq

		if read_other_section and len(nit_other_completed):
			print("[ABM-DvbScanner] Added/Updated %d transponders with network_id = 0x%x and other network_ids = %s" % (transponders_count, nit_current_section_network_id, ','.join(list(map(hex, list(nit_other_completed.keys()))))), file=log)
		else:
			print("[ABM-DvbScanner] Added/Updated %d transponders with network_id = 0x%x" % (transponders_count, nit_current_section_network_id), file=log)

		if len(hd_logical_channel_number_dict_tmp) > 0 and bouquettype == 'hd':
			for id in logical_channel_number_dict_tmp:
				if id in hd_logical_channel_number_dict_tmp:
					lcntofind = hd_logical_channel_number_dict_tmp[id]["logical_channel_number"]
					lcnreplace = logical_channel_number_dict_tmp[id]["logical_channel_number"]
					for id2 in logical_channel_number_dict_tmp:
						if logical_channel_number_dict_tmp[id2]["logical_channel_number"] == lcntofind:
							logical_channel_number_dict[id] = logical_channel_number_dict_tmp[id2]
							logical_channel_number_dict[id]["logical_channel_number"] = lcnreplace
					logical_channel_number_dict[id] = hd_logical_channel_number_dict_tmp[id]
				else:
					logical_channel_number_dict[id] = logical_channel_number_dict_tmp[id]
		else:
			for id in logical_channel_number_dict_tmp:
				logical_channel_number_dict[id] = logical_channel_number_dict_tmp[id]

		if self.extra_debug:
			for key in logical_channel_number_dict:
				print("[ABM-DvbScanner] LCN entry", key, logical_channel_number_dict[key])

		return {
			"TSID_ONID_list": list(self.namespace_dict.keys()),
			"logical_channel_number_dict": logical_channel_number_dict,
			"service_dict_tmp": service_dict_tmp
		}

	def readLCNBAT(self, bouquet_id, descriptor_tag, TSID_ONID_list):
		print("[ABM-DvbScanner] Reading BAT...", file=log)

		fd = dvbreader.open(self.demuxer_device, self.bat_pid, self.bat_table_id, 0xff, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return {}

		bat_section_version = -1
		bat_sections_read = []
		bat_sections_count = 0
		bat_content = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.TIMEOUT_SEC)
		tmp_TSID_ONID_list = []

		if self.extra_debug:
			lcn_list = []
			sid_list = []
			tsid_list = []
			hex_list = []
			xml_dict = {}

		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading BAT", file=log)
				break

			section = dvbreader.read_bat(fd, self.bat_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] BAT raw section header", section["header"])
				print("[ABM-DvbScanner] BAT raw section content", section["content"])
				for service in section["content"]:
					if "hexcontent" in service:
						hex_list.append(service)
					if service["descriptor_tag"] == 71:
						xml_dict[service["bouquet_id"]] = service["description"]

			if section["header"]["table_id"] == self.bat_table_id:
				if section["header"]["bouquet_id"] != bouquet_id:
					continue

				if section["header"]["version_number"] != bat_section_version:
					bat_section_version = section["header"]["version_number"]
					bat_sections_read = []
					bat_content = []
					bat_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in bat_sections_read:
					bat_sections_read.append(section["header"]["section_number"])
					bat_content += section["content"]

					if len(bat_sections_read) == bat_sections_count:
						break

		dvbreader.close(fd)

		logical_channel_number_dict = {}

		for service in bat_content:
			if service["descriptor_tag"] != descriptor_tag:
				continue

			key = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
			TSID_ONID = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])

			logical_channel_number_dict[key] = service
			if TSID_ONID not in tmp_TSID_ONID_list:
				tmp_TSID_ONID_list.append(TSID_ONID)

			if self.extra_debug:
				print("[ABM-DvbScanner] LCN entry", key, service)
				sid_list.append(service["service_id"])
				lcn_list.append(service["logical_channel_number"])
				if service["transport_stream_id"] not in tsid_list:
					tsid_list.append(service["transport_stream_id"])

		if len(tmp_TSID_ONID_list) > 0:
			TSID_ONID_list = tmp_TSID_ONID_list

		if self.extra_debug:
			print("[ABM-DvbScanner] TSID list from BAT", sorted(tsid_list))
			print("[ABM-DvbScanner] SID list from BAT", sorted(sid_list))
			print("[ABM-DvbScanner] LCN list from BAT", sorted(lcn_list))
			for service in hex_list:
				print("[ABM-DvbScanner] hexcontent", service)
				bytes = [int(''.join(service["hexcontent"][i:i + 2]), 16) for i in list(range(0, len(service["hexcontent"]), 2))][2:]
				hexchars = []
				for byte in bytes:
					if byte > 31 and byte < 127:
						hexchars.append(chr(byte))
					else:
						hexchars.append('.')
				print("[ABM-DvbScanner] %s" % (''.join(hexchars)))
			for key in sorted(list(xml_dict.keys())):
				print('		<configuration key="sd_%d" bouquet="0x%x" region="DESCRIPTOR">%s</configuration>' % (key, key, xml_dict[key]))

		return logical_channel_number_dict, TSID_ONID_list

	def updateAndReadServicesLCN(self, transponders, servicehacks, TSID_ONID_list, logical_channel_number_dict, service_dict_tmp, protocol, bouquet_key):
		print("[ABM-DvbScanner] Reading services (LCN)...", file=log)

		if self.sdt_other_table_id == 0x00:
			mask = 0xff
		else:
			mask = self.sdt_current_table_id ^ self.sdt_other_table_id ^ 0xff

		fd = dvbreader.open(self.demuxer_device, self.sdt_pid, self.sdt_current_table_id, mask, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		sdt_secions_status = {}
		for TSID_ONID in TSID_ONID_list:
			sdt_secions_status[TSID_ONID] = {}
			sdt_secions_status[TSID_ONID]["section_version"] = -1
			sdt_secions_status[TSID_ONID]["sections_read"] = []
			sdt_secions_status[TSID_ONID]["sections_count"] = 0
			sdt_secions_status[TSID_ONID]["content"] = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.SDT_TIMEOUT)
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading SDT", file=log)
				break

			section = dvbreader.read_sdt(fd, self.sdt_current_table_id, self.sdt_other_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] SDT raw section header", section["header"])
				print("[ABM-DvbScanner] SDT raw section content", section["content"])

			if (section["header"]["table_id"] == self.sdt_current_table_id or section["header"]["table_id"] == self.sdt_other_table_id) and len(section["content"]):
				TSID_ONID = "%x:%x" % (section["header"]["transport_stream_id"], section["header"]["original_network_id"])
				if TSID_ONID not in TSID_ONID_list:
					continue

				if section["header"]["version_number"] != sdt_secions_status[TSID_ONID]["section_version"]:
					sdt_secions_status[TSID_ONID]["section_version"] = section["header"]["version_number"]
					sdt_secions_status[TSID_ONID]["sections_read"] = []
					sdt_secions_status[TSID_ONID]["content"] = []
					sdt_secions_status[TSID_ONID]["sections_count"] = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in sdt_secions_status[TSID_ONID]["sections_read"]:
					sdt_secions_status[TSID_ONID]["sections_read"].append(section["header"]["section_number"])
					sdt_secions_status[TSID_ONID]["content"] += section["content"]

					if len(sdt_secions_status[TSID_ONID]["sections_read"]) == sdt_secions_status[TSID_ONID]["sections_count"]:
						TSID_ONID_list.remove(TSID_ONID)

			if len(TSID_ONID_list) == 0:
				break

		if len(TSID_ONID_list) > 0:
			print("[ABM-DvbScanner] Cannot fetch SDT for the following TSID_ONID list: ", TSID_ONID_list, file=log)

		dvbreader.close(fd)

		# Create logical_channel_number_dict for VMUK
		if protocol in ('vmuk', 'vmuk2'):
			for key in sdt_secions_status:
				for service in sdt_secions_status[key]["content"]:
					if "logical_channel_number" in service and service["logical_channel_number"] > 0:
						servicekey = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
						logical_channel_number_dict[servicekey] = {"transport_stream_id": service["transport_stream_id"], "original_network_id": service["original_network_id"], "service_id": service["service_id"], "logical_channel_number": service["logical_channel_number"]}

		# When no LCN available, create fake LCN numbers (service-id) and use customlcn file for final channel numbers
		if len(logical_channel_number_dict) == 0:
			print("[ABM-DvbScanner] No LCNs found. Falling back to service ID.", file=log)
			for key in sdt_secions_status:
				for service in sdt_secions_status[key]["content"]:
					servicekey = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
					logical_channel_number_dict[servicekey] = {"transport_stream_id": service["transport_stream_id"], "original_network_id": service["original_network_id"], "service_id": service["service_id"], "logical_channel_number": service["service_id"]}

		service_count = 0
		tmp_services_dict = {}

		if self.extra_debug:
			sid_list = []
			tsid_list = []

		for key in sdt_secions_status:
			for service in sdt_secions_status[key]["content"]:

				servicekey = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])

				if self.extra_debug:
					print("[ABM-DvbScanner] SDT service", service)
					if servicekey not in logical_channel_number_dict:
						print("[ABM-DvbScanner] Above service not in LCN dict")

					sid_list.append(service["service_id"])
					if service["transport_stream_id"] not in tsid_list:
						tsid_list.append(service["transport_stream_id"])

				if servicekey not in logical_channel_number_dict or not self.ignore_visible_service_flag and "visible_service_flag" in logical_channel_number_dict[servicekey] and logical_channel_number_dict[servicekey]["visible_service_flag"] == 0:
					continue
				if service_dict_tmp and servicekey not in service_dict_tmp and protocol not in ("lcn2", "lcnbat2", "vmuk2"):
					if self.extra_debug:
						print("[ABM-DvbScanner] %s not in service_dict_tmp" % service["service_name"])
					continue

				namespace_key = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])
				if namespace_key not in self.namespace_dict:
					continue
				service["namespace"] = self.namespace_dict[namespace_key]

				service["flags"] = 0

				service["number"] = logical_channel_number_dict[servicekey]["logical_channel_number"]

				if servicekey in tmp_services_dict:
					tmp_services_dict[servicekey]["numbers"].append(service["number"])
				else:
					service["numbers"] = [service["number"]]
					tmp_services_dict[servicekey] = service

				service_count += 1

		if self.extra_debug:
			print("[ABM-DvbScanner] TSID list from SDT", sorted(tsid_list))
			print("[ABM-DvbScanner] SID list from SDT", sorted(sid_list))

		print("[ABM-DvbScanner] Read %d services" % service_count, file=log)

		video_services = {}
		radio_services = {}

		service_extra_count = 0

		servicehack_variable_cache = {"add_audio_channels_to_video_bouquet": False}

		skip = skipper()

		for key in self.LCN_order(tmp_services_dict):
			service = tmp_services_dict[key]

			if self.extra_debug:
				print("[ABM-DvbScanner] Service", service)

			if len(servicehacks) > 0:
				skip.skip = False
				exec(servicehacks)

				if skip.skip:
					continue

			tpkey = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
			if tpkey not in transponders:
				continue

			transponders[tpkey]["services"][service["service_id"]] = service
			service_extra_count += 1

			if service["service_type"] in DvbScanner.VIDEO_ALLOWED_TYPES or service["service_type"] in DvbScanner.INTERACTIVE_ALLOWED_TYPES or service["service_type"] in DvbScanner.AUDIO_ALLOWED_TYPES and servicehack_variable_cache["add_audio_channels_to_video_bouquet"]:
				for number in service["numbers"]:
					if number not in video_services:
						video_services[number] = service
			elif service["service_type"] in DvbScanner.AUDIO_ALLOWED_TYPES:
				for number in service["numbers"]:
					if number not in radio_services:
						radio_services[number] = service

		print("[ABM-DvbScanner] %d valid services" % service_extra_count, file=log)
		return {
			"video": video_services,
			"radio": radio_services
		}

	def updateAndReadServicesFastscan(self, transponders, servicehacks, logical_channel_number_dict):
		print("[ABM-DvbScanner] Reading services (fastscan)...", file=log)

		fd = dvbreader.open(self.demuxer_device, self.fastscan_pid, self.fastscan_table_id, 0xff, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		fastscan_section_version = -1
		fastscan_section_id = -1
		fastscan_sections_read = []
		fastscan_sections_count = 0
		fastscan_content = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.TIMEOUT_SEC)
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading fastscan", file=log)
				break

			section = dvbreader.read_fastscan(fd, self.fastscan_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] Fastscan raw section header", section["header"])
				print("[ABM-DvbScanner] Fastscan raw section content", section["content"])

			if section["header"]["table_id"] == self.fastscan_table_id:
				if (section["header"]["version_number"] != fastscan_section_version
					or section["header"]["fastscan_id"] != fastscan_section_id):

					fastscan_section_version = section["header"]["version_number"]
					fastscan_section_id = section["header"]["fastscan_id"]
					fastscan_sections_read = []
					fastscan_content = []
					fastscan_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in fastscan_sections_read:
					fastscan_sections_read.append(section["header"]["section_number"])
					fastscan_content += section["content"]

					if len(fastscan_sections_read) == fastscan_sections_count:
						break

		dvbreader.close(fd)

		# to ignore services on not configured satellites
		if config.autobouquetsmaker.skipservices.value:
			from Components.NimManager import nimmanager
			nims = nimmanager.getNimListOfType("DVB-S")
			orbitals_configured = []
			for nim in nims:
				sats = nimmanager.getSatListForNim(nim)
				for sat in sats:
					if sat[0] not in orbitals_configured:
						orbitals_configured.append(sat[0])

		service_count = 0
		tmp_services_dict = {}
		for service in fastscan_content:

			servicekey = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])

			if servicekey not in logical_channel_number_dict:
				continue

			if logical_channel_number_dict[servicekey]["visible_service_flag"] == 0:
				continue

			if not hasattr(service, "free_ca"):
				service["free_ca"] = 1

			namespace_key = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])
			if namespace_key not in self.namespace_dict:
				continue
			service["namespace"] = self.namespace_dict[namespace_key]

			if not hasattr(service, "flags"):
				service["flags"] = 0

			service["number"] = logical_channel_number_dict[servicekey]["logical_channel_number"]

			service["orbital_position"] = service["namespace"] // (16**4)

			if service["service_type"] in DvbScanner.VIDEO_ALLOWED_TYPES and service["service_type"] not in DvbScanner.HD_ALLOWED_TYPES and (service["service_name"][-2:] == 'HD' or ' HD ' in service["service_name"]):
				service["service_type"] = 25

			if servicekey in tmp_services_dict:
				tmp_services_dict[servicekey]["numbers"].append(service["number"])
			else:
				service["numbers"] = [service["number"]]
				tmp_services_dict[servicekey] = service

			service_count += 1

		print("[ABM-DvbScanner] Read %d services" % service_count, file=log)

		video_services = {}
		radio_services = {}

		service_extra_count = 0
		services_without_transponders = 0

		skip = skipper()

		for key in self.LCN_order(tmp_services_dict):
			service = tmp_services_dict[key]

			if config.autobouquetsmaker.skipservices.value and service["orbital_position"] not in orbitals_configured:
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] Service", service)

			if len(servicehacks) > 0:
				skip.skip = False
				exec(servicehacks)

				if skip.skip:
					continue

			tpkey = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
			if tpkey not in transponders:
				services_without_transponders += 1
				continue

			transponders[tpkey]["services"][service["service_id"]] = service
			service_extra_count += 1

			if service["service_type"] in DvbScanner.VIDEO_ALLOWED_TYPES or service["service_type"] in DvbScanner.INTERACTIVE_ALLOWED_TYPES:
				for number in service["numbers"]:
					if number not in video_services:
						video_services[number] = service
			elif service["service_type"] in DvbScanner.AUDIO_ALLOWED_TYPES:
				for number in service["numbers"]:
					if number not in radio_services:
						radio_services[number] = service

		print("[ABM-DvbScanner] %d valid services" % service_extra_count, file=log)
		if services_without_transponders:
			print("[ABM-DvbScanner] %d services omitted as there is no corresponding transponder" % services_without_transponders, file=log)
		return {
			"video": video_services,
			"radio": radio_services
		}

	def updateAndReadServicesSKY(self, bouquet_id, region_id, bouquet_key, transponders, servicehacks):
		print("[ABM-DvbScanner] Reading services (SKY)...", file=log)

		fd = dvbreader.open(self.demuxer_device, self.bat_pid, self.bat_table_id, 0xff, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		bat_section_version = -1
		bat_sections_read = []
		bat_sections_count = 0
		bat_content = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.TIMEOUT_SEC)
		transport_stream_id_list = []
		extraservices = config.autobouquetsmaker.level.value == "expert" and config.autobouquetsmaker.showextraservices.value
		extra_channel_id_dict = {}
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading BAT", file=log)
				break

			section = dvbreader.read_bat(fd, self.bat_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] BAT raw section header", section["header"])
				print("[ABM-DvbScanner] BAT raw section content", section["content"])

			if section["header"]["table_id"] == self.bat_table_id:
				if section["header"]["bouquet_id"] != bouquet_id:
					if extraservices:
						for content_tmp in section["content"]:
							if content_tmp["descriptor_tag"] == 0xd3 and content_tmp["transport_stream_id"] not in transport_stream_id_list:
								transport_stream_id_list.append(content_tmp["transport_stream_id"])
							if content_tmp["descriptor_tag"] == 0xb1:
								key = "%x:%x:%x" % (content_tmp["transport_stream_id"], content_tmp["original_network_id"], content_tmp["service_id"])
								if key not in extra_channel_id_dict:
									extra_channel_id_dict[key] = content_tmp["channel_id"]
					continue

				if section["header"]["version_number"] != bat_section_version:
					bat_section_version = section["header"]["version_number"]
					bat_sections_read = []
					bat_content = []
					bat_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in bat_sections_read:
					bat_sections_read.append(section["header"]["section_number"])
					bat_content += section["content"]

					if len(bat_sections_read) == bat_sections_count:
						break

		dvbreader.close(fd)

		service_count = 0
		tmp_services_dict = {}
		for service in bat_content:
			if service["descriptor_tag"] != 0xb1:
				continue

			# Workaround: give IEPG data channel a favourable service type so people can find it and use it to download the EPG.
			if service["service_type"] in DvbScanner.EPG_ALLOWED_TYPES:
				service["service_type"] = 1

			if service["service_type"] not in DvbScanner.VIDEO_ALLOWED_TYPES and service["service_type"] not in DvbScanner.AUDIO_ALLOWED_TYPES and service["service_type"] not in DvbScanner.INTERACTIVE_ALLOWED_TYPES:
				continue

			if service["transport_stream_id"] not in transport_stream_id_list:
				transport_stream_id_list.append(service["transport_stream_id"])

			key = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
			if service["region_id"] != region_id and service["region_id"] != 0xff:
				if extraservices and key not in extra_channel_id_dict:
					extra_channel_id_dict[key] = service["channel_id"]
				continue

			if service["service_type"] == 0x05:
				service["service_type"] = 0x01  # enigma2 doesn't like 0x05 VOD

			service["free_ca"] = 1
			service["service_name"] = "Unknown"
			service["provider_name"] = "Unknown"
			namespace_key = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])
			if namespace_key not in self.namespace_dict:
				continue
			service["namespace"] = self.namespace_dict[namespace_key]
			service["flags"] = 0

			if key in tmp_services_dict:
				tmp_services_dict[key]["numbers"].append(service["number"])
			else:
				service["numbers"] = [service["number"]]
				tmp_services_dict[key] = service

			service_count += 1

		print("[ABM-DvbScanner] Read %d services with bouquet_id = 0x%x" % (service_count, bouquet_id), file=log)

		print("[ABM-DvbScanner] Reading services extra info...", file=log)

		if self.sdt_other_table_id == 0x00:
			mask = 0xff
		else:
			mask = self.sdt_current_table_id ^ self.sdt_other_table_id ^ 0xff

		fd = dvbreader.open(self.demuxer_device, self.sdt_pid, self.sdt_current_table_id, mask, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		sdt_secions_status = {}
		for transport_stream_id in transport_stream_id_list:
			sdt_secions_status[transport_stream_id] = {}
			sdt_secions_status[transport_stream_id]["section_version"] = -1
			sdt_secions_status[transport_stream_id]["sections_read"] = []
			sdt_secions_status[transport_stream_id]["sections_count"] = 0
			sdt_secions_status[transport_stream_id]["content"] = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.SDT_TIMEOUT)
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading SDT", file=log)
				break

			section = dvbreader.read_sdt(fd, self.sdt_current_table_id, self.sdt_other_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] SDT raw section header", section["header"])
				print("[ABM-DvbScanner] SDT raw section content", section["content"])

			if section["header"]["table_id"] == self.sdt_current_table_id or section["header"]["table_id"] == self.sdt_other_table_id:
				transport_stream_id = section["header"]["transport_stream_id"]

				if section["header"]["transport_stream_id"] not in transport_stream_id_list:
					if extraservices:  # this is only needed for extra services (channels without LCN) to collect their TSIDs from SDT if not in BAT.
						sdt_secions_status[transport_stream_id] = {}
						sdt_secions_status[transport_stream_id]["section_version"] = -1
						sdt_secions_status[transport_stream_id]["sections_read"] = []
						sdt_secions_status[transport_stream_id]["sections_count"] = 0
						sdt_secions_status[transport_stream_id]["content"] = []
						transport_stream_id_list.append(transport_stream_id)
					else:
						continue

				if section["header"]["version_number"] != sdt_secions_status[transport_stream_id]["section_version"]:
					sdt_secions_status[transport_stream_id]["section_version"] = section["header"]["version_number"]
					sdt_secions_status[transport_stream_id]["sections_read"] = []
					sdt_secions_status[transport_stream_id]["content"] = []
					sdt_secions_status[transport_stream_id]["sections_count"] = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in sdt_secions_status[transport_stream_id]["sections_read"]:
					sdt_secions_status[transport_stream_id]["sections_read"].append(section["header"]["section_number"])
					sdt_secions_status[transport_stream_id]["content"] += section["content"]

					if len(sdt_secions_status[transport_stream_id]["sections_read"]) == sdt_secions_status[transport_stream_id]["sections_count"]:
						transport_stream_id_list.remove(transport_stream_id)

			if len(transport_stream_id_list) == 0:
				break

		if len(transport_stream_id_list) > 0:
			print("[ABM-DvbScanner] Cannot fetch SDT for the following transport_stream_id list: ", transport_stream_id_list, file=log)

		dvbreader.close(fd)

		extras = []

		for key in sdt_secions_status:
			for section in sdt_secions_status[key]["content"]:
				srvkey = "%x:%x:%x" % (section["transport_stream_id"], section["original_network_id"], section["service_id"])

				if srvkey not in tmp_services_dict:
					if extraservices:
						if srvkey in extra_channel_id_dict:
							section["channel_id"] = extra_channel_id_dict[srvkey]
						extras.append(section)
					continue

				service = tmp_services_dict[srvkey]

				service["free_ca"] = section["free_ca"]
				service["service_name"] = section["service_name"]
				service["provider_name"] = section["provider_name"]
				service["category_name"] = self.skyCategoryName(section["category_id"])
				service["bouquet_id"] = bouquet_id  # in Sky UK this is the nation id
				service["bouquet_key"] = bouquet_key

		video_services = {}
		radio_services = {}

		service_extra_count = 0

		tmp_services_dict, LCNs_in_use = self.extrasHelper(tmp_services_dict, extras, True)

		skip = skipper()

		for key in self.LCN_order(tmp_services_dict):
			service = tmp_services_dict[key]

			if self.extra_debug:
				print("[ABM-DvbScanner] Service", service)

			if len(servicehacks) > 0:
				skip.skip = False
				exec(servicehacks)

				if skip.skip:
					continue

			tpkey = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
			if tpkey not in transponders:
				continue

			transponders[tpkey]["services"][service["service_id"]] = service
			service_extra_count += 1

			if service["service_type"] in DvbScanner.VIDEO_ALLOWED_TYPES or service["service_type"] in DvbScanner.INTERACTIVE_ALLOWED_TYPES:
				for number in service["numbers"]:
					if service["region_id"] == 0xff:
						if number not in video_services:
							video_services[number] = service
					else:
						video_services[number] = service
			elif service["service_type"] in DvbScanner.AUDIO_ALLOWED_TYPES:
				for number in service["numbers"]:
					if number not in radio_services:
						radio_services[number] = service

		print("[ABM-DvbScanner] Read extra info for %d services" % service_extra_count, file=log)
		return {
			"video": video_services,
			"radio": radio_services
		}

	def updateAndReadServicesFreeSat(self, bouquet_id, region_id, bouquet_key, transponders, servicehacks):
		print("[ABM-DvbScanner] Reading services (Freesat)...", file=log)

		fd = dvbreader.open(self.demuxer_device, self.bat_pid, self.bat_table_id, 0xff, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		bat_section_version = -1
		bat_sections_read = []
		bat_sections_count = 0
		bat_content = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.TIMEOUT_SEC)
		transport_stream_id_list = []
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading BAT", file=log)
				break

			section = dvbreader.read_bat(fd, self.bat_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] BAT raw section header", section["header"])
				print("[ABM-DvbScanner] BAT raw section content", section["content"])

			if section["header"]["table_id"] == self.bat_table_id:
				if section["header"]["bouquet_id"] != bouquet_id:
					continue

				if section["header"]["version_number"] != bat_section_version:
					bat_section_version = section["header"]["version_number"]
					bat_sections_read = []
					bat_content = []
					bat_sections_count = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in bat_sections_read:
					bat_sections_read.append(section["header"]["section_number"])
					bat_content += section["content"]

					if len(bat_sections_read) == bat_sections_count:
						break

		dvbreader.close(fd)

		service_count = 0
		tmp_services_dict = {}

		# start: read category info from descriptors 0xd5 and 0xd8
		d5 = []
		d8 = {}
		categories = {}
		for service in bat_content:
			if service["descriptor_tag"] == 0xd8:
				d8[service["category_id"]] = service["description"]
			elif service["descriptor_tag"] == 0xd5:
				d5.append(service)

		for service in d5:
			if service["channel_id"] not in categories:
				categories[service["channel_id"]] = [d8[service["category_id"]]]
			elif d8[service["category_id"]] not in categories[service["channel_id"]]:
				categories[service["channel_id"]].append(d8[service["category_id"]])
		# end: read category info from descriptors 0xd5 and 0xd8

		for service in bat_content:
			if service["descriptor_tag"] != 0xd3:
				continue

			if service["transport_stream_id"] not in transport_stream_id_list:
				transport_stream_id_list.append(service["transport_stream_id"])

			if service["region_id"] != region_id and service["region_id"] != 0xffff:
				continue

			service["service_type"] = 1
			service["free_ca"] = 1
			service["service_name"] = "Unknown"
			service["provider_name"] = "Unknown"
			namespace_key = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])
			if namespace_key not in self.namespace_dict:
				continue
			service["namespace"] = self.namespace_dict[namespace_key]
			service["flags"] = 0
			service["service_info"] = categories[service["channel_id"] & 0x0fff]  # add category info from descriptors 0xd5 and 0xd8

			key = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
			if key in tmp_services_dict:
				tmp_services_dict[key]["numbers"].append(service["number"])
				if service["region_id"] == region_id:
					tmp_services_dict[key]["region_id"] = service["region_id"]  # Overwrite the region if this is not the generic region. Makes the table order irrelevant.
			else:
				service["numbers"] = [service["number"]]
				tmp_services_dict[key] = service

			service_count += 1

		for service in bat_content:
			if service["descriptor_tag"] != 0x41:
				continue

			if service["service_type"] not in DvbScanner.VIDEO_ALLOWED_TYPES and service["service_type"] not in DvbScanner.AUDIO_ALLOWED_TYPES and service["service_type"] not in DvbScanner.INTERACTIVE_ALLOWED_TYPES:
				continue

			if service["service_type"] == 0x05:
				service["service_type"] = 0x01  # enigma2 doesn't like 0x05 VOD

			key = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
			if key in tmp_services_dict:
				tmp_services_dict[key]["service_type"] = service["service_type"]

		print("[ABM-DvbScanner] Read %d services with bouquet_id = 0x%x" % (service_count, bouquet_id), file=log)

		print("[ABM-DvbScanner] Reading services extra info...", file=log)

		# Clear double LCN values
		tmp_numbers = []
		tmp_double_numbers = []
		for key in tmp_services_dict:
			if len(tmp_services_dict[key]["numbers"]) > 1:
				for n in tmp_services_dict[key]["numbers"]:
					if n not in tmp_numbers:
						tmp_numbers.append(n)
					else:
						tmp_double_numbers.append(n)
		for key in tmp_services_dict:
			if tmp_double_numbers and len(tmp_services_dict[key]["numbers"]) > 1:
				for n in tmp_services_dict[key]["numbers"]:
					if n in tmp_double_numbers and tmp_services_dict[key]["region_id"] != region_id:  # only delete duplicate if this is not the user defined region.
						print("[ABM-DvbScanner] Deleted double LCN: %d" % (tmp_services_dict[key]["numbers"][0]), file=log)
						tmp_services_dict[key]["numbers"].remove(n)
						tmp_double_numbers.remove(n)

		if self.sdt_other_table_id == 0x00:
			mask = 0xff
		else:
			mask = self.sdt_current_table_id ^ self.sdt_other_table_id ^ 0xff

		fd = dvbreader.open(self.demuxer_device, self.sdt_pid, self.sdt_current_table_id, mask, self.frontend)
		if fd < 0:
			print("[ABM-DvbScanner] Cannot open the demuxer", file=log)
			return None

		sdt_secions_status = {}
		for transport_stream_id in transport_stream_id_list:
			sdt_secions_status[transport_stream_id] = {}
			sdt_secions_status[transport_stream_id]["section_version"] = -1
			sdt_secions_status[transport_stream_id]["sections_read"] = []
			sdt_secions_status[transport_stream_id]["sections_count"] = 0
			sdt_secions_status[transport_stream_id]["content"] = []

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, self.SDT_TIMEOUT)
		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-DvbScanner] Timed out reading SDT", file=log)
				break

			section = dvbreader.read_sdt(fd, self.sdt_current_table_id, self.sdt_other_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if self.extra_debug:
				print("[ABM-DvbScanner] SDT raw section header", section["header"])
				print("[ABM-DvbScanner] SDT raw section content", section["content"])

			if section["header"]["table_id"] == self.sdt_current_table_id or section["header"]["table_id"] == self.sdt_other_table_id:
				transport_stream_id = section["header"]["transport_stream_id"]

				if section["header"]["transport_stream_id"] not in transport_stream_id_list:
					continue

				if section["header"]["version_number"] != sdt_secions_status[transport_stream_id]["section_version"]:
					sdt_secions_status[transport_stream_id]["section_version"] = section["header"]["version_number"]
					sdt_secions_status[transport_stream_id]["sections_read"] = []
					sdt_secions_status[transport_stream_id]["content"] = []
					sdt_secions_status[transport_stream_id]["sections_count"] = section["header"]["last_section_number"] + 1

				if section["header"]["section_number"] not in sdt_secions_status[transport_stream_id]["sections_read"]:
					sdt_secions_status[transport_stream_id]["sections_read"].append(section["header"]["section_number"])
					sdt_secions_status[transport_stream_id]["content"] += section["content"]

					if len(sdt_secions_status[transport_stream_id]["sections_read"]) == sdt_secions_status[transport_stream_id]["sections_count"]:
						transport_stream_id_list.remove(transport_stream_id)

			if len(transport_stream_id_list) == 0:
				break

		if len(transport_stream_id_list) > 0:
			print("[ABM-DvbScanner] Cannot fetch SDT for the following transport_stream_id list: ", transport_stream_id_list, file=log)

		dvbreader.close(fd)

		for key in sdt_secions_status:
			for section in sdt_secions_status[key]["content"]:
				srvkey = "%x:%x:%x" % (section["transport_stream_id"], section["original_network_id"], section["service_id"])

				if srvkey not in tmp_services_dict:
					continue

				service = tmp_services_dict[srvkey]

				service["free_ca"] = section["free_ca"]
				service["service_name"] = section["service_name"]
				service["provider_name"] = section["provider_name"]

		video_services = {}
		radio_services = {}

		service_extra_count = 0

		servicehack_variable_cache = {"add_audio_channels_to_video_bouquet": False}

		skip = skipper()

		for key in self.LCN_order(tmp_services_dict):
			service = tmp_services_dict[key]

			if self.extra_debug:
				print("[ABM-DvbScanner] Service", service)

			if len(servicehacks) > 0:
				skip.skip = False
				exec(servicehacks)

				if skip.skip:
					continue

			tpkey = "%x:%x:%x" % (service["namespace"], service["transport_stream_id"], service["original_network_id"])
			if tpkey not in transponders:
				continue

			transponders[tpkey]["services"][service["service_id"]] = service
			service_extra_count += 1

			if service["service_type"] in DvbScanner.VIDEO_ALLOWED_TYPES or service["service_type"] in DvbScanner.INTERACTIVE_ALLOWED_TYPES or service["service_type"] in DvbScanner.AUDIO_ALLOWED_TYPES and servicehack_variable_cache["add_audio_channels_to_video_bouquet"]:
				for number in service["numbers"]:
					if service["region_id"] == 0xffff:
						if number not in video_services:
							video_services[number] = service
					else:
						video_services[number] = service
			else:
				for number in service["numbers"]:
					if number not in radio_services:
						radio_services[number] = service

		print("[ABM-DvbScanner] Read extra info for %d services" % service_extra_count, file=log)
		return {
			"video": video_services,
			"radio": radio_services
		}

	def extrasHelper(self, tmp_services_dict, extras, allow_encrypted):
		max_channel_number = 1450
		space_for_iteractive = 50
		round_to_nearest = 50
		LCNs = []
		for key in tmp_services_dict:
			service = tmp_services_dict[key]
			for number in service["numbers"]:
				if number <= max_channel_number:
					LCNs.append(number)
		if len(LCNs) == 0:
			return tmp_services_dict, LCNs
		current_lcn = max(LCNs) + space_for_iteractive
		while current_lcn % round_to_nearest:
			current_lcn += 1
		if current_lcn <= max_channel_number:
			import re
			sort_list = []
			i = 0
			for service in extras:
				if (service["service_type"] in DvbScanner.VIDEO_ALLOWED_TYPES or service["service_type"] in DvbScanner.INTERACTIVE_ALLOWED_TYPES) and (allow_encrypted or service["free_ca"] == 0):
					# sort flat, alphabetic before numbers
					sort_list.append((i, re.sub('^(?![a-z])', 'zzzzz', service['service_name'].lower())))
				i += 1
			sort_list = sorted(sort_list, key=lambda listItem: listItem[1])
			for item in sort_list:
				if current_lcn > max_channel_number:
					break
				service = extras[item[0]]
				namespace_key = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])
				if namespace_key not in self.namespace_dict:
					continue
				namespace = self.namespace_dict[namespace_key]
				LCNs.append(current_lcn)
				if "channel_id" not in service:
					service["channel_id"] = 0
				new_service = {
					'region_id': 255,
					'free_ca': service["free_ca"],
					'original_network_id': service["original_network_id"],
					'service_name': service["service_name"],
					'namespace': namespace,
					'number': current_lcn,
					'service_type': service["service_type"],
					'flags': 0,
					'numbers': [current_lcn],
					'service_id': service["service_id"],
					'descriptor_tag': 177,
					'transport_stream_id': service["transport_stream_id"],
					'provider_name': service["provider_name"],
					'channel_id': service["channel_id"],
					'bouquet_id': 0,
					'bouquet_key': ''
				}
				srvkey = "%x:%x:%x" % (service["transport_stream_id"], service["original_network_id"], service["service_id"])
				tmp_services_dict[srvkey] = new_service
				current_lcn += 1

		return tmp_services_dict, LCNs

	def LCN_order(self, tmp_services_dict):
		sort_list = [(x[0], min(x[1]['numbers'])) for x in list(tmp_services_dict.items())]
		return [x[0] for x in sorted(sort_list, key=lambda listItem: listItem[1])]

	def skyCategoryName(self, category_id):
		if category_id == 0:
			return "Unknown"
		cat_0 = category_id >> 8
		cat_f = category_id & 0xFF
		cat_0_dict = {
			0x10: "Sky Info",
			0x30: "Shopping",
			0x50: "Kids",
			0x70: "Entertainment",
			0x90: "Radio",
			0xB0: "News",
			0xD0: "Movies",
			0xF0: "Sports",
			0x00: "Sky Help",
			0x20: "Unknown (0x20)",
			0x40: "Unknown (0x40)",
			0x60: "Unknown (0x60)",
			0x80: "Unknown (0x80)",
			0xA0: "Unknown (0xA0)",
			0xC0: "Unknown (0xC0)",
			0xE0: "Sports Pub"
		}
		cat_f_dict = {
			0x1F: "Lifestyle and Culture",
			0x3F: "Adult",
			0x5F: "Gaming and Dating",
			0x7F: "Documentaries",
			0x9F: "Music",
			0xBF: "Religion",
			0xDF: "International",
			0xFF: "Specialist",
			0x0F: "Unknown (0x0F)",
			0x2F: "Unknown (0x2F)",
			0x4F: "Unknown (0x4F)",
			0x6F: "Unknown (0x6F)",
			0x8F: "Unknown (0x8F)",
			0xAF: "Unknown (0xAF)",
			0xCF: "Unknown (0xCF)",
			0xEF: "Unknown (0xEF)"
		}
		if cat_0 in cat_0_dict:
			return cat_0_dict[cat_0]
		if cat_f in cat_f_dict:
			return cat_f_dict[cat_f]
		return "Unknown"


class skipper():
	def __init__(self):
		self.x = False

	def setSkip(self, skip):
		self.x = skip

	def getSkip(self):
		return self.x

	skip = property(getSkip, setSkip)
