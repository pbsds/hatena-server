#PPM.py by pbsds for python 2.7
#AGPL3 licensed
#
#PIL is required to write images to disk
#
#Credits:
#
#	-Steven for most of the documentation on DSiBrew and his frame decoding example on his talkpage
#	-Remark for help on the 8x8 tiling on the preview image.
#	-Jsafive for supplying .tmb files
#
import sys, wave#needs os and time aswell
try:
	import Image
	hasPIL = True
except ImportError:
	hasPIL = False

#helpers:
def AscDec(ascii, LittleEndian=False):#Converts a ascii string into a decimal
	ret = 0
	l = map(ord, ascii)
	if LittleEndian: l.reverse()
	for i in l:
		ret = (ret<<8) | i
	return ret
def DecAsc(dec, length=None, LittleEndian=False):#Converts a decimal into an ascii string of chosen length
	out = []
	while dec <> 0:
		out.insert(0, dec&0xFF)
		dec >>= 8
	#"".join(map(chr, out))
	
	if length:
		if len(out) > length:
			#return "".join(map(chr, out[-length:]))
			out = out[-length:]
		if len(out) < length:
			#return "".join(map(chr, [0]*(length-len(out)) + out))
			out = [0]*(length-len(out)) + out
			
	if LittleEndian: out.reverse()
	return "".join(map(chr, out))
def AddPadding(i,pad = 0x10):#used mainly for zipaligning offsets
	if i % pad <> 0:
		return i + pad - (i % pad)
	return i

#Class PPM:
#
#	With this class you can read a Flipnote PPM file into memory and get its attributes.
#	You do so by using either instance.ReadFile() or instance.Read() of your instance of the PPM class.
#	When reading the PPM file you can specify what parts you need by passing these parameters:
#	  - DecodeThumbnail = True: The thumbnail will be predecoded. GetThumbnail() will still work if set to False, only takes a bit longer. Default is False
#	  - ReadFrames = True: The frames are decoded. Disabling this will speed up the PPM reading a lot. Default is True
#	  - ReadSound = True: Reads the sound data. Default is False
#
#	After reading a PPM file, these values are available:
#
#	  - instance.FrameCount: The number of frames this flipnote consists of
#	  - instance.Locked: A boolean telling us wether it's locked or not
#	  - instance.ThumbnailFrameIndex: Which frame the thumbnail is(starting at 0)
#	  - instance.OriginalAuthorName: The name of the original author in unicode
#	  - instance.EditorAuthorName: The name of the (previous?) editing author in unicode
#	  - instance.Username: The username in unicode
#	  - instance.OriginalAuthorID: The ID of the original author
#	  - instance.EditorAuthorID: The ID of the last editor, the last user to save the file
#	  - instance.PreviousEditAuthorID: The ID of the previous editor
#	  - instance.OriginalFilename: The original filename
#	  - instance.CurrentFilename: The current filename
#	  - instance.Date: The date in seconds since January 1'st 2000
#	  - instance.GetThumbnail(): The thumbnail stored in a 2D list of uint32 RGBA values. Will decode it first if not done so already
#	  - instance.GetFrame(n): Returns the specified frame as a 2D list of uint32 RGBA values. Only works if ReadFrames was true when reading the PPM file
#	  - instance.Looped: A boolean telling us wether it's looped or not
#	  - instance.SFXUsage: A list telling us when the different sound effects are used:
#			instance.SFXUsage[frame] = [SFX1, SFX2, SFX3] where the SFX's are booleans
#	  - instance.Framespeed: a value between 1 and 8 telling us the speed
#	  - instance.BGMFramespeed: The framespeed when the BGM was recorded. used for resampling
#	  - instance.Frames: A list containing the decoded frames' raw data. Only available if ReadFrames was true when reading the PPM file
#			instance.Frames[frame] = [Inverted(boolean), [color #1, color #2], frame]
#			color #1 and #2 is a value between 0 and 3, check the palette in instance.GetFrame() to see what they are.
#			frame is a 3d list, used like this. frame[layer][x][y] = boolean
#			To get a colored image of a frame, use instance.GetFrame()
#	  - instance.SoundData: A list contaning the raw data of the BGM and the 3 sound effects. Only available if ReadSound was true set to true
class PPM:
	def __init__(self):
		self.Loaded = [False, False, False]#(Meta, Frames, Sound)
		self.Frames = None
		self.Thumbnail = None
		self.RawThumbnail = None
		self.SoundData = None
	def ReadFile(self, path, DecodeThumbnail=False, ReadFrames=True, ReadSound=False):#Load: (thumbnail, frames, sound)
		f = open(path, "rb")
		ret = self.Read(f.read(), DecodeThumbnail, ReadFrames, ReadSound)
		f.close()
		return ret
	def Read(self, data, DecodeThumbnail=False, ReadFrames=True, ReadSound=False):#Load: (thumbnail, frames, sound)
		if data[:4] <> "PARA" or len(data) <= 0x6a0:
			return False
		
		
		#Read the header:
		AudioOffset = AscDec(data[4:8], True) + 0x6a0
		AudioLenght = AscDec(data[8:12], True)
		
		self.FrameCount = AscDec(data[12:14], True) + 1
		self.Locked = ord(data[0x10]) & 0x01 == 1
		self.ThumbnailFrameIndex = AscDec(data[0x12:0x14], True)#which frame the thumbnnail represents
		
		self.OriginalAuthorName = data[0x14:0x2A].decode("UTF-16LE").split(u"\0")[0]
		self.EditorAuthorName = data[0x2A:0x40].decode("UTF-16LE").split(u"\0")[0]
		self.Username = data[0x40:0x56].decode("UTF-16LE").split(u"\0")[0]
		
		self.OriginalAuthorID = data[0x56:0x5e][::-1].encode("HEX").upper()
		self.EditorAuthorID = data[0x5E:0x66][::-1].encode("HEX").upper()#the last user to save the file
		
		self.OriginalFilenameC = data[0x66:0x78]#compressed
		self.CurrentFilenameC = data[0x78:0x8a]#compressed
		self.OriginalFilename = "%s_%s_%s.tmb" % (self.OriginalFilenameC[:3].encode("HEX").upper(), self.OriginalFilenameC[3:-2], str(AscDec(self.OriginalFilenameC[-2:], True)).zfill(3))
		self.CurrentFilename = "%s_%s_%s.tmb" % (self.CurrentFilenameC[:3].encode("HEX").upper(), self.CurrentFilenameC[3:-2], str(AscDec(self.CurrentFilenameC[-2:], True)).zfill(3))
		
		self.PreviousEditAuthorID = data[0x8a:0x92][::-1].encode("HEX").upper()#don't know what this really is
		
		#self.PartialFilenameC = data[0x92:0x9a]#compressed
		
		self.Date = AscDec(data[0x9a:0x9e], True)#in seconds since midnight 1'st january 2000
		
		self.RawThumbnail = data[0xa0:0x6a0]
		if DecodeThumbnail:
			self.GetThumbnail()#self.Thumbnail[x][y] = uint32 RGBA
		
		self.Loaded[0] = True
		
		#read the animation sequence header:
		self.Looped = ord(data[0x06A6]) >> 1 & 0x01 == 1#Unverified?
		AnimationOffset = 0x6a8 + AscDec(data[0x6a0:0x6a4], True)
		FrameOffsets = [AnimationOffset + AscDec(data[0x06a8+i*4:0x06a8+i*4+4], True) for i in xrange(self.FrameCount)]
		
		#Read the audio header:
		self.SFXUsage = [(i&0x1<>0, i&0x2<>0, i&0x4<>0) for i in map(ord, data[AudioOffset:AudioOffset+self.FrameCount])]#SFXUsage[frame] = (sfx1, sfx2, sfx2) shere sfxX is either 0 or 1
		SoundSize =(AscDec(data[AddPadding(AudioOffset+self.FrameCount, 4)   :AddPadding(AudioOffset+self.FrameCount, 4)+ 4], True),#BG music
					AscDec(data[AddPadding(AudioOffset+self.FrameCount, 4)+ 4:AddPadding(AudioOffset+self.FrameCount, 4)+ 8], True),#SFX1
					AscDec(data[AddPadding(AudioOffset+self.FrameCount, 4)+ 8:AddPadding(AudioOffset+self.FrameCount, 4)+12], True),#SFX2
					AscDec(data[AddPadding(AudioOffset+self.FrameCount, 4)+12:AddPadding(AudioOffset+self.FrameCount, 4)+16], True))#SFX3
		self.Framespeed    = 8 - ord(data[AddPadding(AudioOffset+self.FrameCount, 4) + 16])
		self.BGMFramespeed = 8 - ord(data[AddPadding(AudioOffset+self.FrameCount, 4) + 17])#framespeed when the bgm was recorded
		
		#Read the Frames:
		if ReadFrames:
			self.Frames = []#self.Frames[frame]  = [inverted(bool), (color1(0-2), color2(0-2)), frame[layer][x][y] = bool]
			for i, offset in enumerate(FrameOffsets):
				#Read frame header:
				Inverted = ord(data[offset]) & 0x01 == 0
				
				#Reads which color that will be used:
				Colors = (ord(data[offset]) >> 1 & 0x03,
						  ord(data[offset]) >> 3 & 0x03)
				
				Frame = self.ExtractFrame(data, offset, self.Frames[i-1][2] if i else None)
				
				self.Frames.append([Inverted, Colors, Frame])
			
			self.Loaded[1] = True
		else:
			self.Loaded[1] = False
			self.Frames = None
		
		#Read the Audio:
		if ReadSound:
			self.SoundData = []
			pos = AddPadding(AudioOffset+self.FrameCount+32, 4)
			for i in xrange(4):
				self.SoundData.append(data[pos:pos+SoundSize[i]])
				pos += SoundSize[i]
			
			self.Loaded[2] = True
		else:
			self.Loaded[2] = False
			self.SoundData = None
		
		#return the results
		return self
	def WriteFile(self, path):#not implented
		pass
	#Extracting:
	def GetFrame(self, frame):#frame is the index in self.Frames. Only works if ReadFrames was True when reading the PPM file
		if not self.Loaded[1]: return None
		
		Inverted, Colors, Frame = self.Frames[frame]
		
		#Defines the palette:
		Palette = [0xFFFFFFFF,0x000000FF,0xFF0000FF,0x0000FFFF]
		if Inverted:
			Palette[0] = 0x000000FF
			Palette[1] = 0xFFFFFFFF
		Color1 = Palette[Colors[0]]
		Color2 = Palette[Colors[1]]
		
		out = []
		for x in xrange(256):
			out.append([])
			for y in xrange(192):
				if Frame[0][x][y]:#Color 1:
					out[-1].append(Color1)
				elif Frame[1][x][y]:#Color 2:
					out[-1].append(Color2)
				else:#background:
					out[-1].append(Palette[0])
		
		return out
	def GetThumbnail(self, force=False):
		if (not self.Thumbnail or force) and self.RawThumbnail:
			if not self.RawThumbnail:
				return False
		
			out = [[0 for _ in xrange(48)] for _ in xrange(64)]
			palette =  (0xFEFEFEFF,#0
						0x4F4F4FFF,#1
						0xFFFFFFFF,#2
						0x9F9F9FFF,#3
						0xFF0000FF,#4
						0x770000FF,#5
						0xFF7777FF,#6
						0x00FF00FF,#7-
						0x0000FFFF,#8
						0x000077FF,#9
						0x7777FFFF,#A
						0x00FF00FF,#B-
						0xFF00FFFF,#C
						0x00FF00FF,#D-
						0x00FF00FF,#E-
						0x00FF00FF)#F-
			
			#8x8 tiling:
			for ty in range(6):
				for tx in range(8):
					for y in range(8):
						for x in range(0,8,2):
							#two colors stored in each byte:
							byte = ord(self.RawThumbnail[(ty*512+tx*64+y*8+x)/2])
							out[x+tx*8  ][y+ty*8] = palette[byte & 0xF]
							out[x+tx*8+1][y+ty*8] = palette[byte >> 4]
			
			self.Thumbnail = out
		return self.Thumbnail
	#sub functions:
	def ExtractFrame(self, data, offset, PrevFrame=None):
		#defines line encoding storage:
		#Enc1 = [0 for i in range(192)]
		#Enc2 = [0 for i in range(192)]
		#Defines the frame storage:
		#Color1Frame = [[0 for i in range(192)] for i in range(256)]
		#Color2Frame = [[0 for i in range(192)] for i in range(256)]
		
		Encoding = [[], []]
		Frame = [[[False for _ in xrange(192)] for _ in xrange(256)] for _ in xrange(2)]
		
		#Read tags:
		NewFrame = ord(data[offset]) & 0x80 <> 0
		Unknown = ord(data[offset]) >> 5 & 0x03
		
		offset += 1
		
		#WIP - framemove:
		FrameMove = [0,0]
		if Unknown & 0x2:#doesn't work 100%...
			move = AscDec(data[offset:offset+2], True)
			if move > 128:
				FrameMove[0] = move - 256
			else:
				FrameMove[1] = 0-move
			offset += 2
		if Unknown:
			print "Unknown instance:",Unknown,"at offset ",offset-1
		
		
		#read the line encoding of the layers:
		for layer in xrange(2):
			for byte in map(ord, data[offset:offset+48]):
				Encoding[layer].append(byte      & 0x03)
				Encoding[layer].append(byte >> 2 & 0x03)
				Encoding[layer].append(byte >> 4 & 0x03)
				Encoding[layer].append(byte >> 6       )
			offset += 48
		
		#read layers:
		for layer in xrange(2):
			for y in xrange(192):
				if   Encoding[layer][y] == 0:#Nothing
					pass
				elif Encoding[layer][y] == 1:#Normal
					UseByte = AscDec(data[offset:offset+4])
					offset += 4
					x = 0
					while UseByte & 0xFFFFFFFF:
						if UseByte & 0x80000000:
							byte = ord(data[offset])
							offset += 1
							for _ in xrange(8):
								if byte & 0x01:
									Frame[layer][x][y] = True
								x += 1
								byte >>= 1
						else:
							x += 8
						UseByte <<= 1
				elif Encoding[layer][y] == 2:#Inverted
					UseByte = AscDec(data[offset:offset+4])
					offset += 4
					x = 0
					while UseByte&0xFFFFFFFF:
						if UseByte & 0x80000000:
							byte = ord(data[offset])
							offset += 1
							for _ in range(8):
								if not byte & 0x01:
									Frame[layer][x][y] = True
								x += 1
								byte >>= 1
						else:
							x += 8
						UseByte <<= 1
					for n in range(256):
						Frame[layer][n][y] = not Frame[layer][n][y]
				elif Encoding[layer][y] == 3:#Raw/full
					x = 0
					for _ in range(32):
						byte = ord(data[offset])
						offset += 1
						for _ in range(8):
							if byte & 0x01:
								Frame[layer][x][y] = True
							x += 1
							byte >>= 1
		
		#Merges this frame with the previous frame if NewFrame isn't true:
		if not NewFrame and PrevFrame:
			if FrameMove[0] or FrameMove[1]:#Moves the previus frame if specified:
				NewPrevFrame = [[[False for _ in xrange(192)] for _ in xrange(256)] for _ in xrange(2)]
				
				for y in range(192):
					for x in range(256):
						TempX = x+FrameMove[0]
						TempY = y+FrameMove[1]
						if 0 <= Tempx < 256 and 0 <= TempY < 192:
							NewPrevFrame[0][TempX][TempY] = PrevFrame[0][x][y]
							NewPrevFrame[1][TempX][TempY] = PrevFrame[1][x][y]
				
				PrevFrame = NewPrevFrame
			
			#Merge the frames:
			for y in range(192):
				for x in range(256):
					Frame[0][x][y] = Frame[0][x][y] <> PrevFrame[0][x][y]
					Frame[1][x][y] = Frame[1][x][y] <> PrevFrame[1][x][y]
		
		return Frame

#Class TMB:
#
#	With this class you can read a Flipnote TMB file into memory and get its attributes.
#	You do so by using either instance.ReadFile() or instance.Read() of your instance of the TMB class.
#	If you pass DecodeThumbnail=True to these functions, it will decode thumbnail.
#	The TMB file is a file containing the metadata to a corresponding PPM file.
#
#	After reading a TMB file, these values are available:
#
#	  - instance.FrameCount: The number of frames this flipnote consists of
#	  - instance.Locked: A boolean telling us wether it's locked or not
#	  - instance.ThumbnailFrameIndex: Which frame the thumbnail is(starting at 0)
#	  - instance.OriginalAuthorName: The name of the original author in unicode
#	  - instance.EditorAuthorName: The name of the (previous?) editing author in unicode
#	  - instance.Username: The username in unicode
#	  - instance.OriginalAuthorID: The ID of the original author
#	  - instance.EditorAuthorID: The ID of the last editor, the last user to save the file
#	  - instance.PreviousEditAuthorID: The ID of the previous editor
#	  - instance.OriginalFilename: The original filename
#	  - instance.CurrentFilename: The current filename
#	  - instance.Date: The date in seconds since January 1'st 2000
#	  - instance.GetThumbnail(): The thumbnail stored in a 2D list of uint32 RGBA values. Will decode it first if not done so already
class TMB:
	def __init__(self):
		self.Loaded = False
		self.Thumbnail = None
		self.RawThumbnail = None
	def ReadFile(self, path, DecodeThumbnail=False):
		f = open(path, "rb")
		ret = self.Read(f.read(), DecodeThumbnail)
		f.close()
		return ret
	def Read(self, data, DecodeThumbnail=False):
		if data[:4] <> "PARA" or len(data) < 0x6a0:
			return False
		
		#Read the header:
		self.AudioOffset = AscDec(data[4:8], True) + 0x6a0#only stored for self.Pack()
		self.AudioLenght = AscDec(data[8:12], True)#only stored for self.Pack()
		
		self.FrameCount = AscDec(data[12:14], True) + 1
		self.Locked = ord(data[0x10]) & 0x01 == 1
		self.ThumbnailFrameIndex = AscDec(data[0x12:0x14], True)#which frame is in the thumbnnail
		
		#self.OriginalAuthorName = u"".join(unichr(AscDec(data[0x14+i*2:0x14+i*2+2], True)) for i in xrange(11)).split(u"\0")[0]
		#self.EditorAuthorName = u"".join(unichr(AscDec(data[0x2A+i*2:0x2A+i*2+2], True)) for i in xrange(11)).split(u"\0")[0]
		#self.Username = u"".join(unichr(AscDec(data[0x40+i*2:0x40+i*2+2], True)) for i in xrange(11)).split(u"\0")[0]
		self.OriginalAuthorName = data[0x14:0x2A].decode("UTF-16LE").split(u"\0")[0]
		self.EditorAuthorName = data[0x2A:0x40].decode("UTF-16LE").split(u"\0")[0]
		self.Username = data[0x40:0x56].decode("UTF-16LE").split(u"\0")[0]
		
		self.OriginalAuthorID = data[0x56:0x5e][::-1].encode("HEX").upper()
		self.EditorAuthorID = data[0x5E:0x66][::-1].encode("HEX").upper()#the last user to save the file
		
		self.OriginalFilenameC = data[0x66:0x78]#compressed
		self.CurrentFilenameC = data[0x78:0x8a]#compressed
		self.OriginalFilename = "%s_%s_%s.tmb" % (self.OriginalFilenameC[:3].encode("HEX").upper(), self.OriginalFilenameC[3:-2], str(AscDec(self.OriginalFilenameC[-2:], True)).zfill(3))
		self.CurrentFilename = "%s_%s_%s.tmb" % (self.CurrentFilenameC[:3].encode("HEX").upper(), self.CurrentFilenameC[3:-2], str(AscDec(self.CurrentFilenameC[-2:], True)).zfill(3))
		
		self.PreviousEditAuthorID = data[0x8a:0x92][::-1].encode("HEX").upper()#don't know what this really is
		
		self.PartialFilenameC = data[0x92:0x9a]#compressed
		
		self.Date = AscDec(data[0x9a:0x9e], True)#in seconds since midnight 1'st january 2000
		
		self.RawThumbnail = data[0xa0:0x6a0]
		if DecodeThumbnail:
			self.GetThumbnail()#self.Thumbnail[x][y] = uint32 RGBA
		
		self.Loaded = True
		#return the results
		return self
	def WriteFile(self, path):#not implented
		out = self.Pack()
		if out:
			f = open(path, "wb")
			f.write(out)
			f.close()
			return True
		else:
			return False
	def Pack(self, ppm=None):#not implented
		if not self.Loaded: return False
		
		#realself = self
		#if ppm: self = ppm
		
		out = ["PARA",#magic
		       DecAsc(self.AudioOffset-0x6a0, 4, True),#animation data size
		       DecAsc(self.AudioLenght, 4, True),#audio data size
		       DecAsc(self.FrameCount-1, 2, True),#frame count
		       "\x24\x00",#unknown
		       chr(self.Locked), "\0",#locked
		       DecAsc(self.ThumbnailFrameIndex, 2, True),#which frame is in the thumbnnail
		       self.OriginalAuthorName.encode("UTF-16LE") + "\0\0"*(11-len(self.OriginalAuthorName)),#Original Author Name
		       self.EditorAuthorName.encode("UTF-16LE") + "\0\0"*(11-len(self.EditorAuthorName)),#Editor Author Name
		       self.Username.encode("UTF-16LE") + "\0\0"*(11-len(self.Username)),#Username
			   self.OriginalAuthorID.decode("HEX")[::-1],#OriginalAuthorID
			   self.EditorAuthorID.decode("HEX")[::-1],#EditorAuthorID
			   self.OriginalFilenameC,#OriginalFilename
			   self.CurrentFilenameC,#CurrentFilename
			   self.PreviousEditAuthorID.decode("HEX")[::-1],#EditorAuthorID
			   self.PartialFilenameC,#PartialFilename
		       DecAsc(self.Date, 4, True),#Date in seconds
		       "\0\0",#padding
			   self.PackThumbnail()]#thumbnail
		
		return "".join(out)
	def GetThumbnail(self, force=False):
		if (not self.Thumbnail or force) and self.RawThumbnail:
			if not self.RawThumbnail:
				return False
		
			out = [[0 for _ in xrange(48)] for _ in xrange(64)]
			palette =  (0xFEFEFEFF,#0
						0x4F4F4FFF,#1
						0xFFFFFFFF,#2
						0x9F9F9FFF,#3
						0xFF0000FF,#4
						0x770000FF,#5
						0xFF7777FF,#6
						0x00FF00FF,#7-
						0x0000FFFF,#8
						0x000077FF,#9
						0x7777FFFF,#A
						0x00FF00FF,#B-
						0xFF00FFFF,#C
						0x00FF00FF,#D-
						0x00FF00FF,#E-
						0x00FF00FF)#F-
			
			#8x8 tiling:
			for ty in range(6):
				for tx in range(8):
					for y in range(8):
						for x in range(0,8,2):
							#two colors stored in each byte:
							byte = ord(self.RawThumbnail[(ty*512+tx*64+y*8+x)/2])
							out[x+tx*8  ][y+ty*8] = palette[byte & 0xF]
							out[x+tx*8+1][y+ty*8] = palette[byte >> 4]
			
			self.Thumbnail = out
		return self.Thumbnail
	def PackThumbnail(self, Exact=True, force=False):#more or less a private function for now
		palette =  (0xFEFEFEFF,#0
					0x4F4F4FFF,#1
					0xFFFFFFFF,#2
					0x9F9F9FFF,#3
					0xFF0000FF,#4
					0x770000FF,#5
					0xFF7777FF,#6
					0x00FF00FF,#7-
					0x0000FFFF,#8
					0x000077FF,#9
					0x7777FFFF,#A
					0x00FF00FF,#B-
					0xFF00FFFF,#C
					0x00FF00FF,#D-
					0x00FF00FF,#E-
					0x00FF00FF)#F-
		
		
		if not self.Thumbnail:
			return self.RawThumbnail
		else:
			if Exact:
				out = []
				
				#8x8 tiling:
				for ty in range(6):
					for tx in range(8):
						for y in range(8):
							for x in range(0,8,2):
								#two colors stored in each byte:
								#pos = 0xa0+(ty*512+tx*64+y*8+x)/2
								p1 = palette.index(self.Thumbnail[x+tx*8  ][y+ty*8])
								p2 = palette.index(self.Thumbnail[x+tx*8+1][y+ty*8])
								out.append(chr(p2<<4 | p1))
				
				self.RawThumbnail = "".join(out)
				return self.RawThumbnail
			else:
				#not yet implented
				return False

#Function WriteImage:
#
#	Writes a 2D list if uint32 RGBA values as a image files.
#	Designed to work with PPM().Thumbnail or PPM().GetFrame(n)
#
#	This function requires the PIl imaging module
def WriteImage(image, outputPath):
	if not hasPIL or not image: return False
	
	out = []
	for y in xrange(len(image[0])):
		for x in xrange(len(image)):
			out.append(DecAsc(image[x][y], 4))
	
	out = Image.fromstring("RGBA", (len(image), len(image[0])), "".join(out))
	
	filetype = outputPath[outputPath.rfind(".")+1:]
	out.save(outputPath, filetype)
	
	return True

#this is just for experimenting with sound decoding:
#not even remotely close to being finished
def DecodeSound(outputpath, data):
	f = wave.open(outputpath, "wb")
	f.setnchannels(1)
	f.setsampwidth(2)
	f.setframerate(32000)
	for i in data:
		i1 = ord(i)&0xF
		i2 = (ord(i)>>4)&0xF
		#Noise reduction:
		#if i1&0x8: i1 = 0xF-(i1&0x7)
		#if i2&0x8: i2 = 0xF-(i2&0x7)
		i1 = i1&0x7 if i1&0x8 else 0xF-i1
		i2 = i2&0x7 if i2&0x8 else 0xF-i2
		f.writeframes(DecAsc(i1<<12, 2, True)*4)
		f.writeframes(DecAsc(i2<<12, 2, True)*4)
	f.close()

#testing:
# p = PPM()
# print "loading ppm..."
# p.ReadFile("PPMtests/test.ppm", (1, 1, 1))

# print str(p.OriginalAuthorName), str(p.OriginalAuthorID)
# print str(p.EditorAuthorName), str(p.EditorAuthorID)

# print "Dumping Thumbnail..."
# WriteImage(p.Thumbnail, "thumbnail.png")

# print "Dumping frames..."
# for i in xrange(p.FrameCount):
	# WriteImage(p.GetFrame(i), "frames/frame %i.png" % i)

# print "Dumping raw sounds..."
# for i, data in enumerate(p.SoundData):
	# f = open("sound %i.bin" % i, "wb")
	# f.write(data)
	# f.close()

# print "Extracting sounds...."
# for i, d in enumerate(p.SoundData): DecodeSound("out_%i.wav"%i, d)

if __name__ == '__main__':
	print "              ==      PPM.py      =="
	print "             ==      by pbsds      =="
	print "              ==       v1.05      =="
	print
	
	if len(sys.argv) < 3:
		print "Usage:"
		print "      PPM.py <Mode> <Input> [<Output>] [<Frame>]"
		print ""
		print "      <Mode>:"
		print "          -t: Extracts the thumbnail to the file <Output>"
		print "          -f: Extracts the frame(s) to <Output>"
		print "          -s: Dumps the raw sound data files to the folder <Output>"
		print "          -S: Same as mode 2, but will also dump the experimentally decoded"
		print "              sounds."
		print "          -m: Prints out the metadata. Can also write it to <output> which also"
		print "              supports unicode charactes."
		print "          Mode -t and -m supports TMB files aswell"
		print "      <Frame>"
		print "          Only used in mode -f"
		print "          Set this to the exact frame you want to extract(starting at 1) and it"
		print "          will be saved as a file to <Output>."
		print "          If not specified, it will extract all frames to the folder <Output>"
		
		sys.exit()
	
	import os, time
	
	if sys.argv[1]   == "-t":
		print "Reading the flipnote file...",
		if not os.path.isfile(sys.argv[2]):
			print "Error!\nSpecified file doesn't exist!"
			sys.exit()
		flipnote = TMB().ReadFile(sys.argv[2], True)
		if not flipnote:
			print "Error!"
			print "The given file is not a Flipnote PPM file or TMB file!"
			sys.exit()
		print "Done!"
		
		print "Dumping the thumbnail...",
		WriteImage(flipnote.GetThumbnail(), sys.argv[3])
		print "Done!"
	elif sys.argv[1] == "-f":
		if len(sys.argv) < 4:
			print "Error!"
			print "<Output> not specified!"
			sys.exit()
		
		print "Reading the flipnote file...",
		if not os.path.isfile(sys.argv[2]):
			print "Error!\nSpecified file doesn't exist!"
			sys.exit()
		flipnote = PPM().ReadFile(sys.argv[2])
		if not flipnote:
			print "Error!\nThe given file is not a Flipnote PPM file."
			sys.exit()
		print "Done!"
		
		
		if len(sys.argv) < 5:
			if not os.path.isdir(sys.argv[3]):
				print "Error!\nThe specified directory doesn't exist!"
				sys.exit()
			
			for i in xrange(flipnote.FrameCount):
				print "Dumping frame #%i..." % (i+1),
				WriteImage(flipnote.GetFrame(i), os.path.join(sys.argv[3], "frame %s.png" % str(i+1).zfill(3)))
				print "Done!"
		else:
			try:
				int(sys.argv[4])
			except:
				print "Error!\nInvalid <Frame>!"
				sys.exit()
			
			if not (0 <= int(sys.argv[4])-1 < flipnote.FrameCount):
				print "Error!\n<Frame> is out of bounds!"
				sys.exit()
			
			print "Dumping frame #%i..." % int(sys.argv[4]),
			WriteImage(flipnote.GetFrame(int(sys.argv[4])-1), sys.argv[3])
			print "Done!"
	elif sys.argv[1] in ("-s", "-S"):
		if len(sys.argv) < 4:
			print "Error!"
			print "<Output> not specified!"
			sys.exit()
		
		print "Reading the flipnote file...",
		if not os.path.isfile(sys.argv[2]):
			print "Error!\nSpecified file doesn't exist!"
			sys.exit()
		flipnote = PPM().ReadFile(sys.argv[2], ReadFrames=False, ReadSound=True)
		if not flipnote:
			print "Error!\nThe given file is not a Flipnote PPM file."
			sys.exit()
		print "Done!"
		
		if not os.path.isdir(sys.argv[3]):
			print "Error!\nThe specified directory doesn't exist!"
			sys.exit()
		
		print "Dumping the raw sound data...",
		for i, data in enumerate(flipnote.SoundData):
			f = open(os.path.join(sys.argv[3], ("BGM.bin", "SFX1.bin", "SFX2.bin", "SFX3.bin")[i]), "wb")
			f.write(data)
			f.close()
		print "Done!"
		
		if sys.argv[1] == "-S":
			print "Dumping the decoded sound data...",
			for i, data in enumerate(flipnote.SoundData):
				DecodeSound(os.path.join(sys.argv[3], ("BGM decoded.wav", "SFX1 decoded.wav", "SFX2 decoded.wav", "SFX3 decoded.wav")[i]), data)
			print "Done!"
		
		print "Dumping the sound effect usage...",
		f = open(os.path.join(sys.argv[3], "SFX usage.txt"), "w")
		for i, (s1, s2, s3) in enumerate(flipnote.SFXUsage):
			f.write("Frame %i:%s%s%s\n" % (i, " SFX1"*s1, " SFX2"*s2, " SFX3"*s3))
		f.close()
		print "Done!"
	elif sys.argv[1] == "-m":
		epoch = time.mktime(time.struct_time([2000, 1, 1, 0, 0, 0, 5, 1, -1]))
		
		if not os.path.isfile(sys.argv[2]):
			print "Error!\nSpecified file doesn't exist!"
			sys.exit()
		
		filetype = "ppm" if sys.argv[2][-3:] == "ppm" else "tmb"
		flipnote = TMB().ReadFile(sys.argv[2]) if filetype == "tmb" else PPM().ReadFile(sys.argv[2], ReadFrames=False)
		if not flipnote:
			print "Error!\nThe given file is not a Flipnote PPM file or TMB file."
			if len(sys.argv) >= 4:
				f = open(sys.argv, "wb")
				f.write("Error!\nThe given file is not a Flipnote PPM file or TMB file.")
				f.close()
			sys.exit()
		
		meta = []
		meta.append(u"Current filename:                  %s" % flipnote.CurrentFilename[:-3]+filetype)
		meta.append(u"Original filename:                 %s" % flipnote.OriginalFilename[:-3]+filetype)
		meta.append(u"Number of frames:                  %s" % flipnote.FrameCount)
		meta.append(u"Locked:                            %s" % flipnote.Locked)
		if filetype == "ppm":
			meta.append(u"Frame speed:                       %s" % flipnote.Framespeed)
			meta.append(u"Looped:                            %s" % flipnote.Looped)
		meta.append(u"Thumbnail frame index:             %i" % (flipnote.ThumbnailFrameIndex+1))
		meta.append(u"Original author:                   %s" % flipnote.OriginalAuthorName)
		meta.append(u"Editor author:                     %s" % flipnote.EditorAuthorName)
		meta.append(u"Username:                          %s" % flipnote.Username)
		meta.append(u"Original author ID:                %s" % flipnote.OriginalAuthorID)
		meta.append(u"Editor author ID:                  %s" % flipnote.EditorAuthorID)
		meta.append(u"Date(seconds since 1'st Jan 2000): %s" % flipnote.Date)
		meta.append(time.strftime(u"Date:                              %H:%M %d/%m-%Y", time.gmtime(epoch+flipnote.Date)) + " (faulty)")
		
		newline = "\n"
		if sys.platform in ("win32", "cygwin"): newline = "\r\n"
		elif sys.platform in ("darwin"): newline = "\r"
		
		print newline.join(meta).encode('ascii', 'ignore')
		
		if len(sys.argv) >= 4:
			f = open(sys.argv[3], "wb")
			f.write(newline.join(meta).encode("UTF-8"))
			f.close()
	else:
		print "Error!\nThere's no such mode."