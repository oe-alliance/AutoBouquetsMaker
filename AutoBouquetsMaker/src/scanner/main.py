from __future__ import print_function
from __future__ import absolute_import

# for localized messages
from .. import _

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Components.Sources.Progress import Progress
from Components.Sources.FrontendStatus import FrontendStatus

from Components.config import config, configfile
from Components.NimManager import nimmanager
from enigma import eTimer, eDVBDB, eDVBFrontendParametersSatellite, eDVBFrontendParametersTerrestrial, eDVBFrontendParametersCable, eDVBResourceManager, eDVBFrontendParameters

from .manager import Manager
from .providerconfig import ProviderConfig
from .providers import Providers
from Plugins.SystemPlugins.AutoBouquetsMaker.skin_templates import skin_downloadBar
from time import localtime, time, strftime, mktime

from .. import log
import os
import sys

from Tools.Directories import resolveFilename, fileExists, SCOPE_CURRENT_SKIN


class AutoBouquetsMaker(Screen):
	skin = skin_downloadBar()

	LOCK_TIMEOUT_FIXED = 100  # 100ms for tick - 10 sec
	LOCK_TIMEOUT_ROTOR = 1200  # 100ms for tick - 120 sec
	ABM_BOUQUET_PREFIX = "userbouquet.abm."

	def __init__(self, session, args=0):
		self.printconfig()
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("AutoBouquetsMaker"))

		self.frontend = None
		self.rawchannel = None
		self.postScanService = None
		self.providers = Manager().getProviders()

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
		{
			"cancel": self.keyCancel,
			"red": self.keyCancel,
		}, -2)

		# self["background"] = Pixmap()
		self["action"] = Label(_("Starting scanner"))
		self["status"] = Label("")
		self["progress"] = ProgressBar()
		self["progress_text"] = Progress()
		self["tuner_text"] = Label("")
		self["Frontend"] = FrontendStatus(frontend_source=lambda: self.frontend, update_interval=100)

		# dependent providers
		self.dependents = {}
		for provider_key in self.providers:
			if len(self.providers[provider_key]["dependent"]) > 0 and self.providers[provider_key]["dependent"] in self.providers:
				if self.providers[provider_key]["dependent"] not in self.dependents:
					self.dependents[self.providers[provider_key]["dependent"]] = []
				self.dependents[self.providers[provider_key]["dependent"]].append(provider_key)

		# get ABM config string including dependents
		self.abm_settings_str = self.getABMsettings()

		self.actionsList = []

		self.onFirstExecBegin.append(self.firstExec)

	def firstExec(self, postScanService=None):
		from Screens.Standby import inStandby
# 		if not inStandby:
# 			png = resolveFilename(SCOPE_CURRENT_SKIN, "autobouquetsmaker/background.png")
# 			if not png or not fileExists(png):
# 				png = "%s/../images/background.png" % os.path.dirname(sys.modules[__name__].__file__)
# 			self["background"].instance.setPixmapFromFile(png)

		if len(self.abm_settings_str) > 0:
			if not inStandby:
				self["action"].setText(_('Loading bouquets...'))
				self["status"].setText(_("Services: 0 video - 0 radio"))
			self.timer = eTimer()
			self.timer.callback.append(self.go)
			self.timer.start(100, 1)
		else:
			self.showError(_('Please first setup, in configuration'))

	def showError(self, message):
		from Screens.Standby import inStandby
		self.releaseFrontend()
		self.restartService()
		if not inStandby:
			question = self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)
			question.setTitle(_("AutoBouquetsMaker"))
		self.close()

	def keyCancel(self):
		self.releaseFrontend()
		self.restartService()
		self.close()

	def go(self):
		from Screens.Standby import inStandby
		self.manager = Manager()
		self.manager.setPath("/etc/enigma2")
		self.manager.setAddPrefix(config.autobouquetsmaker.addprefix.value)

		self.selectedProviders = {}
		self.actionsList = []

		providers_tmp = self.abm_settings_str.split("|")

		for provider_tmp in providers_tmp:
			provider_config = ProviderConfig(provider_tmp)
			if provider_config.isValid() and Providers().providerFileExists(provider_config.getProvider()):
				self.actionsList.append(provider_config.getProvider())
				self.selectedProviders[provider_config.getProvider()] = provider_config

		if config.autobouquetsmaker.keepallbouquets.getValue():
			bouquets = Manager().getBouquetsList()
			bouquets_tv = []
			bouquets_radio = []
			for bouquet in bouquets["tv"]:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if len(bouquet["filename"]) > 0:
					bouquets_tv.append(bouquet["filename"])
			for bouquet in bouquets["radio"]:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if len(bouquet["filename"]) > 0:
					bouquets_radio.append(bouquet["filename"])
			self.manager.setBouquetsToKeep(bouquets_tv, bouquets_radio)
		else:
			bouquets = config.autobouquetsmaker.keepbouquets.value.split("|")
			bouquets_tv = []
			bouquets_radio = []
			for bouquet in bouquets:
				if bouquet.endswith(".tv"):
					bouquets_tv.append(bouquet)
				elif bouquet.endswith(".radio"):
					bouquets_radio.append(bouquet)
			self.manager.setBouquetsToKeep(bouquets_tv, bouquets_radio)

		bouquetsToHide = {}
		bouquets = config.autobouquetsmaker.hidesections.value.split("|")
		for bouquet in bouquets:
			tmp = bouquet.split(":")
			if len(tmp) != 2:
				continue

			if tmp[0].strip() not in bouquetsToHide:
				bouquetsToHide[tmp[0].strip()] = []

			bouquetsToHide[tmp[0].strip()].append(int(tmp[1].strip()))
		self.manager.setBouquetsToHide(bouquetsToHide)

		self.manager.load()

		self.progresscount = (len(self.actionsList) * 2) + 3
		self.progresscurrent = 1

		if not inStandby:
			self["progress_text"].range = self.progresscount
			self["progress_text"].value = self.progresscurrent
			self["progress"].setRange((0, self.progresscount))
			self["progress"].setValue(self.progresscurrent)

		self.timer = eTimer()
		self.timer.callback.append(self.doActions)
		self.timer.start(100, 1)

	def doActions(self):
		from Screens.Standby import inStandby
		if len(self.actionsList) == 0:
			self.progresscurrent += 1
			self["actions"].setEnabled(False)  # disable action map here so we can't abort half way through writing result to settings files
			if not inStandby:
				self["progress_text"].value = self.progresscurrent
				self["progress"].setValue(self.progresscurrent)
				self["action"].setText(_('Bouquets generation...'))
				self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))
				self["tuner_text"].setText("")
			self.timer = eTimer()
			self.timer.callback.append(self.doBuildIndex)
			self.timer.start(100, 1)
			return

		self.currentAction = self.actionsList[0]
		del (self.actionsList[0])

		self.progresscurrent += 1
		if not inStandby:
			self["progress_text"].value = self.progresscurrent
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_("Tuning %s...") % str(self.providers[self.currentAction]["name"]))
			self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))
			self["tuner_text"].setText("")
		self.timer = eTimer()
		self.timer.callback.append(self.doTune)
		self.timer.start(100, 1)

	def doTune(self):
		print("[ABM-main][doTune] searching for tuner for %s" % self.providers[self.currentAction]["name"], file=log)
		from Screens.Standby import inStandby
		if self.providers[self.currentAction]["streamtype"] == "dvbs":
			transponder = self.providers[self.currentAction]["transponder"]
		else:
			bouquet_key = None
			providers_tmp = self.abm_settings_str.split("|")
			for provider_tmp in providers_tmp:
				provider_config = ProviderConfig(provider_tmp)
				provider_key = provider_config.getProvider()
				if self.currentAction != provider_key:
					continue
				bouquet_key = provider_config.getArea()

			if not bouquet_key:
				print("[ABM-main][doTune] No area found", file=log)
				self.showError(_('No area found'))
				return

			transponder = self.providers[self.currentAction]["bouquets"][bouquet_key]

		self.transponder = transponder

		nimList = []
		tunerSelectionAlgorithm = "UNKNOWN"  # for debug
		for nim in nimmanager.nim_slots:
			if self.providers[self.currentAction]["streamtype"] == "dvbs" and nim.isCompatible("DVB-S"):
				try:
					if nim.isFBCLink():
						continue  # do not load FBC links, only root tuners
				except:
					pass
			try:  # OpenPLi Hot Switch compatible image
				if (nim.config_mode not in ("loopthrough", "satposdepends", "nothing")) and \
					{"dvbs": "DVB-S", "dvbc": "DVB-C", "dvbt": "DVB-T"}.get(self.providers[self.currentAction]["streamtype"], "UNKNOWN") in [x[:5] for x in nim.getTunerTypesEnabled()]:
					if self.validNIM(nim.slot):
						nimList.append(nim.slot)
					tunerSelectionAlgorithm = "OpenPLi Hot Switch compatible"
			except AttributeError:
				try:
					if (nim.config_mode not in ("loopthrough", "satposdepends", "nothing")) and \
						((self.providers[self.currentAction]["streamtype"] == "dvbs" and nim.isCompatible("DVB-S")) or
						(self.providers[self.currentAction]["streamtype"] == "dvbc" and (nim.isCompatible("DVB-C") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-C")))) or
						(self.providers[self.currentAction]["streamtype"] == "dvbt" and (nim.isCompatible("DVB-T") or (nim.isCompatible("DVB-S") and nim.canBeCompatible("DVB-T"))))):
						if self.validNIM(nim.slot):
							nimList.append(nim.slot)
						tunerSelectionAlgorithm = "Conventional"
				except AttributeError:  # OpenATV > 5.3
					if (self.providers[self.currentAction]["streamtype"] == "dvbs" and nim.canBeCompatible("DVB-S") and nim.config_mode_dvbs not in ("loopthrough", "satposdepends", "nothing")) or \
						(self.providers[self.currentAction]["streamtype"] == "dvbc" and nim.canBeCompatible("DVB-C") and nim.config_mode_dvbc != "nothing") or \
						(self.providers[self.currentAction]["streamtype"] == "dvbt" and nim.canBeCompatible("DVB-T") and nim.config_mode_dvbt != "nothing"):
						if self.validNIM(nim.slot):
							nimList.append(nim.slot)
						tunerSelectionAlgorithm = "OpenATV > 5.3"

		print("[ABM-main][doTune] tuner selection algorithm '%s'" % tunerSelectionAlgorithm, file=log)

		if len(nimList) == 0:
			print("[ABM-main][doTune] No NIMs found", file=log)
			self.showError(_('No NIMs found for ') + self.providers[self.currentAction]["name"])
			return

		resmanager = eDVBResourceManager.getInstance()
		if not resmanager:
			print("[ABM-main][doTune] Cannot retrieve Resource Manager instance", file=log)
			self.showError(_('Cannot retrieve Resource Manager instance'))
			return

		if self.providers[self.currentAction]["streamtype"] == "dvbs":  # If we have a choice of dishes sort the nimList so "fixed" dishes have a higher priority than "motorised".
			nimList = [slot for slot in nimList if not self.isRotorSat(slot, transponder["orbital_position"])] + [slot for slot in nimList if self.isRotorSat(slot, transponder["orbital_position"])]

		# stop pip if running
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
			print("[ABM-main][doTune] Stopping PIP.", file=log)

		# find currently playing nim
		currentlyPlayingNIM = None
		currentService = self.session and self.session.nav.getCurrentService()
		frontendInfo = currentService and currentService.frontendInfo()
		frontendData = frontendInfo and frontendInfo.getAll(True)
		if frontendData is not None:
			currentlyPlayingNIM = frontendData.get("tuner_number", None)
			# stop currently playing service if it is using a tuner in ("loopthrough", "satposdepends"), as running in this configuration will prevent getting rawchannel on the root tuner.
			if self.providers[self.currentAction]["streamtype"] == "dvbs" and currentlyPlayingNIM is not None and nimmanager.nim_slots[currentlyPlayingNIM].isCompatible("DVB-S"):
				try:
					nimConfigMode = nimmanager.nim_slots[currentlyPlayingNIM].config_mode
				except AttributeError:  # OpenATV > 5.3
					nimConfigMode = nimmanager.nim_slots[currentlyPlayingNIM].config_mode_dvbs
				if nimConfigMode in ("loopthrough", "satposdepends"):
					self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
					self.session.nav.stopService()
					currentlyPlayingNIM = None
					print("[ABM-main][doTune] The active service was using a %s tuner, so had to be stopped (slot id %s)." % (nimConfigMode, currentlyPlayingNIM), file=log)
		del frontendInfo
		del currentService

		self.releaseFrontend()

		for current_slotid in nimList:
			self.rawchannel = resmanager.allocateRawChannel(current_slotid)
			if self.rawchannel:
				print("[ABM-main][doTune] Tuner %s selected%s" % (chr(ord('A') + current_slotid), (" for orbital position %d" % transponder["orbital_position"] if "orbital_position" in transponder else "")), file=log)
				break

		if not self.rawchannel:
			# if we are here the only possible option is to close the active service
			if currentlyPlayingNIM in nimList:
				print("[ABM-main][doTune] Tuner %s has been selected but it's busy. Stopping currently playing service." % chr(ord('A') + currentlyPlayingNIM), file=log)
				self.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()
				self.session.nav.stopService()
				self.rawchannel = resmanager.allocateRawChannel(currentlyPlayingNIM)
				if self.rawchannel:
					print("[ABM-main][doTune] The active service was stopped, and tuner %s is now free to use." % chr(ord('A') + currentlyPlayingNIM), file=log)
					current_slotid = currentlyPlayingNIM

			if not self.rawchannel:
				if self.session.nav.RecordTimer.isRecording():
					print("[ABM-main][doTune] Cannot free NIM because a recording is in progress", file=log)
					self.showError(_('Cannot free NIM because a recording is in progress'))
					return
				else:
					print("[ABM-main][doTune] Cannot get the NIM", file=log)
					self.showError(_('Cannot get the NIM'))
					return

		# set extended timeout for rotors
		self.motorised = False
		if self.providers[self.currentAction]["streamtype"] == "dvbs" and self.isRotorSat(current_slotid, transponder["orbital_position"]):
			self.motorised = True
			self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_ROTOR
			print("[ABM-main][doTune] Motorised dish. Will wait up to %i seconds for tuner lock." % (self.LOCK_TIMEOUT // 10), file=log)
		else:
			self.LOCK_TIMEOUT = self.LOCK_TIMEOUT_FIXED
			print("[ABM-main][doTune] Fixed dish. Will wait up to %i seconds for tuner lock." % (self.LOCK_TIMEOUT // 10), file=log)

		if not inStandby:
			self["tuner_text"].setText(chr(ord('A') + current_slotid))

		self.frontend = self.rawchannel.getFrontend()
		if not self.frontend:
			print("[ABM-main][doTune] Cannot get frontend", file=log)
			self.showError(_('Cannot get frontend'))
			return

		demuxer_id = self.rawchannel.reserveDemux()
		if demuxer_id < 0:
			print("[ABM-main][doTune] Cannot allocate the demuxer.", file=log)
			self.showError(_('Cannot allocate the demuxer.'))
			return

		if self.providers[self.currentAction]["streamtype"] == "dvbs":
			params = eDVBFrontendParametersSatellite()
			params.frequency = transponder["frequency"]
			params.symbol_rate = transponder["symbol_rate"]
			params.polarisation = transponder["polarization"]
			params.fec = transponder["fec_inner"]
			params.inversion = transponder["inversion"]
			params.orbital_position = transponder["orbital_position"]
			params.system = transponder["system"]
			params.modulation = transponder["modulation"]
			params.rolloff = transponder["roll_off"]
			params.pilot = transponder["pilot"]
			if hasattr(eDVBFrontendParametersSatellite, "No_Stream_Id_Filter"):
				params.is_id = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
			if hasattr(eDVBFrontendParametersSatellite, "PLS_Gold"):
				params.pls_mode = eDVBFrontendParametersSatellite.PLS_Gold
			if hasattr(eDVBFrontendParametersSatellite, "PLS_Default_Gold_Code"):
				params.pls_code = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
			if hasattr(eDVBFrontendParametersSatellite, "No_T2MI_PLP_Id"):
				params.t2mi_plp_id = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
			if hasattr(eDVBFrontendParametersSatellite, "T2MI_Default_Pid"):
				params.t2mi_pid = eDVBFrontendParametersSatellite.T2MI_Default_Pid
			params_fe = eDVBFrontendParameters()
			params_fe.setDVBS(params, False)

		elif self.providers[self.currentAction]["streamtype"] == "dvbt":
			params = eDVBFrontendParametersTerrestrial()
			params.frequency = transponder["frequency"]
			params.bandwidth = transponder["bandwidth"]
			params.code_rate_hp = transponder["code_rate_hp"]
			params.code_rate_lp = transponder["code_rate_lp"]
			params.inversion = transponder["inversion"]
			params.system = transponder["system"]
			params.modulation = transponder["modulation"]
			params.transmission_mode = transponder["transmission_mode"]
			params.guard_interval = transponder["guard_interval"]
			params.hierarchy = transponder["hierarchy"]
			params_fe = eDVBFrontendParameters()
			params_fe.setDVBT(params)

		elif self.providers[self.currentAction]["streamtype"] == "dvbc":
			params = eDVBFrontendParametersCable()
			params.frequency = transponder["frequency"]
			params.symbol_rate = transponder["symbol_rate"]
			params.fec_inner = transponder["fec_inner"]
			params.inversion = transponder["inversion"]
			params.modulation = transponder["modulation"]
			params_fe = eDVBFrontendParameters()
			params_fe.setDVBC(params)

		try:
			self.rawchannel.requestTsidOnid()
		except TypeError:
			# for compatibility with some third party images
			self.rawchannel.requestTsidOnid(self.gotTsidOnid)

		self.frontend.tune(params_fe)
		self.manager.setAdapter(0)  # FIX: use the correct device
		self.manager.setDemuxer(demuxer_id)
		self.manager.setFrontend(current_slotid)

		self.current_slotid = current_slotid
		self.lockcounter = 0
		self.locktimer = eTimer()
		self.locktimer.callback.append(self.checkTunerLock)
		self.locktimer.start(100, 1)

	def checkTunerLock(self):
		from Screens.Standby import inStandby
		fe_status_dict = {}
		self.frontend and self.frontend.getFrontendStatus(fe_status_dict)
		tuner_state = fe_status_dict.get("tuner_state", "UNKNOWN")
		if tuner_state == "TUNING":
			print("[ABM-main][checkTunerLock] TUNING", file=log)
		elif tuner_state == "LOCKED":
			print("[ABM-main][checkTunerLock] ACQUIRING TSID/ONID", file=log)
			self.progresscurrent += 1
			if not inStandby:
				self["progress_text"].value = self.progresscurrent
				self["progress"].setValue(self.progresscurrent)
				self["action"].setText(_("Reading %s...") % str(self.providers[self.currentAction]["name"]))
				self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))
			self.timer = eTimer()
			self.timer.callback.append(self.doScan)
			self.timer.start(100, 1)
			return
		elif tuner_state == "LOSTLOCK":
			print("[ABM-main][checkTunerLock] LOSTLOCK", file=log)
		elif tuner_state == "FAILED":
			print("[ABM-main][checkTunerLock] TUNING FAILED FATAL", file=log)
			self.showError(_('Tuning failed!\n\nProvider: %s\nTuner: %s\nFrequency: %d MHz\n\nPlease check affected tuner for:\n\nTuner configuration errors,\nSignal cabling issues,\nAny other reception issues.') % (str(self.providers[self.currentAction]["name"]), chr(ord('A') + self.current_slotid), self.transponder["frequency"] // int(1e06 if self.providers[self.currentAction]["streamtype"] == "dvbt" else 1e03)))
			return

		self.lockcounter += 1
		if self.lockcounter > self.LOCK_TIMEOUT:
			print("[AutoBouquetsMaker] Timeout for tuner lock, ", file=log)
			self.showError(_('Tuning lock timed out!\n\nProvider: %s\nTuner: %s\nFrequency: %d MHz\n\nPlease check affected tuner for:\n\nTuner configuration errors,\nSignal cabling issues,\nAny other reception issues.') % (str(self.providers[self.currentAction]["name"]), chr(ord('A') + self.current_slotid), self.transponder["frequency"] // int(1e06 if self.providers[self.currentAction]["streamtype"] == "dvbt" else 1e03)))
			return

		self.locktimer.start(100, 1)

	# for compatibility with some third party images
	def gotTsidOnid(self, tsid, onid):
		print("[ABM-main][gotTsidOnid] tsid, onid:", tsid, onid, file=log)

		INTERNAL_PID_STATUS_NOOP = 0
		INTERNAL_PID_STATUS_WAITING = 1
		INTERNAL_PID_STATUS_SUCCESSFUL = 2
		INTERNAL_PID_STATUS_FAILED = 3

		if tsid is not None and onid is not None:
			self.pidStatus = INTERNAL_PID_STATUS_SUCCESSFUL
			self.tsid = tsid
			self.onid = onid
		else:
			self.pidStatus = INTERNAL_PID_STATUS_FAILED
			self.tsid = -1
			self.onid = -1
		self.timer.start(100, True)

	def doScan(self):
		if not self.manager.read(self.selectedProviders[self.currentAction], self.providers, self.motorised):
			print("[ABM-main][doScan] Cannot read data", file=log)
			self.showError(_('Cannot read data'))
			return
		self.doActions()

	def doBuildIndex(self):
		self.manager.save(self.providers, self.dependents)
		self.scanComplete()

	def scanComplete(self):
		from Screens.Standby import inStandby
		self.releaseFrontend()
		self.restartService()

		eDVBDB.getInstance().reloadServicelist()
		eDVBDB.getInstance().reloadBouquets()
		self.progresscurrent += 1
		if not inStandby:
			self["progress_text"].value = self.progresscurrent
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_('Done'))
			self["status"].setText(_("Services: %d video - %d radio") % (self.manager.getServiceVideoRead(), self.manager.getServiceAudioRead()))

		self.timer = eTimer()
		self.timer.callback.append(self.close)
		self.timer.start(2000, 1)

	def releaseFrontend(self):
		if hasattr(self, 'frontend'):
			del self.frontend
		if hasattr(self, 'rawchannel'):
			del self.rawchannel
		self.frontend = None
		self.rawchannel = None

	def restartService(self):
		if self.postScanService:
			self.session.nav.playService(self.postScanService)
			self.postScanService = None

	def isRotorSat(self, slot, orb_pos):
		rotorSatsForNim = nimmanager.getRotorSatListForNim(slot)
		if len(rotorSatsForNim) > 0:
			for sat in rotorSatsForNim:
				if sat[0] == orb_pos:
					return True
		return False

	def validNIM(self, slot):
		return self.providers[self.currentAction]["streamtype"] != "dvbs" or self.providers[self.currentAction]["transponder"]["orbital_position"] in [sat[0] for sat in nimmanager.getSatListForNim(slot)]

	def printconfig(self):
		print("[ABM-config] level: ", config.autobouquetsmaker.level.value, file=log)
		print("[ABM-config] providers: ", config.autobouquetsmaker.providers.value, file=log)
		if config.autobouquetsmaker.bouquetsorder.value:
			print("[ABM-config] bouquetsorder: ", config.autobouquetsmaker.bouquetsorder.value, file=log)
		if config.autobouquetsmaker.keepallbouquets.value:
			print("[ABM-config] keepbouquets: All", file=log)
		else:
			print("[ABM-config] keepbouquets: ", config.autobouquetsmaker.keepbouquets.value, file=log)
		if config.autobouquetsmaker.hidesections.value:
			print("[ABM-config] hidesections: ", config.autobouquetsmaker.hidesections.value, file=log)
		print("[ABM-config] add provider prefix: ", config.autobouquetsmaker.addprefix.value, file=log)
		print("[ABM-config] show in extensions menu: ", config.autobouquetsmaker.extensions.value, file=log)
		print("[ABM-config] placement: ", config.autobouquetsmaker.placement.value, file=log)
		print("[ABM-config] skip services on non-configured satellites: ", config.autobouquetsmaker.skipservices.value, file=log)
		print("[ABM-config] show non-indexed: ", config.autobouquetsmaker.showextraservices.value, file=log)
		if config.autobouquetsmaker.FTA_only.value:
			print("[ABM-config] FTA_only: ", config.autobouquetsmaker.FTA_only.value, file=log)
		print("[ABM-config] schedule: ", config.autobouquetsmaker.schedule.value, file=log)
		if config.autobouquetsmaker.schedule.value:
			print("[ABM-config] schedule time: ", config.autobouquetsmaker.scheduletime.value, file=log)
			print("[ABM-config] schedule days: ", [("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[i] for i in range(7) if config.autobouquetsmaker.days[i].value], file=log)

	def getABMsettings(self):
		providers_extra = []
		providers_tmp = config.autobouquetsmaker.providers.value.split("|")
		for provider_str in providers_tmp:
			provider = provider_str.split(":", 1)[0]
			if provider in self.dependents:
				for descendent in self.dependents[provider]:
					providers_extra.append('|' + descendent + ':' + provider_str.split(":", 1)[1])
		return config.autobouquetsmaker.providers.value + ''.join(providers_extra)

	def about(self):
		self.session.open(MessageBox, "AutoBouquetsMaker\nVersion date - 21/10/2012\n\nCoded by:\n\nSkaman and AndyBlac", MessageBox.TYPE_INFO)

	def help(self):
		self.session.open(MessageBox, "AutoBouquetsMaker\nto be coded.", MessageBox.TYPE_INFO)

	def cancel(self):
		self.close(None)


autoScheduleTimer = None


def Scheduleautostart(reason, session=None, **kwargs):
	#
	# This gets called twice at start up,once by WHERE_AUTOSTART without session,
	# and once by WHERE_SESSIONSTART with session. WHERE_AUTOSTART is needed though
	# as it is used to wake from deep standby. We need to read from session so if
	# session is not set just return and wait for the second call to this function.
	#
	# Called with reason=1 during /sbin/shutdown.sysvinit, and with reason=0 at startup.
	# Called with reason=1 only happens when using WHERE_AUTOSTART.
	# If only using WHERE_SESSIONSTART there is no call to this function on shutdown.
	#
	schedulename = "ABM-Scheduler"
	configname = config.autobouquetsmaker

	print("[%s][Scheduleautostart] reason(%d), session" % (schedulename, reason), session, file=log)
	if reason == 0 and session is None:
		return
	global autoScheduleTimer
	global wasScheduleTimerWakeup
	wasScheduleTimerWakeup = False
	if reason == 0:
		# check if box was woken up by a timer, if so, check if this plugin set this timer. This is not conclusive.
		wasScheduleTimerWakeup = session.nav.wasTimerWakeup() and configname.schedule.value and configname.schedulewakefromdeep.value and abs(configname.nextscheduletime.value - time()) <= 450
		if wasScheduleTimerWakeup:
			# if box is not in standby do it now
			from Screens.Standby import Standby, inStandby
			if not inStandby:
				# hack alert: session requires "pipshown" to avoid a crash in standby.py
				if not hasattr(session, "pipshown"):
					session.pipshown = False
				from Tools import Notifications
				Notifications.AddNotificationWithID("Standby", Standby)

		print("[%s][Scheduleautostart] AutoStart Enabled" % schedulename, file=log)
		if autoScheduleTimer is None:
			autoScheduleTimer = AutoScheduleTimer(session)
	else:
		print("[%s][Scheduleautostart] Stop" % schedulename, file=log)
		if autoScheduleTimer is not None:
			autoScheduleTimer.schedulestop()


class AutoScheduleTimer:
	instance = None

	def __init__(self, session):
		self.schedulename = "ABM-Scheduler"
		self.config = config.autobouquetsmaker
		self.itemtorun = AutoBouquetsMaker
		self.session = session
		self.scheduletimer = eTimer()
		self.scheduletimer.callback.append(self.ScheduleonTimer)
		self.scheduleactivityTimer = eTimer()
		self.scheduleactivityTimer.timeout.get().append(self.scheduledatedelay)
		self.ScheduleTime = 0
		now = int(time())
		if self.config.schedule.value:
			print("[%s][AutoScheduleTimer] Schedule Enabled at " % self.schedulename, strftime("%c", localtime(now)), file=log)
			if now > 1546300800:  # Tuesday, January 1, 2019 12:00:00 AM
				self.scheduledate()
			else:
				print("[%s][AutoScheduleTimer] STB clock not yet set." % self.schedulename, file=log)
				self.scheduleactivityTimer.start(36000)
		else:
			print("[%s][AutoScheduleTimer] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now)), file=log)
			self.scheduleactivityTimer.stop()

		assert AutoScheduleTimer.instance is None, "class AutoScheduleTimer is a singleton class and just one instance of this class is allowed!"
		AutoScheduleTimer.instance = self

	def __onClose(self):
		AutoScheduleTimer.instance = None

	def scheduledatedelay(self):
		self.scheduleactivityTimer.stop()
		self.scheduledate()

	def getScheduleTime(self):
		now = localtime(time())
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, self.config.scheduletime.value[0], self.config.scheduletime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def getScheduleDayOfWeek(self):
		today = self.getToday()
		for i in range(1, 8):
			if self.config.days[(today + i) % 7].value:
				return i

	def getToday(self):
		return localtime(time()).tm_wday

	def scheduledate(self, atLeast=0):
		self.scheduletimer.stop()
		self.ScheduleTime = self.getScheduleTime()
		now = int(time())
		if self.ScheduleTime > 0:
			if self.ScheduleTime < now + atLeast:
				self.ScheduleTime += 86400 * self.getScheduleDayOfWeek()
			elif not self.config.days[self.getToday()].value:
				self.ScheduleTime += 86400 * self.getScheduleDayOfWeek()
			next = self.ScheduleTime - now
			self.scheduletimer.startLongTimer(next)
		else:
			self.ScheduleTime = -1
		print("[%s][scheduledate] Time set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now)), file=log)
		self.config.nextscheduletime.value = self.ScheduleTime
		self.config.nextscheduletime.save()
		configfile.save()
		return self.ScheduleTime

	def schedulestop(self):
		self.scheduletimer.stop()

	def ScheduleonTimer(self):
		self.scheduletimer.stop()
		now = int(time())
		wake = self.getScheduleTime()
		atLeast = 0
		if wake - now < 60:
			atLeast = 60
			print("[%s][ScheduleonTimer] onTimer occured at" % self.schedulename, strftime("%c", localtime(now)), file=log)
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("%s update is about to start.\nDo you want to allow this?") % self.schedulename
				ybox = self.session.openWithCallback(self.doSchedule, MessageBox, message, MessageBox.TYPE_YESNO, timeout=30)
				ybox.setTitle(_('%s scheduled update') % self.schedulename)
			else:
				self.doSchedule(True)
		self.scheduledate(atLeast)

	def doSchedule(self, answer):
		now = int(time())
		if answer is False:
			if self.config.retrycount.value < 2:
				print("[%s][doSchedule] Schedule delayed." % self.schedulename, file=log)
				self.config.retrycount.value += 1
				self.ScheduleTime = now + (int(self.config.retry.value) * 60)
				print("[%s][doSchedule] Time now set to" % self.schedulename, strftime("%c", localtime(self.ScheduleTime)), strftime("(now=%c)", localtime(now)), file=log)
				self.scheduletimer.startLongTimer(int(self.config.retry.value) * 60)
			else:
				atLeast = 60
				print("[%s][doSchedule] Enough Retries, delaying till next schedule." % self.schedulename, strftime("%c", localtime(now)), file=log)
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout=10)
				self.config.retrycount.value = 0
				self.scheduledate(atLeast)
		else:
			self.timer = eTimer()
			self.timer.callback.append(self.runscheduleditem)
			print("[%s][doSchedule] Running Schedule" % self.schedulename, strftime("%c", localtime(now)), file=log)
			self.timer.start(100, 1)

	def runscheduleditem(self):
		self.session.openWithCallback(self.runscheduleditemCallback, self.itemtorun)

	def runscheduleditemCallback(self):
		global wasScheduleTimerWakeup
		from Screens.Standby import Standby, inStandby, TryQuitMainloop, inTryQuitMainloop
		print("[%s][runscheduleditemCallback] inStandby" % self.schedulename, inStandby, file=log)
		if wasScheduleTimerWakeup and inStandby and self.config.scheduleshutdown.value and not self.session.nav.getRecordings() and not inTryQuitMainloop:
			print("[%s] Returning to deep standby after scheduled wakeup" % self.schedulename, file=log)
			self.session.open(TryQuitMainloop, 1)
		wasScheduleTimerWakeup = False  # clear this as any subsequent run will not be from wake up from deep

	def doneConfiguring(self):  # called from plugin on save
		now = int(time())
		if self.config.schedule.value:
			if autoScheduleTimer is not None:
				print("[%s][doneConfiguring] Schedule Enabled at" % self.schedulename, strftime("%c", localtime(now)), file=log)
				autoScheduleTimer.scheduledate()
		else:
			if autoScheduleTimer is not None:
				self.ScheduleTime = 0
				print("[%s][doneConfiguring] Schedule Disabled at" % self.schedulename, strftime("%c", localtime(now)), file=log)
				autoScheduleTimer.schedulestop()
		# scheduletext is not used for anything but could be returned to the calling function to display in the GUI.
		if self.ScheduleTime > 0:
			t = localtime(self.ScheduleTime)
			scheduletext = strftime(_("%a %e %b  %-H:%M"), t)
		else:
			scheduletext = ""
		return scheduletext
