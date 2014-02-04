#NTFT.py by pbsds
#AGPL3 licensed
#
#PIL is required to read and write images to disk
#
#Credits:
#
#	-The guys behind TiledGGD. This sped up my work a lit.
#	-Jsafive for supplying .ugo files
#
import sys, os
try:
	import Image
	hasPIL = True
except ImportError:
	hasPIL = False


#helpers
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
def clamp(value, min, max):
	if value > max: return max
	if value < min: return min
	return value

#Class NTFT:
#
#	The NTFT image format stores RGB values as 5 bits each: a value between 0 and 31.
#	It has 1 bit of transparancy, which means its either vidssible or invisible. No gradients.
#	
#	How to use:
#		
#		Converting to NTFT file:
#			
#			image = ReadImage(input_path)
#			NTFT().SetImage(image).WriteFile(output_path)
#			
#		Reading NTFT file:
#			
#			ntft = NTFT().ReadFile(input_path, (width, height))
#			WriteImage(ntft.Image, output_path)
#		
class NTFT:
	def __init__(self):
		self.Loaded = False
	def ReadFile(self, path, size):
		f = open(path, "rb")
		ret = self.Read(f.read(), size)
		f.close()
		return ret
	def Read(self, data, (w, h)):
		#the actual stored data is a image with the sizes padded to the nearest power of 2. The image is then clipped out from it.
		psize = []
		for i in (w, h):
			p = 1
			while 1<<p < i:
				p += 1
			psize.append(1<<p)
		pw, ph = psize
		
		#check if it fits the file:
		if pw*ph*2 <> len(data):
			print "Invalid sizes"
			return False
		
		#JUST DO IT!
		self.Image = [[None for _ in xrange(h)] for _ in xrange(w)]
		for y in xrange(h):
			for x in xrange(w):
				pos = (x + y*pw)*2
				byte = AscDec(data[pos:pos+2], True)
				
				#ARGB1555 -> RGBA8:
				a = (byte >> 15       ) * 0xFF
				b = (byte >> 10 & 0x1F) * 0xFF / 0x1F
				g = (byte >> 5  & 0x1F) * 0xFF / 0x1F
				r = (byte       & 0x1F) * 0xFF / 0x1F
				
				self.Image[x][y] = (r<<24) | (g<<16) | (b<<8) | a#RGBA8
		
		self.Loaded = True
		return self
	def WriteFile(self, path):
		if self.Loaded:
			f = open(path, "wb")
			f.write(self.Pack())
			f.close()
			return True
		else:
			return False
	def Pack(self):
		if not self.Loaded:
			return False
		
		w = len(self.Image[0])
		h = len(self.Image)
		
		#the actual stored data is a image with the sizes padded to the nearest power of 2
		psize = []
		for i in size:
			p = 1
			while 1<<p < i:
				p += 1
			padded_size.append(1<<p)
		
		out = []
		for y in xrange(psize[1]):
			for x in xrange(psize[0]):
				#read
				c = self.Image[clamp(x, 0, w-1)][clamp(y, 0, h-1)]
				r =  c >> 24
				g = (c >> 16) & 0xFF
				b = (c >> 8 ) & 0xFF
				a =  c        & 0xFF
				
				#convert
				a = 1 if a >= 0x80 else 0
				r = r * 0x1F / 0xFF
				g = g * 0x1F / 0xFF
				b = b * 0x1F / 0xFF
				
				#store
				out.append(DecAsc((a<<15) | (b<<10) | (g<<5) | r, 2, True))
		
		return "".join(out)
	def SetImage(self, Image):
		self.Image = Image
		self.Loaded = True
		return self

#Function WriteImage:
#
#	Writes a 2D list of uint32 RGBA values as a image files.
#	Designed to work with NTFT.Image
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

#Function ReadImage:
#
#	Returns a 2D list of uint32 RGBA values of the image file.
#	This can be passed into NTFT().SetImage()
#
#	This function requires the PIl imaging module
def ReadImage(path):
	if not hasPIL: return False
	
	image = Image.open(path)
	pixeldata = image.getdata()
	w, h = image.size
	
	if len(pixeldata[0]) < 4:
		def Combine((r, g, b)):
			return (r << 24) | (g << 16) | (b << 8) | 0xFF
	else:
		def Combine((r, g, b, a)):
			return (r << 24) | (g << 16) | (b << 8) | a
	
	ret = []
	for x in xrange(w):
		line = []
		for y in xrange(h):
			line.append(Combine(pixeldata[y*w + x]))
		ret.append(line)
	
	return ret



#testing:
# i = NTFT().ReadFile("NTFTtests/kaeru.ntft", (36, 30))
# WriteImage(i.Image, "NTFTtests/kaeru.png")

# i = NTFT().ReadFile("NTFTtests/News.ntft", (32, 32))
# WriteImage(i.Image, "NTFTtests/News.png")

# i = NTFT().ReadFile("NTFTtests/Special Room.ntft", (32, 32))
# WriteImage(i.Image, "NTFTtests/Special Room.png")

#i = NTFT()
#i.Loaded = True
#i.Image = ReadImage("NTFTtests/geh.png")
#i.WriteFile("NTFTtests/geh.ntft")



if __name__ == "__main__":
	print "              ==      NTFT.py     =="
	print "             ==      by pbsds      =="
	print "              ==       v0.72      =="
	print
	
	if not hasPIL:
		print "PIL not found! Exiting..."
	
	if len(sys.argv) < 3:
		print "Usage:"
		print "      NTFT.py <input> [<output> [<width> <height>]]"
		print ""
		print "Can convert a NTFT to PNG or the other way around."
		print "if <output> isn't spesified it will be set to <input> with an another extention"
		print ""
		print "The NTFT file contain only the colordata, so it's up to the user to find or"
		print "store the resolution of the image. <width> and <height> is required"
		print "to convert a NTFT file to a image."
		print "32x32 is the normal resolution for button icons in UGO files."
		sys.exit()
	
	input = sys.argv[1]
	Encode = True#if false it'll decode
	
	if input[-4:].lower == "ntft" or len(sys.argv) >= 5:
		Encode = False
	
	if len(sys.argv) >= 3:
		output = sys.argv[2]
		
		if len(sys.argv) >= 5:
			if (not sys.argv[3].isdigit()) or (not sys.argv[4].isdigit()):
				print "Invalid sizes"
				sys.exit()
			width = int(sys.argv[3])
			height = int(sys.argv[4])
		else:
			width, height = None, None
	else:
		output = ".".join(input.split(".")[:-1]) + (".ntft" if Encode else ".png")
	
	print "Converting..."
	if Encode:
		i = NTFT()
		i.Loaded = True
		i.Image = ReadImage(input)
		i.WriteFile(output)
	else:
		WriteImage(NTFT().ReadFile(input, (width, height)).Image, output)
	print "Done!"