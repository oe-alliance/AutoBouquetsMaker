# One can simply use
# import log
# print>>log, "Some text"
# because the log unit looks enough like a file!
# Or in python 3, print("Some text", file=log)

import sys
import threading
from six import StringIO

logfile = StringIO()
# Need to make our operations thread-safe.
mutex = threading.Lock()


def write(data):
	mutex.acquire()
	try:
		if logfile.tell() > 18000:
			# Do a sort of 8k round robin
			logfile.seek(0)
		logfile.write(data)
	finally:
		mutex.release()
	sys.stdout.write(data)


def getvalue():
	mutex.acquire()
	try:
		pos = logfile.tell()
		head = logfile.read()
		logfile.seek(0)
		tail = logfile.read(pos)
	finally:
		mutex.release()
	return head + tail
