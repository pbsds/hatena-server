#NTFT.py by pbsds
#Free to use as long as credit is given to pbsds / Peder Bergebakken Sundt
#PIL is required to write images to disk
#
#Credit:
#
#	-The guys behind TiledGGD at https://code.google.com/p/tiledggd/
#	 This sped up the my work a lot
import sys
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

#Class NTFT:
#
#	todo: write documentation
class NTFT:
	def __init__(self):
		self.Loaded = False
	def ReadFile(self, path, size):
		f = open(path, "rb")
		ret = self.Read(f.read(), size)
		f.close()
		return ret
	def Read(self, data, (w, h)):
		if w*h*2 <> len(data):
			print "Invalid size"
			return False
		
		self.Image = [[None for _ in xrange(h)] for _ in xrange(w)]
		for y in xrange(h):
			for x in xrange(w):
				pos = (x + y*w)*2
				#print pos
				byte = AscDec(data[pos:pos+2], True)
				byte = AscDec(data[pos:pos+2], True)
				#ARGB1555 -> RGBA8:#require true
				a = (byte >> 15       ) * 0xFF
				b = (byte >> 10 & 0x1F) * 0xFF / 0x1F
				g = (byte >> 5  & 0x1F) * 0xFF / 0x1F
				r = (byte       & 0x1F) * 0xFF / 0x1F
				# #RGB565 -> RGBA8:
				# a = 0xFF
				# r = (byte >> 11 & 0x1F) * 0xFF / 0x1F
				# g = (byte >> 5  & 0x3F) * 0xFF / 0x3F
				# b = (byte       & 0x1F) * 0xFF / 0x1F
				#print x, y
				self.Image[x][y] = (r<<24) | (g<<16) | (b<<8) | a#RGBA8
		
		self.Loaded = True
		return self
	def WriteFile(self, path):
		pass
	def Pack(self):
		pass

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

#testing:
# i = NTFT().ReadFile("NTFTtests/kaeru.ntft", (64, 32))
# WriteImage(i.Image, "NTFTtests/kaeru.png")

# i = NTFT().ReadFile("NTFTtests/News.ntft", (32, 32))
# WriteImage(i.Image, "NTFTtests/News.png")

# i = NTFT().ReadFile("NTFTtests/Special Room.ntft", (32, 32))
# WriteImage(i.Image, "NTFTtests/Special Room.png")

if __name__ == "__main__":
	print "              ==      NTFT.py     =="
	print "             ==      by pbsds      =="
	print "              ==       v0.05      =="
	print
	
	if len(sys.argv) < 4:
		print "Usage:"
		print "      NTFT.py <input> <output> <width> <height>"
		print ""
		print "The NTFT file contain only the colordata, so it's up to the user to find and"
		print "store the resolution of the images."
		print "32x32 is the normal size for button icons in UGO files."
		sys.exit()
	
	input = sys.argv[1]
	output = sys.argv[2]
	width = int(sys.argv[3])
	height = int(sys.argv[4])
	
	print "Converting..."
	WriteImage(NTFT().ReadFile(input, (width, height)).Image, output)
	print "Done!"
	