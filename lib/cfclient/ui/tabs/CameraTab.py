#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#	  ||		  ____	_ __
#  +------+		 / __ )(_) /_______________ _____  ___
#  | 0xBC |		/ __  / / __/ ___/ ___/ __ `/_	/ / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/	__/
#	||	||	  /_____/_/\__/\___/_/	 \__,_/ /___/\___/
#
#  Copyright (C) 2011-2013 Bitcraze AB
#
#  Crazyflie Nano Quadcopter Client
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
#  02110-1301, USA.

"""
An example template for a tab in the Crazyflie Client. It comes pre-configured
with the necessary QT Signals to wrap Crazyflie API callbacks and also
connects the connected/disconnected callbacks.
"""

__author__ = 'Bitcraze AB'
__all__ = ['CameraTab']

import logging
import sys, os

logger = logging.getLogger(__name__)

from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot, pyqtSignal, QThread, Qt, QTimer
from PyQt4.QtGui import *

from cfclient.ui.tab import Tab

from cflib.crazyflie.log import LogConfig, Log
from cflib.crazyflie.param import Param

import pdb
from datetime import datetime
import math

try:
	import cv2
	import numpy as np
	should_enable_tab = True
except:
	should_enable_tab = False

camera_tab_class = uic.loadUiType(sys.path[0] +
								"/cfclient/ui/tabs/cameraTab.ui")[0]

# set these appropriately for which channels the prox sensors
# are connected to
PROX_LEFT_LOGNAME  = 'adc.A0'
PROX_RIGHT_LOGNAME = 'adc.A1'
PROX_FRONT_LOGNAME = 'adc.A2'
SONAR_LOGNAME =		 'adc.A3'

PROX_LEFT_THRESHOLD  = int(4095 * 0.6);
PROX_RIGHT_THRESHOLD = int(4095 * 0.6);
PROX_FRONT_THRESHOLD = int(4095 * 0.6);

class CameraTab(Tab, camera_tab_class):
	"""Tab for plotting logging data"""

	_connected_signal = pyqtSignal(str)
	_disconnected_signal = pyqtSignal(str)
	_log_data_signal = pyqtSignal(int, object, object)
	_log_error_signal = pyqtSignal(object, str)
	_param_updated_signal = pyqtSignal(str, str)

	def __init__(self, tabWidget, helper, *args):
		super(CameraTab, self).__init__(*args)
		self.setupUi(self)

		self.tabName = "Camera"
		self.menuName = "Camera Tab"
		self.tabWidget = tabWidget
		self._helper = helper

		# Disable tab if we can't get the OpenCV library (prevents client from failing to start)
		self.enabled = should_enable_tab
		if not self.enabled:
			logger.warning("Couldn't import OpenCV (cv2) library! "
							"Camera tab is disabled")
			return

		# Always wrap callbacks from Crazyflie API though QT Signal/Slots
		# to avoid manipulating the UI when rendering it
		self._connected_signal.connect(self._connected)
		self._disconnected_signal.connect(self._disconnected)
		self._log_data_signal.connect(self._log_data_received)
		self._param_updated_signal.connect(self._param_updated)

		# Connect the Crazyflie API callbacks to the signals
		self._helper.cf.connected.add_callback(
			self._connected_signal.emit)

		self._helper.cf.disconnected.add_callback(
			self._disconnected_signal.emit)

		# regiser PushButton click event handlers
		self.button_startstop.clicked.connect(self._button_startstop_clicked)
		self.button_snapshot.clicked.connect(self._button_snapshot_clicked)

		# internal state variables
		self.webcam = None
		self.capturing = False
		self.connected = False

		# use a QTimer to redraw the screen when capturing
		self.timer = QTimer(self)
		self.timer.timeout.connect(self._update_ui)
		self.timer.setInterval(1000/24) # 1000/framerate
		self.timer.start()

		# set up array of dicts for updating prox sensors in a loop
		self._prox_sensors = [
			{'logname':		PROX_LEFT_LOGNAME,
			 'threshold':	PROX_LEFT_THRESHOLD,
			 'val_label':	self.label_left_val,
			 'val_text':	'0',
			 'bar_label':	self.label_bar_left,
			 'color':		'white'},

			{'logname':		PROX_RIGHT_LOGNAME,
			 'threshold':	PROX_RIGHT_THRESHOLD,
			 'val_label':	self.label_right_val,
			 'val_text':	'0',
			 'bar_label':	self.label_bar_right,
			 'color':		'white'},

			{'logname':		PROX_FRONT_LOGNAME,
			 'threshold':	PROX_FRONT_THRESHOLD,
			 'val_label':	self.label_front_val,
			 'val_text':	'0',
			 'bar_label':	self.label_bar_front,
			 'color':		'white'}]

		self.sonar_text = '0'



	def _button_startstop_clicked(self):
		# not running, so start
		if not self.capturing:
			# open webcam (should always be None when stopped, but do this for error checking)
			if self.webcam is None:
				self.webcam = cv2.VideoCapture(int(self.spinbox_webcam_number.value()))

			# update buttons
			self.button_startstop.setText("Stop Camera")
			self.button_snapshot.setEnabled(True)

			# start capturing
			#self.timer.start()
			self.capturing = True
		else:
			# stop capturing and release webcam
			#self.timer.stop()
			if self.webcam is not None:
				self.webcam.release()
				self.webcam = None

			# update buttons
			self.button_startstop.setText("Start Camera")
			self.button_snapshot.setEnabled(False)
			self.capturing = False

	def _button_snapshot_clicked(self):
		timestr = str(datetime.now()) # get timestamp to use as filename
		filename = 'snapshot_' + timestr[:-3].replace(':', '.').replace(' ', '_') + '.jpg'

		# check if running from bin dir
		if os.path.basename(os.getcwd()) == 'bin':
			snapshotdir = os.path.join(os.getcwd(), os.pardir, 'snapshots')
		else:
			snapshotdir = os.path.join(os.getcwd(), 'snapshots')

		# create snapshot directory if needed
		if not os.path.isdir(snapshotdir):
			os.mkdir(snapshotdir)

		filepath = os.path.join(snapshotdir, filename)
		cv2.imwrite(filepath, self.current_frame)

		logger.info("%dx%d Saved snapshot to "%(self.frame_width, self.frame_height) + filepath)

	def _update_ui(self):
		for sensor in self._prox_sensors:
			stylesheet = 'background-color: %s;'%sensor['color']
			sensor['bar_label'].setStyleSheet(stylesheet)
			sensor['val_label'].setText(sensor['val_text'])
		self.label_height_val.setText(self.sonar_text)

		self._draw_webcam()

	def _draw_webcam(self):
		if self.webcam is not None:
			# read a frame from the webcam, bail if we can't read for some reason
			ret, self.current_frame = self.webcam.read()
			if self.current_frame is None:
				return

			frame_height, frame_width, frame_byteValue = self.current_frame.shape
			frame_ratio = float(frame_width) / float(frame_height)

			self.frame_height = frame_height
			self.frame_width = frame_width

			# get current size of the display label
			label_height = self.label_video.height()
			label_width = self.label_video.width()
			label_ratio = float(label_width) / float(label_height)

			if label_ratio < frame_ratio: # label is narrower, so add letterbox bars
				new_height = int(round(frame_width / label_ratio))
				border_height = int(round((new_height - frame_height) / 2))
				
				# add borders					  input img, top,		   bottom,		left, right
				border_img = cv2.copyMakeBorder(self.current_frame, border_height, border_height, 0,  0,
												  # solid border,		 border color
													cv2.BORDER_CONSTANT, value=[255,255,255])

			elif label_ratio > frame_ratio: # wider, so pillarbox
				new_width = int(round(frame_height * label_ratio))
				border_width = int(round((new_width - frame_width) / 2))
				border_img = cv2.copyMakeBorder(self.current_frame, 0, 0, border_width, border_width,
													cv2.BORDER_CONSTANT, value=[255,255,255])

			else: # same dimensions, so no border needed
				border_img = self.current_frame

			height, width, byteValue = border_img.shape
			byteValue = byteValue * width
			cv2.cvtColor(border_img, cv2.COLOR_BGR2RGB, border_img)
			qimg = QImage(border_img, width, height, byteValue, QImage.Format_RGB888)

			self.label_video.setPixmap(QPixmap.fromImage(qimg))


	def _connected(self, link_uri):
		"""Callback when the Crazyflie has been connected"""

		logger.debug("Crazyflie connected to {}".format(link_uri))

		#defining the logconfig
		self._log_adc = LogConfig(name="ADC", period_in_ms = 50)
		self._log_adc.add_variable("adc.A0", "uint16_t")
		self._log_adc.add_variable("adc.A1", "uint16_t")
		self._log_adc.add_variable("adc.A2", "uint16_t")
		self._log_adc.add_variable("adc.A3", "uint16_t")
				
		# add log config and activate callbacks if successful
		self._helper.cf.log.add_config(self._log_adc)
		if self._log_adc.valid:
			self._log_adc.data_received_cb.add_callback(self._log_adc_data)
			self._log_adc.error_cb.add_callback(self._log_adc_error)
			self._log_adc.start()
		else:
			logger.warn("CameraTab: Unable to start ADC logging")
			
			
	def _log_adc_error(self, logconf, msg):
		logger.warn("CameraTab: log error!")
	

	# callback function when adc log data is received
	def _log_adc_data(self, timestamp, data, logconf): 
		# update UI data for each proximity sensor
		for sensor in self._prox_sensors:
			value = data[sensor['logname']]
			distance = value / 4095.0
			distance = 5.0 * math.exp(-1.0*(distance-0.41)/0.11) + 10
			sensor['val_text'] = "%3.1fcm"%distance

			if value > sensor['threshold']:
				sensor['color'] = 'red'
			else:
				sensor['color'] = 'white'

		# display sonar reading
		sonar_raw = data[SONAR_LOGNAME]
		sonar_distance = sonar_raw / 2.8
		self.sonar_text = "%3.1fcm"%sonar_distance
		

	def _disconnected(self, link_uri):
		"""Callback for when the Crazyflie has been disconnected"""
		pass

		logger.debug("Crazyflie disconnected from {}".format(link_uri))

	def _param_updated(self, name, value):
		"""Callback when the registered parameter get's updated"""

		logger.debug("Updated {0} to {1}".format(name, value))

	def _log_data_received(self, timestamp, data, log_conf):
		"""Callback when the log layer receives new data"""

		logger.debug("{0}:{1}:{2}".format(timestamp, log_conf.name, data))

	def _logging_error(self, log_conf, msg):
		"""Callback from the log layer when an error occurs"""

		QMessageBox.about(self, "Example error",
						  "Error when using log config"
						  " [{0}]: {1}".format(log_conf.name, msg))
