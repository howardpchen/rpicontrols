#!/usr/bin/env python3
# Detect temperature, humidity, display to LCD, and if humidity is below a certain number, turn on Wemo
from RPLCD.i2c import CharLCD
from RPi import GPIO
import Adafruit_DHT
import time
from subprocess import call

lcd = CharLCD('PCF8574', 0x3f)

def show(h, degreec):
    h_status = "OK"
    t_status = "OK"
    if h < 30:
        call(["wemo", "switch", "Humidifier", "on"])
        h_status = "L"
    elif h > 60:
        call(["wemo", "switch", "Humidifier", "off"])
        h_status = "H"
 
    degreef = degreec * 9/5 + 32
    if degreef < 68:
        t_status = "L"
    elif degreef > 76:
        t_status = "H"
    
    lcd.cursor_pos = (0, 0)
    lcd.write_string(" T: %d F (%s)    " % (degreef, t_status))
    lcd.cursor_pos = (1, 0)
    lcd.write_string(" H: %d %% (%s)    " % (h, h_status))


# In[2]:




# In[3]:


lcd.cursor_pos = (0, 0)
lcd.write_string(" Initializing...   ")
lcd.cursor_pos = (1, 0)
lcd.write_string("                     ")


samples = 5

h, deg = Adafruit_DHT.read_retry(11, 17)

lcd.backlight_enabled = False
show(h, deg)

humidity = [h]*samples
degreec = [deg]*samples

counter = 0



# In[9]:


button0=27
GPIO.setmode(GPIO.BCM)
GPIO.setup(button0, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def buttondown(input_pin):
    if (input_pin == button0):
        lcd.backlight_enabled = True
        time.sleep(2)
        if (GPIO.input(button0) == 1):
            lcd.backlight_enabled = False

        
GPIO.add_event_detect(button0, GPIO.FALLING, callback=buttondown, bouncetime=500)


# In[ ]:


try:
    while True:
        counter = (counter + 1) % samples

        for i in range(samples):
           humidity[counter], degreec[counter] = Adafruit_DHT.read_retry(11, 17)

        h = sum(humidity)/len(humidity)
        dc = sum(degreec)/len(degreec)
        show(h, dc)
        time.sleep(10)
except KeyboardInterrupt:
    print("\nUser interrupted - exiting...")
finally:
    GPIO.cleanup()

