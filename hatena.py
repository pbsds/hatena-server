from twisted.web import static, resource
from twisted.internet import reactor
import sys, os, atexit, glob, imp

from Hatenatools import *#UGO, PPM, TMB and NTFT
ServerLog = None#Is set to the log class by server.py

Silent = False
def Log(request, path=None):
	if not path:
		path = "\"%s\"" % request.path
	ServerLog.write("%s requested %s" % (request.getClientIP(), path), Silent)

#Responses:
class AccessDenied(resource.Resource):
	isLeaf = True
	def render(self, request):
		ServerLog.write("%s got 403 when requesting \"%s\"" % (request.getClientIP(), request.path), Silent)
		
		request.setResponseCode(403)
		return "403 - Access denied\nThis proxy is only for Flipnote Hatena for the DSi."
AccessDenied = AccessDenied()
class NotFound(resource.Resource):
	isLeaf = True
	def render(self, request):
		args = "&".join(("%s=%s" % (i, request.args[i][0]) for i in request.args))
		path = ("%s?%s" % (request.path, args)) if args else request.path
		
		ServerLog.write("%s got 404 when requesting \"%s\"" % (request.getClientIP(), path), Silent)
		request.setResponseCode(404)
		return "404 - Not Found\nThis proxy is only for Flipnote Hatena for the DSi."
NotFound = NotFound()

#Root structure:
class Root(resource.Resource):#filters out non-hantena clients
	isLeaf = False
	def __init__(self):
		resource.Resource.__init__(self)
		
		self.dsResource = ds()
		self.cssResource = static.File("hatenadir/css/")
		self.imagesResource = static.File("hatenadir/images/")
	def getChild(self, name, request):
		if "x-dsi-sid" not in request.getAllHeaders():
			return AccessDenied
		
		if name == "ds":
			return self.dsResource
		elif name == "css":
			return self.cssResource
		elif name == "images":
			return self.imagesResource
		elif name == "":
			return self
		
		#return NotFound
		return self
	def render(self, request):
		Log(request, "root")
		return "Welcome to hatena.pbsds.net!\nThis is in early stages, so please don't expect too much."
class ds(resource.Resource):#child of Root
	isLeaf = False
	def __init__(self):
		resource.Resource.__init__(self)
		
		self.region = UgoRoot()
		self.regions = ("v2-xx", "v2-eu", "v2-us", "v2-jp")
	def getChild(self, name, request):
		if name in self.regions:
			return self.region
		elif name == "":
			return self
		return NotFound
	def render(self, request):
		Log(request)
		return "ds desu"
class UgoRoot(resource.Resource):#child of ds. (v2-xx)
	isLeaf = False
	def __init__(self):
		resource.Resource.__init__(self)
		
		LoadHatenaStructure(self)
	def getChild(self, name, request):
		if name == "":
			return self
		return NotFound
	def render(self, request):
		Log(request, "ugoroot")
		return "UgoRoot desu"

#UgoRoot filestructure:
class FileResource(resource.Resource):
	isLeaf = True
	def __init__(self, filepath, Store=False):
		resource.Resource.__init__(self)
		
		self.Store = Store
		
		if Store:
			f = open(filepath, "rb")
			self.file = f.read()
			f.close()
		else:
			self.file = filepath
		
		self.html = filepath.split(".")[-1][:3] == "htm"
	def render(self, request):
		path = "/".join(request.path.split("/")[3:])
		Log(request, path)
		
		if self.html:
			#request.responseHeaders.setRawHeaders('content-type', ['text/html'])
			pass
		else:
			request.responseHeaders.setRawHeaders('content-type', ['text/plain'])
		
		if self.Store:
			return self.file
		else:
			#f = open(self.file, "rb")
			#ret = f.read()
			#f.close()
			#return ret
			
			return static.File(self.file).render(request)
class UGOXMLResource(resource.Resource):
	isLeaf = True
	def __init__(self, filepath):
		resource.Resource.__init__(self)
		
		
		self.ugofile = UGO().ReadXML(filepath, False)
		self.ugofile = self.ugofile.Pack()
	def render(self, request):
		path = "/".join(request.path.split("/")[3:])
		Log(request, path)
		
		#page = int(request.args["page"][0]) if "page" in request.args else 1
		request.responseHeaders.setRawHeaders('content-type', ['text/plain'])
		return self.ugofile
class FolderResource(resource.Resource):
	isLeaf = False
	def getChild(self, name, request):
		if name == "":
			return self
		return NotFound
	def render(self, request):
		path = "/".join(request.path.split("/")[3:])
		Log(request, path)
		return "This is a folder, but I'm to lazy to list the contents..."
def LoadHatenaStructure(Resource, path="hatenadir/ds/v2-xx", root = True):
	for i in glob.glob("%s\*" % path):
		if os.path.isfile(i):
			filename = os.path.basename(i)
			filetype = filename.split(".")[-1].lower()
			
			if filetype == "ugoxml":
				Resource.putChild(filename[:-3], UGOXMLResource(i))
			elif filetype == "py":
				try:
					#sys.path.append(os.path.abspath(os.path.dirname(i)))
					# #pyfile = __import__(filename[:-3])
					#pyfile = importlib.import_module(filename[:-3])
					#sys.path.pop(-1)
					#pyfile = imp.load_module(i)
					
					pyfile = imp.load_source("pyfile", os.path.abspath(i))
				except ImportError as err:
					pyfile = None
					print "Error!"
					print "Failed to import the python file \"%s\"" % i
					print err
				
				if pyfile:
					Resource.putChild(filename[:-3], pyfile.PyResource())
			elif filetype == "pyc":
				pass#ignore
			else:
				Resource.putChild(filename, FileResource(os.path.join(path, filename)))
		elif os.path.isdir(i):
			if os.path.basename(i)[:2] <> "__":
				folder = FolderResource()
				LoadHatenaStructure(folder, os.path.join(path, os.path.basename(i)), False)
				Resource.putChild(os.path.basename(i), folder)

#Flipnote handler:
class Database:
	def __init__(self):
		#read:
		f = open("database/new_flipnotes.dat", "rb")#contains the newest 5000 flipnotes
		self.Newest = [tuple(i.split("\t")) for i in f.read().split("\n")]#[i] = [creatorID, filename]
		self.new = False#True when new flipnotes has been uploaded
		f.close()
		
		self.Creator = {}#to store creator info updates before writing to disk. Creator[id][n] = [filename, views, stars, green stars, red stars, blue stars, purple stars, Channel]
		
		reactor.callLater(60*3, self.flusher)
		atexit.register(self.write)
		
		#to check if an update is neccesary:
		self.Views = 0
		self.Stars = 0
	def flusher(self):#Automatically flushes the files every 3 minutes and trims down memory usage
		reactor.callLater(60*3, self.flusher)
		
		#trim newest:
		if len(self.Newest) > 5000:
			self.Newest = self.Newest[:5000]
		
		self.write()
	def write(self):
		if self.new:
			f = open("database/new_flipnotes.dat", "wb")
			f.write("\n".join(("\t".join(i) for i in self.Newest)))
			f.close()
			self.new = False
		
		for ID in self.Creator.keys():
			f = open("database/Creators/%s/flipnotes.dat" % ID, "wb")
			f.write("\n".join(("\t".join(map(str, i)) for i in self.Creator[ID])))
			f.close()
			del self.Creator[ID]
	#helpers:	
	def FlipnotePath(self, CreatorID, filename):
		return "database/Creators/%s/%s" % (CreatorID, filename)
	def CreatorExists(self, CreatorID):
		return os.path.exists("database/Creators/" + CreatorID) or (CreatorID in self.Creator)
	def FlipnoteExists(self, CreatorID, filename):
		return os.path.exists("database/Creators/%s/%s.ppm" % (CreatorID, filename))
	#interface:
	def GetCreator(self, CreatorID, Store=False):#"Store" holds it in memory, use this when making changes or reading it often
		if CreatorID in self.Creator:
			return self.Creator[CreatorID]
		else:
			if not os.path.exists("database/Creators/" + CreatorID):
				return None
			
			f = open("database/Creators/%s/flipnotes.dat" % CreatorID, "rb")
			ret = [i.split("\t") for i in f.read().split("\n")]
			f.close()
			
			if Store:
				self.Creator[CreatorID] = ret
			
			return ret
	def GetFlipnote(self, CreatorID, filename):#[filename, views, stars, green stars, red stars, blue stars, purple stars, Channel]
		for i in (self.GetCreator(CreatorID) or []):
			if i[0] == filename:
				return i
		return False
	def AddFlipnote(self, content, Channel=""):
		tmb = TMB().Read(content)
		if not tmb:
			return False
		
		#CreatorID = tmb.Username
		CreatorID = tmb.EditorAuthorID
		filename = tmb.CurrentFilename[:-4]
		del tmb
		
		if os.path.exists("database/Creators/%s/%s.ppm" % (CreatorID, filename)):#already exists
			return False
		
		#add to database:
		self.new = True
		self.Newest.insert(0, (CreatorID, filename))
		
		if not self.GetCreator(CreatorID, True):
			self.Creator[CreatorID] = [[filename, 0, 0, 0, 0, 0, 0, Channel]]
		else:
			self.Creator[CreatorID].append([filename, 0, 0, 0, 0, 0, 0, Channel])
		
		#write flipnote to file:
		if not os.path.isdir("database/Creators/" + CreatorID):
			os.mkdir("database/Creators/" + CreatorID)
		f = open("database/Creators/%s/%s.ppm" % (CreatorID, filename), "wb")
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
	def AddStar(self, CreatorID, filename, amount=1):
		for i, flipnote in enumerate(self.GetCreator(CreatorID, True) or []):
			if flipnote[0] == filename:
				self.Creator[CreatorID][i][2] = int(flipnote[2]) + amount
				self.Stars += 1
				return True
		return False
Database = Database()

#when loading:
def Setup():
	print "Setting up hatena...",
	root = Root()
	print "Done!"
	return root























