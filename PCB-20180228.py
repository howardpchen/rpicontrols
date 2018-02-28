#!/usr/bin/env python3
# Detect temperature, humidity, display to LCD, and if humidity is below a certain number, turn on Wemo
from RPLCD.i2c import CharLCD
from RPi import GPIO
import time
from subprocess import call, check_output
import smbus2
import bme280

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import ssl, socket
import json
import config
import sys

port = 1
address = 0x76
bus = smbus2.SMBus(port)

tele_sleep = 30 # how often to send data to MQTT in seconds
wemo_count = 0
wemo_max = 30   #wemo_max * tele_sleep = max frequency of updating humidifier

bme280.load_calibration_params(bus, address)

# MQTT Configuration
# Details for free MQTT service which we are registering data to.
thingsboard_server = "hcthings.eastus.cloudapp.azure.com"  # 



displaydata = dict()

def init_mqtt():
    client=mqtt.Client()
    client = mqtt.Client()
# Register connect callback
    client.on_connect = on_connect
# Set access token
    client.username_pw_set(config.token)
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
        "pressure": data[2]
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
    global wemo_count, mqttc, displaydata

    h_status = "OK"
    t_status = "OK"

    if h < 40:
        h_status = "L"
        if wemo_count <= 0:
            try:
                call(["wemo", "switch", "Humidifier", "on"])
                wemo_count = wemo_max
            except:
                print ("Unexpected error:", sys.exc_info()[0])
                pass
    elif h > 55 and wemo_count <= 0:
        try: 
            call(["wemo", "switch", "Humidifier", "off"])
            wemo_count = wemo_max
        except:
            print ("Unexpected error:", sys.exc_info()[0])
            pass
            
    elif h > 60:
        h_status = "H"

    #Correct for self-heating; approximately 2C  
    degreef = (degreec-2) * 9/5 + 32

    if degreef < 68:
        t_status = "L"
    elif degreef > 76:
        t_status = "H"

    wemo_count = max(wemo_count - 1, 0)
    displaydata['f'] = degreef
    displaydata['p'] = pres
    displaydata['h'] = h
    displaydata['hstat'] = h_status
    print(displaydata)

    if (mqttc):
        mqttc = mqtt_publish(mqttc, (h, degreef, pres))
    else:
        mqttc = init_mqtt()


print("Initializing")
# lcd = CharLCD('PCF8574', 0x3f)
# lcd.cursor_pos = (0, 0)
# lcd.write_string(" Initializing...   ")
# lcd.cursor_pos = (1, 0)
# lcd.write_string("                ")
# lcd.backlight_enabled = False
# lcd.close()

samples = 1
data = bme280.sample(bus, address)
h = data.humidity
deg = data.temperature
pres = data.pressure


humidity = [h]*samples
degreec = [deg]*samples
pressure = [pres]*samples

counter = 0

# In[9]:

button0=17
GPIO.setmode(GPIO.BCM)
GPIO.setup(button0, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def buttondown(input_pin):
    global displaydata
    print("Button Down")
    if (input_pin == button0 and GPIO.input(button0) == 0):
        print (displaydata)
        # lcd = CharLCD('PCF8574', 0x3f)
        # lcd.cursor_pos = (0, 0)
        # lcd.write_string(" %2.1fF  %dhPa " % (displaydata['f'], 
                                              # displaydata['p']))
        # lcd.cursor_pos = (1, 0)
        # lcd.write_string(" %d%% Hum. (%s)  " % (displaydata['h'],
                                                # displaydata['hstat']))
        time.sleep(5)
        # lcd.backlight_enabled = False
        # lcd.close()
        
GPIO.add_event_detect(button0, GPIO.FALLING, callback=buttondown, bouncetime=200)

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
        time.sleep(tele_sleep)
except KeyboardInterrupt:
    print("\nUser interrupted - exiting...")
finally:
    GPIO.cleanup()

