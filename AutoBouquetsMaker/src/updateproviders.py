# for localized messages
from . import _

from . import log

import os
import sys
import socket

from urllib2 import Request, urlopen
from xml.dom.minidom import parseString

from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ProgressBar import ProgressBar
from Components.config import config
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from scanner.manager import Manager
from scanner.providerconfig import ProviderConfig
from scanner.providers import Providers
from version import PLUGIN_VERSION as localVersion

from Tools.Directories import resolveFilename, fileExists
try:
	from Tools.Directories import SCOPE_ACTIVE_SKIN
except:
	pass

class AutoBouquetsMaker_UpdateProviders(Screen, ConfigListScreen):
# Note to skinners: no need to skin this screen if you have skinned the screen 'AutoBouquetsMaker'.
	skin = """
	<screen position="c-300,e-80" size="600,70" flags="wfNoBorder" >
		<widget name="background" position="0,0" size="600,70" zPosition="-1" />
		<widget name="action" halign="center" valign="center" position="65,10" size="520,20" font="Regular;18" backgroundColor="#11404040" transparent="1" />
		<widget name="status" halign="center" valign="center" position="65,35" size="520,20" font="Regular;18" backgroundColor="#11000000" transparent="1" />
		<widget name="progress" position="65,55" size="520,5" borderWidth="1" backgroundColor="#11000000"/>
	</screen>"""

	def __init__(self, session, args = 0):
		print>>log, "[ABM-UpdateProviders][__init__] Starting..."
		print "[ABM-UpdateProviders][__init__] args", args
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
		try:
			png = resolveFilename(SCOPE_ACTIVE_SKIN, "autobouquetsmaker/background.png")
		except:
			png = None
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
		except Exception, e:
			if hasattr(e, 'code') and hasattr(e, 'reason'):
				print>>log, "[ABM-UpdateProviders][checkRemoteVersion] Failed to retrieve version file. Error: %s %s" % (str(e.code), str(e.reason))
				self.showError(_('Failed to retrieve version file. Error: %s %s') % (str(e.code), str(e.reason)))
			else:
				if hasattr(e, 'reason'):
					print>>log, '[ABM-UpdateProviders][checkRemoteVersion] Failed to reach Github: ', str(e.reason)
					self.showError(_('Network connection error: \n%s') % str(e.reason))
				else:
					print>>log, '[ABM-UpdateProviders][checkRemoteVersion] Failed to reach Github.'
					self.showError(_('Network connection error.'))
			return

		try:
			remoteVersion = response.read().split('"')[1]
			print>>log, '[ABM-UpdateProviders][checkRemoteVersion] Local version: %s' % localVersion
			print>>log, '[ABM-UpdateProviders][checkRemoteVersion] Remote version: %s' % remoteVersion
			if remoteVersion != localVersion:
				print>>log, '[ABM-UpdateProviders][checkRemoteVersion] Incompatible versions: %s > %s' % (localVersion, remoteVersion)
				self.showError(_('Incompatible versions: %s > %s') % (localVersion, remoteVersion))
				return
			self.version_checked = True
			self.go()
		except:
			print>>log, '[ABM-UpdateProviders][checkRemoteVersion] Cannot read version.'
			self.showError(_('Cannot read version'))
			return

	def fetchProviders(self):
		if self.index < len(self.actionsList):
			self.provider = self.actionsList[self.index]
			self.provider_name = str(self.providers[self.actionsList[self.index]]["name"])
			print>>log, "[ABM-UpdateProviders][fetchProviders] Fetching provider file for ", self.provider_name
			self.progresscurrent = self.index
			self.index += 1
			self["progress"].setValue(self.progresscurrent)
			self["action"].setText(_("Retrieving config file for %s") % self.provider_name)
			self["status"].setText(_("Downloading latest file from Github..."))
			self.fetchtimer = eTimer()
			self.fetchtimer.callback.append(self.getResource)
			self.fetchtimer.start(self.timerlength, 1)
		else:
			self.session.openWithCallback(self.done, MessageBox, '\n'.join(self.messages), MessageBox.TYPE_INFO, timeout=30)

	def getResource(self):
		URL = self.pluginGit + self.gitProvidersFolder + "/" + self.provider + ".xml"
		req = Request(URL)
		try:
			response = urlopen(req)
		except Exception, e:
			if hasattr(e, 'code') and hasattr(e, 'reason'):
				print>>log, "[ABM-UpdateProviders][getResource] Failed to retrieve file for %s. Error: %s %s" % (self.provider_name, str(e.code), str(e.reason))
				self.messages.append(_("Failed to retrieve file for %s. Error: %s %s") % (self.provider_name, str(e.code), str(e.reason)))
				self["action"].setText(_("Failed..."))
				self["status"].setText(_("Unable to download config file for %s") % self.provider_name)
				self.resourcetimer = eTimer()
				self.resourcetimer.callback.append(self.fetchProviders)
				self.resourcetimer.start(self.timerlength, 1)
			else:
				if hasattr(e, 'reason'):
					print>>log, '[ABM-UpdateProviders][getResource] Failed to reach Github: ', str(e.reason)
					self.showError(_('Network connection error: \n%s')% str(e.reason))
				else:
					print>>log, '[ABM-UpdateProviders][getResource] Failed to reach Github.'
					self.showError(_('Network connection error.'))
			return

		providerxml = response.read().replace("\r", "")
		if '<provider>' in providerxml:

			try:
				dom = parseString(providerxml) # This is to check the downloaded xml file parses
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
					print>>log, "[ABM-UpdateProviders][getResource] Config file for %s did not need updating." % self.provider_name
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
					print>>log, "[ABM-UpdateProviders][getResource] Config file for %s has been updated to the latest version" % self.provider_name
					self.messages.append(_("Config file for %s has been updated.") % (self.provider_name))
					self.resourcetimer = eTimer()
					self.resourcetimer.callback.append(self.fetchProviders)
					self.resourcetimer.start(self.timerlength, 1)

			else:
				self["action"].setText(_("Retrieved config file for %s") % self.provider_name)
				self["status"].setText(_("Config file for %s does not parse.") % self.provider_name)
				print>>log, "[ABM-UpdateProviders][getResource] Retrieved config file for %s does not parse." % self.provider_name
				self.messages.append(_("Retrieved config file for %s does not parse.") % (self.provider_name))
				self.resourcetimer = eTimer()
				self.resourcetimer.callback.append(self.fetchProviders)
				self.resourcetimer.start(self.timerlength, 1)
				return

		else:
			self["action"].setText(_("Retrieved provider file for %s") % self.provider_name)
			self["status"].setText(_("Config file for %s is faulty.") % self.provider_name)
			print>>log, "[ABM-UpdateProviders][getResource] Retrieved config file for %s is faulty or incomplete." % self.provider_name
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
