#!/usr/bin/env python
#PPM.py by pbsds for python 2.7
#AGPL3 licensed
#
#Numpy is required
#PIL is needed to write images to disk
#
#Credits:
#
#	- Steven for most of the documentation on DSiBrew and his frame decoding example on his talkpage
#	- Remark for help on the 8x8 tiling on the preview image.
#	- Jsafive for supplying .tmb files
#	- Austin Burk, Midmad on hatena haiku and WDLmaster on hcs64.com for determining the sound codec
#
import sys, wave, audioop, re, os #needs os and time aswell in CMD mode (UPDATE 2018/07/04: os used to get devnull for discarding subprocess output)
import numpy as np
import subprocess # used for ffmpeg
import tempfile, shutil # temporary directory whilst exporting, shutil to clean up after
import time
try:
	from PIL import Image
	hasPIL = True
except ImportError:
	print "Warning: PIL not found, image extraction won't work!"
	hasPIL = False
# Test for ffmpeg by executing ffmpeg -h; an OSError indicates ffmpeg is not installed

try:
	with open(os.devnull,"w") as null:
		subprocess.call(["ffmpeg","-h"],
						stdout=null,
						stderr=null)
	hasffmpeg = True
except OSError:
	print "Warning: ffmpeg not found, video export unavailable. Please make sure ffmepg is installed and can be accessed on your path."
	hasffmpeg = False

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

#palettes:
FramePalette = [0xFFFFFFFF,0x000000FF,0xFF0000FF,0x0000FFFF]
ThumbPalette = (0xFEFEFEFF,#0
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
#	  - instance.GetThumbnail(): The thumbnail stored in a 2D list of uint32 RGBA values (>u4). Will decode it first if not done so already
#	  - instance.GetFrame(n): Returns the specified frame as a 2D list of uint32 RGBA values (>u4). Only works if ReadFrames was true when reading the PPM file
#	  - instance.GetSound(n): Returns the decoded sound. Index 0 is the BGM. 1, 2 and 3 are the SFXs. if outputpath is None, the raw mono PCM @ 8184Hz is returned instead as a string
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
	def __init__(self,forced_speed=None):
		self.Loaded = [False, False, False]#(Meta, Frames, Sound)
		self.Frames = None
		self.Thumbnail = None
		self.RawThumbnail = None
		self.SoundData = None
		self.forced_speed = forced_speed
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
		self.OriginalFilename = "%s_%s_%s.ppm" % (self.OriginalFilenameC[:3].encode("HEX").upper(), self.OriginalFilenameC[3:-2], str(AscDec(self.OriginalFilenameC[-2:], True)).zfill(3))
		self.CurrentFilename = "%s_%s_%s.ppm" % (self.CurrentFilenameC[:3].encode("HEX").upper(), self.CurrentFilenameC[3:-2], str(AscDec(self.CurrentFilenameC[-2:], True)).zfill(3))
		
		self.PreviousEditAuthorID = data[0x8a:0x92][::-1].encode("HEX").upper()#don't know what this really is
		
		#self.PartialFilenameC = data[0x92:0x9a]#compressed
		
		self.Date = AscDec(data[0x9a:0x9e], True)#in seconds since midnight 1'st january 2000
		
		self.RawThumbnail = data[0xa0:0x6a0]
		if DecodeThumbnail:
			self.GetThumbnail()#self.Thumbnail[x, y] = uint32 RGBA
		
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
		if self.forced_speed == None:
			self.Framespeed    = 8 - ord(data[AddPadding(AudioOffset+self.FrameCount, 4) + 16])
		else:
			self.Framespeed = self.forced_speed
		self.BGMFramespeed = 8 - ord(data[AddPadding(AudioOffset+self.FrameCount, 4) + 17])#framespeed when the bgm was recorded
		
##            self.BGMFramespeed = self.forced_speed
		
		#Read the Frames:
		if ReadFrames:
			self.Frames = []#self.Frames[frame]  = [inverted(bool), (color1(0-2), color2(0-2)), frame[layer, x, y] = bool]
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
		global FramePalette
		if not self.Loaded[1]: return None
		
		Inverted, Colors, Frame = self.Frames[frame]
		
		#Defines the palette:
		Palette = FramePalette[:]
		if Inverted:
			Palette[0], Palette[1] = Palette[1], Palette[0]
		Color1 = Palette[Colors[0]]
		Color2 = Palette[Colors[1]]
		
		out = np.zeros((256, 192), dtype=">u4")
		out[:] = Palette[0]
		out[Frame[1]] = Color2
		out[Frame[0]] = Color1
		
		return out
	def GetThumbnail(self, force=False):
		if (self.Thumbnail is None or force):# and self.RawThumbnail:
			global ThumbPalette
			if not self.RawThumbnail:
				return False
			
			out = np.zeros((64, 48), dtype=">u4")
			
			#speedup:
			palette = ThumbPalette
			
			#8x8 tiling:
			for ty in range(6):
				for tx in range(8):
					for y in range(8):
						for x in range(0,8,2):
							#two colors stored in each byte:
							byte = ord(self.RawThumbnail[(ty*512+tx*64+y*8+x)/2])
							out[x+tx*8  , y+ty*8] = palette[byte & 0xF]
							out[x+tx*8+1, y+ty*8] = palette[byte >> 4]
			
			self.Thumbnail = out
		return self.Thumbnail
	def GetSound(self, index, outputpath=None):#index 0 is BGM. 1, 2 and 3 is SFX. if outputpath is None, the raw mono PCM @ 8184Hz is returned instead
		if self.Loaded[2]:
			if self.SoundData[index]:
				#reverse nibbles:
				data = []
				for i in map(ord,self.SoundData[index]):
					data.append(chr((i&0xF)<< 4 | (i>>4)))
				data = "".join(data)
				
				#4bit ADPCM decode
				decoded = audioop.adpcm2lin(data, 2, None)[0]
				
				#write to wav:
				if outputpath:
					f = wave.open(outputpath, "wb")
					f.setnchannels(1)
					f.setsampwidth(2)
					f.setframerate(8192)#possibly 8184, but not a noticable difference anyway
					f.writeframes(decoded)
					#f.writeframes("".join(out))
					f.close()
					
					return True
				else:
					return decoded
			else:
				return False
	#sub functions: (private)
	def ExtractFrame(self, data, offset, PrevFrame=None):
		#defines line encoding storage:
		#Enc1 = [0 for i in range(192)]
		#Enc2 = [0 for i in range(192)]
		#Defines the frame storage:
		#Color1Frame = [[0 for i in range(192)] for i in range(256)]
		#Color2Frame = [[0 for i in range(192)] for i in range(256)]
		
		Encoding = [[], []]
		#Frame = [[[False for _ in xrange(192)] for _ in xrange(256)] for _ in xrange(2)]
		Frame = np.zeros((2, 256, 192), dtype=np.bool_)
		
		#Read tags:
		NewFrame = ord(data[offset]) & 0x80 <> 0
		Unknown = ord(data[offset]) >> 5 & 0x03
		
		offset += 1
		
		#WIP - framemove:
		FrameMove = [0,0]
		if Unknown & 0x2:#doesn't work 100%...
			print "FrameMove at offset ",offset-1
			
			move_x = AscDec(data[offset+0:offset+1], True)
			move_y = AscDec(data[offset+1:offset+2], True)
			FrameMove[0] = move_x if move_x <= 127 else move_x-256
			FrameMove[1] = move_y if move_y <= 127 else move_y-256
			offset += 2
		elif Unknown:
			print "Unknown tags:",Unknown,"at offset ",offset-1
		
		
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
									Frame[layer, x, y] = True
								x += 1
								byte >>= 1
						else:
							x += 8
						UseByte <<= 1
					for n in range(256):
						#Frame[layer][n][y] = not Frame[layer][n][y]
						Frame[layer, n, y] = not Frame[layer, n, y]
				elif Encoding[layer][y] == 3:#Raw/full
					x = 0
					for _ in range(32):
						byte = ord(data[offset])
						offset += 1
						for _ in range(8):
							if byte & 0x01:
								Frame[layer, x, y] = True
							x += 1
							byte >>= 1
		
		#Merges this frame with the previous frame if NewFrame isn't true:
		if not NewFrame and PrevFrame.all() <> None:#maybe optimize this better for numpy...
			if FrameMove[0] or FrameMove[1]:#Moves the previous frame if specified:
				NewPrevFrame = np.zeros((2, 256, 192), dtype=np.bool_)
				
				for y in range(192):#this still isn't perfected
					for x in range(256):
						TempX = x+FrameMove[0]
						TempY = y+FrameMove[1]
						if 0 <= TempX < 256 and 0 <= TempY < 192:
							NewPrevFrame[0, TempX, TempY] = PrevFrame[0, x, y]
							NewPrevFrame[1, TempX, TempY] = PrevFrame[1, x, y]
				
				PrevFrame = NewPrevFrame
			
			#merge the frames:
			Frame = Frame <> PrevFrame
		
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
#	  - instance.GetThumbnail(): The thumbnail stored in a 2D numpy array of uint32 RGBA values (>u4). Will decode it first if not done so already
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
			self.GetThumbnail()#self.Thumbnail[x, y] = uint32 RGBA
		
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
		if (self.Thumbnail is None or force):# and self.RawThumbnail:
			global ThumbPalette
			if not self.RawThumbnail:
				return False
			
			out = np.zeros((64, 48), dtype=">u4")
			
			#speedup:
			palette = ThumbPalette
			
			#8x8 tiling:
			for ty in range(6):
				for tx in range(8):
					for y in range(8):
						for x in range(0,8,2):
							#two colors stored in each byte:
							byte = ord(self.RawThumbnail[(ty*512+tx*64+y*8+x)/2])
							out[x+tx*8  , y+ty*8] = palette[byte & 0xF]
							out[x+tx*8+1, y+ty*8] = palette[byte >> 4]
			
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
								p1 = palette.index(int(self.Thumbnail[x+tx*8  , y+ty*8]))
								p2 = palette.index(int(self.Thumbnail[x+tx*8+1, y+ty*8]))
								out.append(chr(p2<<4 | p1))
				
				self.RawThumbnail = "".join(out)
				return self.RawThumbnail
			else:
				#not yet implented
				return False

#Function WriteImage:
#
#	Writes a 2D numpy array of uint32 RGBA values (>u4) as a image files.
#	Designed to work with PPM().Thumbnail or PPM().GetFrame(n)
#
#	This function requires the PIl imaging module
def WriteImage(image, outputPath, scale=1):
	if not hasPIL:
		print "Error: PIL not found!"
		return False
	#if not image: return False

	#	Upscale the image by the scale factor so each original pixel is
	#	represented by a n-by-n-pixel square in the larger version.
	#	Any number 1 or smaller is just treated as a scale factor of 1.
	if scale > 1:
		newImg = np.repeat(np.repeat(image, scale, axis = 0), scale, axis = 1)
	else:
		newImg = image

	out = newImg.tostring("F")	
	out = Image.frombytes("RGBA", (len(newImg), len(newImg[0])), out)
	
	filetype = outputPath[outputPath.rfind(".")+1:]
	out.save(outputPath, filetype)
	
	return True

def get_metadata(flipnote):
	epoch = time.mktime(time.struct_time([2000, 1, 1, 0, 0, 0, 5, 1, -1]))

	meta = {
	u"Current filename":flipnote.CurrentFilename[:-3]+filetype,
	u"Original filename":flipnote.OriginalFilename[:-3]+filetype,
	u"Number of frames":flipnote.FrameCount,
	u"Locked":flipnote.Locked,
	u"Thumbnail frame index":(flipnote.ThumbnailFrameIndex+1),
	u"Original author":flipnote.OriginalAuthorName,
	u"Editor author":flipnote.EditorAuthorName,
	u"Username":flipnote.Username,
	u"Original author ID":flipnote.OriginalAuthorID,
	u"Editor author ID":flipnote.EditorAuthorID,
	u"Date(seconds since 1'st Jan 2000)":flipnote.Date,
	u"Date":time.strftime("%H:%M %d/%m-%Y (faulty)", time.gmtime(epoch+flipnote.Date)),
	}
	if filetype == "ppm":
		meta[u"Frame speed"]=flipnote.Framespeed
		meta[u"BGM Frame speed"]=flipnote.BGMFramespeed
		meta[u"Looped"]=flipnote.Looped
			
	return meta

def DumpFrames(flipnote,directory,scale=1):
	for i in xrange(flipnote.FrameCount):
		print "Dumping frame #%i of %i..." % (i+1, flipnote.FrameCount)
		WriteImage(flipnote.GetFrame(i), os.path.join(directory, "frame %s.png" % str(i+1).zfill(3)), scale)
			
def DumpSoundFiles(flipnote,directory,raw=False):
	for i, data in enumerate(flipnote.SoundData):
		if not data: continue
		path = os.path.join(directory, ("BGM.wav", "SFX1.wav", "SFX2.wav", "SFX3.wav")[i])
		flipnote.GetSound(i, path)
		
		if raw:
			f = open(path[:-3]+"bin", "wb")
			f.write(data)
			f.close()

def DumpSFXUsage(flipnote,directory):
	with open(os.path.join(directory, "SFX usage.txt"), "w") as f:
		for i, (s1, s2, s3) in enumerate(flipnote.SFXUsage):
			f.write("Frame %i:%s%s%s\n" % (i, " SFX1"*s1, " SFX2"*s2, " SFX3"*s3))

if __name__ == '__main__':
	print "              ==      PPM.py      =="
	print "             ==      by pbsds      =="
	print "              ==       v1.3      =="
	print
	
	if len(sys.argv) < 3:
		print "Usage:"
		print "      PPM.py <Mode> <Input> [<Output>] [<Frame>] [<Option>]"
		print ""
		print "      <Mode>:"
		print "          -t: Extracts the thumbnail to the file <Output>"
		print "          -f: Extracts the frame(s) to <Output>"
		print "          -s: Dumps the sound files to the folder <Output>"
		print "          -S: Same as mode -s, but will also dump the raw sound data files"
		print "          -e: Exports the flipnote to an MKV"
		print "          -m: Prints out the metadata. Can also write it to <output> which also"
		print "              supports unicode charactes."
		print "          -oa: Seach a directory for an original author that matches the RegEx"
		print "          Mode -t and -m supports TMB files aswell"
		print "      <Frame>"
		print "          Only used in mode -f"
		print "          Set this to the exact frame you want to extract(starting at 1) and it"
		print "          will be saved as a file to <Output>."
		print "          If not specified, it will extract all frames to the folder <Output>"
		print "      <Option>"
		print "          --speed N: Only used in mode -e. Set this to force a specific"
		print "                     flipnote speed (1 to 8)."
		print "          --scale N: Only used in modes -e and -f. Set this to upscale the"
		print "                     frames N times."
		
		sys.exit()
	
	import os, time
	
	if sys.argv[1] == "-t":
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

		try:
			scale = int(sys.argv[sys.argv.index("--scale")+1])
			print "Using frame scaling "+str(scale)
		except (IndexError,ValueError):
			scale = 1
		
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

			DumpFrames(flipnote,sys.argv[3], scale)
			
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
			WriteImage(flipnote.GetFrame(int(sys.argv[4])-1), sys.argv[3], scale)
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
			print "Error!\nThe specified output directory doesn't exist!"
			sys.exit()
		
		print "Converting the sound files...",
		DumpSoundFiles(flipnote,sys.argv[3],raw=(sys.argv[1]=="-S"))
		print "Done!"
		
		print "Dumping the sound effect usage...",
		DumpSFXUsage(flipnote,sys.argv[3])
		print "Done!"
	elif sys.argv[1] == "-m":
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
		
		meta = get_metadata(flipnote)
		newline = "\n"
		if sys.platform in ("win32", "cygwin"): newline = "\r\n"
		elif sys.platform in ("darwin"): newline = "\r"

		print newline.join(["\t".join([unicode(char) for char in line]) for line in meta.items()]).encode('ascii', 'ignore')
		
		if len(sys.argv) >= 4:
			f = open(sys.argv[3], "wb")
			f.write(newline.join(meta).encode("UTF-8"))
			f.close()
	elif sys.argv[1] == "-oa":
		regex = re.compile(sys.argv[2])
		os.chdir(sys.argv[3])
		for filename in os.listdir("."):
			epoch = time.mktime(time.struct_time([2000, 1, 1, 0, 0, 0, 5, 1, -1]))
			if not os.path.isfile(filename):
				print "Error!\nSpecified file doesn't exist!"
				sys.exit()
				
			filetype = "ppm" if filename[-3:].lower() == "ppm" else "tmb"
			flipnote = TMB().ReadFile(filename) if filetype == "tmb" else PPM().ReadFile(filename, ReadFrames=False)
			if not flipnote:
				continue

			meta = get_metadata(flipnote)
			if regex.match(meta["Original author"]):
				print filename

	elif sys.argv[1] == "-e":
		if not hasffmpeg:
			print "Error!\nffmpeg is not installed."
			sys.exit()
		in_file = sys.argv[2]
		out_file = sys.argv[3]
		try:
			sleep_time = int(sys.argv[sys.argv.index("--sleep")+1])
		except (IndexError,ValueError):
			sleep_time = 0
			print "Not sleeping."
		try:
			forced_speed = int(sys.argv[sys.argv.index("--speed")+1])
			print "Using forced speed "+str(forced_speed)
		except (IndexError,ValueError):
			forced_speed = None
		try:
			scale = int(sys.argv[sys.argv.index("--scale")+1])
			print "Using frame scaling "+str(scale)
		except (IndexError,ValueError):
			scale = 1
			
		if out_file.lower()[-4:] != ".mkv":
			out_file += ".mkv"
		if not os.path.isfile(in_file):
			print "Error!\nSpecified file doesn't exist!"
			sys.exit()
		if os.path.isfile(out_file):
			print "Overwrite existing file?"
			overwrite = ""
			while overwrite != "y" and overwrite != "n":
				overwrite = raw_input("(Y/N) ").lower()
			if overwrite == "n":
				print "Not overwriting; exiting."
				sys.exit()
		filetype = "ppm" if in_file[-3:].lower() == "ppm" else "tmb"
		flipnote = TMB().ReadFile(in_file) if filetype == "tmb" else PPM(forced_speed).ReadFile(in_file, ReadFrames=True, ReadSound=True)

		# Make temp dir and dump the frames and sound here
		tempdir = tempfile.mkdtemp()
		os.mkdir(tempdir+"/sounds")
		print "Dumping the frames..."
		DumpFrames(flipnote,tempdir,scale)
		print "Done!"
		print "Dumping the sounds..."
		DumpSoundFiles(flipnote,tempdir+"/sounds")
		print "Done!"
		print "Dumping SFX usage..."
		DumpSFXUsage(flipnote,tempdir+"/sounds")
		print "Done!"

		# Now we need the metadata so we can look up the FPS
		SPEEDS = [None,0.5,1,2,4,6,12,20,30]
		print "Getting metadata..."
		metadata = get_metadata(flipnote)
		print "Done!"
		speed = int(metadata["Frame speed"])
		fps = SPEEDS[speed]
		duration = float(metadata["Number of frames"])/float(fps)
		print "Flipnote is speed {speed}, so {fps} FPS for {dur} seconds".format(speed=speed,fps=fps,dur=duration)

		# Now to make the video in ffmpeg
		print "Exporting video with ffmpeg..."
		export_command = ["ffmpeg","-framerate",str(fps),"-start_number","1","-i","{path}/frame %03d.png".format(path=tempdir),"-i","{path}/sounds/BGM.wav".format(path=tempdir),"-c:v","libx264","-preset","veryslow","-c:a","pcm_s16le","-t","{dur}".format(dur=duration),"-y",out_file]
		if not os.path.isfile(tempdir+"/sounds/BGM.wav"):
			print "No background music. Adding silent track..."
			#has_bgm = False
			export_command = ["ffmpeg","-framerate",str(fps),"-start_number","1","-i","{path}/frame %03d.png".format(path=tempdir),"-f","lavfi","-i","anullsrc=r=8192:cl=mono","-c:v","libx264","-preset","veryslow","-c:a","pcm_s16le","-shortest","-y",out_file]
		else:
			#has_bgm = True
			pass
		with open(os.devnull) as null:
			subprocess.call(export_command,stdout=null,stderr=null)
		print "Done!"

		# If the audio has been sped up, we have to do it again manually
		bgm_speed = int(metadata["BGM Frame speed"])
		if bgm_speed != speed:
			print "Background music speed must be modified!"
			original_rate = 8192
			newrate = 8192*(float(fps)/SPEEDS[bgm_speed])
			print "Using new rate: "+str(newrate)
			speed_change_command = ["ffmpeg","-i","{path}/sounds/BGM.wav".format(path=tempdir),"-filter_complex","asetrate={rate}".format(rate=newrate),"-i",out_file,"-map","0:a","-map","1:v","-vcodec","copy","-acodec","pcm_s16le","{path}/temp_out.mkv".format(path=tempdir)]
			with open(os.devnull,"w") as null:
				subprocess.call(speed_change_command,stdout=null,stderr=null)
			os.remove(out_file)
			shutil.move("{path}/temp_out.mkv".format(path=tempdir),out_file)
			print "Done!"
			
		# These are the ffmpeg commands I need for each sound effect
		# The first generates a silent track, with variable length. This gets concatenated to the front of the sound effect.
		silence_command = ["ffmpeg","-f","lavfi","-i","anullsrc=r=8192:cl=mono","-t","{length}","-f","wav","-y","{path}/silence.wav"]
		# The second concatenates the silent track and the sound effect, producing a sound file that can be mixed into the video's audio track so that it plays at the correct time.
		SFX_command = ["ffmpeg","-i","{path}/silence.wav","-i","{path}/sounds/{sfx}.wav","-filter_complex","[0:a] [1:a] concat=n=2:v=0:a=1","-y","{path}/sfx.wav"]
		# The third mixes the silence+sound effect into the video file
		merge_command = ["ffmpeg","-i",out_file,"-i","{path}/sfx.wav","-filter_complex","[0:a][1:a] amix=inputs=2:duration=longest:dropout_transition={video_length},volume=2","-c:a","pcm_s16le","-c:v","copy","-max_muxing_queue_size","1024","-y","{path}/temp_out.mkv"]

##        normalise_command = ["ffmpeg","-i",out_file,"-filter_complex","dynaudnorm","{path}/temp_out.mkv".format(path=tempdir)]
##        for sfx in ["SFX1","SFX2","SFX3"]:
##            if not os.path.isfile("{path}/sounds/{sfx}.wav".format(path=tempdir,sfx=sfx)):
##                print sfx+" does not exist."
##                continue
##            else:

		# Read in the sound effect usage data
		print "Reading sound effect usage..."
		with open("{path}/sounds/SFX usage.txt".format(path=tempdir),"r") as sfx_usage_file:
			sfx_usage = sfx_usage_file.read().split("\n")
		print "Done!"

		# Iterate through the frames, checking if sound effects need to be added
		for frame in range(len(sfx_usage)):
			line = sfx_usage[frame]
			# If a frame has an associated sound effect, get which sound effect to use
			sfx = line.split(":")[1].strip() if line.strip() != "" else ""
			if sfx != "": # If a sound effect must be played...
				length = frame/float(fps)
				print "Adding "+sfx+" at {length} seconds into the video.".format(length=length)
				# ...run each command in series with the correct arguments
				with open(os.devnull,"w") as null:
					subprocess.call([i.format(path=tempdir,sfx=sfx,length=length) for i in silence_command],stdout=null,stderr=null)
					subprocess.call([i.format(path=tempdir,sfx=sfx) for i in SFX_command],stdout=null,stderr=null)
					subprocess.call([i.format(path=tempdir,video_length=fps*len(sfx_usage)) for i in merge_command],stdout=null,stderr=null)
					os.remove(out_file)
					shutil.move("{path}/temp_out.mkv".format(path=tempdir),out_file)
				print "Done!"
				time.sleep(sleep_time) # optional sleep -- in case you want to slow things down for HDD strain or reliability or something

##        subprocess.call(normalise_command)
##        os.remove(out_file)
##        shutil.move("{path}/temp_out.mkv".format(path=tempdir),out_file)
				

		# Remove the temp dir and all files in it
		print "Removing temporary directory..."
		shutil.rmtree(tempdir)
		print "Done!"
			
	else:
		print "Error!\nThere's no such mode."
