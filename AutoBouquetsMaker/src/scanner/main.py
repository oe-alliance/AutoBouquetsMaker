from __future__ import absolute_import, print_function
from time import localtime, mktime, strftime, time

from enigma import eTimer

from Components.config import config, configfile
from Screens.MessageBox import MessageBox

from .. import _, log


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

		self.addNetworkTimeCallback()

	def __getattr__(self, name):
		if name == "itemtorun":
			from .scan import AutoBouquetsMaker  # Load the scanner only when a scheduled scan runs.
			self.itemtorun = AutoBouquetsMaker
			return self.itemtorun
		raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

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
		from Screens.Standby import inStandby, TryQuitMainloop, inTryQuitMainloop
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

	def addNetworkTimeCallback(self):
		try:
			from Components.NetworkTime import ntpsyncpoller
			ntpsyncpoller.addTimeUpdatedCallback(self.timeCallback)
		except Exception as err:
			print("[%s][doneConfiguring] addNetworkTimeCallback\nError:\n" % self.schedulename, err)

	def timeCallback(self):
		print("[ABM-Scheduler][timeCallback] Clock update detected; updating timers")
		if AutoScheduleTimer.instance is not None:
			AutoScheduleTimer.instance.doneConfiguring()


def __getattr__(name):
	if name == "AutoBouquetsMaker":
		from .scan import AutoBouquetsMaker  # Preserve the public scan screen import.
		return AutoBouquetsMaker
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
