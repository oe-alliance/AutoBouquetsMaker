from __future__ import print_function

# for localized messages
from .. import _

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Components.Sources.Progress import Progress
from Components.Sources.FrontendStatus import FrontendStatus
from Components.NimManager import nimmanager
from enigma import eDVBFrontendParameters, eDVBFrontendParametersTerrestrial, eDVBResourceManager, eTimer, iFrontendInformation

import dvbreader
# from scanner.main import AutoBouquetsMaker
from Plugins.SystemPlugins.AutoBouquetsMaker.skin_templates import skin_downloadBar

import os
import errno
import sys
import re

import datetime
import time

from Tools.Directories import resolveFilename, fileExists, SCOPE_CURRENT_SKIN


def setParams(frequency, system, bandwidth=8):  # freq is nine digits (474000000)
	params = eDVBFrontendParametersTerrestrial()
	params.frequency = frequency
	params.bandwidth = bandwidth * 1000000
	params.code_rate_hp = eDVBFrontendParametersTerrestrial.FEC_Auto
	params.code_rate_lp = eDVBFrontendParametersTerrestrial.FEC_Auto
	params.inversion = eDVBFrontendParametersTerrestrial.Inversion_Unknown
	params.system = system
	params.modulation = eDVBFrontendParametersTerrestrial.Modulation_Auto
	params.transmission_mode = eDVBFrontendParametersTerrestrial.TransmissionMode_Auto
	params.guard_interval = eDVBFrontendParametersTerrestrial.GuardInterval_Auto
	params.hierarchy = eDVBFrontendParametersTerrestrial.Hierarchy_Auto
	return params


def setParamsFe(params):
	params_fe = eDVBFrontendParameters()
	params_fe.setDVBT(params)
	return params_fe


def channel2freq(channel, bandwidth=8):  # Europe channels
	if 4 < channel < 13:  # Band III
		return (((177 + (bandwidth * (channel - 5))) * 1000000) + 500000)
	elif 20 < channel < 70:  # Bands IV,V
		return ((474 + (bandwidth * (channel - 21))) * 1000000)  # returns nine digits


def getChannelNumber(frequency):
	f = (frequency + 50000) // 100000 / 10.
	if 174 < f < 230:  # III
		d = (f + 1) % 7
		return str(int(f - 174) // 7 + 5) + (d < 3 and "-" or d > 4 and "+" or "")
	elif 470 <= f < 863:  # IV,V
		d = (f + 2) % 8
		return str(int(f - 470) // 8 + 21) + (d < 3.5 and "-" or d > 4.5 and "+" or "")
	return ""


class AutoBouquetsMaker_FrequencyFinder(Screen):
	skin = skin_downloadBar()

	def __init__(self, session, args=0):
		print("[ABM-FrequencyFinder][__init__] Starting...")
		print("[ABM-FrequencyFinder][__init__] args", args)
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("FrequencyFinder"))
		self.skinName = ["AutoBouquetsMaker"]

		self.frontend = None
		self.rawchannel = None

		self["background"] = Pixmap()
		self["action"] = Label(_("Starting scanner"))
		self["status"] = Label("")
		self["progress"] = ProgressBar()
		self["progress_text"] = Progress()
		self["Frontend"] = FrontendStatus(frontend_source=lambda: self.frontend, update_interval=100)

		self["actions"] = ActionMap(["SetupActions"],
		{
			"cancel": self.keyCancel,
		}, -2)

		self.selectedNIM = -1  # -1 is automatic selection
		self.uhf_vhf = "uhf"
		self.networkid = 0  # this is an onid, not a regional network id
		self.restrict_to_networkid = False
		if args:  # These can be added in ABM config at some time in the future
			if "feid" in args:
				self.selectedNIM = args["feid"]
			if "uhf_vhf" in args:
				self.uhf_vhf = args["uhf_vhf"]
			if "networkid" in args:
				self.networkid = args["networkid"]
			if "restrict_to_networkid" in args:
				self.restrict_to_networkid = args["restrict_to_networkid"]
		self.isT2tuner = False  # unlikely any modern internal terrestrial tuner can't play T2, but some USB tuners can't
		self.session.postScanService = None
		self.index = 0
		self.frequency = 0
		self.system = eDVBFrontendParametersTerrestrial.System_DVB_T
		self.lockTimeout = 50  # 100ms for tick - 5 sec
		self.snrTimeout = 100  # 100ms for tick - 10 sec
		# self.bandwidth = 8 # MHz
		self.scanTransponders = []
		if self.uhf_vhf == "uhf_vhf":
			bandwidth = 7
			for a in list(range(5, 13)):  # channel
				for b in (eDVBFrontendParametersTerrestrial.System_DVB_T, eDVBFrontendParametersTerrestrial.System_DVB_T2):  # system
					self.scanTransponders.append({"frequency": channel2freq(a, bandwidth), "system": b, "bandwidth": bandwidth})
		if self.uhf_vhf in ("uhf", "uhf_vhf"):
			bandwidth = 8
			for a in list(range(21, 70)):  # channel
				for b in (eDVBFrontendParametersTerrestrial.System_DVB_T, eDVBFrontendParametersTerrestrial.System_DVB_T2):  # system
					self.scanTransponders.append({"frequency": channel2freq(a, bandwidth), "system": b, "bandwidth": bandwidth})
		self.transponders_found = []
		self.transponders_unique = {}
# 		self.custom_dir = os.path.dirname(__file__) + "/../custom"
# 		self.customfile = self.custom_dir + "/CustomTranspondersOverride.xml"
# 		self.removeFileIfExists(self.customfile)
		self.providers_dir = os.path.dirname(__file__) + "/../providers"
		self.providersfile = self.providers_dir + "/terrestrial_finder.xml"
		self.network_name = None
		self.onClose.append(self.__onClose)
		self.onFirstExecBegin.append(self.firstExec)

	def showError(self, message):
		question = self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)
		question.setTitle(_("ABM frequency finder"))
		self.close()

	def showAdvice(self, message):
		question = self.session.open(MessageBox, message, MessageBox.TYPE_INFO)
		question.setTitle(_("ABM frequency finder"))
		self.close()

	def keyCancel(self):
		self.close()

	def firstExec(self):
		png = resolveFilename(SCOPE_CURRENT_SKIN, "FrequencyFinder/background.png")
		if not png or not fileExists(png):
			png = "%s/images/background.png" % os.path.dirname(sys.modules[__name__].__file__)
		self["background"].instance.setPixmapFromFile(png)

		if len(self.scanTransponders) > 0:
			self["action"].setText(_('Starting search...'))
			self["status"].setText(_("Scanning for active transponders"))
			self.progresscount = len(self.scanTransponders)
			self.progresscurrent = 1
			self["progress_text"].range = self.progresscount
			self["progress_text"].value = self.progresscurrent
			self["progress"].setRange((0, self.progresscount))
			self["progress"].setValue(self.progresscurrent)
			self.timer = eTimer()
			self.timer.callback.append(self.search)
			self.timer.start(100, 1)
		else:
			self.showError(_('No frequencies to search'))

	def search(self):
		if self.index < len(self.scanTransponders):
			self.system = self.scanTransponders[self.index]["system"]
			self.bandwidth = self.scanTransponders[self.index]["bandwidth"]
			self.frequency = self.scanTransponders[self.index]["frequency"]
			print("[ABM-FrequencyFinder][Search] Scan frequency %d (ch %s)" % (self.frequency, getChannelNumber(self.frequency)))
			print("[ABM-FrequencyFinder][Search] Scan system %d" % self.system)
			print("[ABM-FrequencyFinder][Search] Scan bandwidth %d" % self.bandwidth)
			self.progresscurrent = self.index
			self["progress_text"].value = self.progresscurrent
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_("Tuning %s MHz (ch %s)") % (str(self.frequency // 1000000), getChannelNumber(self.frequency)))
			self["status"].setText(ngettext("Found %d unique transponder", "Found %d unique transponders", len(self.transponders_unique)) % len(self.transponders_unique))
			self.index += 1
			if self.frequency in self.transponders_found or self.system == eDVBFrontendParametersTerrestrial.System_DVB_T2 and self.isT2tuner == False:
				print("[ABM-FrequencyFinder][Search] Skipping T2 search of %s MHz (ch %s)" % (str(self.frequency // 1000000), getChannelNumber(self.frequency)))
				self.search()
				return
			self.searchtimer = eTimer()
			self.searchtimer.callback.append(self.getFrontend)
			self.searchtimer.start(100, 1)
		else:
			if len({k: v for k, v in list(self.transponders_unique.items()) if v["system"] == eDVBFrontendParametersTerrestrial.System_DVB_T}) > 0:  # check DVB-T transponders exist
				if self.frontend:
					self.frontend = None
					del (self.rawchannel)
				self["action"].setText(_("Saving data"))
				if self.session.postScanService:
					self.session.nav.playService(self.session.postScanService)
					self.session.postScanService = None
# 				self.saveTransponderList()
# 				message = "Transponder frequencies updated.\nDo you want to continue with a scan for services."
# 				question = self.session.openWithCallback(self.scanMessageCallback, MessageBox, message, type=MessageBox.TYPE_YESNO, default=True)
# 				question.setTitle(_("ABM frequency finder"))
				self.saveProviderFile()
				message = 'New provider created called "%s terrestrial".\n Disable the existing ABM terrestrial provider and perform an ABM scan with the new one.' % self.strongestTransponder["network_name"]
				self.showAdvice(message)
			elif len(self.transponders_unique) > 0:
				print("[ABM-FrequencyFinder][Search] Only DVB-T2 multiplexes found. Insufficient data to create a provider file.")
				self.showError(_('Only DVB-T2 multiplexes found. Insufficient data to create a provider file.'))
			else:
				print("[ABM-FrequencyFinder][Search] No terrestrial multiplexes found.")
				self.showError(_('No terrestrial multiplexes found.'))

	def config_mode(self, nim):  # Workaround for OpenATV > 5.3
		try:
			return nim.config_mode
		except AttributeError:
			return nim.isCompatible("DVB-T") and nim.config_mode_dvbt or "nothing"

	def getFrontend(self):
		print("[ABM-FrequencyFinder][getFrontend] searching for available tuner")
		nimList = []
		if self.selectedNIM < 0:  # automatic tuner selection
			for nim in nimmanager.nim_slots:
				if self.config_mode(nim) not in ("nothing",) and (nim.isCompatible("DVB-T2") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-T2"))):
					nimList.append(nim.slot)
					self.isT2tuner = True
			if len(nimList) == 0:
				print("[ABM-FrequencyFinder][getFrontend] No T2 tuner found")
				for nim in nimmanager.nim_slots:
					if self.config_mode(nim) not in ("nothing",) and (nim.isCompatible("DVB-T") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-T"))):
						nimList.append(nim.slot)
			if len(nimList) == 0:
				print("[ABM-FrequencyFinder][getFrontend] No terrestrial tuner found.")
				self.showError(_('No terrestrial tuner found.'))
				return
		else:  # manual tuner selection, and subsequent iterations
			nim = nimmanager.nim_slots[self.selectedNIM]
			if self.config_mode(nim) not in ("nothing",) and (nim.isCompatible("DVB-T2") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-T2"))):
				nimList.append(nim.slot)
				self.isT2tuner = True
			if len(nimList) == 0:
				print("[ABM-FrequencyFinder][getFrontend] User selected tuner is not T2 compatible")
				if self.config_mode(nim) not in ("nothing",) and (nim.isCompatible("DVB-T") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-T"))):
					nimList.append(nim.slot)
			if len(nimList) == 0:
				print("[ABM-FrequencyFinder][getFrontend] User selected tuner not configured")
				self.showError(_('Selected tuner is not configured.'))
				return

		if len(nimList) == 0:
			print("[ABM-FrequencyFinder][getFrontend] No terrestrial tuner found.")
			self.showError(_('No terrestrial tuner found.'))
			return

		resmanager = eDVBResourceManager.getInstance()
		if not resmanager:
			print("[ABM-FrequencyFinder][getFrontend] Cannot retrieve Resource Manager instance")
			self.showError(_('Cannot retrieve Resource Manager instance'))
			return

		if self.selectedNIM < 0:  # automatic tuner selection
			print("[ABM-FrequencyFinder][getFrontend] Choosing NIM")

		# stop pip if running
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
			print("[ABM-FrequencyFinder][getFrontend] Stopping PIP.")

		# Find currently playing NIM
		currentlyPlayingNIM = None
		currentService = self.session and self.session.nav.getCurrentService()
		frontendInfo = currentService and currentService.frontendInfo()
		frontendData = frontendInfo and frontendInfo.getAll(True)
		if frontendData is not None:
			currentlyPlayingNIM = frontendData.get("tuner_number", None)
		del frontendInfo
		del currentService

		current_slotid = -1
		if self.rawchannel:
			del (self.rawchannel)

		self.frontend = None
		self.rawchannel = None

		nimList.reverse()  # start from the last
		for slotid in nimList:
			if current_slotid == -1:  # mark the first valid slotid in case of no other one is free
				current_slotid = slotid
			self.rawchannel = resmanager.allocateRawChannel(slotid)
			if self.rawchannel:
				print("[ABM-FrequencyFinder][getFrontend] Nim found on slot id %d" % (slotid))
				current_slotid = slotid
				break

		if current_slotid == -1:
			print("[ABM-FrequencyFinder][getFrontend] No valid NIM found")
			self.showError(_('No valid NIM found for terrestrial.'))
			return

		if not self.rawchannel:
			# if we are here the only possible option is to close the active service
			if currentlyPlayingNIM in nimList:
				slotid = currentlyPlayingNIM
				print("[ABM-FrequencyFinder][getFrontend] Nim found on slot id %d but it's busy. Stopping active service" % slotid)
				self.session.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
				self.session.nav.stopService()
				self.rawchannel = resmanager.allocateRawChannel(slotid)
				if self.rawchannel:
					print("[ABM-FrequencyFinder][getFrontend] The active service was stopped, and the NIM is now free to use.")
					current_slotid = slotid

			if not self.rawchannel:
				if self.session.nav.RecordTimer.isRecording():
					print("[ABM-FrequencyFinder][getFrontend] Cannot free NIM because a recording is in progress")
					self.showError(_('Cannot free NIM because a recording is in progress'))
					return
				else:
					print("[ABM-FrequencyFinder][getFrontend] Cannot get the NIM")
					self.showError(_('Cannot get the NIM'))
					return

		print("[ABM-FrequencyFinder][getFrontend] Will wait up to %i seconds for tuner lock." % (self.lockTimeout // 10))

		self.selectedNIM = current_slotid  # Remember for next iteration

		self.frontend = self.rawchannel.getFrontend()
		if not self.frontend:
			print("[ABM-FrequencyFinder][getFrontend] Cannot get frontend")
			self.showError(_('Cannot get frontend'))
			return

		self.rawchannel.requestTsidOnid()

		self.tsid = None
		self.onid = None

		self.demuxer_id = self.rawchannel.reserveDemux()
		if self.demuxer_id < 0:
			print("[ABM-FrequencyFinder][getFrontend] Cannot allocate the demuxer.")
			self.showError(_('Cannot allocate the demuxer.'))
			return

		self.frontend.tune(setParamsFe(setParams(self.frequency, self.system, self.bandwidth)))

		self.lockcounter = 0
		self.locktimer = eTimer()
		self.locktimer.callback.append(self.checkTunerLock)
		self.locktimer.start(100, 1)

	def checkTunerLock(self):
		self.dict = {}
		self.frontend.getFrontendStatus(self.dict)
		if self.dict["tuner_state"] == "TUNING":
			if self.lockcounter < 1:  # only show this once in the log per retune event
				print("[ABM-FrequencyFinder][checkTunerLock] TUNING")
		elif self.dict["tuner_state"] == "LOCKED":
			print("[ABM-FrequencyFinder][checkTunerLock] LOCKED")
			self["action"].setText(_("Reading %s MHz (ch %s)") % (str(self.frequency // 1000000), getChannelNumber(self.frequency)))
			self.tsidOnidtimer = eTimer()
			self.tsidOnidtimer.callback.append(self.tsidOnidWait)
			self.tsidOnidtimer.start(100, 1)
			return
		elif self.dict["tuner_state"] in ("LOSTLOCK", "FAILED"):
			print("[ABM-FrequencyFinder][checkTunerLock] TUNING FAILED")
			self.search()
			return

		self.lockcounter += 1
		if self.lockcounter > self.lockTimeout:
			print("[ABM-FrequencyFinder][checkTunerLock] Timeout for tuner lock")
			self.search()
			return
		self.locktimer.start(100, 1)

	def tsidOnidWait(self):
		self.getCurrentTsidOnid()
		if self.tsid is not None and self.onid is not None:
			print("[ABM-FrequencyFinder][tsidOnidWait] tsid & onid found", self.tsid, self.onid)
			self.signalQualityWait()
			return

		print("[ABM-FrequencyFinder][tsidOnidWait] tsid & onid wait failed")
		self.search()
		return

	def signalQualityWait(self):
		self.readNIT()  # by the time this is completed SNR should be stable
		signalQuality = self.frontend.readFrontendData(iFrontendInformation.signalQuality)
		if signalQuality > 0:
			found = {"frequency": self.frequency, "tsid": self.tsid, "onid": self.onid, "system": self.system, "bandwidth": self.bandwidth, "signalQuality": signalQuality, "network_name": self.network_name, "custom_transponder_needed": self.custom_transponder_needed}
			self.transponders_found.append(self.frequency)
			tsidOnidKey = "%x:%x" % (self.tsid, self.onid)
			if (tsidOnidKey not in self.transponders_unique or self.transponders_unique[tsidOnidKey]["signalQuality"] < signalQuality) and (not self.restrict_to_networkid or self.networkid == self.onid):
				self.transponders_unique[tsidOnidKey] = found
			print("[ABM-FrequencyFinder][signalQualityWait] transponder details", found)
			self.search()
			return

		print("[ABM-FrequencyFinder][signalQualityWait] Failed to collect SNR")
		self.search()

	def getCurrentTsidOnid(self, from_retune=False):
		adapter = 0
		demuxer_device = "/dev/dvb/adapter%d/demux%d" % (adapter, self.demuxer_id)
		start = time.time()  # for debug info

		sdt_pid = 0x11
		sdt_current_table_id = 0x42
		mask = 0xff
		tsidOnidTimeout = 5  # maximum time allowed to read the service descriptor table (seconds)
		self.tsid = None
		self.onid = None

		fd = dvbreader.open(demuxer_device, sdt_pid, sdt_current_table_id, mask, self.selectedNIM)
		if fd < 0:
			print("[ABM-FrequencyFinder][getCurrentTsidOnid] Cannot open the demuxer")
			return None

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, tsidOnidTimeout)

		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-FrequencyFinder][getCurrentTsidOnid] Timed out")
				break

			section = dvbreader.read_sdt(fd, sdt_current_table_id, 0x00)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if section["header"]["table_id"] == sdt_current_table_id:
				self.tsid = section["header"]["transport_stream_id"]
				self.onid = section["header"]["original_network_id"]
				break

		print("[ABM-FrequencyFinder][getCurrentTsidOnid] Read time %.1f seconds." % (time.time() - start))
		dvbreader.close(fd)

	def readNIT(self):
		adapter = 0
		demuxer_device = "/dev/dvb/adapter%d/demux%d" % (adapter, self.demuxer_id)
		start = time.time()  # for debug info

		nit_current_pid = 0x10
		nit_current_table_id = 0x40
		nit_other_table_id = 0x00  # don't read other table

		self.network_name = None
		self.custom_transponder_needed = True

		if nit_other_table_id == 0x00:
			mask = 0xff
		else:
			mask = nit_current_table_id ^ nit_other_table_id ^ 0xff
		nit_current_timeout = 20  # maximum time allowed to read the network information table (seconds)

		nit_current_version_number = -1
		nit_current_sections_read = []
		nit_current_sections_count = 0
		nit_current_content = []
		nit_current_completed = False

		fd = dvbreader.open(demuxer_device, nit_current_pid, nit_current_table_id, mask, self.selectedNIM)
		if fd < 0:
			print("[ABM-FrequencyFinder][readNIT] Cannot open the demuxer")
			return

		timeout = datetime.datetime.now()
		timeout += datetime.timedelta(0, nit_current_timeout)

		while True:
			if datetime.datetime.now() > timeout:
				print("[ABM-FrequencyFinder][readNIT] Timed out reading NIT")
				break

			section = dvbreader.read_nit(fd, nit_current_table_id, nit_other_table_id)
			if section is None:
				time.sleep(0.1)  # no data.. so we wait a bit
				continue

			if section["header"]["table_id"] == nit_current_table_id and not nit_current_completed:
				if section["header"]["version_number"] != nit_current_version_number:
					nit_current_version_number = section["header"]["version_number"]
					nit_current_sections_read = []
					nit_current_sections_count = section["header"]["last_section_number"] + 1
					nit_current_content = []

				if section["header"]["section_number"] not in nit_current_sections_read:
					nit_current_sections_read.append(section["header"]["section_number"])
					nit_current_content += section["content"]

					if 'network_name' in section["header"] and section["header"]["network_name"] != "Unknown":
						self.network_name = section["header"]["network_name"]

					if len(nit_current_sections_read) == nit_current_sections_count:
						nit_current_completed = True

			if nit_current_completed:
				break

		dvbreader.close(fd)

		if not nit_current_content:
			print("[ABM-FrequencyFinder][readNIT] current transponder not found")
			return

		print("[ABM-FrequencyFinder][readNIT] NIT read time %.1f seconds." % (time.time() - start))

		# descriptor_tag 0x5A is DVB-T, descriptor_tag 0x7f is DVB-T
		transponders = [t for t in nit_current_content if "descriptor_tag" in t and t["descriptor_tag"] in (0x5A, 0x7f) and t["original_network_id"] == self.onid and t["transport_stream_id"] == self.tsid]  # this should only ever have a length of one transponder
		print("[ABM-FrequencyFinder][readNIT] transponders", transponders)
		if transponders:

			if transponders[0]["descriptor_tag"] == 0x5A:  # DVB-T
				self.system = eDVBFrontendParametersTerrestrial.System_DVB_T
			else:  # must be DVB-T2
				self.system = eDVBFrontendParametersTerrestrial.System_DVB_T2

			if "frequency" in transponders[0] and abs((transponders[0]["frequency"] * 10) - self.frequency) < 1000000:
				self.custom_transponder_needed = False
				if self.frequency != transponders[0]["frequency"] * 10:
					print("[ABM-FrequencyFinder][readNIT] updating transponder frequency from %.03f MHz to %.03f MHz" % (self.frequency // 1000000, transponders[0]["frequency"] // 100000))
					self.frequency = transponders[0]["frequency"] * 10

# 	def saveTransponderList(self):
# 		# make custom transponders file content
# 		customTransponderList = []
# 		customTransponderList.append('<provider>\n')
# 		customTransponderList.append('\t<customtransponders>\n')
# 		for tsidOnidKey in self.iterateUniqueTranspondersByFrequency():
# 			transponder = self.transponders_unique[tsidOnidKey]
# 			customTransponderList.append('\t\t<customtransponder key="_OVERRIDE_" frequency="%d" transport_stream_id="%04x" system="%d"/><!-- original_network_id="%04x" signalQuality="%05d" -->\n' % (transponder["frequency"], transponder["tsid"], transponder["system"], transponder["onid"], transponder["signalQuality"]))
# 		customTransponderList.append('\t</customtransponders>\n')
# 		customTransponderList.append('</provider>\n')

# 		# save to ABM custom folder
# 		outFile = open(self.customfile, "w")
# 		outFile.write(''.join(customTransponderList))
# 		outFile.close()
# 		print("[ABM-FrequencyFinder][saveTransponderList] Custom transponders file saved."

	def saveProviderFile(self):
		customProviderList = []
		self.strongestTransponder = self.transponders_unique[self.iterateUniqueTranspondersBySignalQuality()[-1]]
		for tsidOnidKey in self.iterateUniqueTranspondersBySignalQuality()[::-1]:  # iterate in reverse order and select the first system 0 transponder
			transponder = self.transponders_unique[tsidOnidKey]
			if transponder["system"] == 0:
				self.strongestTransponder = transponder
				break
		network_name = re.sub(r'&(?![A-Za-z]+[0-9]*;|#[0-9]+;|#x[0-9a-fA-F]+;)', r'&amp;', self.strongestTransponder["network_name"])  # regex to avoid unencoded ampersands that are not entities
		customProviderList.append('<provider>\n')
		customProviderList.append('\t<name>%s terrestrial</name>\n' % network_name)
		customProviderList.append('\t<streamtype>dvbt</streamtype>\n')
		customProviderList.append('\t<protocol>lcn</protocol>\n')
		customProviderList.append('\t<dvbtconfigs>\n')
		customProviderList.append('\t\t<configuration key="custom" frequency="%d" system="%d">%s terrestrial</configuration>\n' % (self.strongestTransponder["frequency"], self.strongestTransponder["system"], network_name))
		customProviderList.append('\t</dvbtconfigs>\n\n')
		customProviderList.append('\t<customtransponders>\n')
		for tsidOnidKey in self.iterateUniqueTranspondersByFrequency():
			transponder = self.transponders_unique[tsidOnidKey]
			if transponder["custom_transponder_needed"]:
				customProviderList.append('\t\t<customtransponder key="custom" frequency="%d" transport_stream_id="%04x" system="%d"/><!-- original_network_id="%04x" signalQuality="%05d" channel="%s" -->\n' % (transponder["frequency"], transponder["tsid"], transponder["system"], transponder["onid"], transponder["signalQuality"], getChannelNumber(transponder["frequency"])))
			else:
				customProviderList.append('\t\t<!-- customtransponder key="custom" frequency="%d" transport_stream_id="%04x" system="%d"/ --><!-- original_network_id="%04x" signalQuality="%05d" channel="%s" -->\n' % (transponder["frequency"], transponder["tsid"], transponder["system"], transponder["onid"], transponder["signalQuality"], getChannelNumber(transponder["frequency"])))
		customProviderList.append('\t</customtransponders>\n\n')
		customProviderList.append('\t<sections>\n')
		customProviderList.append('\t\t<section number="1">Entertainment</section>\n')
		customProviderList.append('\t\t<section number="100">High Definition</section>\n')
		customProviderList.append('\t\t<section number="201">Children</section>\n')
		customProviderList.append('\t\t<section number="230">News</section>\n')
		customProviderList.append('\t\t<section number="260">BBC Interactive</section>\n')
		customProviderList.append('\t\t<section number="670">Adult</section>\n')
		customProviderList.append('\t\t<section number="700">Radio</section>\n')
		customProviderList.append('\t</sections>\n\n')
		customProviderList.append('\t<swapchannels>\n')
		customProviderList.append('\t\t<channel number="1" with="101"/>	<!-- BBC One HD -->\n')
		customProviderList.append('\t\t<channel number="2" with="102"/>	<!-- BBC TWO HD -->\n')
		customProviderList.append('\t\t<channel number="3" with="103"/>	<!-- ITV HD -->\n')
		customProviderList.append('\t\t<channel number="4" with="104"/>	<!-- Channel 4 HD -->\n')
		customProviderList.append('\t\t<channel number="5" with="105"/>	<!-- Channel 5 HD -->\n')
		customProviderList.append('\t\t<channel number="9" with="106"/>	<!-- BBC FOUR HD -->\n')
		customProviderList.append('\t\t<channel number="201" with="204"/>	<!-- CBBC HD -->\n')
		customProviderList.append('\t\t<channel number="202" with="205"/>	<!-- CBeebies HD -->\n')
		customProviderList.append('\t\t<channel number="231" with="107"/>	<!-- BBC NEWS HD -->\n')
		customProviderList.append('\t</swapchannels>\n\n')
		customProviderList.append('\t<servicehacks>\n')
		customProviderList.append('\t<![CDATA[\n\n')
		customProviderList.append('tsidonidlist= [\n')
		for tsidOnidKey in self.iterateUniqueTranspondersByFrequency():
			customProviderList.append('\t"%s",\n' % tsidOnidKey)
		customProviderList.append(']\n\n')
		customProviderList.append('tsidonidkey = "%x:%x" % (service["transport_stream_id"], service["original_network_id"])\n')
		customProviderList.append('if tsidonidkey not in tsidonidlist:\n')
		customProviderList.append('\tskip.skip = True\n\n')
		customProviderList.append('servicehack_variable_cache["add_audio_channels_to_video_bouquet"] = True\n\n')
		customProviderList.append('\t]]>\n')
		customProviderList.append('\t</servicehacks>\n')
		customProviderList.append('</provider>\n')

		# save to ABM providers folder
		outFile = open(self.providersfile, "w")
		outFile.write(''.join(customProviderList))
		outFile.close()
		print("[ABM-FrequencyFinder][saveProviderFile] Provider file saved.")

	def iterateUniqueTranspondersByFrequency(self):
		# returns an iterator list for self.transponders_unique in frequency order ascending
		sort_list = [(x[0], x[1]["frequency"]) for x in list(self.transponders_unique.items())]
		return [x[0] for x in sorted(sort_list, key=lambda listItem: listItem[1])]

	def iterateUniqueTranspondersBySignalQuality(self):
		# returns an iterator list for self.transponders_unique in SignalQuality order ascending
		sort_list = [(x[0], x[1]["signalQuality"]) for x in list(self.transponders_unique.items())]
		return [x[0] for x in sorted(sort_list, key=lambda listItem: listItem[1])]

# 	def scanMessageCallback(self, answer):
# 		if answer:
# 			self.session.open(AutoBouquetsMaker)
# 		self.close()

# 	def removeFileIfExists(self, filename):
# 		try:
# 			os.remove(filename)
# 		except OSError as e:
# 			if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
# 				raise # re-raise exception if a different error occurred

	def __onClose(self):
		if self.frontend:
			self.frontend = None
			del (self.rawchannel)

		if self.session.postScanService:
			self.session.nav.playService(self.session.postScanService)
			self.session.postScanService = None
