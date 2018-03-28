# rpicontrols

Required packages:

`sudo pip3 install -r requirements.txt`

## Install BME280 driver from source

`cd bme280`
`git pull`
`sudo python3 setup.py install`

## Install Ouimeaux.git

`pip install git+https://github.com/syphoxy/ouimeaux.git`

## LIDAR sensor
`sudo apt-get install build-essential python-dev`

`git clone https://github.com/johnbryanmoore/VL53L0X_rasp_python.git`

`cd VL53L0X_rasp_python`

`make`

You need to then copy the library and the driver py file to the home directory

From the git folder (VL53L0X_rasp_python)
`cp python/VL53L0X.py .`

Chang the new copy of the code reflect new path of the bin
Path may be relative or absolute.

line 68:
`tof_lib = CDLL("/home/pi/rpicontrols/VL53L0X_rasp_python/bin/vl53l0x_python.so")`

You will want to copy the template config file to its own file, and populate it with thingsboard API key.

`cp config_rpi.py.bak config_rpi.py`





