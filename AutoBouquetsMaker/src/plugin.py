from __future__ import absolute_import, print_function
from os import makedirs
from os.path import exists, join, realpath

from Components.config import ConfigClock, ConfigEnableDisable, ConfigNumber, ConfigSelection, ConfigSubDict, ConfigSubsection, ConfigText, ConfigYesNo, NoSave, config
from Components.NimManager import nimmanager
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import SCOPE_CONFIG, resolveFilename

from . import _
from .scanner.main import Scheduleautostart

config.autobouquetsmaker = ConfigSubsection()
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
config.autobouquetsmaker.extraservices = ConfigText("", False)
config.autobouquetsmaker.extra_debug = ConfigYesNo(default=False)
config.autobouquetsmaker.frequencyfinder = ConfigYesNo(default=False)
config.autobouquetsmaker.FTA_only = ConfigText("", False)

user_providers_dir = join(realpath(resolveFilename(SCOPE_CONFIG)), "AutoBouquetsMaker", "providers")
user_custom_dir = join(realpath(resolveFilename(SCOPE_CONFIG)), "AutoBouquetsMaker", "custom")
if not exists(user_providers_dir):
	makedirs(user_providers_dir, mode=0o755)
if not exists(user_custom_dir):
	makedirs(user_custom_dir, mode=0o755)


def main(session, **kwargs):
	from .menu import AutoBouquetsMaker_Menu  # Load the setup screens only when opened.
	session.open(AutoBouquetsMaker_Menu)


def startscan(session, **kwargs):
	from .scanner.scan import AutoBouquetsMaker  # Load the scanner only when a scan starts.
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
		plist.append(PluginDescriptor(name=_("AutoBouquetsMaker"), description=_("Scan and create bouquets."), where=PluginDescriptor.WHERE_MENU, fnc=AutoBouquetsMakerSetup, needsRestart=True))
		if config.autobouquetsmaker.extensions.getValue():
			plist.append(PluginDescriptor(name=_("AutoBouquetsMaker Scanner"), description=_("Scan and create bouquets."), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=startscan, needsRestart=True))
	return plist


def __getattr__(name):
	if name == "AutoBouquetsMaker":
		from .scanner.scan import AutoBouquetsMaker  # Keep external scan screen imports compatible.
		return AutoBouquetsMaker
	if name == "AutoBouquetsMaker_Menu":
		from .menu import AutoBouquetsMaker_Menu  # Keep external setup screen imports compatible.
		return AutoBouquetsMaker_Menu
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
