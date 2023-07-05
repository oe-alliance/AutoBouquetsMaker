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

from .skin_templates import skin_keepbouquets
from .scanner.manager import Manager


class AutoBouquetsMaker_KeepBouquets(Screen):
	skin = skin_keepbouquets()

	ABM_BOUQUET_PREFIX = "userbouquet.abm."

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		Screen.setTitle(self, _("AutoBouquetsMaker Keep bouquets"))
		self.startlist = config.autobouquetsmaker.keepbouquets.getValue()
		self.drawList = []

		self["list"] = List(self.drawList)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button("Save")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
		{
			"red": self.keyCancel,
			"green": self.keySave,
			"ok": self.ok,
			"cancel": self.keyCancel,
		}, -2)

		self.refresh()

	def buildListEntry(self, enabled, name, type):
		pixmap = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/lock_%s.png" % ("on" if enabled else "off")))

		return ((pixmap, str(name), str(type)))

	def refresh(self):
		bouquets = Manager().getBouquetsList()
		self.listTv = bouquets["tv"]
		self.listRadio = bouquets["radio"]
		self.drawList = []
		self.listAll = []
		self.bouquets = config.autobouquetsmaker.keepbouquets.value.split("|")

		if self.listTv is not None and self.listRadio is not None:
			for bouquet in self.listTv:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if bouquet["filename"] in self.bouquets:
					self.drawList.append(self.buildListEntry(True, bouquet["name"], "TV"))
				else:
					self.drawList.append(self.buildListEntry(False, bouquet["name"], "TV"))
				self.listAll.append(bouquet["filename"])

			for bouquet in self.listRadio:
				if bouquet["filename"][:len(self.ABM_BOUQUET_PREFIX)] == self.ABM_BOUQUET_PREFIX:
					continue
				if bouquet["filename"] in self.bouquets:
					self.drawList.append(self.buildListEntry(True, bouquet["name"], "Radio"))
				else:
					self.drawList.append(self.buildListEntry(False, bouquet["name"], "Radio"))
				self.listAll.append(bouquet["filename"])
		self["list"].setList(self.drawList)

	def ok(self):
		if len(self.listAll) == 0:
			return
		index = self["list"].getIndex()
		if self.listAll[index] in self.bouquets:
			self.bouquets.remove(self.listAll[index])
		else:
			self.bouquets.append(self.listAll[index])
		config.autobouquetsmaker.keepbouquets.value = "|".join(self.bouquets)
		self.refresh()
		self["list"].setIndex(index)

	# keySave and keyCancel are just provided in case you need them.
	# you have to call them by yourself.
	def keySave(self):
		config.autobouquetsmaker.keepbouquets.save()
		configfile.save()
		self.close()

	def cancelConfirm(self, result):
		if not result:
			return
		config.autobouquetsmaker.keepbouquets.cancel()
		self.close()

	def keyCancel(self):
		if self.startlist != config.autobouquetsmaker.keepbouquets.getValue():
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close()
