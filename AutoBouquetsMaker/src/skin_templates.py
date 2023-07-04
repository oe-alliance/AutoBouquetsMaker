# This is work in progress. The aim of this file is to create a common template
# so the look and feel of all ABM embedded screens is uniform

# screen has always been 600 x 500 so stick with that.
# button size was always 140 x 40 so stick with that.
# use 8 px margin either side of buttons and 4 px margin above and below
# button bar width = 8 + 140 + 8 + 140 + 8 + 140 + 8 + 140 + 8 = 600
# button bar height = 4 + 40 + 4 = 48

from __future__ import print_function

import os
from enigma import getDesktop

# Set this to True to print the embedded skins.
# This debug is printed on enigma2 startup, not when using the plugin.
extraDebug = False

# values common to all templates
fontSize = 22
menuFontSize = fontSize + 2
descriptionsFontSize = fontSize - 2  # hints texts
windowWidth = 600  # button bar needs a minimum of 600
marginTop = 2  # for config lists
marginTopTexts = 10  # for text windows
marginLeft = 8
buttonWidth = 140  # this is the real width of the buttons graphics
buttonHeight = 40  # this is the real height of the buttons graphics
buttonMargin = 8
buttonMarginBottom = 4
configListLength = 15  # minimum 15. changing this should force the window height change in all screens without breaking anything.
configItemHeight = 30
configItemHeightMainMenu = 40

# dynamic variables
windowHeight = (configListLength * configItemHeight) + marginTop + buttonHeight + (buttonMarginBottom * 2)  # 500 based on configListLength = 15
widgetWidth = windowWidth - (marginLeft * 2)

# These button colours have been selected specially so anti-aliasing around the button
# text will be done to the correct shade. This is necessary even though the button text
# widget is transparent, to avoid a black halo around the button text.
colours = {"red": 0x9f1313, "green": 0x1f771f, "yellow": 0xa08500, "blue": 0x18188b}


def insertValues(xml, values):
	# The skin template is designed for a HD screen so the scaling factor is 720.
	# double negative to round up not round down
	return xml % tuple([int(-(x * getDesktop(0).size().height() // (-720))) for x in values])


def header():
	headerXML = '\n<screen position="center,center" size="%d,%d">'
	headerValues = [windowWidth, windowHeight]
	return insertValues(headerXML, headerValues)


def footer():
	return "\n</screen>"


def buttonBar():
	buttonFontSize = fontSize + 1
	buttonBarElevation = buttonHeight + buttonMarginBottom
	buttonPath = "%s/images/" % os.path.dirname(os.path.realpath(__file__))
	buttonBarXML = ''.join(['\n\t<widget name="key_' + c + '" conditional="key_' + c + '" position="%d,e-%d" size="%d,%d" valign="center" halign="center" font="Regular;%d" backgroundColor="#' + "%x" % colours[c] + '" foregroundColor="#ffffff" transparent="1" zPosition="+2"/>\n\t<ePixmap name="' + c + '" conditional="key_' + c + '" position="%d,e-%d" size="%d,%d" pixmap="' + buttonPath + 'key_' + c + '.png" transparent="1" zPosition="+1" alphatest="on" scale="1"/>' for c in ("red", "green", "yellow", "blue")])
	buttonBarValues = []
	for x in range(4):
		buttonBarValues += [buttonMargin + ((buttonWidth + buttonMargin) * x), buttonBarElevation, buttonWidth, buttonHeight, buttonFontSize, buttonMargin + ((buttonWidth + buttonMargin) * x), buttonBarElevation, buttonWidth, buttonHeight]
	return insertValues(buttonBarXML, buttonBarValues)


def templateOne():
	# templateOne is for hidesections and keepbouquets
	templateOneHeight = configItemHeight * configListLength  # make the template 15 lines high
	templateOneXML = """
	<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand">
		<convert type="TemplatedMultiContent">
			{"template": [
				MultiContentEntryPixmapAlphaTest(pos = (%d, %d), size = (%d, %d), flags = BT_SCALE, png = 0),
				MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_TOP, text = 1),
				MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_TOP, text = 2),
				],
				"fonts": [gFont("Regular", %d)],
				"itemHeight": %d
			}
		</convert>
	</widget>"""
	templateOneValues = [
		marginLeft, marginTop, widgetWidth, templateOneHeight,  # templateOneXML line 1
		2, 1, 25, 24,  # templateOneXML line 4
		35, 2, 300, configItemHeight - 2,  # templateOneXML line 5
		350, 2, 210, configItemHeight - 2,  # templateOneXML line 6
		fontSize,
		configItemHeight
	]
	return insertValues(templateOneXML, templateOneValues)


def templateTwo():
	# template two is for the main menu
	templateTwoWidgetHeight = configItemHeightMainMenu * 11  # make the template 11 lines high. Currently there are 9 menu items.
	templateTwoXML = """
	<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand">
		<convert type="TemplatedMultiContent">
			{"template": [
				MultiContentEntryPixmapAlphaTest(pos = (%d, %d), size = (%d, %d), flags = BT_SCALE, png = 0),
				MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_TOP, text = 1),
				],
				"fonts": [gFont("Regular", %d)],
				"itemHeight": %d
			}
		</convert>
	</widget>"""
	templateTwoValues = [
		marginLeft, marginTop, widgetWidth, templateTwoWidgetHeight,  # templateTwoXML line 1
		2, 4, 32, 32,  # templateTwoXML line 4
		44, 4, 530, configItemHeightMainMenu - 4,  # templateTwoXML line 5
		menuFontSize,
		configItemHeightMainMenu
	]
	return insertValues(templateTwoXML, templateTwoValues)


def templateThree():
	# template three is for about
	# "oea logo" is fixed size from plugin image folder, 176 x 142

	templateThreeXML = """
	<widget name="about" conditional="about" position="%d,%d" size="%d,%d" font="Regular;%d" transparent="1"/>
	<widget name="oealogo" conditional="oealogo" position="e-%d-176,e-%d-142" size="176,142" zPosition="-1" transparent="1" alphatest="blend"/>"""
	templateThreeValues = [
		marginLeft, marginTopTexts, widgetWidth, configItemHeight * configListLength, fontSize,  # templateThreeXML line 1
		buttonMargin, buttonMarginBottom  # templateThreeXML line 2
	]
	return insertValues(templateThreeXML, templateThreeValues)


def templateFour():
	# template four is for ordering
	templateFourHeight = configItemHeight * configListLength  # make the template 15 lines high
	templateFourXML = """
	<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand">
		<convert type="TemplatedMultiContent">
			{"template": [
				MultiContentEntryText(pos = (%d, %d), size = (%d, %d), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_TOP, text = 0),
				],
				"fonts": [gFont("Regular", %d)],
				"itemHeight": %d
			}
		</convert>
	</widget>
	<widget name="pleasewait" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" valign="center" transparent="0" zPosition="+1"/>"""
	templateFourValues = [
		marginLeft, marginTop, widgetWidth, templateFourHeight,  # templateFourXML line 1
		2, 2, widgetWidth - 4, configItemHeight - 2,  # templateFourXML line 4
		fontSize,
		configItemHeight,
		0, templateFourHeight // 2, widgetWidth, configItemHeight, fontSize  # templateFourXML line 11
	]
	return insertValues(templateFourXML, templateFourValues)


def templateFive():
	# template five is for log
	templateFiveXML = '\n\t<widget name="list" position="%d,%d" size="%d,%d" itemHeight="%d" font="Regular;%d" scrollbarMode="showOnDemand"/>'
	templateFiveValues = [
		marginLeft, marginTop, widgetWidth, configItemHeight * configListLength, configItemHeight, fontSize  # templateFiveXML line 1
	]
	return insertValues(templateFiveXML, templateFiveValues)


def templateSix():
	# template six is for setup
	templateSixHeight = configItemHeight * (configListLength - 5)  # leave 5 lines for description widget
	templateSixDescHeight = configItemHeight * 4  # make the description 4 lines high
	templateSixXML = """
	<widget name="config" position="%d,%d" size="%d,%d" itemHeight="%d" font="Regular;%d" scrollbarMode="showOnDemand"/>
	<widget name="description" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" valign="top" transparent="0"/>
	<widget name="pleasewait" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" valign="center" transparent="0" zPosition="+1"/>"""
	templateSixValues = [
		marginLeft, marginTop, widgetWidth, templateSixHeight, configItemHeight, fontSize,  # templateSixXML line 1
		marginLeft, templateSixHeight + configItemHeight, widgetWidth, templateSixDescHeight, descriptionsFontSize,  # templateSixXML line 3
		0, templateSixHeight // 2, widgetWidth, configItemHeight, fontSize  # templateSixXML line 3
	]
	return insertValues(templateSixXML, templateSixValues)


def downloadBar():
	# download bar is for scanner, frequency finder, update proviers
	downloadBarHeight = 36
	textBoxHeight = 30
	textBoxTopMargin = 4
	actionBoxLeftAlign = 7
	actionBoxWidth = 433
	statusBoxLeftAlign = 466
	statusBoxWidth = 433
	lockImageLeftAlign = 929
	lockImageTopMargin = 3
	lockImageWidth = 25
	lockImageHeight = 24
	tunerLetterLeftAlign = 955
	tunerLetterWidth = fontSize
	snrBoxLeftAlign = 980
	snrBoxWidth = 87  # up to 7 chars, e.g. "16.2 dB"
	progressTextBoxLeftAlign = 1080
	progressTextBoxWidth = 87
	progressPercentLeftAlign = 1187
	progressPercentBoxWidth = 73
	downloadBarXML = """
	<screen name="DownloadBar" position="0,0" size="%d,%d" flags="wfNoBorder" backgroundColor="#54111112">
		<widget name="action" position="%d,%d" size="%d,%d" font="Regular;%d" transparent="1" foregroundColor="#ffffff"/>
		<widget name="status" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" transparent="1" foregroundColor="#ffffff"/>
		<widget source="Frontend" conditional="Frontend" render="Pixmap" pixmap="icons/lock_on.png" position="%d,%d" size="%d,%d" alphatest="on" scale="1">
			<convert type="FrontendInfo">LOCK</convert>
			<convert type="ConditionalShowHide"/>
		</widget>
		<widget source="Frontend" conditional="Frontend" render="Pixmap" pixmap="icons/lock_off.png" position="%d,%d" size="%d,%d" alphatest="on" scale="1">
			<convert type="FrontendInfo">LOCK</convert>
			<convert type="ConditionalShowHide">Invert</convert>
		</widget>
		<widget name="tuner_text" conditional="tuner_text" position="%d,%d" size="%d,%d" font="Regular;%d" halign="center" transparent="1" foregroundColor="#ffffff"/>
		<widget source="Frontend" conditional="Frontend" render="Label" position="%d,%d" size="%d,%d" font="Regular;%d" halign="left" transparent="1" foregroundColor="#ffffff">
			<convert type="FrontendInfo">SNRdB</convert>
		</widget>
		<widget source="progress_text" render="Label" position="%d,%d" size="%d,%d" font="Regular;%d" halign="right" transparent="1" foregroundColor="#ffffff">
			<convert type="ProgressToText">InText</convert>
		</widget>
		<widget source="progress_text" render="Label" position="%d,%d" size="%d,%d" font="Regular;%d" halign="left" transparent="1" foregroundColor="#ffffff">
			<convert type="ProgressToText">InPercent</convert>
		</widget>
	</screen>"""
	downloadBarValues = [
		getDesktop(0).size().width(), downloadBarHeight,  # downloadBarXML line 1, "screen" element
		actionBoxLeftAlign, textBoxTopMargin, actionBoxWidth, textBoxHeight, fontSize,  # downloadBarXML line 2, "action" widget
		statusBoxLeftAlign, textBoxTopMargin, statusBoxWidth, textBoxHeight, fontSize,  # downloadBarXML line 3, "status" widget
		lockImageLeftAlign, lockImageTopMargin, lockImageWidth, lockImageHeight,  # downloadBarXML, "lock_on" widget
		lockImageLeftAlign, lockImageTopMargin, lockImageWidth, lockImageHeight,  # downloadBarXML, "lock_off" widget
		tunerLetterLeftAlign, textBoxTopMargin, tunerLetterWidth, textBoxHeight, fontSize,  # downloadBarXML, "tuner letter" widget
		snrBoxLeftAlign, textBoxTopMargin, snrBoxWidth, textBoxHeight, fontSize,  # downloadBarXML, "SNR" widget
		progressTextBoxLeftAlign, textBoxTopMargin, progressTextBoxWidth, textBoxHeight, fontSize,  # downloadBarXML, "progress text" widget
		progressPercentLeftAlign, textBoxTopMargin, progressPercentBoxWidth, textBoxHeight, fontSize,  # downloadBarXML, "progress percent" widget
	]
	return insertValues(downloadBarXML, downloadBarValues)

# ------------------------------------------------------------------


def skin_mainmenu():
	skin = header() + buttonBar() + templateTwo() + footer()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_mainmenu:", skin)
	return skin


def skin_about():
	skin = header() + buttonBar() + templateThree() + footer()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_about:", skin)
	return skin


def skin_hidesections():
	skin = header() + buttonBar() + templateOne() + footer()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_hidesections:", skin)
	return skin


def skin_keepbouquets():
	return skin_hidesections()


def skin_log():
	skin = header() + buttonBar() + templateFive() + footer()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_log:", skin)
	return skin


def skin_ordering():
	skin = header() + buttonBar() + templateFour() + footer()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_ordering:", skin)
	return skin


def skin_setup():
	skin = header() + buttonBar() + templateSix() + footer()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_setup:", skin)
	return skin


def skin_downloadBar():
	skin = downloadBar()
	if extraDebug:
		print("[ABM-SkinTemplates] skin_downloadBar:", skin)
	return skin
