# -*- coding: utf-8 -*-
# for localized messages
from __future__ import absolute_import
from . import _

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.config import getConfigListEntry, config, configfile
from Components.Sources.List import List
from Components.ActionMap import ActionMap
from Components.Button import Button
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN

from .skin_templates import skin_hidesections
from .scanner.manager import Manager
from .scanner.providerconfig import ProviderConfig


class AutoBouquetsMaker_HideSections(Screen):
	skin = skin_hidesections()

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		Screen.setTitle(self, _("AutoBouquetsMaker Hide sections"))
		self.startlist = config.autobouquetsmaker.hidesections.getValue()
		self.drawList = []

		self["list"] = List(self.drawList)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
		{
			"red": self.keyCancel,
			"green": self.keySave,
			"ok": self.ok,
			"cancel": self.keyCancel,
		}, -2)

		self.providers = Manager().getProviders()
		self.providers_enabled = []
		providers_tmp = config.autobouquetsmaker.providers.value.split("|")
		for provider_tmp in providers_tmp:
			provider_config = ProviderConfig(provider_tmp)

			if not provider_config.isValid():
				continue

			if provider_config.getProvider() not in self.providers:
				continue

			self.providers_enabled.append(provider_config.getProvider())

		self.housekeeping()
		self.refresh()

	def buildListEntry(self, enabled, name, type):
		pixmap = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/lock_%s.png" % ("on" if enabled else "off")))

		return ((pixmap, str(name), str(type)))

	def refresh(self):
		self.providers_selected = config.autobouquetsmaker.hidesections.value.split("|")
		self.drawList = []
		self.listAll = []

		for provider in self.providers_enabled:
			for section in sorted(self.providers[provider]["sections"].keys()):
				key = provider + ":" + str(section)
				self.listAll.append(key)
				self.drawList.append(self.buildListEntry(key in self.providers_selected, self.providers[provider]["sections"][section], self.providers[provider]["name"]))

		self["list"].setList(self.drawList)

	def ok(self):
		if len(self.listAll) == 0:
			return
		index = self["list"].getIndex()

		if self.listAll[index] in self.providers_selected:
			self.providers_selected.remove(self.listAll[index])
		else:
			self.providers_selected.append(self.listAll[index])
		config.autobouquetsmaker.hidesections.value = "|".join(self.providers_selected)
		self.refresh()
		self["list"].setIndex(index)

	# keySave and keyCancel are just provided in case you need them.
	# you have to call them by yourself.
	def keySave(self):
		config.autobouquetsmaker.hidesections.save()
		configfile.save()
		self.close()

	def cancelConfirm(self, result):
		if not result:
			return
		config.autobouquetsmaker.hidesections.cancel()
		self.close()

	def keyCancel(self):
		if self.startlist != config.autobouquetsmaker.hidesections.getValue():
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close()

	def housekeeping(self):
		# remove non-existent hidden sections, due to changes in the provider file
		hidden_sections = config.autobouquetsmaker.hidesections.value.split("|")
		new_hidden_sections = []
		for provider in self.providers_enabled:
			for section in sorted(self.providers[provider]["sections"].keys()):
				key = provider + ":" + str(section)
				if key in hidden_sections:
					new_hidden_sections.append(key)
		config.autobouquetsmaker.hidesections.value = "|".join(new_hidden_sections)
