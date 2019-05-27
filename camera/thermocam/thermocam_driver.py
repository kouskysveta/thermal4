import usb.core
import usb.util
import numpy
import sys
import os
import cv2

import pixelmathA


# noinspection PyMethodMayBeStatic,PyGlobalUndefined,PyShadowingNames,PyBroadException
class CameraDriver:
	bwcolor = -1
	pixelcorr = 1
	listfile = -1
	noraster = 1
	applyoffs = -1
	avg9 = 1
	useshuttercal = 1
	ForC = 1
	mkr1tamf = 0
	tzoom = -1
	useframe10 = -1
	useframe1 = 1
	imgw = 206
	imgh = 156
	diffshouldbe = -400
	ambientT = 78
	pixel1atT = 4371
	sensrref = 7679
	palfile = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
	palnum = 0
	panechanged = 0
	minmaxmkr = 1
	imgscale = 1
	firstcalframe = 0

	kclrs = numpy.zeros((1024, 3), dtype=numpy.uint8)
	mintamf = 16000
	maxtamf = 4
	tamfctr = 2415
	clrsperdeg = 0
	zoomlvl = 0  # to match clrsperdeg
	avgframes = -1

	nimage = 0
	writetestfile = -1
	calibrating = -1

	priorcalframe = 0
	thiscalframe = 0
	priorcalvalue = 0
	thiscalvalue = 0
	calpixel = 118
	correction = 0

	firstscene = 0
	firstimg = 0
	firstcal = 0
	nshutter = 0

	videorec = None
	curvebase = None
	pixl1 = None
	freezeframe = None
	palctr = None
	numberofcolors = None
	tamfsperdeg = None

	def __init__(self):
		pass

	def init(self):
		self.diffcurve = numpy.zeros((13320, 2), dtype=numpy.uint8)
		self.calbfr = numpy.zeros(64896, dtype=numpy.uint8)
		self.refbfr = numpy.zeros(64896, dtype=numpy.uint8)
		self.tamfx22 = numpy.zeros(64896, dtype=numpy.uint8)
		self.rgbbfr = numpy.zeros(97344, dtype=numpy.uint8)
		self.frame10 = numpy.zeros(64896, dtype=numpy.uint8)
		self.bwbfr = numpy.zeros(32448, dtype=numpy.uint8)
		self.negoffsets = numpy.zeros(64896, dtype=numpy.int16)
		self.basevalues = numpy.zeros(64896, dtype=numpy.uint8)
		self.scalebfr = numpy.zeros((self.imgscale * self.imgscale * 97344), dtype=numpy.uint8)
		self.badpxls = None
		self.shutterref = None
		self.sumofimg = numpy.zeros(32448, dtype=numpy.int32)
		self.sumofcal = numpy.zeros(32448, dtype=numpy.int32)

		self.usbinit()
		self.setup()

		if self.ForC < 0: self.ambientT = self.ambientT * 1.8 + 32

		self.readpixelcal()
		self.readrefframe()


	def calibrateCamera(self):
		self.calibrating = 1

	#usb init nalezne zarizeni a vraci dev
	def usbinit(self):
		dev = usb.core.find(idVendor=0x289d, idProduct=0x0010)
		if not dev: raise ValueError('Device not found')

		# set the active configuration. With no arguments, the first configuration will be the active one
		dev.set_configuration()

		# get an endpoint instance
		cfg = dev.get_active_configuration()
		intf = cfg[(0, 0)]

		custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
		ep = usb.util.find_descriptor(intf, custom_match=custom_match)  # match the first OUT endpoint
		assert ep is not None

		self.dev = dev


	def send_msg(self, bmRequestType, bRequest, wValue=0, wIndex=0, data_or_wLength=None, timeout=None):
		self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_wLength, timeout) # == len(data_or_wLength))

	def release(self):
		msg = '\x00\x00'
		for i in range(3):
			self.send_msg(0x41, 0x3C, 0, 0, msg)
		usb.util.dispose_resources(self.dev)

	def setup(self):
		try:
			msg = '\x01'
			self.send_msg(0x41, 0x54, 0, 0, msg)
		except Exception:
			self.release()
			msg = '\x01'
			self.send_msg(0x41, 0x54, 0, 0, msg)

		self.send_msg(0x41, 0x3C, 0, 0, '\x00\x00')
		self.send_msg(0xC1, 0x4E, 0, 0, 4)
		self.send_msg(0xC1, 0x36, 0, 0, 12)
		self.send_msg(0x41, 0x56, 0, 0, '\x20\x00\x30\x00\x00\x00')
		self.send_msg( 0xC1, 0x58, 0, 0, 0x40)
		self.send_msg(0x41, 0x56, 0, 0, '\x20\x00\x50\x00\x00\x00')
		self.send_msg(0xC1, 0x58, 0, 0, 0x40)
		self.send_msg(0x41, 0x56, 0, 0, '\x0C\x00\x70\x00\x00\x00')
		self.send_msg(0xC1, 0x58, 0, 0, 0x18)
		self.send_msg(0x41, 0x56, 0, 0, '\x06\x00\x08\x00\x00\x00')
		self.send_msg(0xC1, 0x58, 0, 0, 0x0C)
		self.send_msg(0x41, 0x3E, 0, 0, '\x08\x00')
		self.send_msg(0xC1, 0x3D, 0, 0, 2)
		self.send_msg(0x41, 0x3E, 0, 0, '\x08\x00')
		self.send_msg(0x41, 0x3C, 0, 0, '\x01\x00')
		self.send_msg(0xC1, 0x3D, 0, 0, 2)

	def readpixelcal(self):
		try:
			fp = open(os.path.dirname(os.path.realpath(__file__)) + "/pixelcal.txt", 'r')
			self.badpxls = numpy.empty(32448, dtype=numpy.uint8)
			ix = 0
			while ix < self.imgh * self.imgw:
				s = fp.readline()
				self.badpxls[ix] = int(s)
				ix = ix + 1
			fp.close()
		except:
			self.badpxls = numpy.full(32448, 100, dtype=numpy.uint8)
			self.badpxls[1] = 0
			for i in range(10, 32430, 15):
				self.badpxls[i] = 0

	def readrefframe(self):
		try:
			fp = open(os.path.dirname(os.path.realpath(__file__)) + "/refframe.txt", 'r')
			self.shutterref = numpy.empty(32448, dtype=numpy.int16)
			ix = 0
			while ix < self.imgh * self.imgw:
				s = fp.readline()
				self.shutterref[ix] = int(s)
				ix = ix + 1
			fp.close()
		except:
			self.shutterref = numpy.full(32448, 8000, dtype=numpy.uint16)
			self.shutterref[1] = 1
			for i in range(10, 32430, 15):
				self.shutterref[i] = 0

	def setframe10cal(self):
		ix = 0
		while ix < self.imgw * self.dev.imgh:
			self.badpxls[ix] = self.frame10[2 * ix]
			ix = ix + 1

	def read_cam_input_to_buffers(self):

		while True:
			# Send read frame request
			self.send_msg(0x41, 0x53, 0, 0, '\xC0\x7E\x00\x00')

			# try:
			ret9 = self.dev.read(0x81, 0x3F60, 1000)
			ret9 += self.dev.read(0x81, 0x3F60, 1000)
			ret9 += self.dev.read(0x81, 0x3F60, 1000)
			ret9 += self.dev.read(0x81, 0x3F60, 1000)
			# except Exception as e:
			#	print(e)
			# except usb.USBError:
			#	sys.exit()

			status = ret9[20]

			if status == 4:
				self.basevalues = ret9

			if status == 70:  # change to 70 when not used
				self.negoffsets = ret9

			if status == 9:
				ambientIndex = int(21.94 * (40 + self.ambientT))  # location of ambient temp on curve 9
				self.sensrref = 291 + self.pixel1atT + ((ret9[2 * ambientIndex + 1] << 8) + ret9[2 * ambientIndex])

				self.curvebase = (ret9[2] + 256 * ret9[3])
				ix = 0
				index = 0
				while index < 11316:
					index = (ret9[2 * ix] + 256 * ret9[2 * ix + 1]) - self.curvebase
					if (index > -1) & (index < 11317):
						self.diffcurve[index][0] = ix & 0xff
						self.diffcurve[index][1] = ix >> 8
					ix = ix + 1

				if self.ForC > 0: self.tamfsperdeg = 14636.0 / 667.0
				if self.ForC < 0: self.tamfsperdeg = 14636.0 / 371.0

			if status == 10:  #Expand
				pixelmathA.strip2col(ret9, self.frame10, self.basevalues)
				if self.useframe10 > 0: self.setframe10cal()

			if status == 1:
				if self.useframe1 > 0: pixelmathA.strip2col(ret9, self.calbfr, self.basevalues)
				if self.useframe1 < 0: self.calbfr = self.refbfr
				if self.firstcalframe == 0: self.firstcalframe = 1

				if (self.thiscalframe < 1) & (self.nimage > 0):
					self.thiscalframe = self.nimage
					# Calculate the normalized value of the cal frame at the chosen pixel
					self.thiscalvalue = 100 * ((ret9[2 * self.calpixel + 1] << 8) + ret9[2 * self.calpixel]) / self.badpxls[self.calpixel]

				if self.thiscalframe > 0:
					self.priorcalframe = self.thiscalframe
					self.thiscalframe = self.nimage
					self.priorcalvalue = self.thiscalvalue
					self.thiscalvalue = 100 * ((ret9[2 * self.calpixel + 1] << 8) + ret9[2 * self.calpixel]) / self.badpxls[self.calpixel]
				self.nshutter = self.nshutter + 1

			if status == 3:
				self.stripbfr = numpy.zeros(64896, dtype=numpy.uint8)
				pixelmathA.strip2col(ret9, self.stripbfr, self.basevalues)  # Remove the 2 garbage columns at right edge
				if self.writetestfile > 0: self.refbfr = ret9

				correction = 0
				if self.priorcalframe > 0:
					self.framedelta = self.thiscalframe - self.priorcalframe
					self.pixeldelta = self.thiscalvalue - self.priorcalvalue

					if ((abs(self.pixeldelta) > 20) & (
						abs(self.pixeldelta) < 1000)):  # More than 2 degree F change between cal frames, but not the big jump
						perframestep = self.pixeldelta / self.framedelta
						correction = perframestep * (self.nimage - self.thiscalframe)

				if (self.calibrating < 0) | ((self.calibrating > 0) & (self.firstcalframe < 1)): self.firstimg = self.nimage
				if (self.calibrating > 0) & (self.firstcalframe > 0):
					# Do the addition in C because python takes too long on the Rpi
					pixelmathA.addimages(self.stripbfr, self.calbfr, self.sumofimg, self.imgw, self.imgh, self.nimage, self.firstimg)

					if self.nimage > (self.firstimg + 9):
						self.calibrating = -1
						self.firstimg = 0

						filePath = os.path.dirname(os.path.realpath(__file__)) + "/calfile.txt"
						if os.path.exists(filePath):
							os.remove(filePath)
						f2 = open(filePath, 'w')
						ix = 0
						while ix < self.imgw * self.imgh:
							if self.sumofimg[ix] > 0: self.sumofimg[ix] = 0  # Get rid of what will be negative numbers
							s = str(int(100 * self.sumofimg[ix] / (self.diffshouldbe * 10))) + "\n"  # just write scaling factors
							f2.write(s)
							ix = ix + 1
						f2.close()

						filePath = os.path.dirname(os.path.realpath(__file__)) + "/refframe.txt"
						if os.path.exists(filePath):
							os.remove(filePath)
						f2 = open(filePath, 'w')
						ix = 0
						while ix < self.imgw * self.imgh:
							s = str((self.calbfr[2 * ix + 1] << 8) + self.calbfr[2 * ix]) + "\n"  # just write ref pixel factors
							f2.write(s)
							ix = ix + 1
						f2.close()

				self.nimage = self.nimage + 1
				mintamfbfr = numpy.zeros(5, dtype=numpy.uint8)
				maxtamfbfr = numpy.zeros(5, dtype=numpy.uint8)
				diffs = numpy.zeros((self.imgw * self.imgh), dtype=numpy.int16)

				palctr =10
				numberofcolors=255
				pixelmathA.shuttercal(self.stripbfr, self.calbfr, self.tamfx22, self.rgbbfr, self.kclrs, self.badpxls, self.bwbfr, self.diffcurve, diffs, self.negoffsets, self.shutterref, mintamfbfr,maxtamfbfr, self.sensrref - correction, self.curvebase, self.bwcolor, self.pixelcorr, self.noraster, self.listfile, self.applyoffs, self.avg9, self.useshuttercal,self.ForC, self.mkr1tamf, self.tzoom, self.imgw, self.imgh, palctr, self.tamfctr,numberofcolors, self.clrsperdeg, self.tamfsperdeg)

				break
				# return self.tamfx22


	def get_temp_matrix(self):
		self.read_cam_input_to_buffers()
		tempMatrix = numpy.around((self.tamfx22[0::2] + 256 * self.tamfx22[1::2]) / self.tamfsperdeg - 40, 1)
		tempMatrix = numpy.around(5 * (tempMatrix - 32) / 9, 1)
		return tempMatrix


	def convert_temp_to_image(self, temp_mat):
		imgw = 206
		imgh = 156
		maxtemp = max(temp_mat)

		temp_mat = temp_mat / maxtemp
		temp_mat = numpy.reshape(temp_mat[0:imgw * imgh], (imgh, imgw))
		temp_mat = numpy.abs(temp_mat)

		return temp_mat


	def run(self):
		while True:
			temp_mat = self.get_temp_matrix()
			image_bw = self.convert_temp_to_image(temp_mat)

			cv2.imshow('image', image_bw)
			keyStroke = cv2.waitKey(33)
			if keyStroke == ord('q'):
				break
			elif keyStroke == ord('c'):
				self.calibrateCamera()

		cv2.destroyWindow('image')


if __name__ == "__main__":
	cam = CameraDriver()
	cam.init()
	cam.run()

