from twisted.web import resource
from twisted.internet import reactor
import time

from hatena import Log, NotFound
from DB import Database
from Hatenatools import UGO

#makes a flipnote list of the most seen ones among the recently uploaded
class PyResource(resource.Resource):
	isLeaf = True
	def __init__(self):
		resource.Resource.__init__(self)
		
		self.pages = []#10 first pages
		self.newestview = None
		self.newestflip = None
		self.Update()
	def render(self, request):
		page = int(request.args["page"][0]) if "page" in request.args else 1
		
		if len(self.pages) >= page:
			path = "/".join(request.path.split("/")[3:])
			Log(request, "%s page %i" % (path, page))
			
			request.responseHeaders.setRawHeaders('content-type', ['text/plain'])
			return self.pages[page-1]
		else:
			return NotFound.render(request)
	#===
	def Update(self):#called every 15 minutes
		reactor.callLater(60*10, self.Update)
		
		if self.newestflip <> Database.Newest[0] or self.newestview <> Database.Views:
			self.newestflip = Database.Newest[0]
			self.newestview = Database.Views
			reactor.callInThread(self.UpdateThreaded, Database.Newest)
	def UpdateThreaded(self, flipnotes):#run in an another thread
		#sort the flipnotes by viewcount, affected by amount of stars
		def sort((i, (ID, flip))):
			views, stars = Database.GetFlipnote(ID, flip)[1:3]
			return int(views)*60 + int(stars)/4 - i
		flipnotes = map(lambda x: x[1], sorted(enumerate(flipnotes), key=sort)[::-1])[:500]
		
		#create pages:
		pages = []
		pagecount = (len(flipnotes)-1)/50 + 1
		if pagecount > 10: pagecount = 10#temp?
		flipcount = len(flipnotes) if len(flipnotes) < 500 else 500
		
		for i in xrange(pagecount):
			pages.append(self.MakePage(flipnotes[i*50:i*50+50], i+1, i<pagecount-1, flipcount))
		
		if self.pages:#not on startup
			print time.strftime("[%H:%M:%S] Updated hotmovies.ugo")
		self.pages = pages
	def MakePage(self, flipnotes, page, next, count):
		ugo = UGO()
		ugo.Loaded = True
		ugo.Items = []
		
		#meta
		ugo.Items.append(("layout", (2, 1)))
		ugo.Items.append(("topscreen text", ["Popular Flipnotes", "Flipnotes", str(count), "", "The most popular new Flipnotes."], 0))
		
		#categories
		ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/hotmovies.uls", "Most Popular", True))
		ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/likedmovies.uls", "Most Liked", False))
		#ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/recommended.uls", "Recommended", False))
		ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/newmovies.uls", "New Flipnotes", False))
		#ugo.Items.append(("category", "http://flipnote.hatena.com/ds/v2-xx/frontpage/following.uls", "New Favourites", False))
		
		#the "post flipnote" button
		ugo.Items.append(("unknown", ("3", "http://flipnote.hatena.com/ds/v2-xx/help/post_howto.htm", "UABvAHMAdAAgAEYAbABpAHAAbgBvAHQAZQA=")))
		
		#previous page
		if page > 1:
			ugo.Items.append(("button", 115, "Previous", "http://flipnote.hatena.com/ds/v2-xx/frontpage/hotmovies.uls?page=%i" % (page-1), ("", ""), None))
		
		#Flipnotes
		for creatorid, filename in flipnotes:
			stars = str(Database.GetFlipnote(creatorid, filename)[2])
			ugo.Items.append(("button", 3, "", "http://flipnote.hatena.com/ds/v2-xx/movie/%s/%s.ppm" % (creatorid, filename), (stars, "765", "573", "0"), (filename+".ppm", Database.GetFlipnoteTMB(creatorid, filename))))
		
		#next page
		if next:
			ugo.Items.append(("button", 115, "Next", "http://flipnote.hatena.com/ds/v2-xx/frontpage/hotmovies.uls?page=%i" % (page+1), ("", ""), None))
		
		return ugo.Pack()





