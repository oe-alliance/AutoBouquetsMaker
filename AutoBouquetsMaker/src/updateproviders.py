from __future__ import print_function
from __future__ import absolute_import

# for localized messages
from . import _

from . import log

import os
import sys
import socket
import six

from six.moves.urllib.request import Request, urlopen

from xml.dom.minidom import parseString

from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Components.config import config
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from .scanner.manager import Manager
from .scanner.providerconfig import ProviderConfig
from .scanner.providers import Providers
from .version import PLUGIN_VERSION as localVersion

from Tools.Directories import resolveFilename, fileExists, SCOPE_CURRENT_SKIN

from .skin_templates import skin_downloadBar


class AutoBouquetsMaker_UpdateProviders(Screen):
	# Note to skinners: no need to skin this screen if you have skinned the screen 'AutoBouquetsMaker'.
	skin = skin_downloadBar()

	def __init__(self, session, args=0):
		print("[ABM-UpdateProviders][__init__] Starting...", file=log)
		print("[ABM-UpdateProviders][__init__] args", args)
		Screen.__init__(self, session)
		self.session = session
		self.skinName = "AutoBouquetsMaker"
		Screen.setTitle(self, _("UpdateProviders"))

		self["background"] = Pixmap()
		self["action"] = Label(_("Finding configured providers..."))
		self["status"] = Label("")
		self["progress"] = ProgressBar()

		self["actions"] = ActionMap(["SetupActions"],
		{
			"cancel": self.keyCancel,
		}, -2)

		self.timerlength = 100
		socket_timeout = 10
		socket.setdefaulttimeout(socket_timeout)
		self.index = 0
		self.messages = []
		self.version_checked = False
		self.pluginGit = "https://github.com/oe-alliance/AutoBouquetsMaker"
		self.gitProvidersFolder = "/raw/master/AutoBouquetsMaker/providers"
		self.remoteVersion = "/raw/master/AutoBouquetsMaker/src/version.py"
		self.providersFolder = "%s/providers/" % os.path.dirname(sys.modules[__name__].__file__)

		self.providers = Manager().getProviders()

		# dependent providers
		self.dependents = {}
		for provider_key in self.providers:
			if len(self.providers[provider_key]["dependent"]) > 0 and self.providers[provider_key]["dependent"] in self.providers:
				if self.providers[provider_key]["dependent"] not in self.dependents:
					self.dependents[self.providers[provider_key]["dependent"]] = []
				self.dependents[self.providers[provider_key]["dependent"]].append(provider_key)

		# get ABM config string including dependents
		self.abm_settings_str = self.getABMsettings()

		self.onFirstExecBegin.append(self.firstExec)

	def showError(self, message):
		question = self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)
		question.setTitle(_("UpdateProviders"))
		self.close()

	def keyCancel(self):
		self.close()

	def firstExec(self):
		if len(self.abm_settings_str) < 1:
			self.showError(_('No providers configured.'))
			return
		png = resolveFilename(SCOPE_CURRENT_SKIN, "autobouquetsmaker/background.png")
		if not png or not fileExists(png):
			png = "%s/images/background.png" % os.path.dirname(sys.modules[__name__].__file__)
		self["background"].instance.setPixmapFromFile(png)

		self.actionsList = []

		providers_tmp = self.abm_settings_str.split("|")

		for provider_tmp in providers_tmp:
			provider_config = ProviderConfig(provider_tmp)
			if provider_config.isValid() and Providers().providerFileExists(provider_config.getProvider()):
				self.actionsList.append(provider_config.getProvider())
		self.go()

	def go(self):
		if len(self.actionsList) > 0:
			if self.version_checked == False:
				self["action"].setText(_('Starting update...'))
				self["status"].setText(_("Checking version compatibility..."))
				self.progresscount = len(self.actionsList)
				self.progresscurrent = 0
				self["progress"].setRange((0, self.progresscount))
				self["progress"].setValue(self.progresscurrent)
				self.timer = eTimer()
				self.timer.callback.append(self.checkRemoteVersion)
				self.timer.start(self.timerlength, 1)
			else:
				self.timer = eTimer()
				self.timer.callback.append(self.fetchProviders)
				self.timer.start(self.timerlength, 1)
		else:
			self.showError(_('No providers are configured.'))

	def checkRemoteVersion(self):
		URL = self.pluginGit + self.remoteVersion
		req = Request(URL)
		try:
			response = urlopen(req)
		except Exception as e:
			if hasattr(e, 'code') and hasattr(e, 'reason'):
				print("[ABM-UpdateProviders][checkRemoteVersion] Failed to retrieve version file. Error: %s %s" % (str(e.code), str(e.reason)), file=log)
				self.showError(_('Failed to retrieve version file. Error: %s %s') % (str(e.code), str(e.reason)))
			else:
				if hasattr(e, 'reason'):
					print('[ABM-UpdateProviders][checkRemoteVersion] Failed to reach Github: ', str(e.reason), file=log)
					self.showError(_('Network connection error: \n%s') % str(e.reason))
				else:
					print('[ABM-UpdateProviders][checkRemoteVersion] Failed to reach Github.', file=log)
					self.showError(_('Network connection error.'))
			return

		try:
			if six.PY2:
				remoteVersion = response.read().split('"')[1]
			else:
				remoteVersion = response.read()
				remoteVersion = six.ensure_str(remoteVersion).split('"')[1]
			print('[ABM-UpdateProviders][checkRemoteVersion] Local version: %s' % localVersion, file=log)
			print('[ABM-UpdateProviders][checkRemoteVersion] Remote version: %s' % remoteVersion, file=log)
			if remoteVersion != localVersion:
				print('[ABM-UpdateProviders][checkRemoteVersion] Incompatible versions: %s > %s' % (localVersion, remoteVersion), file=log)
				self.showError(_('Incompatible versions: %s > %s') % (localVersion, remoteVersion))
				return
			self.version_checked = True
			self.go()
		except:
			print('[ABM-UpdateProviders][checkRemoteVersion] Cannot read version.', file=log)
			self.showError(_('Cannot read version'))
			return

	def fetchProviders(self):
		if self.index < len(self.actionsList):
			self.provider = self.actionsList[self.index]
			self.provider_name = str(self.providers[self.actionsList[self.index]]["name"])
			print("[ABM-UpdateProviders][fetchProviders] Fetching provider file for ", self.provider_name, file=log)
			self.progresscurrent = self.index
			self.index += 1
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_("Retrieving config file for %s") % self.provider_name)
			self["status"].setText(_("Downloading latest file from Github..."))
			self.fetchtimer = eTimer()
			self.fetchtimer.callback.append(self.getResource)
			self.fetchtimer.start(self.timerlength, 1)
		else:
			self.session.openWithCallback(self.done, ShowResult, '\n'.join(self.messages))

	def getResource(self):
		URL = self.pluginGit + self.gitProvidersFolder + "/" + self.provider + ".xml"
		req = Request(URL)
		try:
			response = urlopen(req)
		except Exception as e:
			if hasattr(e, 'code') and hasattr(e, 'reason'):
				print("[ABM-UpdateProviders][getResource] Failed to retrieve file for %s. Error: %s %s" % (self.provider_name, str(e.code), str(e.reason)), file=log)
				self.messages.append(_("Failed to retrieve file for %s. Error: %s %s") % (self.provider_name, str(e.code), str(e.reason)))
				self["action"].setText(_("Failed..."))
				self["status"].setText(_("Unable to download config file for %s") % self.provider_name)
				self.resourcetimer = eTimer()
				self.resourcetimer.callback.append(self.fetchProviders)
				self.resourcetimer.start(self.timerlength, 1)
			else:
				if hasattr(e, 'reason'):
					print('[ABM-UpdateProviders][getResource] Failed to reach Github: ', str(e.reason), file=log)
					self.showError(_('Network connection error: \n%s') % str(e.reason))
				else:
					print('[ABM-UpdateProviders][getResource] Failed to reach Github.', file=log)
					self.showError(_('Network connection error.'))
			return

		if six.PY2:
			providerxml = response.read().replace("\r", "")
		else:
			providerxml = response.read()
			providerxml = six.ensure_str(providerxml).replace("\r", "")

		if '<provider>' in providerxml:

			try:
				dom = parseString(providerxml)  # This is to check the downloaded xml file parses
			except:
				dom = None
			if dom is not None:
				currentProviderFile = self.providersFolder + "/" + self.provider + ".xml"
				with open(currentProviderFile, 'r') as f:
					currentProviderFileStr = f.read().replace("\r", "")
					f.close()
				if currentProviderFileStr == providerxml:
					self["action"].setText(_("Retrieved config file for %s") % self.provider_name)
					self["status"].setText(_("Config file for %s does not need updating.") % self.provider_name)
					print("[ABM-UpdateProviders][getResource] Config file for %s did not need updating." % self.provider_name, file=log)
					self.messages.append(_("Config file for %s didn't need updating.") % (self.provider_name))
					self.resourcetimer = eTimer()
					self.resourcetimer.callback.append(self.fetchProviders)
					self.resourcetimer.start(self.timerlength, 1)
					return
				else:
					with open(currentProviderFile, 'w') as f:
						f.write(providerxml)
						f.close()
					self["action"].setText(_("Retrieved config file for %s") % self.provider_name)
					self["status"].setText(_("Config file for %s has been updated.") % self.provider_name)
					print("[ABM-UpdateProviders][getResource] Config file for %s has been updated to the latest version" % self.provider_name, file=log)
					self.messages.append(_("Config file for %s has been updated.") % (self.provider_name))
					self.resourcetimer = eTimer()
					self.resourcetimer.callback.append(self.fetchProviders)
					self.resourcetimer.start(self.timerlength, 1)

			else:
				self["action"].setText(_("Retrieved config file for %s") % self.provider_name)
				self["status"].setText(_("Config file for %s does not parse.") % self.provider_name)
				print("[ABM-UpdateProviders][getResource] Retrieved config file for %s does not parse." % self.provider_name, file=log)
				self.messages.append(_("Retrieved config file for %s does not parse.") % (self.provider_name))
				self.resourcetimer = eTimer()
				self.resourcetimer.callback.append(self.fetchProviders)
				self.resourcetimer.start(self.timerlength, 1)
				return

		else:
			self["action"].setText(_("Retrieved provider file for %s") % self.provider_name)
			self["status"].setText(_("Config file for %s is faulty.") % self.provider_name)
			print("[ABM-UpdateProviders][getResource] Retrieved config file for %s is faulty or incomplete." % self.provider_name, file=log)
			self.messages.append(_("Retrieved config file for %s is faulty or incomplete.") % (self.provider_name))
			self.resourcetimer = eTimer()
			self.resourcetimer.callback.append(self.fetchProviders)
			self.resourcetimer.start(self.timerlength, 1)
			return

	def done(self, answer=None):
		self.close()

	def getABMsettings(self):
		providers_extra = []
		providers_tmp = config.autobouquetsmaker.providers.value.split("|")
		for provider_str in providers_tmp:
			provider = provider_str.split(":", 1)[0]
			if provider in self.dependents:
				for descendent in self.dependents[provider]:
					providers_extra.append('|' + descendent + ':' + provider_str.split(":", 1)[1])
		return config.autobouquetsmaker.providers.value + ''.join(providers_extra)


class ShowResult(Screen):
	def __init__(self, session, text):
		Screen.__init__(self, session)
		self.skinName = "Setup"
		self.setTitle(_("Update summary"))

		self["key_red"] = StaticText(_("Close"))
		self["config"] = ScrollLabel(text)

		self["actions"] = ActionMap(["WizardActions", "ColorActions"],
		{
			"up": self.pageUp,
			"down": self.pageDown,
			"left": self.pageUp,
			"right": self.pageDown,
			"back": self.close,
			"red": self.close,
		}, -2)

	def pageUp(self):
		self["config"].pageUp()

	def pageDown(self):
		self["config"].pageDown()
