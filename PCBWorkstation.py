#!/usr/bin/env python3
from RPLCD.i2c import CharLCD
from RPi import GPIO
import VL53L0X
import threading
import time
from subprocess import call, check_output
import smbus2
import bme280

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import ssl, socket
import json
import config_rpi
import sys
tof = VL53L0X.VL53L0X()
port = 1
address = 0x76
bus = smbus2.SMBus(port)

""" 
Buffering mechanism for workstation occupancy - basically number builds up/down with each DistanceThread update
Once reaching upper/lower limit threshold the actual occupancy status is changed.
"""
dist_tele_sleep = 0.5       # in seconds
dist_occupied_max = 10      # multiplied by sleep duration for total threshold
dist_occupied_counter = 0   # start with 0
dist_occ_stat = False

mqtt_tele_sleep = 10 # how often to send data to MQTT in seconds.

bme280.load_calibration_params(bus, address)

# MQTT Configuration
# Details for free MQTT service which we are registering data to.
thingsboard_server = "hcthings.eastus.cloudapp.azure.com"  # 

displaydata = dict()
displaydata['occ'] = False

def init_mqtt():
    client = mqtt.Client()
# Register connect callback
    client.on_connect = on_connect
# Set access token
    client.username_pw_set(config_rpi.token)
# Connect to ThingsBoard using default MQTT port and 60 seconds keepalive interval
    no_conn = True
    try:
        client.connect(thingsboard_server, 1883, 60)
    except:
        print("Cannot establish connection to MQTT server. Trying again later.")
        return None
    return client

def mqtt_publish(c, data):

    data_dict = {
        "humidity": data[0],
        "temperature": data[1],
        "pressure": data[2],
        "occupied": data[3]
    }
    result = c.publish('v1/devices/me/telemetry', json.dumps(data_dict), 1)
    if (result[0] != mqtt.MQTT_ERR_SUCCESS):
        print("Failed publishing data", ". Error code", result[0])
    if result[1] >= 20:
        return init_mqtt()
    return c


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, rc, *extra_params):
    print('Connected with result code ' + str(rc))
    # Subscribing to receive RPC requests
    client.subscribe('v1/devices/me/rpc/request/+')



# Initialize mqtt connection and return handle
mqttc = init_mqtt();

# the sample method will take a single reading and return a
# compensated_reading object

def poll(h, degreec, pres):
    global mqttc, displaydata, dist_occ_stat

    h_status = "OK"

    if h < 40:
        h_status = "L"
    elif h > 60:
        h_status = "H"

    #Correct for self-heating
    degreef = (degreec-2) * 9/5 + 32

    displaydata['f'] = degreef
    displaydata['p'] = pres
    displaydata['h'] = h
    displaydata['hstat'] = h_status
    displaydata['occ'] = dist_occ_stat
    if (mqttc):
        mqttc = mqtt_publish(mqttc, (h, degreef, pres, dist_occ_stat))
    else:
        mqttc = init_mqtt()


print("Initializing")
lcd = CharLCD('PCF8574', 0x3f)
lcd.cursor_pos = (0, 0)
lcd.write_string(" Initializing...   ")
lcd.cursor_pos = (1, 0)
lcd.write_string("                ")
lcd.close()

samples = 1
data = bme280.sample(bus, address)
h = data.humidity
deg = data.temperature
pres = data.pressure

humidity = [h]*samples
degreec = [deg]*samples
pressure = [pres]*samples

counter = 0

def update_lcd(backlight_enabled=False):
    global displaydata, lcd
    try:
        #lcd = CharLCD('PCF8574', 0x3f, backlight_enabled=backlight_enabled)
        lcd.backlight_enabled=backlight_enabled
        lcd.cursor_pos = (0, 0)
        lcd.write_string(" %2.1fF  %dhPa " % (displaydata['f'], 
                                              displaydata['p']))
        lcd.cursor_pos = (1, 0)
        lcd.write_string(" %d%% Hum. (%s)  " % (displaydata['h'],
                                                displaydata['hstat']))
        
        #lcd.cursor_pos = (0, 0)
        #lcd.write_string(" %2.1fF  %d%% Hum.  " % (displaydata['f'],
        #                                           displaydata['h']))
        #lcd.cursor_pos = (1, 0)
        #lcd.write_string("Wkstation: %s" % ("occupied " if displaydata['occ'] else "available"))
    except KeyError:
        lcd = CharLCD('PCF8574', 0x3f)
        lcd.cursor_pos = (0, 0)
        lcd.write_string(" Initializing...   ")
        lcd.cursor_pos = (1, 0)
        lcd.write_string("                ")

    lcd.close()


class DistanceThread(threading.Thread):
    @staticmethod
    def run():
        global tof, lcd, dist_occupied_counter, dist_occ_stat
        print ("Starting distance sensor thread")
        tof.start_ranging(VL53L0X.VL53L0X_BEST_ACCURACY_MODE)
        while True:
            d = tof.get_distance()

            if d < 0:
                print ("Error getting distance")
                tof.stop_ranging()
                tof.start_ranging()
            else:
                update_lcd(backlight_enabled=True if d < 450 else False)
                dist_occupied_counter = max(min(dist_occupied_counter + (1 if d < 8190 else -1), dist_occupied_max), 0)
                #print(dist_occupied_counter)
                if dist_occupied_counter == dist_occupied_max:
                    dist_occ_stat = True
                elif dist_occupied_counter == 0:
                    dist_occ_stat = False

            try: 
                time.sleep(0.5)
            except KeyboardInterrupt:
                DistanceThread.stop_ranging()

    @staticmethod
    def stop_ranging():
        global tof
        tof.stop_ranging()

print("creating new thread")
dist = DistanceThread()
dist.daemon = True
dist.start()
print("started new thread")

try:
    while True:
        counter = (counter + 1) % samples
        try:
            data = bme280.sample(bus, address)
            for i in range(samples):
                humidity[counter] = data.humidity
                degreec[counter] = data.temperature
                pressure[counter] = data.pressure
        except:
            print ("Error sampling data.  Maybe reset bus and try again... ")
            bus = smbus2.SMBus(port)
        h = sum(humidity)/len(humidity)
        dc = sum(degreec)/len(degreec)
        pr = sum(pressure)/len(pressure)
        poll(h, dc, pr)
        time.sleep(mqtt_tele_sleep)
except KeyboardInterrupt:
    print("\nUser interrupted - exiting...")
finally:
    tof.stop_ranging()
    sys.exit()
