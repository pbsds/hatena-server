from twisted.internet import reactor
import atexit, os
from Hatenatools import TMB

#The database handling flipnote files and info
#this one stores them in plaintext, only works with one server worker
class Database:
	def __init__(self):
		#read database stuff into memory:
		if os.path.exists("database/new_flipnotes.dat"):
			f = open("database/new_flipnotes.dat", "rb")#contains the newest 5000 flipnotes
			file = f.read()
			f.close()
		else:
			file = ""
		
		if file:
			self.Newest = [tuple(i.split("\t")) for i in file.split("\n")]#[i] = [creatorID, filename]
		else:
			self.Newest = []
		
		self.Creator = {}#to store creator info updates before writing to disk. Creator[id][n] = [filename, views, stars, green stars, red stars, blue stars, purple stars, Channel, Downloads]
		
		#to check if an update is neccesary(caching):
		self.new = False#True when new flipnotes has been uploaded
		self.Views = 0
		self.Stars = 0
		self.Downloads = 0
		
		#schtuff
		reactor.callLater(60*3, self.flusher)
		atexit.register(self.write)
	def flusher(self):#Automatically flushes the files every 3 minutes and trims down memory usage
		reactor.callLater(60*3, self.flusher)
		self.write()
	def write(self):
		if self.new:
			#trim newest:
			if len(self.Newest) > 5000:
				self.Newest = self.Newest[:5000]
			
			#write to file:
			f = open("database/new_flipnotes.dat", "wb")
			f.write("\n".join(("\t".join(i) for i in self.Newest)))
			f.close()
			self.new = False
		
		#write creator changes to file:
		for ID in self.Creator.keys():
			f = open("database/Creators/%s/flipnotes.dat" % ID, "wb")
			f.write("\n".join(("\t".join(map(str, i)) for i in self.Creator[ID])))
			f.close()
			del self.Creator[ID]
	#interface:
	def CreatorExists(self, CreatorID):
		return os.path.exists("database/Creators/" + CreatorID) or (CreatorID in self.Creator)
	def FlipnoteExists(self, CreatorID, filename):
		return os.path.exists(self.FlipnotePath(CreatorID, filename))
	def GetCreator(self, CreatorID, Store=False):#Returns a list of all the self.GetFlipnote(). "Store" holds it in memory for a while, use this when making changes or reading it often
		if CreatorID in self.Creator:
			return self.Creator[CreatorID]
		else:
			if not os.path.exists("database/Creators/" + CreatorID):
				return None
			
			f = open("database/Creators/%s/flipnotes.dat" % CreatorID, "rb")
			ret = [i.split("\t") for i in f.read().split("\n")]
			f.close()
			
			#update to newer format:
			#current format = [filename, views, stars, green stars, red stars, blue stars, purple stars, Channel, Downloads]
			for i in xrange(len(ret)):
				if len(ret[i]) < 9:
					filename = ret[i][0]#take this as a give for now
					for n, default in enumerate((filename, 0, 0, 0, 0, 0, 0, "", 0)):
						if len(ret[i]) <= n:
							ret[i].append(default)
			
			if Store:
				self.Creator[CreatorID] = ret
			
			return ret
	def GetFlipnote(self, CreatorID, filename, Store=False):#returns: [filename, views, stars, green stars, red stars, blue stars, purple stars, Channel, Downloads]
		for i in (self.GetCreator(CreatorID, Store) or []):
			if i[0] == filename:
				return i
		return False
	def GetFlipnotePPM(self, CreatorID, filename):#the ppm binary data
		f = open(self.FlipnotePath(CreatorID, filename), "rb")
		ret = f.read()
		f.close()
		return ret
	def GetFlipnoteTMB(self, CreatorID, filename):#the tmb binary data
		f = open(self.FlipnotePath(CreatorID, filename), "rb")
		ret = f.read(0x6a0)
		f.close()
		return ret
	def AddFlipnote(self, content, Channel=""):#content = ppm binary data
		tmb = TMB().Read(content)
		if not tmb:
			return False
		
		#CreatorID = tmb.Username
		CreatorID = tmb.EditorAuthorID
		filename = tmb.CurrentFilename[:-4]
		del tmb
		
		if self.FlipnoteExists(CreatorID, filename):#already exists
			return False
		
		#add to database:
		self.new = True
		self.Newest.insert(0, (CreatorID, filename))
		
		if not self.GetCreator(CreatorID, True):
			self.Creator[CreatorID] = [[filename, 0, 0, 0, 0, 0, 0, Channel, 0]]
		else:
			self.Creator[CreatorID].append([filename, 0, 0, 0, 0, 0, 0, Channel, 0])
		
		#write flipnote to file:
		if not os.path.isdir("database/Creators/" + CreatorID):
			os.mkdir("database/Creators/" + CreatorID)
		f = open(self.FlipnotePath(CreatorID, filename), "wb")
		f.write(content)
		f.close()
		
		return CreatorID, filename
	def AddView(self, CreatorID, filename):
		for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
			if flipnote[0] == filename:
				self.Creator[CreatorID][i][1] = int(flipnote[1]) + 1
				self.Views += 1
				return True
		return False
	def AddStar(self, CreatorID, filename, amount=1):#todo: add support for other colored stars
		for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
			if flipnote[0] == filename:
				self.Creator[CreatorID][i][2] = int(flipnote[2]) + amount
				self.Stars += 1
				return True
		return False
	def AddDownload(self, CreatorID, filename):
		for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
			if flipnote[0] == filename:
				self.Creator[CreatorID][i][8] = int(flipnote[8]) + 1
				self.Downloads += 1
				return True
		return False
	#internal helpers:
	def FlipnotePath(self, CreatorID, filename):#use self.GetFlipnotePPM() instead
		return "database/Creators/%s/%s.ppm" % (CreatorID, filename)
Database = Database()#is loaded, yesth!