from __future__ import print_function
from __future__ import absolute_import

# for localized messages
from . import _
import os

from Plugins.Plugin import PluginDescriptor
from Components.NimManager import nimmanager
from Tools.Directories import resolveFilename, SCOPE_CONFIG

from .menu import AutoBouquetsMaker_Menu
from .scanner.main import Scheduleautostart, AutoBouquetsMaker

from Components.config import config, configfile, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock, getConfigListEntry, ConfigEnableDisable, ConfigSubDict
config.autobouquetsmaker = ConfigSubsection()
config.autobouquetsmaker.level = ConfigSelection(default="expert", choices=[("simple", _("simple")), ("expert", _("expert"))])
config.autobouquetsmaker.level.value = "expert"  # force to expert mode for all users
config.autobouquetsmaker.providers = ConfigText("", False)
config.autobouquetsmaker.bouquetsorder = ConfigText("", False)
config.autobouquetsmaker.schedule = ConfigYesNo(default=False)
config.autobouquetsmaker.scheduletime = ConfigClock(default=0)  # 1:00
config.autobouquetsmaker.retry = ConfigNumber(default=30)
config.autobouquetsmaker.retrycount = NoSave(ConfigNumber(default=0))
config.autobouquetsmaker.nextscheduletime = ConfigNumber(default=0)
config.autobouquetsmaker.schedulewakefromdeep = ConfigYesNo(default=True)
config.autobouquetsmaker.scheduleshutdown = ConfigYesNo(default=True)
config.autobouquetsmaker.dayscreen = ConfigSelection(choices=[("1", _("Press OK"))], default="1")
config.autobouquetsmaker.days = ConfigSubDict()
for i in range(7):
	config.autobouquetsmaker.days[i] = ConfigEnableDisable(default=True)
config.autobouquetsmaker.lastlog = ConfigText(default=' ', fixed_size=False)
config.autobouquetsmaker.keepallbouquets = ConfigYesNo(default=True)
config.autobouquetsmaker.keepbouquets = ConfigText("", False)
config.autobouquetsmaker.hidesections = ConfigText("", False)
config.autobouquetsmaker.addprefix = ConfigYesNo(default=False)
config.autobouquetsmaker.markersinindex = ConfigYesNo(default=False)
config.autobouquetsmaker.indexmarkerstyle = ConfigSelection(
	default="%s",
	choices=[
		("%s", _("none")),
		("     %s", _("indent + text")),
		("<-- %s -->", _("<-- text -->")),
		("< - - %s - - >", _("< - - text - - >")),
		("== %s ==", _("== text ==")),
		("= = %s = =", _("= = text = =")),
		("=== %s ===", _("=== text ===")),
		("= = = %s = = =", _("= = = text = = =")),
		("-------- %s --------", _("-------- text --------")),
		("== ABM - %s ==", _("== ABM - 'text' ==")),
		("---- ABM - %s ----", _("---- ABM - 'text' ----"))
	]
)
config.autobouquetsmaker.bouquetmarkerstyle = ConfigSelection(
	default="%s",
	choices=[
		("%s", _("none")),
		("     %s", _("indent + text")),
		("<-- %s -->", _("<-- text -->")),
		("< - - %s - - >", _("< - - text - - >")),
		("== %s ==", _("== text ==")),
		("= = %s = =", _("= = text = =")),
		("=== %s ===", _("=== text ===")),
		("= = = %s = = =", _("= = = text = = =")),
		("-------- %s --------", _("-------- text --------")),
		("== ABM - %s ==", _("== ABM - 'text' ==")),
		("---- ABM - %s ----", _("---- ABM - 'text' ----"))
	]
)
config.autobouquetsmaker.extensions = ConfigYesNo(default=False)
config.autobouquetsmaker.placement = ConfigSelection(default="top", choices=[("top", _("top")), ("bottom", _("bottom"))])
config.autobouquetsmaker.skipservices = ConfigYesNo(default=True)
config.autobouquetsmaker.showextraservices = ConfigYesNo(default=False)
config.autobouquetsmaker.extra_debug = ConfigYesNo(default=False)
config.autobouquetsmaker.frequencyfinder = ConfigYesNo(default=False)
config.autobouquetsmaker.FTA_only = ConfigText("", False)

user_providers_dir = os.path.realpath(resolveFilename(SCOPE_CONFIG)) + "/AutoBouquetsMaker/providers"
user_custom_dir = os.path.realpath(resolveFilename(SCOPE_CONFIG)) + "/AutoBouquetsMaker/custom"
if not os.path.exists(user_providers_dir):
	os.makedirs(user_providers_dir, mode=0o755)
if not os.path.exists(user_custom_dir):
	os.makedirs(user_custom_dir, mode=0o755)


def main(session, **kwargs):
	session.open(AutoBouquetsMaker_Menu)


def startscan(session, **kwargs):
	session.open(AutoBouquetsMaker)


def AutoBouquetsMakerSetup(menuid, **kwargs):
	if menuid == "scan":
		return [(_("AutoBouquetsMaker"), main, "autobouquetsmakermaker", 10)]
	else:
		return []


def AutoBouquetsMakerWakeupTime():
	print("[AutoBouquetsMaker] next wake up due %d" % (config.autobouquetsmaker.schedule.value and config.autobouquetsmaker.schedulewakefromdeep.value and config.autobouquetsmaker.nextscheduletime.value > 0 and config.autobouquetsmaker.nextscheduletime.value or -1))
	return config.autobouquetsmaker.schedule.value and config.autobouquetsmaker.schedulewakefromdeep.value and config.autobouquetsmaker.nextscheduletime.value > 0 and config.autobouquetsmaker.nextscheduletime.value or -1


def Plugins(**kwargs):
	plist = []
	if any([nimmanager.hasNimType(x) for x in ("DVB-S", "DVB-T", "DVB-C")]):
		plist.append(PluginDescriptor(name="AutoBouquetsMakerSessionStart", where=[PluginDescriptor.WHERE_AUTOSTART, PluginDescriptor.WHERE_SESSIONSTART], fnc=Scheduleautostart, wakeupfnc=AutoBouquetsMakerWakeupTime, needsRestart=True))
		plist.append(PluginDescriptor(name=_("AutoBouquetsMaker"), description="Scan and create bouquets.", where=PluginDescriptor.WHERE_MENU, fnc=AutoBouquetsMakerSetup, needsRestart=True))
		if config.autobouquetsmaker.extensions.getValue():
			plist.append(PluginDescriptor(name=_("AutoBouquetsMaker Scanner"), description="Scan and create bouquets.", where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=startscan, needsRestart=True))
	return plist
