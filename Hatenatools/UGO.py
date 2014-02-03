#UGO.py by pbsds
#AGPL3 licensed
#
#This class reads and writes UGO files.
#It can also export and import it in a xml format
#Extended functionality added by PPM.py
#
#Credits:
#
#	-Jsafive for supplying .ugo files
#
#Note:
#	The current implentation can possibly mess up the files stored in Section #2, but will do for most needs
#	Next version will probably bring a big change in the ugoxml format
#
import sys, os
from base64 import b64encode, b64decode
import xml.etree.ElementTree as ET

try:
	import PPM
	HasPPM = True
except ImportError:
	HasPPM = False

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
def zipalign(length, r=4):
	return length + (4 - length % r) if length % r else length
def indentXML(elem, level=0):#"borrowed" from: http://effbot.org/zone/element-lib.htm#prettyprint
    i = "\n" + level*"\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indentXML(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

#class UGO:
class UGO:
	def __init__(self):
		self.Loaded = False
	def ReadFile(self, path):
		f = open(path, "rb")
		ret = self.Read(f.read())
		f.close()
		return ret
	def Read(self, data):
		#Filestructure:
		#	- Header
		#	- Table of Contents
		#	- Padding, normally of length 2
		#	- Extra Data
		#	- Padding
		#The padding seems to do zipaligning to a length of 4
		global HasPPM
		
		#Header:
		if data[:4] <> "UGAR": return False#The file isn't a UGO file
		Sections    = AscDec(data[ 4: 8], True)#could also be version
		if Sections >= 1:
			self.TableLength = AscDec(data[ 8:12], True)
		if Sections >= 2:
			self.ExtraLength = AscDec(data[12:16], True)
		if Sections > 2:
			print "Warning: This UGO file has more than the 2 known sections:",Sections
			print "Please send this UGO file to pbsds over at pbsds.net"
			print "This file could possibly be read incorrectly..."
		headerlength = 8 + Sections*4
		
		#Read table of contents:
		#A table where the rows are seperated with newlines, and colons with tabs
		if Sections >= 1:
			TableOfContents = tuple((i.split("\t") for i in data[headerlength:headerlength+self.TableLength].split("\n")))
		else:
			TableOfContents = []
		
		#Extra data:
		if Sections >= 2:
			ExtraData = data[zipalign(headerlength+self.TableLength) : zipalign(headerlength+self.TableLength)+self.ExtraLength]
		
		#Parse data:
		self.Items = []
		
		#todo: implement this:
		self.Files = []#[i] = (filename, filecontent)
		#see todo.txt
		
		pos = 0#Extra Data position
		tmbcount = 1#used if HasPPM is False
		ntftcount = 1#used if no label
		names = []
		for i in TableOfContents:
			type = int(i[0])
			if   type == 0:#layout
				#I've always seen just numbers here.
				#The amount of numbers also differ.
				#maybe related to color scheme? or the button scheme/layout
				
				#all pages containing TMBs have so far been: i = ["0", "2", "1"]
				self.Items.append(("layout", map(int, i[1:])))
				continue
			elif type == 1:#Text on topscreen
				num = int(i[1])#always seen as 0, unknown purpose
				labels = [b64decode(i[n]).decode("UTF-16LE") for n in xrange(2,7)]#5 labels probably one label for each line of text
				
				self.Items.append(("topscreen text", labels, num))
				continue
			elif type == 2:#catogories(like "reccomended" and "new flipnotes" and "most popular")
				#this one may visually change greatly depending on what layout is set in type==0
				
				link = i[1]
				label = b64decode(i[2]).decode("UTF-16LE")
				selected = int(i[3]) <> 0#bool
				
				self.Items.append(("category", link, label, selected))
				continue
			elif type == 3:#POST button/link to POST form. "Post Flipnote" uses this
				link = i[1]
				label = b64decode(i[2]).decode("UTF-16LE")
				
				self.Items.append(("post", link, label))
				continue
			elif type == 4:#Button
				link = i[1]
				trait = int(i[2])
				label = b64decode(i[3]).decode("UTF-16LE")
				other = i[4:]#varies
				
				#extra data
				file = None#== ("filename", "filedata")
				if trait < 100 and ExtraData:
					if ExtraData == "\x20":#empty
						pass#no files
					elif ExtraData[pos:pos+4] == "PARA":#tmb file
						file = ExtraData[pos:pos+0x6A0]
						pos += 0x6A0
						
						if HasPPM:
							tmb = PPM.TMB().Read(file)
							name = tmb.CurrentFilename[:-4]
							del tmb
						else:
							name = "embedded tmb #%i" % tmbcount
							tmbcount += 1
						
						if name+".tmb" in names:
							j = 2
							while "%s_%i.tmb" % (name, j) not in names:
								j += 1
							name = "%s_%i" % (name, j)
						
						file = (name+".tmb", file)
						names.append(name+".tmb")
					else:#ntft icon
						name = label.encode("ascii", "ignore")
						if not name:
							name = "nameless ntft %i" % ntftcount
							ntftcount += 1
						
						if name+".ntft" in names:
							j = 2
							while "%s_%i.ntft" % (name, j) not in names:
								j += 1
							name = "%s_%i" % (name, j)
						
						file = (name+".ntft", ExtraData[pos:pos+2048])
						names.append(name+".ntft")
						pos += 2048
				
				self.Items.append(("button", trait, label, link, other, file))
				
				
				# if   subtype == 3:#flipnote
					# tmb = PPM.TMB().Read(ExtraData[pos:pos+0x6A0]); pos += 0x6A0
					# unknown1 = i[3]#empty
					# stars = int(i[4])#not sure
					# unknown2 = map(int, i[5:8])#unknown = [765, 573, 0]
					
					# self.Items.append(("flipnote", link, tmb, stars, unknown1, unknown2))
					# continue
				# elif subtype == 100: pass
				# elif subtype == 101: pass
				# elif subtype == 102: pass
				# elif subtype == 104:#list item? like mails and announcements
					# label = b64decode(i[3]).decode("UTF-16LE")
					# unknown = i[4]
					# num = int(i[5])#only seen as 0
					
					# # self.Items.append(("list item?", link, label, unknown, num))
					# # continue
					# pass
				# elif subtype == 115:#Labeled button link(size of a flipnote thumbnail, commonly "next page")
					# label = b64decode(i[3]).decode("UTF-16LE")
					# unknown = i[4:6]
					# self.Items.append(("thumbnail link", link, label, unknown))
					# continue
				# elif subtype == 117: pass
				continue
			
			#if not recognized:
			self.Items.append(("unknown", i))
			print "Unknown UGO item discovered:", i
		self.Loaded = True
		return self
	def WriteFile(self, path):
		if self.Loaded:
			out = self.Pack()
			if out:
				f = open(path, "wb")
				f.write(out)
				f.close()
				return True
			else:
				return False
	def Pack(self):
		if not self.Loaded: return False
		
		Header = ["UGAR", None]
		TableOfContents = []
		ExtraData = []
		
		#Encode data:
		for i in self.Items:
			if   i[0] == "unknown":
				TableOfContents.append("\t".join(i[1]))
			elif i[0] == "layout":#0
				TableOfContents.append("\t".join(["0"] + map(str, list(i[1]))))
			elif i[0] == "topscreen text":#1
				labels, num = i[1:]
				
				num = str(num)
				for i in xrange(5):
					labels[i] = b64encode(labels[i].encode("UTF-16LE"))
				
				TableOfContents.append("\t".join(("1", num, labels[0], labels[1], labels[2], labels[3], labels[4])))
			elif i[0] == "category":#2
				link, label, selected = i[1:]
				
				label = b64encode(label.encode("UTF-16LE"))
				selected = str(1*selected)
				
				TableOfContents.append("\t".join(("2", link, label, selected)))
			elif i[0] == "post":#3
				link, label = i[1:]
				
				label = b64encode(label.encode("UTF-16LE"))
				
				TableOfContents.append("\t".join(("3", link, label)))
			elif i[0] == "button":#4
				trait, label, link, other, file = i[1:]
				
				trait = str(trait)
				label = b64encode(label.encode("UTF-16LE"))
				
				TableOfContents.append("\t".join(["4", link, trait, label] + list(other)))
				
				if file:
					ExtraData.append(file[1])
			else:
				print "Unrecognized entry in self.Items:", i
		TableOfContents = "\n".join(TableOfContents)
		ExtraData = "".join(ExtraData)
		
		#Format data:
		Sections = 0
		if TableOfContents:
			Sections += 1
			Header.append(DecAsc(len(TableOfContents), 4, True))
			
			#padding/zipaligning
			if len(TableOfContents) % 4:
				TableOfContents += "\0" * (4 - len(TableOfContents) % 4)
		if ExtraData:
			Sections += 1
			Header.append(DecAsc(len(ExtraData), 4, True))
			
			#padding/zipaligning
			if len(ExtraData) % 4:
				ExtraData += "\0" * (4 - len(ExtraData) % 4)
		Header[1] = DecAsc(Sections, 4, True)
		
		#Zip up and send the file:
		return "".join(Header) + TableOfContents + ExtraData
	#XML
	def WriteXML(self, xmlname="content.ugoxml", folder="content.ugoxml embedded"):#WIP
		if not self.Loaded: return False
		
		path, xmlname = os.path.split(xmlname)
		ugo_xml = ET.Element("ugo_xml")
		files = []
		
		for i in self.Items:
			if   i[0] == "unknown":
				elem = ET.SubElement(ugo_xml, "raw", type=i[1][0])
				for value in i[1][1:]:
					ET.SubElement(elem, "value").text = value
				continue
			elif i[0] == "layout":#0
				elem = ET.SubElement(ugo_xml, "layout")
				for value in i[1]:
					ET.SubElement(elem, "value").text = str(value)
				continue
			elif i[0] == "topscreen text":#1
				elem = ET.SubElement(ugo_xml, "title")
				labels, num = i[1:]
				
				for label in labels:
					ET.SubElement(elem, "label").text = label
				
				ET.SubElement(elem, "num").text = str(num)
				continue
			elif i[0] == "category":#2
				elem = ET.SubElement(ugo_xml, "category")
				link, label, selected = i[1:]
				
				ET.SubElement(elem, "label").text = label
				ET.SubElement(elem, "address").text = link
				ET.SubElement(elem, "selected").text = str(selected).lower()
			elif i[0] == "post":#3
				elem = ET.SubElement(ugo_xml, "post")
				link, label = i[1:]
				
				ET.SubElement(elem, "label").text = label
				ET.SubElement(elem, "address").text = link
			elif i[0] == "button":#4
				elem = ET.SubElement(ugo_xml, "button")
				trait, label, link, other, file = i[1:]
				
				ET.SubElement(elem, "label").text = label
				ET.SubElement(elem, "address").text = link
				ET.SubElement(elem, "trait").text = str(trait)#todo: add names
				
				for n, value in enumerate(other):
					entry = ET.SubElement(elem, "value")
					entry.text = value
					if n == 0 and trait == 3:
						entry.attrib["tip"] = "stars"
				
				if file:
					ET.SubElement(elem, "embedded_file").text = os.path.join(folder, file[0])
					files.append((os.path.join(folder, file[0]), file[1]))
		
		#intend
		indentXML(ugo_xml)
		
		#pack xml
		files.append((xmlname, ET.tostring(ugo_xml, encoding="UTF-8")))
		
		#write files
		if not os.path.isdir(os.path.join(path, folder)):
			os.mkdir(os.path.join(path, folder))
		for name, data in files:
			f = open(os.path.join(path, name), "wb")
			f.write(data)
			f.close()
	def ReadXML(self, xmlfile, silent=True):
		ugo_xml = ET.parse(xmlfile).getroot()
		xmlpath = os.path.split(xmlfile)[0]
		
		Items = []
		for elem in ugo_xml:
			if elem.tag == "raw":
				if "type" not in elem.attrib:
					if not silent: print "Invalid formatting. <raw> without \"type\" attribute"
					return False
				values = [elem.attrib["type"]]
				for value in elem:
					if value.tag <> "value":
						if not silent: print "Invalid formatting. <%s> found within <unknown>" % value.tag
						return False
					values.append(value.text if value.text else "")
				
				Items.append(("unknown", values))
			elif elem.tag == "layout":#0
				values = []
				for value in elem:
					if value.tag <> "value":
						if not silent: print "Invalid formatting. <%s> found within <layout>" % value.tag
						return False
					if not value.text.isdigit():
						if not silent: print "Invalid entry. <value> in <layout> is not a number" % value.tag
						return False
					values.append(int(value.text))
				Items.append(("layout", values))
			elif elem.tag == "title":#1
				labels = ["", "", "", "", ""]
				num = 0
				pos = 0
				numset = False
				
				for value in elem:
					if value.tag not in ("label", "num"):
						if not silent: print "Invalid formatting. <%s> found within <title>" % value.tag
						return False
					if value.tag == "label":
						if pos >= 5:
							if not silent: print "Invalid formatting. More than 5 <labels> in <title>"
							return False
						if value.text: labels[pos] = value.text
						pos += 1
					elif value.tag == "num":
						if numset:
							if not silent: print "Invalid formatting. Multible <num> in <title>"
							return False
						if not value.text.isdigit():
							if not silent: print "Invalid entry. <num> in <title> is not a number!"
							return False
						num = int(value.text)
						numset = True
						
				Items.append(("topscreen text", labels, num))
			elif elem.tag == "category":#2
				link = None
				label = None
				selected = None
				
				for value in elem:
					if value.tag not in ("label", "address", "selected"):
						if not silent: print "Invalid formatting. <%s> found within <category>" % value.tag
						return False
					
					if value.tag == "address":
						if isinstance(link, str):
							if not silent: print "Invalid formatting. multible <address> within <category>"
							return False
						link = value.text if value.text else ""
					elif value.tag == "label":
						if isinstance(label, str):
							if not silent: print "Invalid formatting. multible <label> within <category>"
							return False
						label = value.text if value.text else ""
					elif value.tag == "selected":
						if selected in (True, False):
							if not silent: print "Invalid formatting. multible <selected> within <category>"
							return False
						selected = value.text[0].lower() in "t1"
				
				Items.append(("category", link, label, selected))
			elif elem.tag == "post":#3
				label = None
				link = None
				
				for value in elem:
					if value.tag == "label":
						if isinstance(label, str):
							if not silent: print "Invalid formatting. Multible <label> within <post>"
							return False
						label = value.text if value.text else ""
					elif value.tag == "address":
						if isinstance(link, str):
							if not silent: print "Invalid formatting. Multible <address> within <post>"
							return False
						link = value.text if value.text else ""
				
				if None in (link, label):
					if not silent: print "Invalid formatting. <button> lacks either a <address> or <label>"
					return False
				
				Items.append(("post", link, label))
			elif elem.tag == "button":#4
				trait = None#todo: add names
				label = None
				link = None
				other = []
				file = None
				
				for value in elem:
					if value.tag not in ("label", "address", "trait", "value", "embedded_file"):
						if not silent: print "Invalid formatting. <%s> found within <button>" % value.tag
						return False
					
					if value.tag == "label":
						if isinstance(label, str):
							if not silent: print "Invalid formatting. Multible <label> within <button>"
							return False
						label = value.text if value.text else ""
					elif value.tag == "address":
						if isinstance(link, str):
							if not silent: print "Invalid formatting. Multible <address> within <button>"
							return False
						link = value.text if value.text else ""
					elif value.tag == "trait":#todo: add names
						if isinstance(trait, str):
							if not silent: print "Invalid formatting. Multible <trait> within <button>"
							return False
						if not value.text.isdigit():
							if not silent: print "Invalid entry. <trait> in <button> is not a number"
							return False
						trait = int(value.text)
					elif value.tag == "value":
						other.append(value.text if value.text else "")
					elif value.tag == "embedded_file":
						if file <> None:
							if not silent: print "Invalid formatting. Multible <embedded_file> within <button>"
							return False
						
						path = os.path.join(xmlpath, value.text)
						if not os.path.isfile(path):
							if not silent: print "Invalid entry. Embedded file \"%s\" not found!" % value.text
							print path
							return False
						
						
						f = open(path, "rb")
						file = (os.path.split(value.text)[1], f.read())
						f.close()
				
				if None in (trait, label, link):
					if not silent: print "Invalid formatting. <button> lacks either a <trait>, a <address> or a <label>"
					return False
				
				Items.append(("button", trait, label, link, other, file))
			else:
				if not silent:
					print "Invalid formatting: <%s> found within <ugo_xml>" % elem.tag
			
		self.Items = Items
		self.Loaded = True
		return self

if __name__ == "__main__":
	print "              ==      UGO.py      =="
	print "             ==      by pbsds      =="
	print "              ==       v0.92      =="
	print
	
	if len(sys.argv) < 2:
		print "Usage:"
		print "      UGO.py [<mode>] <input> [<output> [<foldername>]]"
		print ""
		print "      <Mode>:"
		print "          -d: Converts the UGO file in <input> to a UGOXML file with the same"
		print "              name, unless <output> is specified. Any embedded files will be"
		print "              written to a folder called UGOXML-filename + \" embedded\" unless"
		print "              <foldername> is given."
		print "              <foldername> is relative to the XML."
		print "          -e: Converts the UGOXML file in <input> to a UGO file with the same"
		print "              name, unless <output> is specified."
		print "          If mode is not specified, it will try to find out for itself"
		sys.exit()
	
	mode = sys.argv[1]
	if mode not in ("-d", "-e"):
		if os.path.exists(mode):#the mode is actually the file
			f = open(mode, "rb")
			magic = f.read(4)
			f.close()
			
			if magic == "UGAR":
				mode = "-d"
				print "No mode specified. UGO -> UGOXML chosen"
			else:
				mode = "-e"
				print "No mode specified. UGOXML -> UGO chosen"
			
			sys.argv.insert(1, mode)
		else:
			print "Invalid <mode> given!"
			sys.exit()
	
	if mode == "-d":
		input = sys.argv[2]
		output = sys.argv[3] if len(sys.argv) >= 4 else sys.argv[2]+"xml"
		foldername = sys.argv[4] if len(sys.argv) >= 5 else os.path.split(output)[1] + " embedded"
		
		print "Reading %s..." % os.path.split(input)[1]
		ugo = UGO().ReadFile(input)
		if not ugo:
			print "Error!\n The given file is not a UGO file!"
			sys.exit()
		print "Done!"
		
		print "Writing XML..."
		ugo.WriteXML(output, foldername)
		
		print "Done!\n\nHave a nice day!"
	if mode == "-e":
		input = sys.argv[2]
		output = sys.argv[3] if len(sys.argv) >= 4 else ".".join(sys.argv[2].split(".")[:-1]) + ".ugo"
		
		print "Reading %s..." % os.path.split(input)[1]
		try:
			ugo = UGO().ReadXML(input, False)
		except EL.ParseError:
			print "Error!\nThe given file is not in the XML format!"
			ugo = False
		if not ugo:
			#it prints sufficient errormessages
			#print "Error!\n The given file is not a UGO file!"
			sys.exit()
		print "Done!"
		
		print "Writing UGO..."
		ugo.WriteFile(output)
		print "Done"