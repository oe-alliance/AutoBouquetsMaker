from __future__ import print_function
from __future__ import absolute_import

# for localized messages
from . import _

from .scanner.main import AutoBouquetsMaker, AutoScheduleTimer
from .scanner.manager import Manager
from .about import AutoBouquetsMaker_About
from .setup import AutoBouquetsMaker_Setup, AutoBouquetsMaker_ProvidersSetup
from .hidesections import AutoBouquetsMaker_HideSections
from .keepbouquets import AutoBouquetsMaker_KeepBouquets
from .ordering import AutoBouquetsMaker_Ordering
from .deletebouquets import AutoBouquetsMaker_DeleteBouquets, AutoBouquetsMaker_DeleteMsg
from .updateproviders import AutoBouquetsMaker_UpdateProviders
from .scanner.frequencyfinder import AutoBouquetsMaker_FrequencyFinder

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox

from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.config import config
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel

from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap

from .skin_templates import skin_mainmenu, skin_log

from time import localtime, time, strftime
import os
import sys
from . import log


class AutoBouquetsMaker_Menu(Screen):
	skin = skin_mainmenu()

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setup_title = _("AutoBouquetsMaker")
		Screen.setTitle(self, self.setup_title)
		self.init_level = config.autobouquetsmaker.level.getValue()
		self.init_providers = config.autobouquetsmaker.providers.getValue()
		self.init_keepallbouquets = config.autobouquetsmaker.keepallbouquets.getValue()
		self.init_schedule = config.autobouquetsmaker.schedule.getValue()
		self.init_scheduletime = config.autobouquetsmaker.scheduletime.getValue()
		self.init_frequencyfinder = config.autobouquetsmaker.frequencyfinder.getValue()
		print('[ABM-menu][__init__] self.init_schedule', self.init_schedule)
		print('[ABM-menu][__init__] self.init_scheduletime', self.init_scheduletime)

		self.onChangedEntry = []
		l = []

		self["list"] = List(l)

		self["setupActions"] = ActionMap(["ColorActions", "SetupActions", "MenuActions"],
		{
			"red": self.quit,
			"green": self.startScan,
			"cancel": self.quit,
			"ok": self.openSelected,
			"menu": self.quit,
		}, -2)
		self["key_red"] = Button(_("Exit"))
		self["key_green"] = Button(_("Scan"))

		self.createsetup()
		if len(config.autobouquetsmaker.providers.value) < 1:
			self.onFirstExecBegin.append(self.openSetup)

	def createsetup(self):
		l = []
		l.append(self.buildListEntry(_("Configure"), "configure.png"))
		l.append(self.buildListEntry(_("Providers"), "opentv.png"))
		if len(config.autobouquetsmaker.providers.getValue().split('|')) > 1:
			l.append(self.buildListEntry(_("Providers order"), "reorder.png"))
		if len(config.autobouquetsmaker.providers.getValue().split('|')) > 0:
			l.append(self.buildListEntry(_("Hide sections"), "reorder.png"))
		if not config.autobouquetsmaker.keepallbouquets.value:
			l.append(self.buildListEntry(_("Keep bouquets"), "reorder.png"))
		l.append(self.buildListEntry(_("Start scan"), "download.png"))
		l.append(self.buildListEntry(_("Delete ABM bouquets"), "reorder.png"))
		l.append(self.buildListEntry(_("Update provider files"), "reorder.png"))
		if config.autobouquetsmaker.level.getValue() == "expert" and config.autobouquetsmaker.frequencyfinder.getValue():
			l.append(self.buildListEntry(_("DVB-T frequency finder"), "reorder.png"))
		l.append(self.buildListEntry(_("Show log"), "dbinfo.png"))
		l.append(self.buildListEntry(_("About"), "about.png"))
		self["list"].list = l

	# for summary:
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return str(self["list"].getCurrent()[1])

	def getCurrentValue(self):
		return ""

	def createSummary(self):
		return AutoBouquetsMaker_MenuSummary

	def buildListEntry(self, description, image):
		pixmap = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "autobouquetsmaker/" + image))
		if pixmap == None:
			pixmap = LoadPixmap(cached=True, path="%s/images/%s" % (os.path.dirname(sys.modules[__name__].__file__), image))
		return ((pixmap, description))

	def openSetup(self):
		self.session.open(AutoBouquetsMaker_Setup)

	def refresh(self):
		AutoScheduleTimer.instance.doneConfiguring()
		if self.init_level != config.autobouquetsmaker.level.getValue() or self.init_providers != config.autobouquetsmaker.providers.getValue() or self.init_keepallbouquets != config.autobouquetsmaker.keepallbouquets.getValue() or self.init_frequencyfinder != config.autobouquetsmaker.frequencyfinder.getValue():
			self.init_level = config.autobouquetsmaker.level.getValue()
			self.init_providers = config.autobouquetsmaker.providers.getValue()
			self.init_keepallbouquets = config.autobouquetsmaker.keepallbouquets.getValue()
			self.init_frequencyfinder = config.autobouquetsmaker.frequencyfinder.getValue()
			index = self["list"].getIndex()
			self.createsetup()
			if index is not None and len(self["list"].list) > index:
				self["list"].setIndex(index)
			else:
				self["list"].setIndex(0)

	def openSelected(self):

		index = self["list"].getIndex()

		if index == 0:
			self.session.openWithCallback(self.refresh, AutoBouquetsMaker_Setup)
			return

		if index == 1:
			self.session.openWithCallback(self.refresh, AutoBouquetsMaker_ProvidersSetup)
			return

		if len(config.autobouquetsmaker.providers.getValue().split('|')) < 2:  # menu "ordering" not shown
			index += 1

		if index == 2:
			self.session.open(AutoBouquetsMaker_Ordering)
			return

		if len(config.autobouquetsmaker.providers.getValue().split('|')) < 1:  # menu "hide sections" not shown
			index += 1

		if index == 3:
			self.session.open(AutoBouquetsMaker_HideSections)
			return

		if config.autobouquetsmaker.keepallbouquets.value:  # menu "keep bouquets" not shown
			index += 1

		if index == 4:
			self.session.open(AutoBouquetsMaker_KeepBouquets)
			return

		if index == 5:
			self.session.open(AutoBouquetsMaker)
			return

		if index == 6:
			self.session.openWithCallback(AutoBouquetsMaker_DeleteBouquets, AutoBouquetsMaker_DeleteMsg)
			return

		if index == 7:
			self.session.open(AutoBouquetsMaker_UpdateProviders)
			return

		if not (config.autobouquetsmaker.level.getValue() == "expert" and config.autobouquetsmaker.frequencyfinder.getValue()):
			index += 1

		if index == 8:
			self.session.open(AutoBouquetsMaker_FrequencyFinder)
			return

		if index == 9:
			self.session.open(AutoBouquetsMaker_Log)
			return

		if index == 10:
			self.session.open(AutoBouquetsMaker_About)
			return

	def startScan(self):
		self.session.open(AutoBouquetsMaker)

	def quit(self):
		self.close()


class AutoBouquetsMaker_MenuSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self.skinName = ["AutoBouquetsMaker_MenuSummary", "SetupSummary"]
		self["SetupTitle"] = StaticText(_(parent.setup_title))
		self["SetupEntry"] = StaticText("")
		self["SetupValue"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent["list"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)
		self.parent["list"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["SetupEntry"].text = self.parent.getCurrentEntry()
		self["SetupValue"].text = self.parent.getCurrentValue()


class AutoBouquetsMaker_Log(Screen):
	skin = skin_log()

	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("AutoBouquetsMaker Log"))
		self["list"] = ScrollLabel(log.getvalue())
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "MenuActions"],
		{
			"cancel": self.cancel,
			"ok": self.cancel,
			"up": self["list"].pageUp,
			"down": self["list"].pageDown,
			"menu": self.closeRecursive,
			"green": self.save,
		}, -2)

		self["key_green"] = Button(_("Save Log"))
		self["key_red"] = Button(_("Close"))

	def save(self):
		output = open('/tmp/abm.log', 'w')
		output.write(log.getvalue())
		output.close()
		self.session.open(MessageBox, _("ABM log file has been saved to the tmp directory"), MessageBox.TYPE_INFO, timeout=45)

	def cancel(self):
		self.close()

	def closeRecursive(self):
		self.close(True)
