# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import

# for localized messages
from .. import _

from .. import log

from Components.config import config
from .tools import Tools
from .dvbscanner import DvbScanner
import os
import codecs
import re
import six

from enigma import eDVBFrontendParametersSatellite


class BouquetsWriter():

	ABM_BOUQUET_PREFIX = "userbouquet.abm."

	def writeLamedb(self, path, transponders):
		print("[ABM-BouquetsWriter] Writing lamedb...", file=log)

		transponders_count = 0
		services_count = 0

		lamedblist = []
		lamedblist.append("eDVB services /4/\n")
		lamedblist.append("transponders\n")

		for key in list(transponders.keys()):
			transponder = transponders[key]
			if "services" not in list(transponder.keys()) or len(transponder["services"]) < 1:
				continue
			lamedblist.append("%08x:%04x:%04x\n" %
				(transponder["namespace"],
				transponder["transport_stream_id"],
				transponder["original_network_id"]))

			if transponder["dvb_type"] == "dvbs":
				if transponder["orbital_position"] > 1800:
					orbital_position = transponder["orbital_position"] - 3600
				else:
					orbital_position = transponder["orbital_position"]

				if transponder["system"] == 0:  # DVB-S
					lamedblist.append("\ts %d:%d:%d:%d:%d:%d:%d\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"]))
				else:  # DVB-S2
					multistream = ''
					t2mi = ''
					if "t2mi_plp_id" in transponder and "t2mi_pid" in transponder:
						t2mi = ':%d:%d' % (
							transponder["t2mi_plp_id"],
							transponder["t2mi_pid"])
					if "is_id" in transponder and "pls_code" in transponder and "pls_mode" in transponder:
						multistream = ':%d:%d:%d' % (
							transponder["is_id"],
							transponder["pls_code"],
							transponder["pls_mode"])
					if t2mi and not multistream:  # this is to pad t2mi values if necessary.
						try:  # some images are still not multistream aware after all this time
							multistream = ':%d:%d:%d' % (
								eDVBFrontendParametersSatellite.No_Stream_Id_Filter,
								eDVBFrontendParametersSatellite.PLS_Gold,
								eDVBFrontendParametersSatellite.PLS_Default_Gold_Code)
						except AttributeError as err:
							print("[ABM-BouquetsWriter] some images are still not multistream aware after all this time", err, file=log)
					lamedblist.append("\ts %d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d%s%s\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"],
						transponder["system"],
						transponder["modulation"],
						transponder["roll_off"],
						transponder["pilot"],
						multistream,
						t2mi))
			elif transponder["dvb_type"] == "dvbt":
				lamedblist.append("\tt %d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["bandwidth"],
					transponder["code_rate_hp"],
					transponder["code_rate_lp"],
					transponder["modulation"],
					transponder["transmission_mode"],
					transponder["guard_interval"],
					transponder["hierarchy"],
					transponder["inversion"],
					transponder["flags"],
					transponder["system"],
					transponder["plpid"]))
			elif transponder["dvb_type"] == "dvbc":
				lamedblist.append("\tc %d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["symbol_rate"],
					transponder["inversion"],
					transponder["modulation"],
					transponder["fec_inner"],
					transponder["flags"],
					transponder["system"]))
			lamedblist.append("/\n")
			transponders_count += 1

		lamedblist.append("end\nservices\n")
		for key in list(transponders.keys()):
			transponder = transponders[key]
			if "services" not in list(transponder.keys()):
				continue

			for key2 in list(transponder["services"].keys()):
				service = transponder["services"][key2]

				lamedblist.append("%04x:%08x:%04x:%04x:%d:%d%s\n" %
					(service["service_id"],
					service["namespace"],
					service["transport_stream_id"],
					service["original_network_id"],
					service["service_type"],
					service["flags"],
					":%x" % service["ATSC_source_id"] if "ATSC_source_id" in service else ""))

				control_chars = ''.join(list(map(six.unichr, list(range(0, 32)) + list(range(127, 160)))))
				control_char_re = re.compile('[%s]' % re.escape(control_chars))
				if 'provider_name' in list(service.keys()):
					if six.PY2:
						service_name = control_char_re.sub('', service["service_name"]).decode('latin-1').encode("utf8")
						provider_name = control_char_re.sub('', service["provider_name"]).decode('latin-1').encode("utf8")
					else:
						service_name = control_char_re.sub('', six.ensure_text(six.ensure_str(service["service_name"], encoding='latin-1'), encoding='utf-8', errors='ignore'))
						provider_name = control_char_re.sub('', six.ensure_text(six.ensure_str(service["provider_name"], encoding='latin-1'), encoding='utf-8', errors='ignore'))
				else:
					service_name = service["service_name"]

				lamedblist.append("%s\n" % service_name)

				service_ca = ""
				if "free_ca" in list(service.keys()) and service["free_ca"] != 0:
					service_ca = ",C:0000"

				service_flags = ""
				if "service_flags" in list(service.keys()) and service["service_flags"] > 0:
					service_flags = ",f:%x" % service["service_flags"]

				if 'service_line' in list(service.keys()):
					lamedblist.append(self.utf8_convert("%s\n" % service["service_line"]))
				else:
					lamedblist.append("p:%s%s%s\n" % (provider_name, service_ca, service_flags))
				services_count += 1

		lamedblist.append("end\nHave a lot of bugs!\n")
		lamedb = codecs.open(path + "/lamedb", "w", "utf-8")
		lamedb.write(''.join(lamedblist))
		lamedb.close()
		del lamedblist

		print("[ABM-BouquetsWriter] Wrote %d transponders and %d services" % (transponders_count, services_count), file=log)

	def writeLamedb5(self, path, transponders):
		print("[ABM-BouquetsWriter] Writing lamedb V5...", file=log)

		transponders_count = 0
		services_count = 0

		lamedblist = []
		lamedblist.append("eDVB services /5/\n")
		lamedblist.append("# Transponders: t:dvb_namespace:transport_stream_id:original_network_id,FEPARMS\n")
		lamedblist.append("#     DVBS  FEPARMS:   s:frequency:symbol_rate:polarisation:fec:orbital_position:inversion:flags\n")
		lamedblist.append("#     DVBS2 FEPARMS:   s:frequency:symbol_rate:polarisation:fec:orbital_position:inversion:flags:system:modulation:rolloff:pilot[,MIS/PLS:is_id:pls_code:pls_mode][,T2MI:t2mi_plp_id:t2mi_pid]\n")
		lamedblist.append("#     DVBT  FEPARMS:   t:frequency:bandwidth:code_rate_HP:code_rate_LP:modulation:transmission_mode:guard_interval:hierarchy:inversion:flags:system:plp_id\n")
		lamedblist.append("#     DVBC  FEPARMS:   c:frequency:symbol_rate:inversion:modulation:fec_inner:flags:system\n")
		lamedblist.append('# Services: s:service_id:dvb_namespace:transport_stream_id:original_network_id:service_type:service_number:source_id,"service_name"[,p:provider_name][,c:cached_pid]*[,C:cached_capid]*[,f:flags]\n')

		for key in list(transponders.keys()):
			transponder = transponders[key]
			if "services" not in list(transponder.keys()) or len(transponder["services"]) < 1:
				continue
			lamedblist.append("t:%08x:%04x:%04x," %
				(transponder["namespace"],
				transponder["transport_stream_id"],
				transponder["original_network_id"]))

			if transponder["dvb_type"] == "dvbs":
				if transponder["orbital_position"] > 1800:
					orbital_position = transponder["orbital_position"] - 3600
				else:
					orbital_position = transponder["orbital_position"]

				if transponder["system"] == 0:  # DVB-S
					lamedblist.append("s:%d:%d:%d:%d:%d:%d:%d\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"]))
				else:  # DVB-S2
					multistream = ''
					t2mi = ''
					if "is_id" in transponder and "pls_code" in transponder and "pls_mode" in transponder:
						try:  # some images are still not multistream aware after all this time
							# don't write default values
							if not (transponder["is_id"] == eDVBFrontendParametersSatellite.No_Stream_Id_Filter and transponder["pls_code"] == eDVBFrontendParametersSatellite.PLS_Gold and transponder["pls_mode"] == eDVBFrontendParametersSatellite.PLS_Default_Gold_Code):
								multistream = ',MIS/PLS:%d:%d:%d' % (
									transponder["is_id"],
									transponder["pls_code"],
									transponder["pls_mode"])
						except AttributeError as err:
							print("[ABM-BouquetsWriter] some images are still not multistream aware after all this time", err, file=log)
					if "t2mi_plp_id" in transponder and "t2mi_pid" in transponder:
						t2mi = ',T2MI:%d:%d' % (
							transponder["t2mi_plp_id"],
							transponder["t2mi_pid"])
					lamedblist.append("s:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d%s%s\n" %
						(transponder["frequency"],
						transponder["symbol_rate"],
						transponder["polarization"],
						transponder["fec_inner"],
						orbital_position,
						transponder["inversion"],
						transponder["flags"],
						transponder["system"],
						transponder["modulation"],
						transponder["roll_off"],
						transponder["pilot"],
						multistream,
						t2mi))
			elif transponder["dvb_type"] == "dvbt":
				lamedblist.append("t:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["bandwidth"],
					transponder["code_rate_hp"],
					transponder["code_rate_lp"],
					transponder["modulation"],
					transponder["transmission_mode"],
					transponder["guard_interval"],
					transponder["hierarchy"],
					transponder["inversion"],
					transponder["flags"],
					transponder["system"],
					transponder["plpid"]))
			elif transponder["dvb_type"] == "dvbc":
				lamedblist.append("c:%d:%d:%d:%d:%d:%d:%d\n" %
					(transponder["frequency"],
					transponder["symbol_rate"],
					transponder["inversion"],
					transponder["modulation"],
					transponder["fec_inner"],
					transponder["flags"],
					transponder["system"]))
			transponders_count += 1

		for key in list(transponders.keys()):
			transponder = transponders[key]
			if "services" not in list(transponder.keys()):
				continue

			for key2 in list(transponder["services"].keys()):
				service = transponder["services"][key2]

				lamedblist.append("s:%04x:%08x:%04x:%04x:%d:%d%s," %
					(service["service_id"],
					service["namespace"],
					service["transport_stream_id"],
					service["original_network_id"],
					service["service_type"],
					service["flags"],
					":%x" % service["ATSC_source_id"] if "ATSC_source_id" in service else ":0"))

				control_chars = ''.join(list(map(six.unichr, list(range(0, 32)) + list(range(127, 160)))))
				control_char_re = re.compile('[%s]' % re.escape(control_chars))
				if 'provider_name' in list(service.keys()):
					if six.PY2:
						service_name = control_char_re.sub('', service["service_name"]).decode('latin1').encode("utf8")
						provider_name = control_char_re.sub('', service["provider_name"]).decode('latin1').encode("utf8")
					else:
						service_name = control_char_re.sub('', six.ensure_text(six.ensure_str(service["service_name"], encoding='latin1'), encoding='utf8', errors='ignore'))
						provider_name = control_char_re.sub('', six.ensure_text(six.ensure_str(service["provider_name"], encoding='latin1'), encoding='utf8', errors='ignore'))
				else:
					service_name = service["service_name"]

				lamedblist.append('"%s"' % service_name)

				service_ca = ""
				if "free_ca" in list(service.keys()) and service["free_ca"] != 0:
					service_ca = ",C:0000"

				service_flags = ""
				if "service_flags" in list(service.keys()) and service["service_flags"] > 0:
					service_flags = ",f:%x" % service["service_flags"]

				if 'service_line' in list(service.keys()):
					if len(service["service_line"]):
						lamedblist.append(",%s\n" % self.utf8_convert(service["service_line"]))
					else:
						lamedblist.append("\n")
				else:
					lamedblist.append(",p:%s%s%s\n" % (provider_name, service_ca, service_flags))
				services_count += 1

		lamedb = codecs.open(path + "/lamedb5", "w", "utf-8")
		lamedb.write(''.join(lamedblist))
		lamedb.close()
		del lamedblist

		print("[ABM-BouquetsWriter] Wrote %d transponders and %d services" % (transponders_count, services_count), file=log)

	def makeCustomSeparator(self, path, filename, max_count):
		print("[ABM-BouquetsWriter] Make custom seperator for %s in main bouquet..." % filename, file=log)

		try:
			bouquet_in = open(path + "/" + filename, "r")
		except Exception as e:
			print("[ABM-BouquetsWriter] ", e, file=log)
			return

		content = bouquet_in.read()
		bouquet_in.close()

		seperator_name = "/%s%s.separator.tv" % (self.ABM_BOUQUET_PREFIX, filename[:len(filename) - 3])
		try:
			bouquet_out = open(path + seperator_name, "w")
		except Exception as e:
			print("[ABM-BouquetsWriter] ", e, file=log)
			return

		rows = content.split("\n")
		count = 0

		name = ''
		for row in rows:
			if len(row.strip()) == 0:
				break

			if row[:5] == "#NAME" and name == '':
				name = row.strip()[6:]

			if row[:8] == "#SERVICE" and row[:13] != "#SERVICE 1:64":
				count += 1
				if count > max_count:
					break

			# bouquet_out_list.append(row + "\n")

		print("[ABM-BouquetsWriter] Custom seperator name: %s" % name, file=log)

		bouquet_out_list = []

		bouquet_out_list.append("#NAME CustomSeparatorMain for %s\n" % name)
		bouquet_out_list.append("#SERVICE 1:64:0:0:0:0:0:0:0:0:\n")
		bouquet_out_list.append("#DESCRIPTION CustomSeparatorMain for %s\n" % name)

		if count < max_count:
			for i in list(range(count, max_count)):
				bouquet_out_list.append(self.spacer())

		bouquet_out.write(''.join(bouquet_out_list))
		bouquet_out.close()
		del bouquet_out_list

		print("[ABM-BouquetsWriter] Custom seperator made. %s" % seperator_name, file=log)

	def containServices(self, path, filename):
		try:
			bouquets = open(path + "/" + filename, "r")
			content = bouquets.read().strip().split("\n")
			bouquets.close()
			return len(content) > 2
		except Exception as e:
			return False

	def containServicesLines(self, path, filename):
		try:
			bouquets = open(path + "/" + filename, "r")
			content = bouquets.read().strip().split("\n")
			bouquets.close()
			recognised_service_lines = ["#SERVICE %d:0:" % i for i in Tools.SERVICEREF_ALLOWED_TYPES] + ["#SERVICE 1:7:"]
			for line in content:
				if "%s:" % ':'.join(line.split(":")[:2]) in recognised_service_lines:  # service or iptv line found, eg "#SERVICE 4097:0:"
					return True
					break
			return False
		except Exception as e:
			return False

	def buildBouquetsIndex(self, path, bouquetsOrder, providers, bouquetsToKeep, currentBouquets, bouquets_to_hide, provider_configs):
		print("[ABM-BouquetsWriter] Writing bouquets index...", file=log)

		bouquets_tv = open(path + "/bouquets.tv", "w")
		bouquets_tv_list = []
		bouquets_tv_list.append("#NAME Bouquets (TV)\n")

		bouquets_radio = open(path + "/bouquets.radio", "w")
		bouquets_radio_list = []
		bouquets_radio_list.append("#NAME Bouquets (Radio)\n")

		bouquetsToKeep2 = {}
		bouquetsToKeep2["tv"] = []
		bouquetsToKeep2["radio"] = []

		customfilenames = []
		display_empty_bouquet = ['userbouquet.favourites.tv', 'userbouquet.favourites.radio', 'userbouquet.LastScanned.tv']

		if 'userbouquet.LastScanned.tv' not in bouquetsToKeep["tv"] and config.autobouquetsmaker.keepallbouquets.getValue():
			bouquetsToKeep["tv"].append('userbouquet.LastScanned.tv')
		if 'userbouquet.LastScanned.tv' not in currentBouquets["tv"]:
			currentBouquets["tv"].append('userbouquet.LastScanned.tv')

		if config.autobouquetsmaker.placement.getValue() == 'bottom':
			for bouquet_type in ["tv", "radio"]:
				for filename in currentBouquets[bouquet_type]:
					if filename[:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
						continue
					if filename in bouquetsToKeep[bouquet_type] and (self.containServicesLines(path, filename) or filename in display_empty_bouquet):
						to_write = "#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s\" ORDER BY bouquet\n" % filename
					else:
						to_write = "#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s\" ORDER BY bouquet\n" % filename
					if bouquet_type == "tv":
						bouquets_tv_list.append(to_write)
					else:
						bouquets_radio_list.append(to_write)

		for section_identifier in bouquetsOrder:
			sections = providers[section_identifier]["sections"]
			if config.autobouquetsmaker.markersinindex.value and provider_configs[section_identifier].isMakeAnyBouquet():
				bouquets_tv_list.append(self.styledBouquetMarker(providers[section_identifier]["name"], "index"))

			if provider_configs[section_identifier].isMakeNormalMain() or provider_configs[section_identifier].isMakeHDMain() or provider_configs[section_identifier].isMakeFTAHDMain():
				if self.containServices(path, "%s%s.main.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier)):
					bouquets_tv_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.main.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier))
				else:
					bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.main.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier))
				bouquetsToKeep2["tv"].append("%s%s.main.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier))
			elif provider_configs[section_identifier].isMakeCustomMain() and config.autobouquetsmaker.placement.getValue() == 'top':
				customfilename = provider_configs[section_identifier].getCustomFilename()
				bouquets_tv_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s\" ORDER BY bouquet\n" % customfilename)
				customseperator = "%s%s.separator.tv" % (self.ABM_BOUQUET_PREFIX, customfilename[:len(customfilename) - 3])
				bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s\" ORDER BY bouquet\n" % customseperator)
				bouquetsToKeep2["tv"].append(customfilename)
				bouquetsToKeep2["tv"].append(customseperator)
				customfilenames.append(customfilename)

			if provider_configs[section_identifier].isMakeSections():
				for section_number in sorted(list(sections.keys())):
					if (section_identifier in bouquets_to_hide and section_number in bouquets_to_hide[section_identifier]) or not self.containServicesLines(path, "%s%s.%d.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_number)):
						bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%d.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_number))
					else:
						bouquets_tv_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%d.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_number))
					bouquetsToKeep2["tv"].append("%s%s.%d.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_number))

			if provider_configs[section_identifier].isMakeNormalMain() or \
				provider_configs[section_identifier].isMakeHDMain() or \
				provider_configs[section_identifier].isMakeFTAHDMain() or \
				provider_configs[section_identifier].isMakeSections() or \
				provider_configs[section_identifier].isMakeCustomMain():
				bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.separator.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier))
				bouquetsToKeep2["tv"].append("%s%s.separator.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier))

			if provider_configs[section_identifier].isMakeHD():
				section_type = "hd"
				if self.containServicesLines(path, "%s%s.%s.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type)):
					bouquets_tv_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%s.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))
				else:
					bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%s.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))
				bouquetsToKeep2["tv"].append("%s%s.%s.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))

			if provider_configs[section_identifier].isMakeFTAHD():
				section_type = "ftahd"
				if self.containServicesLines(path, "%s%s.%s.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type)):
					bouquets_tv_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%s.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))
				else:
					bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%s.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))
				bouquetsToKeep2["tv"].append("%s%s.%s.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))

			if provider_configs[section_identifier].isMakeFTA():
				section_type = "fta"
				if self.containServicesLines(path, "%s%s.%s.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type)):
					bouquets_tv_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%s.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))
				else:
					bouquets_tv_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.%s.tv\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))
				bouquetsToKeep2["tv"].append("%s%s.%s.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_type))

			containsLines = self.containServicesLines(path, "%s%s.main.radio" % (self.ABM_BOUQUET_PREFIX, section_identifier))
			if config.autobouquetsmaker.markersinindex.value and containsLines:
				bouquets_radio_list.append(self.styledBouquetMarker(providers[section_identifier]["name"], "index"))
			if containsLines:
				bouquets_radio_list.append("#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.main.radio\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier))
			else:
				bouquets_radio_list.append("#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s%s.main.radio\" ORDER BY bouquet\n" % (self.ABM_BOUQUET_PREFIX, section_identifier))
			bouquetsToKeep2["radio"].append("%s%s.main.radio" % (self.ABM_BOUQUET_PREFIX, section_identifier))

		if config.autobouquetsmaker.placement.getValue() == 'top':
			for bouquet_type in ["tv", "radio"]:
				for filename in currentBouquets[bouquet_type]:
					if filename[:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX or filename in customfilenames:
						continue
					if filename in bouquetsToKeep[bouquet_type] and (self.containServicesLines(path, filename) or filename in display_empty_bouquet):
						to_write = "#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s\" ORDER BY bouquet\n" % filename
					else:
						to_write = "#SERVICE 1:519:1:0:0:0:0:0:0:0:FROM BOUQUET \"%s\" ORDER BY bouquet\n" % filename
					if bouquet_type == "tv":
						bouquets_tv_list.append(to_write)
					else:
						bouquets_radio_list.append(to_write)

		bouquets_tv.write(''.join(bouquets_tv_list))
		bouquets_tv.close()
		del bouquets_tv_list

		bouquets_radio.write(''.join(bouquets_radio_list))
		bouquets_radio.close()
		del bouquets_radio_list

		for bouquet_type in ["tv", "radio"]:
			for filename in currentBouquets[bouquet_type]:
				if filename[:len(self.ABM_BOUQUET_PREFIX)] != self.ABM_BOUQUET_PREFIX or filename in bouquetsToKeep2[bouquet_type]:
					continue

				try:
					os.remove(path + "/" + filename)
				except Exception as e:
					print("[ABM-BouquetsWriter] Cannot delete %s: %s" % (filename, e), file=log)
					continue
		print("[ABM-BouquetsWriter] Done", file=log)

	def buildLastScannedBouquet(self, path, services):
		last_scanned_bouquet_list = ["#NAME " + _("Last Scanned") + "\n"]
		tmp_services = {}
		sort_list = []
		avoid_duplicates = []
		i = 1
		import re
		for provider in list(services.keys()):
			for type in ('video', 'radio'):
				for lcn in services[provider][type]:
					service = services[provider][type][lcn]
					# sort flat, alphabetic before numbers
					ref = "%x:%x:%x:%x" % (
						service["service_id"],
						service["transport_stream_id"],
						service["original_network_id"],
						service["namespace"]
					)
					if ref in avoid_duplicates:
						continue
					tmp_services[i] = service
					avoid_duplicates.append(ref)
					sort_list.append((i, re.sub('^(?![a-z])', 'zzzzz', service['service_name'].lower()), service["service_type"] not in DvbScanner.VIDEO_ALLOWED_TYPES))
					i += 1
		sort_list = sorted(sort_list, key=lambda listItem: (listItem[2], listItem[1]))  # listItem[2] puts radio channels second.
		for item in sort_list:
			service = tmp_services[item[0]]
			last_scanned_bouquet_list.append(self.bouquetServiceLine(service))
		print("[ABM-BouquetsWriter] Writing Last Scanned bouquet...", file=log)
		bouquet_current = open(path + "/userbouquet.LastScanned.tv", "w")
		bouquet_current.write(''.join(last_scanned_bouquet_list))
		bouquet_current.close()
		del sort_list
		del tmp_services
		del last_scanned_bouquet_list
		del avoid_duplicates

	def buildBouquets(self, path, provider_config, services, sections, section_identifier, preferred_order, bouquets_to_hide, section_prefix):
		section_sep = " - " if len(section_prefix) > 0 else ""
		current_number = 0

		# as first thing we're going to cleanup channels
		# with a numeration inferior to the first section
		first_section_number = sorted(list(sections.keys()))[0]
		for number in sorted(list(services["video"].keys())):
			if number >= first_section_number:
				break

			del (services["video"][number])

		print("[ABM-BouquetsWriter] Writing %s bouquet..." % section_identifier, file=log)

		force_keep_numbers = False

		# swap channels
		swapDict = {}
		for swaprule in preferred_order:
			if swaprule[0] in services["video"] and swaprule[1] in services["video"] and services["video"][swaprule[1]]["service_type"] in DvbScanner.HD_ALLOWED_TYPES and services["video"][swaprule[0]]["service_type"] not in DvbScanner.HD_ALLOWED_TYPES:
				# conditional is optional. If not present the swaprule is automatically added to the swap dict. If conditional is present it must evaluate to True
				conditional = len(swaprule) > 2 and swaprule[2] or None
				if not conditional or eval(conditional, {}, {'service_sd': services["video"][swaprule[0]], 'service_hd': services["video"][swaprule[1]]}):
					swapDict[swaprule[0]] = swaprule[1]
					swapDict[swaprule[1]] = swaprule[0]

		# create a swapped list for fulltime use in HD bouquets
		if provider_config.isMakeHDMain() or \
			provider_config.isMakeFTAHDMain() or \
			provider_config.isMakeHD() or \
			provider_config.isMakeFTAHD():
			services_swapped = {"video": {}}
			for number in services["video"]:
				if number in swapDict:
					services_swapped["video"][swapDict[number]] = services["video"][number]
				else:
					services_swapped["video"][number] = services["video"][number]

		if provider_config.isMakeNormalMain():
			bouquet_current = open(path + "/%s%s.main.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
			current_bouquet_list = []
			current_bouquet_list.append("#NAME %s%s\n" % (section_prefix, "" if len(section_prefix) > 0 and provider_config.isMakeNormalMainOnly() else section_sep + _('All channels')))

			# Clear unused sections
			sections_c = sections.copy()
			sections_c = Tools().clearsections(services, sections_c, 'ALL', "video")

			# small hack to handle the "preferred_order" list
			higher_number = sorted(list(services["video"].keys()))[-1]
			preferred_order_tmp = []

			# expand a range into a list
			for number in list(range(1, higher_number + 1)):
				preferred_order_tmp.append(number)

			# Always write first not hidden section on top of list
			for number in preferred_order_tmp:
				if number in sections_c and number not in bouquets_to_hide:
					current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, sections_c[number])))
					first_section = number
					break

			# Use separate section counter. Preferred_order_tmp has swapped numbers. Can put sections on wrong places
			section_number = 1
			for number in preferred_order_tmp:
				if section_number in sections_c and section_number not in bouquets_to_hide and section_number != first_section:
					current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, sections_c[section_number])))
				orig_number = number  # Workaround to allow swapped channels to show when their section is hidden. i.e. test the real position in the bouquet (by channel number), not the source of the swap.
				if provider_config.isSwapChannels() and number in swapDict:
					number = swapDict[number]
				if number in services["video"] and orig_number not in bouquets_to_hide:  # "bouquets_to_hide" is a complete list of all numbers in each hidden section, whether a channel occupies that number or not.
					current_bouquet_list.append(self.bouquetServiceLine(services["video"][number]))
				else:
					current_bouquet_list.append(self.spacer())

				current_number += 1
				section_number += 1

			bouquet_current.write(''.join(current_bouquet_list))
			bouquet_current.close()
			del current_bouquet_list

		elif provider_config.isMakeHDMain() or provider_config.isMakeFTAHDMain():
			bouquet_current = open(path + "/%s%s.main.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
			current_bouquet_list = []
			if provider_config.isMakeHDMain():
				hd_or_ftahd = "HD"
				current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, _('HD Channels')))
			elif provider_config.isMakeFTAHDMain():
				hd_or_ftahd = "FTAHD"
				current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, _('FTA HD Channels')))

			higher_number = sorted(list(sections.keys()))[0]

			# Clear unused sections
			sections_c = sections.copy()
			sections_c = Tools().clearsections(services_swapped, sections_c, hd_or_ftahd, "video")

			section_keys_temp = sorted(list(sections_c.keys()))
			section_key_current = section_keys_temp[0]

			if higher_number > 1:
				todo = None
				for number in sorted(list(services_swapped["video"].keys())):
					if number >= section_key_current:
						todo = None
						if section_key_current not in bouquets_to_hide:
							if section_key_current in sections_c:
								current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, sections_c[section_key_current])))
							todo = section_key_current

						if section_key_current in section_keys_temp:
							section_keys_temp.remove(section_key_current)

						if len(section_keys_temp) > 0:
							section_key_current = section_keys_temp[0]
						else:
							section_key_current = 65535

					if todo and number >= todo:
						if services_swapped["video"][number]["service_type"] in DvbScanner.HD_ALLOWED_TYPES and (provider_config.isMakeHDMain() or (provider_config.isMakeFTAHDMain() and 'free_ca' in services_swapped["video"][number] and services_swapped["video"][number]["free_ca"] == 0)):
							current_number += 1
							current_bouquet_list.append(self.bouquetServiceLine(services_swapped["video"][number]))

					if current_number == higher_number - 1:
						break

				for x in list(range(current_number, higher_number - 1)):
					current_bouquet_list.append(self.spacer())

				current_number = higher_number - 1

			bouquet_current.write(''.join(current_bouquet_list))
			bouquet_current.close()
			del current_bouquet_list
			force_keep_numbers = True

		elif provider_config.isMakeCustomMain() and config.autobouquetsmaker.placement.getValue() == 'top':
			current_number = sorted(list(sections.keys()))[0] - 1
			self.makeCustomSeparator(path, provider_config.getCustomFilename(), current_number)
			force_keep_numbers = True
		else:
			force_keep_numbers = True

		if provider_config.isMakeSections():
			if not provider_config.isMakeNormalMain() and not provider_config.isMakeHDMain() and not provider_config.isMakeFTAHDMain() and not provider_config.isMakeCustomMain():
				section_current_number = 0
			else:
				section_current_number = sorted(list(sections.keys()))[0] - 1

			for section_number in sorted(list(sections.keys())):
				section_name = sections[section_number]

				# discover the highest number for this section
				# it's tricky... i don't like it
				higher_number = 0
				key_found = False
				for key in sorted(list(sections.keys())):
					if key_found:
						higher_number = key - 1
						break

					if key == section_number:
						key_found = True

				if higher_number == 0:  # it mean this is the last section
					higher_number = sorted(list(services["video"].keys()))[-1]  # the highest number!

				# write it!
				bouquet_current = open(path + "/%s%s.%d.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier, section_number), "w")
				current_bouquet_list = []
				if section_number not in bouquets_to_hide:
					current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, section_name))
					current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, section_name)))
				elif section_current_number == 0:
					current_bouquet_list.append("#NAME %s%sHidden\n" % (section_prefix, section_sep))
					current_bouquet_list.append("#SERVICE 1:64:0:0:0:0:0:0:0:0:\n")
					current_bouquet_list.append("#DESCRIPTION %s%sHidden\n" % (section_prefix, section_sep))

				# current_number += 1
				section_current_number += 1
				for number in list(range(section_current_number, higher_number + 1)):
					if provider_config.isSwapChannels() and number in swapDict:
						number = swapDict[number]
					if number in services["video"] and section_number not in bouquets_to_hide:
						current_bouquet_list.append(self.bouquetServiceLine(services["video"][number]))
						current_number += 1
					elif force_keep_numbers:
						current_bouquet_list.append(self.spacer())
						current_number += 1

				bouquet_current.write(''.join(current_bouquet_list))
				bouquet_current.close()
				del current_bouquet_list
				section_current_number = higher_number

		# Seperator bouquet
		if provider_config.isMakeNormalMain() or \
			provider_config.isMakeHDMain() or \
			provider_config.isMakeFTAHDMain() or \
			provider_config.isMakeSections() or \
			provider_config.isMakeCustomMain():
			bouquet_current = open(path + "/%s%s.separator.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
			current_bouquet_list = []
			current_bouquet_list.append("#NAME %s%sSeparator\n" % (section_prefix, section_sep))
			current_bouquet_list.append("#SERVICE 1:64:0:0:0:0:0:0:0:0:\n")
			current_bouquet_list.append("#DESCRIPTION %s%sSeparator\n" % (section_prefix, section_sep))

			for x in list(range(current_number, (int(current_number / 1000) + 1) * 1000)):
				current_bouquet_list.append(self.spacer())
				current_number += 1

			bouquet_current.write(''.join(current_bouquet_list))
			bouquet_current.close()
			del current_bouquet_list

		# HD channels
		if provider_config.isMakeHD():
			bouquet_current = open(path + "/%s%s.hd.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
			current_bouquet_list = []
			current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, _('HD Channels')))

			# Clear unused sections
			sections_c = sections.copy()
			sections_c = Tools().clearsections(services_swapped, sections_c, "HD", "video")

			section_keys_temp = sorted(list(sections_c.keys()))
			section_key_current = section_keys_temp[0]

			todo = None
			for number in sorted(list(services_swapped["video"].keys())):
				if number >= section_key_current:
					todo = None
					if section_key_current not in bouquets_to_hide:
						if section_key_current in sections_c:
							current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, sections_c[section_key_current])))
						todo = section_key_current

					if section_key_current in section_keys_temp:
						section_keys_temp.remove(section_key_current)

					if len(section_keys_temp) > 0:
						section_key_current = section_keys_temp[0]
					else:
						section_key_current = 65535

				if todo and number >= todo:
					if services_swapped["video"][number]["service_type"] in DvbScanner.HD_ALLOWED_TYPES:
						current_number += 1
						current_bouquet_list.append(self.bouquetServiceLine(services_swapped["video"][number]))

			for x in list(range(current_number, (int(current_number / 1000) + 1) * 1000)):
				current_bouquet_list.append(self.spacer())
				current_number += 1

			bouquet_current.write(''.join(current_bouquet_list))
			bouquet_current.close()
			del current_bouquet_list

		# FTA HD channels
		if provider_config.isMakeFTAHD():
			bouquet_current = open(path + "/%s%s.ftahd.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
			current_bouquet_list = []
			current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, _('FTA HD Channels')))

			# Clear unused sections
			sections_c = sections.copy()
			sections_c = Tools().clearsections(services_swapped, sections_c, "FTAHD", "video")

			section_keys_temp = sorted(list(sections_c.keys()))
			section_key_current = section_keys_temp[0]

			todo = None
			for number in sorted(list(services_swapped["video"].keys())):
				if number >= section_key_current:
					todo = None
					if section_key_current not in bouquets_to_hide:
						if section_key_current in sections_c:
							current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, sections_c[section_key_current])))
						todo = section_key_current

					if section_key_current in section_keys_temp:
						section_keys_temp.remove(section_key_current)

					if len(section_keys_temp) > 0:
						section_key_current = section_keys_temp[0]
					else:
						section_key_current = 65535

				if todo and number >= todo:
					if services_swapped["video"][number]["service_type"] in DvbScanner.HD_ALLOWED_TYPES and 'free_ca' in services_swapped["video"][number] and services_swapped["video"][number]["free_ca"] == 0:
						current_number += 1
						current_bouquet_list.append(self.bouquetServiceLine(services_swapped["video"][number]))

			for x in list(range(current_number, (int(current_number / 1000) + 1) * 1000)):
				current_bouquet_list.append(self.spacer())
				current_number += 1

			bouquet_current.write(''.join(current_bouquet_list))
			bouquet_current.close()
			del current_bouquet_list

		# FTA channels
		if provider_config.isMakeFTA():
			bouquet_current = open(path + "/%s%s.fta.tv" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
			current_bouquet_list = []
			current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, _('FTA Channels')))

			# Clear unused sections
			sections_c = sections.copy()
			sections_c = Tools().clearsections(services, sections_c, "FTA", "video")

			section_keys_temp = sorted(list(sections_c.keys()))
			section_key_current = section_keys_temp[0]

			higher_number = sorted(list(services["video"].keys()))[-1]

			todo = None
			for number in list(range(1, higher_number + 1)):
				if number >= section_key_current:
					todo = None
					if section_key_current not in bouquets_to_hide:
						if section_key_current in sections_c:
							current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, sections_c[section_key_current])))
						todo = section_key_current

					if section_key_current in section_keys_temp:
						section_keys_temp.remove(section_key_current)

					if len(section_keys_temp) > 0:
						section_key_current = section_keys_temp[0]
					else:
						section_key_current = 65535

				if todo and number >= todo:
					if number in services["video"] and 'free_ca' in services["video"][number] and services["video"][number]["free_ca"] == 0 and number not in bouquets_to_hide:
						current_number += 1
						current_bouquet_list.append(self.bouquetServiceLine(services["video"][number]))

			for x in list(range(current_number, (int(current_number / 1000) + 1) * 1000)):
				current_bouquet_list.append(self.spacer())
				current_number += 1

			bouquet_current.write(''.join(current_bouquet_list))
			bouquet_current.close()
			del current_bouquet_list

		# now the radio bouquet
		bouquet_current = open(path + "/%s%s.main.radio" % (self.ABM_BOUQUET_PREFIX, section_identifier), "w")
		current_bouquet_list = []
		current_bouquet_list.append("#NAME %s%s%s\n" % (section_prefix, section_sep, _('Radio Channels')))
		current_bouquet_list.append(self.styledBouquetMarker("%s%s%s" % (section_prefix, section_sep, _('Radio Channels'))))

		if len(list(services["radio"].keys())) > 0:
			higher_number = sorted(list(services["radio"].keys()))[-1]  # the highest number!
			for number in list(range(1, higher_number + 1)):
				if number in services["radio"]:
					current_bouquet_list.append(self.bouquetServiceLine(services["radio"][number]))
				else:
					current_bouquet_list.append(self.spacer())

		bouquet_current.write(''.join(current_bouquet_list))
		bouquet_current.close()
		del current_bouquet_list

		print("[ABM-BouquetsWriter] Done", file=log)

	def bouquetServiceLine(self, service):
		return "#SERVICE %d:0:%x:%x:%x:%x:%x:0:0:0:%s\n%s" % (
			(service["servicereftype"] if "servicereftype" in service and service["servicereftype"] in Tools.SERVICEREF_ALLOWED_TYPES else 1),
			service["service_type"],
			service["service_id"],
			service["transport_stream_id"],
			service["original_network_id"],
			service["namespace"],
			(("%s:%s" % (service["stream"], self.utf8_convert(service["service_name"]))) if "stream" in service else ""),
			(("#DESCRIPTION %s\n" % self.utf8_convert(service["interactive_name"])) if "interactive_name" in service else "")
		)

	def spacer(self):
		return "#SERVICE 1:320:0:0:0:0:0:0:0:0:\n#DESCRIPTION  \n"

	def utf8_convert(self, text):
		for encoding in ["utf8", "latin1"]:
			try:
				if six.PY2:
					text.decode(encoding=encoding)
				else:
					six.ensure_str(text, encoding=encoding)
			except UnicodeDecodeError:
				encoding = None
			else:
				break
		if encoding == "utf8":
			return text
		if encoding is None:
			encoding = "utf8"
		if six.PY2:
			return text.decode(encoding=encoding, errors="ignore").encode("utf8")
		else:
			return six.ensure_text(six.ensure_str(text, encoding=encoding, errors='ignore'), encoding='utf8')

	def styledBouquetMarker(self, text, caller="bouquets"):
		if caller == "index":
			return "#SERVICE 1:64:0:0:0:0:0:0:0:0:\n#DESCRIPTION %s\n" % (config.autobouquetsmaker.indexmarkerstyle.value % text)
		return "#SERVICE 1:64:0:0:0:0:0:0:0:0:\n#DESCRIPTION %s\n" % (config.autobouquetsmaker.bouquetmarkerstyle.value % text)
