from twisted.web import static, resource
import sys, os, imp

from Hatenatools import *#UGO, PPM, TMB and NTFT
#from DB import Database#flipnote handler
#from DB import Database#flipnote handler
ServerLog = None#Is set to the log class by server.py

Silent = False
def Log(request, path=None, silent=Silent):
	if not path:
		path = "\"%s\"" % request.path
	ServerLog.write("%s requested %s" % (request.getClientIP(), path), Silent)

#Responses:
class AccessDenied(resource.Resource):
	isLeaf = True
	def render(self, request):
		ServerLog.write("%s got 403 when requesting \"%s\"" % (request.getClientIP(), request.path), Silent)
		print "debug:",request.getAllHeaders()
		
		request.setResponseCode(403)
		return "403 - Access denied\nThis proxy is only allowed to use for Flipnote Hatena for the DSi."
AccessDenied = AccessDenied()
class NotFound(resource.Resource):
	isLeaf = True
	def render(self, request):
		args = "&".join(("%s=%s" % (i, request.args[i][0]) for i in request.args))
		path = ("%s?%s" % (request.path, args)) if args else request.path
		
		ServerLog.write("%s got 404 when requesting \"%s\"" % (request.getClientIP(), path), Silent)
		request.setResponseCode(404)
		return "404 - Not Found\nThis proxy is only allowed to use for Flipnote Hatena for the DSi."
NotFound = NotFound()
class ConnectionTest(resource.Resource):#used for people setting up the proxy in their DSi. It's nice to see it's actually working.
	#http://conntest.nintendowifi.net/
	isLeaf = True
	def render(self, request):
		ServerLog.write("%s performed a connection test" % request.getClientIP(), True)
		request.responseHeaders.setRawHeaders('X-Organization', ['Nintendo'])#i hope this isn't illegal...
		return '<html><head><title>HTML Page</title></head><body bgcolor="#FFFFFF">This is test.html page</body></html>'
ConnectionTest = ConnectionTest()

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
			if "host" in request.getAllHeaders():
				if request.getAllHeaders()["host"] == "conntest.nintendowifi.net":
					return ConnectionTest
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
		if request.getHost() == "conntest.nintendowifi.net":
			return ConnectionTest
		Log(request, "root")
		return "Welcome to hatena.pbsds.net!\nThis is still in early stages, so please don't expect too much."
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
		
		LoadHatenadirStructure(self)
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
		return "I am a folder, but I'm to lazy to list my contents..."
def LoadHatenadirStructure(Resource, path=os.path.join("hatenadir", "ds", "v2-xx")):
	for root, dirs, files in os.walk(path):
		if root <> path: continue#use recursion instead
		for filename in files:
			filetype = filename.split(".")[-1].lower()
			os.path.join(path, filename)
			
			if filetype == "ugoxml":
				Resource.putChild(filename[:-3], UGOXMLResource(os.path.join(path, filename)))
			elif filetype == "py":
				try:
					pyfile = imp.load_source("pyfile", os.path.abspath(os.path.join(path, filename)))
				except ImportError as err:
					pyfile = None
					print "Error!"
					print "Failed to import the python file \"%s\"" % os.path.join(path, filename)
					print err
				
				if pyfile:
					Resource.putChild(filename[:-3], pyfile.PyResource())
			elif filetype == "pyc":
				pass#ignore
			else:
				Resource.putChild(filename, FileResource(os.path.join(path, filename)))
		for foldername in dirs:# os.path.isdir(i):
			if foldername[:2] <> "__":
				folder = FolderResource()
				LoadHatenadirStructure(folder, os.path.join(path, foldername))
				Resource.putChild(foldername, folder)

#when loading:
def Setup():
	root = Root()
	return root























