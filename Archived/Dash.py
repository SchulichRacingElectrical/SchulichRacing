import asyncio
from threading import Thread

import datetime
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, BoundedNumericProperty
from kivy.lang import Builder
import socket
import json
from kivy.core.window import Window
from kivy.config import Config
import threading

from SocketPusher import DashPusher
from Process import Process
from CloudPusher import Pusher
from Utilities import readifyData
import time
import logging
import operator
import collections
import os

import psutil
import requests

Config.set('graphics', 'fullscreen', 'auto')

# init values
eng_temperature = -45
init_afr = -45
current_rpm = 999
init_oilPress = -45
current_gear = 999
init_oilTemp = -45
Builder.load_file("Dashboard.kv")
#PUB_ENDPOINT = 'http://10.142.0.3:8080/pub'
#ANALYTICS_CHANNEL = 'schulich_analytics'

"""
################TO DO LIST################
-PUT EVERYTHING IN FUNCTIONS
-GET THE DATA FROM DAQ
-TEST ON RASPERRY PI
-SEE IF SCREEN IS VISIBLE FROM ALL ANGLES
-MAYBE PUT SOME DESIGN PATTERNS
-MAKE IT PRETTIER
-TEST WITH DRIVERS
"""


class Display(Widget):
    # used for the flashing of the rpm
    counter = 0
    shiftIndicator = False

    '''
    ASSIGNING THE DEFUALT VALUES
    MUST BE NUMERICPROPERTY TO WORK WITH KIVY (IDK)
    '''
    rpm = NumericProperty(current_rpm)
    oilPress = NumericProperty(init_oilPress)
    oilTemp = NumericProperty(init_oilTemp)
    coolantTemp = NumericProperty(eng_temperature)
    afr = NumericProperty(init_afr)

    DAQ_Missing = StringProperty("DAQ IS MISSING")

    # This is how to load image file path
    img = StringProperty("green.png")

    glowUp = StringProperty("glow3.jpeg")
    glowDown = StringProperty("glow4.jpeg")
    '''add these for glow later
    Rectangle:
            id: myRect
            size: 760,30
            pos: 20, 500
            source: self.glowUp

        Rectangle:
            id: myRect
            size: 760,25
            pos: 20, 385
            source: self.glowDown    
    '''

    img_size = BoundedNumericProperty(0.9, max=1.0, min=0.1)
    # serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    host = "35.193.18.90"
    port = 5002

    buffer_size = 4096

    # serverSocket.bind((host, port))
    # serverSocket.listen(1)
    data = {'timestamp': 0, 'interval': 0, 'battery': 0, 'accelX': 0, 'accelY': 0, 'accelZ': 0, 'yaw': 0, 'pitch': 0,
            'roll': 0, 'rpm': 0, 'map': 0, 'tps': 0, 'oilPressure': 0, 'afr': 0, 'coolantTemperature': 0, 'iat': 0,
            'oilTemperature': 0, 'gear': 0, 'speed': 0, 'frontLeft': 0, 'frontRight': 0, 'rearLeft': 0, 'rearRight': 0,
            'latitude': 0, 'longitude': 0, 'injectorPW': 0, 'fuelTemp': 0, 'baro': 0, 'altitude': 0, 'session': 0,
            'lambda': 0}
    worker_loop = asyncio.new_event_loop()

    # dPusher = DashPusher(5002)
    processor = None
    last_updated_time = datetime.datetime.now()
    sticky_rpm = 999
    rpm_counter = 0
    sum = 0
    connected = False
    publisher_loop = None
    publisher = None
    logOnCloud = True
    #s = requests.Session()
    dPusher = DashPusher(5001)

    def __init__(self, **kwargs):
        # needed for constructor
        super(Display, self).__init__(**kwargs)
        # these two lines needed to use the keyboard and stuff
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        # timer just like in java, takes in a function and acts as a independent thread
        Clock.schedule_interval(self.update, 0.01)

        worker = Thread(target=self.start_worker, args=(self.worker_loop,))
        worker.start()
        if self.logOnCloud:
            try:
                self.publisher_loop = asyncio.new_event_loop()
                publisher_wrk = threading.Thread(target=self.start_worker_publisher, args=(self.publisher_loop,))
                publisher_wrk.start()
                self.publisher = Pusher("winged-line-203918", "cardata")
            except Exception as e:
                print("Unable to connect to Google Cloud")
                print(e)
        try:
            self.processor = Process()
            self.connected = True
        except Exception as e:
            print("Unable to connect to DAQ")
            self.connected = False

    def _keyboard_closed(self):  # also part of the keyboard stuff
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modeifires):
        if keycode[1] == 'q':
            exit()

    def start_worker(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def start_worker_publisher(self, loop):
        """Switch to new event loop and run forever"""
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def get_data(self):

        # print(self.serverSocket)
        # data, server = self.serverSocket.recvfrom(self.buffer_size)
        # self.serverSocket.recv(self.buffer_size*2)
        self.data = json.loads(self.processor.getData().decode('utf-8'))
        # self.data =
        # print(datetime.datetime.now() - start)

    def publish(self, publisher, data):
        publisher.publish(readifyData(data))
        self.dPusher.publish(readifyData(data))
        # self.s.post(PUB_ENDPOINT, params={'id': ANALYTICS_CHANNEL}, json=data)

    def update(self, *args):
        self.connected = True
        if self.connected:
            self.DAQ_Missing = ""
            # self.worker_loop.call_soon(self.get_data())
            if self.logOnCloud:
                self.publisher_loop.call_soon_threadsafe(self.publish, self.publisher, self.data)
        # print(self.data)

        '''
        UPDATING VALUES
        '''
        self.rpm = self.data["rpm"]
        # self.rpm = self.data["frontleft"]
        self.oilPress = round(self.data["oilPressure"], 1)
        # self.gear = self.data["gear"]

        self.oilTemp = int(self.data["oilTemperature"])

        if self.data["coolantTemperature"] > 0:
            self.coolantTemp = int(self.data["coolantTemperature"])

        # if self.data["afr"] > 0:
        multiplier = 14.7
        self.afr = round(self.data["afr"], 1)
        # print(self.air_temp)
        # print(self.data["rpm"])
        '''
        DEBUGGING
        '''
        # print(self.data)
        '''
        SHIFT LIGHTS TURN ON
        '''
        if (self.rpm > 10500):
            # now its time for shifting
            shiftIndicator = True
        else:
            shiftIndicator = False
            self.img = "green.png"

        '''
        FLASHING EFFECT
        '''
        if (shiftIndicator == True):
            if self.counter < 100:
                self.img = "red.jpg"
            else:
                self.img = "blue.jpg"

            # change this to chang the timing of the flashes
            self.counter = self.counter + 20
            if self.counter == 200:
                self.counter = 0


class DashboardApp(App):
    def build(self):
        return Display()


if __name__ == '__main__':
    DashboardApp().run()
