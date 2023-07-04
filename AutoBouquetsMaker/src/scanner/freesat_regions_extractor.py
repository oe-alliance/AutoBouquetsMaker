# Use: Tuner A. Tune Freesat home transponder (28.2E, 11426 H 27500 2/3).
# Using satfiner is one way to tune the above.
# Run this file from the command line.
# python /usr/lib/enigma2/python/Plugins/SystemPlugins/AutoBouquetsMaker/scanner/freesat_regions_extractor.py >/tmp/freesat.log
from __future__ import print_function

import dvbreader
import datetime
import time

# from operator import itemgetter

bat_pid = 0xbba  # This is the correct PID on Freesat home transponder. On other transponders use 0xf01.
bat_table = 0x4a
mask = 0xff
frontend = 0

TIMEOUT_SEC = 30

bouquets_list = []


def readBouquet(bouquet_id):
	print("[DvbScanner] Reading bouquet_id = 0x%x..." % bouquet_id)

	fd = dvbreader.open("/dev/dvb/adapter0/demux0", bat_pid, bat_table, mask, frontend)
	if fd < 0:
		print("[DvbScanner] Cannot open the demuxer")
		return None

	bat_section_version = -1
	bat_sections_read = []
	bat_sections_count = 0
	bat_content = []

	timeout = datetime.datetime.now()
	timeout += datetime.timedelta(0, TIMEOUT_SEC)
	while True:
		if datetime.datetime.now() > timeout:
			print("[DvbScanner] Timed out")
			break

		section = dvbreader.read_bat(fd, bat_table)
		if section is None:
			time.sleep(0.1)  # no data.. so we wait a bit
			continue

		if section["header"]["table_id"] == bat_table:
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

	bouquet_name = None
	for section in bat_content:
		if section["descriptor_tag"] == 0x47:
			bouquet_name = section["description"]
			break

	if bouquet_name is None:
		print("[DvbScanner] Cannot get bouquet name for bouquet_id = 0x%x" % bouquet_id)
		return

	for section in bat_content:
		if section["descriptor_tag"] == 0xd4:
			bouquet = {
				"name": bouquet_name + " - " + section["description"],
				"region": section["region_id"],
				"bouquet": bouquet_id
			}
			bouquets_list.append(bouquet)

	print("[DvbScanner] Done")


def getSortKey(elem):
	# group by: SD/HD/G2
	# sort by: "name"
	if " SD " in elem["name"]:
		return "SD " + elem["name"]
	elif " HD " in elem["name"]:
		return "HD " + elem["name"]
	else:
		return "G2 " + elem["name"]


# for bouquet_id in [0x100, 0x101]:
for bouquet_id in [0x100, 0x101, 0x102, 0x103, 0x110, 0x111, 0x112, 0x113, 0x118, 0x119, 0x11a, 0x11b]:
	readBouquet(bouquet_id)

# bouquets_list = sorted(bouquets_list, key=itemgetter('name'))
bouquets_list = sorted(bouquets_list, key=getSortKey)
for bouquet in bouquets_list:
	key = "freesat_%x_%x" % (bouquet["bouquet"], bouquet["region"])
	name = bouquet["name"].replace("&", "&amp;")
	print("<configuration key=\"%s\" bouquet=\"0x%x\" region=\"0x%x\">%s</configuration>" % (key, bouquet["bouquet"], bouquet["region"], name))
