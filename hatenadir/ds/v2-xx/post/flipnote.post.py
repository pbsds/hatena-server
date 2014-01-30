from twisted.web import resource
from twisted.internet import reactor
import time

from hatena import ServerLog, Silent
from DB import Database
from Hatenatools import TMB

#Handle flipnote uploads
class PyResource(resource.Resource):
	isLeaf = True
	def render_GET(self, request):
		ServerLog.write("%s got 403 when requesting post/flipnote.post with GET" % (request.getClientIP()), Silent)
		
		request.setResponseCode(405)
		return "405 - Method Not Allowed"
	def render_POST(self, request):#implement channels?
		data = request.content.read()
		
		channel = ""
		if "channel" in request.args:
			channel = request.args["channel"][0]
		
		add = Database.AddFlipnote(data, channel)
		if add:
			ServerLog.write("%s successfully uploaded \"%s.ppm\"" % (request.getClientIP(), add[1]), Silent)
			request.setResponseCode(200)
		else:
			ServerLog.write("%s tried to upload a flipnote, but failed..." % request.getClientIP(), Silent)
			request.setResponseCode(500)#only causes an error, need to fix
		
		return ""
	#===