from __future__ import absolute_import, print_function

from enigma import eDVBDB, eDVBFrontendParameters, eDVBFrontendParametersCable, eDVBFrontendParametersSatellite, eDVBFrontendParametersTerrestrial, eDVBResourceManager, eTimer

from Components.ActionMap import ActionMap
from Components.config import config
from Components.Label import Label
from Components.NimManager import nimmanager
from Components.ProgressBar import ProgressBar
from Components.Sources.FrontendStatus import FrontendStatus
from Components.Sources.Progress import Progress
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from .manager import Manager
from .providerconfig import ProviderConfig
from .providers import Providers
from .. import _, log
from ..skin_templates import skin_downloadBar


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
			self.showError(_('Tuning failed!\n\nProvider: %s\nTuner: %s\nFrequency: %d MHz%s\n\nPlease check the affected tuner for:\n\nTuner configuration errors,\nSignal cabling issues,\nAny other reception issues.') % (str(self.providers[self.currentAction]["name"]), chr(ord('A') + self.current_slotid), self.transponder["frequency"] // int(1e06 if self.providers[self.currentAction]["streamtype"] == "dvbt" else 1e03), ('\nPolarization: %s' % self.transponder["polarization"]) if "polarization" in self.transponder else ''))
			return

		self.lockcounter += 1
		if self.lockcounter > self.LOCK_TIMEOUT:
			print("[AutoBouquetsMaker] Timeout for tuner lock, ", file=log)
			self.showError(_('Tuning lock timed out!\n\nProvider: %s\nTuner: %s\nFrequency: %d MHz%s\n\nPlease check the affected tuner for:\n\nTuner configuration errors,\nSignal cabling issues,\nAny other reception issues.') % (str(self.providers[self.currentAction]["name"]), chr(ord('A') + self.current_slotid), self.transponder["frequency"] // int(1e06 if self.providers[self.currentAction]["streamtype"] == "dvbt" else 1e03), ('\nPolarization: %s' % self.transponder["polarization"]) if "polarization" in self.transponder else ''))
			return

		self.locktimer.start(100, 1)

	# for compatibility with some third party images
	def gotTsidOnid(self, tsid, onid):
		print("[ABM-main][gotTsidOnid] tsid, onid:", tsid, onid, file=log)

		INTERNAL_PID_STATUS_NOOP = 0  # noqa: F841
		INTERNAL_PID_STATUS_WAITING = 1  # noqa: F841
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
		print("[ABM-config] show non-indexed: ", config.autobouquetsmaker.extraservices.value, file=log)
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
