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
import sys

logger = logging.getLogger(__name__)

from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot, pyqtSignal, QThread, Qt, QTimer
from PyQt4.QtGui import *

from cfclient.ui.tab import Tab

from cflib.crazyflie.log import LogConfig, Log
from cflib.crazyflie.param import Param

import pdb
import cv2

camera_tab_class = uic.loadUiType(sys.path[0] +
								"/cfclient/ui/tabs/cameraTab.ui")[0]

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

		self.button_startstop.clicked.connect(self._button_clicked)

		self.webcam = None

		self.timer = QTimer(self)
		self.timer.timeout.connect(self.draw_webcam)
		self.timer.setInterval(1000/24)
		

	def _button_clicked(self):
		logger.info("pushButton Clicked callback")

		if not self.timer.isActive():
			if self.webcam is None:
				self.webcam = cv2.VideoCapture(int(self.spinbox_webcam_number.value()))
			self.button_startstop.setText("Stop Camera")
			self.timer.start()
		else:
			self.timer.stop()
			if self.webcam is not None:
				self.webcam.release()
				self.webcam = None
			self.button_startstop.setText("Start Camera")

	def draw_webcam(self):
		if self.webcam is not None:
			ret, cvimg = self.webcam.read()
			height, width, byteValue = cvimg.shape
			byteValue = byteValue * width
			cv2.cvtColor(cvimg, cv2.COLOR_BGR2RGB, cvimg)
			qimg = QImage(cvimg, width, height, byteValue, QImage.Format_RGB888)

			self.label_video.setPixmap(QPixmap.fromImage(qimg))


	def _connected(self, link_uri):
		"""Callback when the Crazyflie has been connected"""

		logger.debug("Crazyflie connected to {}".format(link_uri))

	def _disconnected(self, link_uri):
		"""Callback for when the Crazyflie has been disconnected"""
		if self.webcam is not None:
			self.webcam.release()

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
