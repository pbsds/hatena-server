#Settings:
useWSGI = False#not fully tested and WILL NOT support multible instances/workers with the plaintext database
port = 8080

#import:
print "Importing modules...",
from twisted.web import server#filehost
from twisted.internet import reactor
if useWSGI: from twisted.application import internet, service

import sys, time, os, atexit
print "Done!"

#set working directory
if os.path.dirname(__file__):
	os.chdir(os.path.dirname(__file__))
else:
	for i in sys.path:
		path = os.path.split(i)[0]
		if not os.path.exists(os.path.join(path, "server.py")): continue
		if not os.path.exists(os.path.join(path, "hatena.py")): continue
		if not os.path.exists(os.path.join(path, "DB.py")): continue
		os.chdir(path)
		break
	else:
		print "Can't force working directory, may fail crash!"

#Logging
class Log:
	class filesplit:#a file object writing to two outputs
		def __init__(self):
			self.files = []
		def write(self, data):
			for i in self.files: i.write(data)
		def flush(self):#ipython needs this
			pass
	def __init__(self):
		minutes, seconds = map(int, time.strftime("%M %S").split(" "))
		minutes = 59 - minutes
		seconds = 59 - seconds
		reactor.callLater(60*minutes + seconds + 5, self.HandleUpdate)
		reactor.callLater(60*5, self.AutoFlush)
		
		#make year folder
		if not os.path.exists("logs/"+time.strftime("%Y")):
			os.mkdir("logs/"+time.strftime("%Y"))
		
		#make month folder
		if not os.path.exists("logs/"+time.strftime("%Y/%B")):
			os.mkdir("logs/"+time.strftime("%Y/%B"))
		
		self.Activityhandle = open(time.strftime("logs/%Y/%B/%d %B activity.log"),"a")
		self.Errorhandle = open(time.strftime("logs/%Y/%B/%d %B error.log"),"a")
		
		self.stderr = sys.stderr
		sys.stderr = self.filesplit()
		sys.stderr.files.append(self.stderr)
		sys.stderr.files.append(self.Errorhandle)
		
		self.write("Server startup...\n", True)
	def HandleUpdate(self):#Automatically updates the handles for new filenames every hour
		reactor.callLater(60*60, self.HandleUpdate)
		
		print time.strftime("[%H:%M:%S] Handle update")
		
		#make year folder
		if not os.path.exists("logs/"+time.strftime("%Y")):
			os.mkdir("logs/"+time.strftime("%Y"))
		
		#make month folder
		if not os.path.exists("logs/"+time.strftime("%Y/%B")):
			os.mkdir("logs/"+time.strftime("%Y/%B"))
		
		self.close()
		
		self.Activityhandle = open(time.strftime("logs/%Y/%B/%d %B activity.log"),"a")
		self.Errorhandle = open(time.strftime("logs/%Y/%B/%d %B error.log"),"a")
		
		sys.stderr.files[1] = self.Errorhandle
	def AutoFlush(self):#Automatically flushes the files 5 minutes between
		reactor.callLater(60*5, self.AutoFlush)
		self.flush()
	def flush(self):#Flushes to the files
		self.Activityhandle.flush()
		os.fsync(self.Activityhandle.fileno())
		
		self.Errorhandle.flush()
		os.fsync(self.Errorhandle.fileno())
	def close(self):
		self.Activityhandle.close()
		self.Errorhandle.close()
	#=====
	def write(self, String, Silent=False):
		if not Silent:
			print time.strftime("[%H:%M:%S]"), String
		self.Activityhandle.write(time.strftime("[%H:%M:%S] ") + String + "\n")
	Print = write
Log = Log()

#init database:
print "Initializing flipnote database...",
import DB
print "Done!"

#Setup hatena server:
print "Setting up hatena site...",
import hatena
hatena.ServerLog = Log
site = server.Site(hatena.Setup())
print "Done!"


#make the hatena server accept proxy connections:
print "Setting up proxy hack...",
silent = True
old_lineReceived = site.protocol.lineReceived
def lineReceived(self, line):
	if not silent: print line
	if line[:31] == "GET http://flipnote.hatena.com/":
		line = "GET " + line[30:]
		if not silent: print line
	elif line[:32] == "POST http://flipnote.hatena.com/":
		line = "POST " + line[31:]
		if not silent: print line
	old_lineReceived(self, line)
site.protocol.lineReceived = lineReceived
print "Done!"

#run!
print "Server start!\n"
if useWSGI:
	application = service.Application('web')
	sc = service.IServiceCollection(application)
	internet.TCPServer(port, site).setServiceParent(sc)
	
	atexit.register(Log.write, String="Server shutdown", Silent=True)
else:
	reactor.listenTCP(port, site)#Hey listen!~
	reactor.run()
	
	#dunn
	Log.write("Server shutdown", True)