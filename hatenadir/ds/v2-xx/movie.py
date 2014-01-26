from twisted.web import resource
import os

from hatena import Database, Log, ServerLog, Silent, NotFound

detailsHMTL = """uguu"""


#The movie folder:
class PyResource(resource.Resource):
	isLeaf = False
	def __init__(self):
		resource.Resource.__init__(self)
		
		self.CreatorID = CreatorID()
	def getChild(self, name, request):
		if Database.CreatorExists(name):
			return self.CreatorID
		elif name == "":
			return self
		else:
			return NotFound
	def render(self, request):
		request.setResponseCode(403)
		return "403 - Denied access"

#The creator ID folder:
class CreatorID(resource.Resource):
	isLeaf = False
	def __init__(self):
		resource.Resource.__init__(self)
		
		self.CreatorIDFile = CreatorIDFile()
	def getChild(self, name, request):
		CreatorID = request.path.split("/")[-2]
		filename = ".".join(name.split(".")[:-1])
		
		if Database.FlipnoteExists(CreatorID, filename):#html, ppm and info
			return self.CreatorIDFile
		elif name == "":
			return self
		else:
			return NotFound
	def render(self, request):
		request.setResponseCode(403)
		return "403 - Denied access"

#Any public file inside creator ID folder:
class CreatorIDFile(resource.Resource):
	isLeaf = True
	def __init__(self):
		resource.Resource.__init__(self)
	def render(self, request):
		creator, file = request.path.split("/")[-2:]
		filetype = file.split(".")[-1].lower()
		
		if filetype == "ppm":
			#log it:
			path = "/".join(request.path.split("/")[3:])
			Log(request, path)
			
			#add a view:
			Database.AddView(creator, file[:-4])
			
			#read ppm file:
			f = open(Database.FlipnotePath(creator, file), "rb")
			data = f.read()
			f.close()
			
			#send file to client:
			request.responseHeaders.setRawHeaders('content-type', ['text/plain'])
			return data
		elif filetype == "info":
			path = "/".join(request.path.split("/")[3:])
			Log(request, path)
			request.responseHeaders.setRawHeaders('content-type', ['text/plain'])
			return "0\n0\n"#undocumented what it means
		elif filetype == "htm":#not yet implemented
			
			
			#ret = detailsHMTL[:]
			#ret.replace("%%CreatorID%%", creator)
			#ret.replace("%%Filename%%", file[:-4])#without the ext
			#ret.replace("%%%%", )
			#ret.replace("%%%%", )
			
			return "Not yet implemented"
		else:
			path = "/".join(request.path.split("/")[3:])
			ServerLog.write("%s got 403 when requesting " % (request.getClientIP(), path), Silent)
			
			request.setResponseCode(403)
			return "403 - Denied access"