from twisted.web import server#filehost
from twisted.internet import reactor
import sys, time, os

#Logging
class Log:
	class filesplit:#a file object writing to two outputs
		def __init__(self):
			self.files = []
		def write(self, data):
			for i in self.files: i.write(data)
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

#Setup hatena server:
print "Setting up flipnote database..."
import hatena
hatena.ServerLog = Log
print "Setting up hatena site structure..."
site = server.Site(hatena.Setup())

#make the hatena server accept proxy coneections:
print "Setting up proxy hack..."
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

#run!
print "Server start!\n"
reactor.listenTCP(8080, site)#Hey listen!~
reactor.run()

#dunn
Log.write("Server shutdown", True)