
# ------------------------------------------- as_GPS HAS BEEN MODIFIED --------------------------------------------------
# --------------------------------- DOCUMENTING THIS IS GOING TO BE EXTREMELY PAINFUL -----------------------------------

from machine import I2C,Pin,UART,SPI,freq,PWM
from math import sqrt,pi,asin,atan,tan,cos,sin,atan2,acos
from time import ticks_ms,sleep,sleep_us,sleep_ms
from ulab import numpy as np
from bno055 import *
from bmp280 import *
import kx132
import as_GPS
import uasyncio as asyncio
import ustruct
import uos
import gc
import micropython
import ads1x15
import sys
micropython.alloc_emergency_exception_buf(100)
gc.collect()

# OVERCLOCK PICO BECAUSE UDH BHI GAYA TO GOVERNMENT KA HI TO PAISA HAI LOL
freq(270000000)
# JUST KIDDING NEED THE SPEED, CODE IS REALLY BIG 


class async_test:
    
    # ALTITUDE FROM STATIC AIR PRESSURE
    def altitude(self):
        return 4947.19 * (8.9611 - pow(self.bmp.pressure,0.190255))

    # DENSITY
    def rho(self,y):
        return pow(8.9611 - (y + self.calib_altitude)/4947.19,5.2479)/(78410.439 + 287.06*self.calib_temp - 1.86589*(y + self.calib_altitude))
    
    # TOGGLE LED ASYNCHRONOUSLY 
    async def blink(self, t):
        while True:
            self.led_1.value(0)
            self.led_2.value(0)
            await asyncio.sleep_ms(t)
            self.led_1.value(1)
            self.led_2.value(1)
            await asyncio.sleep_ms(t)
    
    # LED + BEEPS ON POWER UP
    def board_init(self):
        
        pwm = PWM(Pin(6))
        
        # Define the notes and their frequencies
        G6 = int(1568*1)
        C7 = int(2093*1)
        E7 = int(2637*1)
        G7 = int(3136)

        # Mario main theme melody
        melody = [
            E7, E7, 0, E7,
            0, C7, E7, 0,
            G7, 0, 0, 0,
            G6, 0, 0, 0,

        ]

        # Mario main theme tempo
        tempo = [
            11, 11, 11, 11,
            11, 11, 11, 11,
            11, 11, 11, 11,
            11, 11, 11, 11,
        ]

        # Function to play a note
        def play_tone(frequency, duration):
            if frequency == 0:
                sleep(duration / 1000)
            else:
                pwm.freq(frequency)
                pwm.duty_u16(60000)  # 50% duty cycle
                sleep(duration / 1000)
                pwm.duty_u16(0)

        # Play the Mario theme tune
        for i in range(len(melody)):
            play_tone(melody[i], tempo[i] * 10)
            sleep(0.05)
        
    # LED + BEEPS IF MOTOR CONTROLLER BOARD IS NOT FOUND
    def mc_missing(self):
        return # REMOVE LATER
        
        self.xbee.write('MC')

        if self.state == 0:
            while True:
                self.led_1.value(0)
                self.led_2.value(0)
                self.beep()
                self.led_1.value(1)
                self.led_2.value(1)
                sleep(0.1)
        else:
            pass
            
    # LED + BEEPS FOR OTHER GENERAL FAILURES
    def failure(self,e):

        self.xbee.write(e)
        
        if self.free_bytes - self.size > 1000:
            failure_log = open('fail_log.txt','a')
            failure_log.write('data_' + str(self.index) + ' : ' + str(self.t_log) + ',' + str(e) + '\n')
            failure_log.close()
        
        if self.state == 0:
            while True:
                self.buzzer.duty_u16(60000)
                self.led_1.value(0)
                self.led_2.value(0)
                sleep(1)

        else:
            pass

    # BUZZER BEEP
    def beep(self,*args):
             
        n = 1
        f = 2000
        t = 75

        if len(args) == 1:
            n = args[0]
        elif len(args) == 2:
            n = args[0]
            t = args[1]
        elif len(args) == 3:
            n = args[0]
            t = args[1]
            f = args[2]
        
        self.buzzer.freq(f)

        for i in range(n):
            self.buzzer.duty_u16(60000)
            sleep_ms(t)
            self.buzzer.duty_u16(0)
            sleep_ms(t)
    
    # INITIALISE BOARD    
    def init(self):
        self.async_loop = None
        self.tel_delay = 100
        self.tel_delay_fast = 100
        self.tel_delay_slow = 1000
        self.t_events = [0.,0.,0.,0.,0.]
        self.logging_done = False
        self.state = 0
        self.bmp, self.bno, self.xbee, self.gps, self.flash, self.adc, self.kx = None, None, None, None, None, None, None
        self.send_calib = False
        self.buzzer = PWM(Pin(6))
        self.buzzer.freq(2000)
        self.led_1 = Pin(21,Pin.OUT)
        self.led_2 = Pin(19,Pin.OUT)
        
        self.drogue_pin = Pin(28,Pin.OUT)
        self.main_pin = Pin(20,Pin.OUT)
        
        self.drogue_pin.value(0)
        self.main_pin.value(0)
        
        self.r = 6371000                     # RADIUS OF EARTH
        self.g = 9.80665                     # ACCELERATION DUE TO GRAVITY
        self.bno_scale = 0
        self.kx_scale = 0
        self.except_occr = False
        self.t_log = ticks_ms()
        sleep_ms(10)
        self.last_t_log = ticks_ms()
        self.speed = 0
        self.latitude = (0,0,0.0,'N')
        self.longitude = (0,0,0.0,'E')
        self.course = 0
        self.hdop = 0
        self.vdop = 0
        self.gps_altitude = 0
        self._fix_time = 0
        self.time_since_fix = 0
        self.gps_counter = 0
        self.last_gps_counter = 0
        self.sentence_type = b'NUL'
        
        # RAW READINGS FROM FAST SENSORS
        self.bno_accel = [0,0,0]
        self.kx_accel = [0,0,0]
        self.gyro = [0,0,0]
        self.mag = [0,0,0]
        self.orientation = [0,0,0]
        self.temp = 0
        self.alt = 0
        self.ram_diff = 0               # RESTRICTED TO 10 HZ. READINGS ARE VERY UNSTABLE FOR HX710B AT 40 HZ.
        self.density = 1.15
        self.volt_main = 0
        self.volt_drogue = 0
        self.volt_3v3 = 0
        self.volt_vcc = 0
        self.x = 0
        
        self.bno_working = True
        self.bmp_working = True
        self.kx_working = True
        self.mc = I2C(0,scl=Pin(5),sda=Pin(4))
        self.mc_delay = 1
        
        self.mass = 8
        self.target = 1000
        self.calib_time, self.calib_altitude, self.calib_temp ,self.ram_offset = 0,0,0,0
        self.shutdown = False
        self.calib_data = bytes(26)
        self.track_init = 0
        self.data_buffer = bytearray(0)
        
        self.runtime = 3600 * 1000
        
        self.temp_mult = 100
        self.acc_mult = 100
        self.volt_mult = 10
        self.gps_mult = 100
        self.packing_str = '!sibhffhhhffffffbbbb'
        self.packing_str_slow = '!sbbfbbbfbHHHH3sfff'
        
        self.ram_baro_scale = 575.5
        
        self.max_alt = 0
        self.calib_gap = 1 * 1000 # GAP BETWEEN CALIBRATIONS IN MILLISECONDS
        self.calib_count = 0 # NUMBER OF CALIBRATIONS PERFORMED SO FAR
        self.calib_max = 2  # MAX NUMBER OF CALIBRATIONS
        
        self.liftoff_accel = 0 * 3 # MINIMUM SUSTAINED Gs FOR LIFTOFF DETECTION
        self.min_liftoff_alt = 2/10 * 10 # MINIMUM ALT TO BE CLEARED FOR LIFTOFF DETECTION (m)
        self.force_liftoff_alt = 50 # FORCE LIFTOFF ABOVE THIS ALT (m)
        
        self.force_burnout_time = 100 * 5 * 1000 # FORCE BURNOUT AFTER THIS MANY MILLISECONDS FROM LIFTOFF
        
        self.force_drogue_time = 100 * 17 * 1000 # FORCE DROGUE AFTER THIS MANY MILLISECONDS FROM LIFTOFF
        self.lockout_drogue_time = 0 * 6 * 1000 # CANNOT FIRE DROGUE BEFORE THIS MANY MILLISECONDS FROM LIFTOFF
        
        self.main_alt = 1/400 * 400 # DEPLOY MAIN BELOW THIS ALTITUDE DURING DESCENT (m)
        self.drogue_to_main_lockout = 0 * 5000 # CANNOT FIRE MAIN BEFORE THIS MANY MILLISECONDS FROM DROGUE (INCASE DROGUE DEPLOYEMENT MESSES UP PRESSURE VALUES)
        
        self.touchdown_alt = 0.3/50 * 50 # ALTITUDE MUST BE LESS THAN THIS FOR TOUCHDOWN DETECTION
        self.touchdown_vel_limit = 0.01 # MINIMUM VELOCITY FOR TOUCHDOWN DETECTION (m/s)
        self.main_to_touchdown_lockout =  0 * 5000 # CANNOT DETECT TOUCHDOWN BEFORE THIS MANY MILLISECONDS FROM MAIN (INCASE DROGUE DEPLOYEMENT MESSES UP PRESSURE VALUES)

        # ALTITUDE, VERTICAL VELOCITY, ACCELERATION BUFFER FOR STATE MACHINE
        self.buf_len = 5
        self.alt_buf = np.zeros((self.buf_len))
        self.acc_buf = np.zeros((self.buf_len))
        self.vel_buf = np.zeros((self.buf_len))
        
        # BUFFERS FOR FAST AND SLOW DATA
        self.data_fast = bytearray(50)
        self.data_slow = bytearray(38)
        
        # SIZE OF DATA FILE IN BYTES
        self.size = 0
        
        # CALCULATE FREE SPACE
        storage = uos.statvfs("/")
        self.free_bytes = storage[0]*storage[3]
        
        # PARTY TIME YEAH
        self.board_init()
    
    # RUNS FOR EACH VALID GPS FIX
    def callback_gps(self,gps, *_):
        try:
            self.gps_counter += 1

            self.latitude = gps.latitude(coord_format=as_GPS.DMS)
            self.longitude = gps.longitude(coord_format=as_GPS.DMS)
            self.speed = 0.5144*gps.speed()                           # CONVERTING KNOTS TO M/S
            self.course = gps.course
            self.sentence_type = gps.sentence_type
            self.hdop = gps.hdop
            self.vdop = gps.vdop
            self.gps_altitude = gps.altitude - self.calib_altitude
            self._fix_time = gps._fix_time
            self.time_since_fix = gps.time_since_fix()
        except Exception as e:
            e = 'GPS Error : ' + str(e)
            print(e)
            self.failure(e)

        
    
    # RAW DATA FROM RAM BAROMETER (MULTIPLY BY 1/RAM_BARO_SCALE TO GET DIFFERENTIAL PRESSURE)
    def ram_raw_data(self):
        try:
            data = 0
            for i in range(24):
                self.ram_sck.value(1)
                data = (data << 1) | self.ram_dout.value()
                self.ram_sck.value(0)

            self.ram_sck.value(1)
            self.ram_sck.value(0)
            
            if data & 0x800000:
                data -= 1 << 24
                
            if data < - pow(2,11):
                data += pow(2,26)
                
            return data
        
        except Exception as e:
            
            return 0 # IF SOMETHING FAILS, AIRSPEED WILL RETURN AS 0 AND NAV FILTER WILL IGNORE IT
            
            e = 'Failed to read Airspeed Sensor : ' + str(e)
            print(e)
            self.failure(e)
            
    
    # CALIBRATE INITIAL ALTITUDE  
    def calib_bmp(self, n = 10):
        try:
            self.calib_temp = self.bmp.temperature
            avg_alt = 0
            for i in range(n):
                avg_alt += self.altitude()
                sleep_ms(10)
            self.calib_altitude = avg_alt/n
        except Exception as e:
            
            self.calib_altitude = 0
            
            e = 'Failed to calibrate BMP280 : ' + str(e)
            print(e)
            self.failure(e)
        
    # CALIBRATE RAM BAROMETER OFFSET
    def calib_ram(self,n = 10):
        try:
            self.ram_offset = 0
            count = 0
            while count < n:
                if self.ram_dout.value() == 0:
                    self.ram_offset += self.ram_raw_data()/n
                    count += 1
        except Exception as e:
            
            e = 'Failed to calibrate airspeed sensor : ' + str(e)
            print(e)
            self.failure(e)

                
    
    # INITIALISE BOARD
    def init_board(self):
        print("starting init")

        # UART BUS OF GPS
        # BAUDRATE : 9600 FOR NEO-6M
        #            38400 FOR NEO-M9N
        self.uart = UART(1, 9600, rx = Pin(9), tx = Pin(8))
        
        # UART BUS OF XBEE
        self.xbee = UART(0, 57600, rx = Pin(1), tx = Pin(0))
                
        # RAM BAROMETER PINS        
        self.ram_sck = Pin(14,Pin.OUT)
        self.ram_dout = Pin(15,Pin.IN)
        
        # INITIALISE STATIC BAROMTER
        try:
            self.bmp = BMP280(I2C(1,
                            scl = Pin(3),
                            sda = Pin(2)))
            print('bmp done')
        except Exception as e:
            e = 'Failed to initialize BMP280 : ' + str(e)
            print(e)
            self.failure(e)

        # INITIALISE FLASH (DISABLED FOR NOW. WILL ONLY USE IS EXTERNAL FLASH IS 100% RELIABLE)
#         try:
#             cspins = [Pin(7)] # has to be a list for this library to work
#             spi = SPI(1, sck= Pin(10), mosi=Pin(11), miso=Pin(12))
#             self.flash = FLASH(spi, cspins,cmd5 = False)
#             uos.mount(self.flash, '/flash')
#             print('flash done')
#         except Exception as e: #OSError
#             print('Failed to initialize Flash')
#             print(e)
#             self.except_occr = True
        
        # INITIALISE GPS
        try:
            sreader = asyncio.StreamReader(self.uart)  # Create a StreamReader
            
            # fix_cb DEFINES THE FUNCTION CALLED WHEN A VALID FIX IS ACCQUIRED
            # cb_mask DEFINES THE NMEA SENTENCES WHICH WILL TRIGGER THE CALLBACK (RMC,VTG,GLL,GGA)
            self.gps = as_GPS.AS_GPS(sreader,fix_cb = self.callback_gps,cb_mask= as_GPS.RMC | as_GPS.VTG | as_GPS.GLL | as_GPS.GGA)
            
            print('gps done')
        except Exception as e:
            e = 'Failed to initialize GPS : ' + str(e)
            print(e)
            self.failure(e)
         
        # INITIIALISE IMU 
        try:
            self.bno = BNO055(I2C(1,
                scl = Pin(3),
                sda = Pin(2)))
            
            # REGISTER ADDRESSES FOR ACCELEROMTER OFFSETS
            ACCEL_OFFSET_X_LSB_ADDR = const(0x55)
            ACCEL_OFFSET_X_MSB_ADDR = const(0x56)
            ACCEL_OFFSET_Y_LSB_ADDR = const(0x57)
            ACCEL_OFFSET_Y_MSB_ADDR = const(0x58)
            ACCEL_OFFSET_Z_LSB_ADDR = const(0x59)
            ACCEL_OFFSET_Z_MSB_ADDR = const(0x5A)
            ACCEL_RADIUS_LSB_ADDR = const(0x67)
            ACCEL_RADIUS_MSB_ADDR = const(0x68)
            
            # SET IMU TO CONFIG MODE (TO SET ACCELEROMTER OFFSETS)
            
            self.bno.mode(0)

            # BYTEARRAY OF IMU OFFSETS (CALIBRATE BEFORE LAUNCH)            
            
            bno_offsets = bytearray(b'\xef\xff\t\x00\xef\xff\xae\x03\xa2\xff\x98\x04\xff\xff\x02\x00\xff\xff\xe8\x03\x02\x03')

            # WRITE ACCELEROMETER OFFSETS TO THEIR REGISTERS (GYRO WILL CALIBRATE WHEN LEFT AT REST)
            #                                                (MAGNETOMETER IS PROBLEMATIC. EVEN TILTING IT A LITTLE BIT IS ENOUGH TO CALIBRATE.)
            #                                                (SO MIGHT HAVE TO TILT THE ROCKET BACK AND FORTH ON THE RAIL A LITTLE BIT. BUT IT'S NOT ESSENTIAL SO IT'S FINE)

            self.bno._write(ACCEL_OFFSET_X_LSB_ADDR, bno_offsets[0])
            self.bno._write(ACCEL_OFFSET_X_MSB_ADDR, bno_offsets[1])
            self.bno._write(ACCEL_OFFSET_Y_LSB_ADDR, bno_offsets[2])
            self.bno._write(ACCEL_OFFSET_Y_MSB_ADDR, bno_offsets[3])
            self.bno._write(ACCEL_OFFSET_Z_LSB_ADDR, bno_offsets[4])
            self.bno._write(ACCEL_OFFSET_Z_MSB_ADDR, bno_offsets[5])
            self.bno._write(ACCEL_RADIUS_LSB_ADDR, bno_offsets[18])
            self.bno._write(ACCEL_RADIUS_MSB_ADDR, bno_offsets[19])
                    
            # SWITCH TO FUSION MODE
                    
            self.bno.mode(7)
            self.bno.config(ACC,(16,62))
            self.bno.config(GYRO,(2000,32))
            self.bno.config(MAG,(30,))
                
            # CALCULATING ACCELEROMETER SCALING
            print('Place IMU at rest')

            self.bno_scale = 0
            
            for i in range(10):
                bno_accel = (0.0,0.0,0.0)
                while bno_accel == (0.0,0.0,0.0):
                    bno_accel = self.bno.accel()
                    sleep_ms(1)
                
                self.bno_scale += self.g/(sqrt(pow(bno_accel[0],2) + pow(bno_accel[1],2) + pow(bno_accel[2],2)))/10
            
            print('bno done')
        except Exception as e:
            e = 'Failed to initialize BNO055 : ' + str(e)
            print(e)
            self.failure(e)

        # INITIALISE KX-134
        try:
            self.kx = kx132.KX132(i2c = I2C(1,scl=Pin(3), sda=Pin(2)), address = 31)
            self.kx.acc_range = kx132.ACC_RANGE_16
            
            self.kx_scale = 0
            
            for i in range(10):
                kx_accel = (0.0,0.0,0.0)
                while kx_accel == (0.0,0.0,0.0):
                    kx_accel = self.kx.acceleration
                    sleep_ms(1)
                self.kx_scale += self.g/(sqrt(pow(kx_accel[0],2) + pow(kx_accel[1],2) + pow(kx_accel[2],2)))/10
            
            print('kx done')
        except Exception as e:
            e = 'Failed to initialize KX134 : ' + str(e)
            print(e)
            self.failure(e)

        # INITIALISE ADC
        try:
            self.adc = ads1x15.ADS1115(I2C(1,scl=Pin(3), sda=Pin(2)), 72)
            print('adc done')
        except Exception as e:
            e = 'Failed to initialize ADC : ' + str(e)
            print(e)
            self.failure(e)

        ram_done = False
        
        while not ram_done:
            # INITIALISE RAM BAROMETER        
            if self.ram_dout.value() == 0:           # IF DATA FROM RAM BAROMETER IS READY
                if self.ram_raw_data() != 0:         # AND IT IS NOT 0 (CONNECTION IS GOOD)
                    print('ram done')
                    ram_done = True
                else:
                    print('Failed to initialize Ram Barometer')
                    self.beep()
            else:
                print('Failed to initialize Ram Barometer')
                self.beep()
    
    # CALIBRATION
    async def calibrate(self):

        try:
            self.calib_count += 1
            
            self.calib_time = ticks_ms()
            
            print('Calibration Number ' + str(self.calib_count))
            
            # CALIBRATE RAM AND STATIC BAROMETERS
            self.calib_bmp()
            self.calib_ram()

            lat = self.latitude[0] + self.latitude[1]/60 + self.latitude[2]/3600
            lon = self.longitude[0] + self.longitude[1]/60 + self.longitude[2]/3600
            
            # CALIBRATION DATA PACKED TO BYTES
            self.calib_data = ustruct.pack('!fffffbfb',
                                                  self.calib_altitude,
                                                  self.ram_offset,
                                                  self.calib_temp,
                                                  self.track_init,
                                                  lat,
                                                  (int)(ord(self.latitude[3])),
                                                  lon,
                                                  (int)(ord(self.longitude[3]))
                                                  )
            self.send_calib = True
            
            self.led_1.value(0)
            self.led_2.value(0)
            self.beep()
            self.led_1.value(1)
            self.led_2.value(1)
            self.beep()
            
        except Exception as e:
            e = 'Failed calibration procedure : ' + str(e)
            print(e)
            self.failure(e)

        await asyncio.sleep(0)

    # DATA ACQUISITION
    async def get_data(self):
                
        while True:

            self.t_log = ticks_ms() - self.calib_time

            # TRY BNO
            try:
                self.bno_accel = np.array(self.bno.accel())*self.bno_scale # NEED TO CONVERT TUPLE TO NUMPY ARRAY TO SCALE VALUES (CAN'T EDIT TUPLES)
                self.gyro = self.bno.gyro()
                self.bno_working = True
            except Exception as e:
                e = 'Failed to read bno : ' + str(e)
                print(e)
                self.failure(e)
                self.bno_working = False
                
            # TRY KX
            try:
                self.kx_accel = np.array(self.kx.acceleration)*self.kx_scale # NEED TO CONVERT TUPLE TO NUMPY ARRAY TO SCALE VALUES (CAN'T EDIT TUPLES)
                self.kx_working = True
            except Exception as e:
                e = 'Failed to read kx : ' + str(e)
                print(e)
                self.failure(e)
                self.kx_working = False
            
            # TRY BMP
            try:
                self.temp = self.bmp.temperature
                self.alt = self.altitude() - self.calib_altitude
                self.density = self.rho(self.alt)
                self.bmp_working = True
            except Exception as e:
                e = 'Failed to read bmp : ' + str(e)
                print(e)
                self.failure(e)
                self.bmp_working = False
                    
            # READ RAM BAROMETER ONLY IF DATA IS READY
            if self.ram_dout.value() == 0:
                self.ram_diff = self.ram_raw_data() - self.ram_offset
                self.new_ram_data = True
            else:
                self.new_ram_data = False
                
            try:
                # DELAY NEEDED BETWEEN MEASUREMENTS
                self.adc.set_conv(7, 0)
                self.volt_vcc = self.adc.raw_to_v(self.adc.read_rev())
                sleep_ms(1)
                self.adc.set_conv(7, 1)
                self.volt_drogue = self.adc.raw_to_v(self.adc.read_rev())
                sleep_ms(1)
                self.adc.set_conv(7, 2)
                self.volt_main = self.adc.raw_to_v(self.adc.read_rev())
                sleep_ms(1)
                self.adc.set_conv(7, 3)
                self.volt_3v3 = self.adc.raw_to_v(self.adc.read_rev())
                                
            except Exception as e:
                e = 'Failed to read ADC : ' + str(e)
                print(e)
                self.failure(e)
                
            # CHECK IF CALIBRATION IS NEEDED   
            if self.state == 0:
                if self.t_log > self.calib_gap and self.calib_count < self.calib_max:
                    self.async_loop.create_task(self.calibrate()) # RUN CALIBRATION ONCE

            await asyncio.sleep(0)
        
        
    # STATE MACHINE
    async def state_machine(self):
        
        last_beep_time = 0
        
        while True:
            
            try:
                t = ticks_ms()
                
                # SHIFT VALUES ONE ELEMENT TO LEFT
                self.alt_buf = np.roll(self.alt_buf,-1)
                self.vel_buf = np.roll(self.vel_buf,-1)
                self.acc_buf = np.roll(self.acc_buf,-1)
                # UPDATE LAST VALUE    
                self.alt_buf[-1] = self.alt
                self.vel_buf[-1] = 1000 * (self.alt_buf[-1] - self.alt_buf[-2])/(self.t_log - self.last_t_log)
                
                if self.bno_working and self.kx_working:
                    self.acc_buf[-1] = (self.bno_accel[0] + self.kx_accel[1])/2
                elif self.bno_working:
                    self.acc_buf[-1] = self.bno_accel[0]
                elif self.kx_working:
                    self.acc_buf[-1] = self.kx_accel[1]
                
                if self.state == 0 and abs(self.acc_buf[-1]-self.g)/self.g < 0.15 and self.t_log - last_beep_time > 5000:
                    self.beep(1,50)
                    last_beep_time = self.t_log
                
                # SEND TELEMETRY FAST IN FLIGHT
                if (self.state != 0 and self.state != 5):
                    self.tel_delay = self.tel_delay_fast
                else:
                    self.tel_delay = self.tel_delay_slow
                
                # RUN STATE MACHINE UNTIL RUNTIME ENDS OR TOUCHDOWN
                if (self.t_log > self.runtime or self.logging_done):  
                    self.data_array = bytearray() # why? IDK I JUST COPIED WHAT YOU DID @Shobhit LOL
                    self.state = 5
                    self.async_loop.stop() # EXIT ASYNC LOOP
                
                # LIFTOFF DETECTED IF - (STATE IS 0 & (ALT > MIN LIFTOFF ALT & (CONTINUOUS ACCELERATION or ALT HIGH ENOUGH))
                if self.state==0 and ((np.all(self.alt_buf > self.min_liftoff_alt) and np.all(self.acc_buf > self.liftoff_accel*self.g)) or np.all(self.alt_buf > self.force_liftoff_alt)): #Liftoff
                    self.state = 1
                    self.t_events[0] = self.t_log
                    print('liftoff')
                            
                # BURNOUT DETECTED IF - (LIFTOFF DETECTED & CONTINUOUS ACCELERATION IN OPPOSITE DIRECTION & DECELERATION(DRAG) IS DECREASING) or (ENOUGH TIME HAS PASSED SINCE LIFTOFF)
                elif self.state==1 and ((np.all(self.acc_buf < 0) and self.acc_buf[-1] > self.acc_buf[-2]) or self.t_log - self.t_events[0] > self.force_burnout_time):
                    self.state = 2
                    self.t_events[1] = self.t_log
                    print("burnout")
                
                # DROGUE DEPLOYED IF - (BURNOUT DETECTED & LOCKOUT TIME CROSSED) & (VERTICAL VELOCITY NEGATIVE or ENOUGH TIME HAS PASSED SINCE LIFTOFF )
                elif (self.state==2 and self.t_log - self.t_events[0] > self.lockout_drogue_time) and (np.all(self.vel_buf < 0) or self.t_log - self.t_events[0] > self.force_drogue_time):
                    self.state = 3
                    self.t_events[2] = self.t_log
                    print("drogue")
                    
                    # SPAM DROGUE PYRO
                    for i in range(3):
                        self.drogue_pin.value(1)
                        sleep_ms(300)
                        self.drogue_pin.value(0)
                        sleep_ms(100)
                
                # MAIN DEPLOYED IF - (DROGUE DEPLOYED & ALT < MAIN DEPLOYMENT ALTITUDE & LOCKOUT TIME CROSSED)
                elif self.state==3 and np.all(self.alt_buf < self.main_alt) and self.t_log - self.t_events[2] > self.drogue_to_main_lockout:
                    self.state = 4
                    self.t_events[3] = self.t_log
                    print("main")
                    
                    # SPAM MAIN PYRO
                    for i in range(3):
                        self.main_pin.value(1)
                        sleep_ms(300)
                        self.main_pin.value(0)
                        sleep_ms(100)

                        
                # DETECT TOUCHDOWN IF - (ALT < TOUCHDOWN ALT & VERTICAL VELOCITY IS REALLY SMALL & LOCKOUT TIME CROSSED)
                elif self.state == 4 and np.all(self.alt_buf < self.touchdown_alt) and abs(np.mean(self.vel_buf)) < self.touchdown_vel_limit and self.t_log - self.t_events[3] > self.main_to_touchdown_lockout:
                    self.state = 5
                    self.t_events[4] = self.t_log
                    self.logging_done = True
                    self.tel_delay = self.tel_delay_slow                    
                    print('touchdown')
                    
                # AFTER TOUCHDOWN WE CHILL
                else:
                    pass
                
                self.drogue_pin.value(0)
                self.main_pin.value(0)

                self.last_t_log = self.t_log
                
            except Exception as e:
                e = 'Failure in State Machine : ' + str(e)
                print(e)
                self.failure(e)
            
            await asyncio.sleep(0) 

    # LOG DATA
    async def log_data(self):
        
        pad_loc_count = 0
        
        while True:

            t = ticks_ms()
            
            try:
                # PACK FAST READINGS TO BYTES(PACK_INTO SO IT DOESN'T CREATE A NEW BUFFER EVERY TIME)
                ustruct.pack_into(self.packing_str,       # PACK ACCORDING TO THIS FORMAT
                                  self.data_fast,         # INTO THIS BUFFER
                                  0,                      # WITH OFFSET 0 (DATA STARTS AFTER THIS)
                                  
                                  b'F',                   # F FOR FAST READINGS
                                  (int)(self.t_log),
                                  (int)(self.state),
                                  (int)((self.temp - self.calib_temp)*self.temp_mult),
                                  (float)(self.alt),
                                  (float)(self.ram_diff),
                                  (int)(self.bno_accel[0]*self.acc_mult),
                                  (int)(self.bno_accel[1]*self.acc_mult),
                                  (int)(self.bno_accel[2]*self.acc_mult),
                                  (float)(self.kx_accel[1]),
                                  (float)(-self.kx_accel[0]),
                                  (float)(self.kx_accel[2]),
                                  (float)(self.gyro[0]),
                                  (float)(self.gyro[1]),
                                  (float)(self.gyro[2]),
                                  (int)(self.volt_main*self.volt_mult),
                                  (int)(self.volt_drogue*self.volt_mult),
                                  (int)(self.volt_3v3*self.volt_mult),
                                  (int)(self.volt_vcc*self.volt_mult)
                                  )
            except Exception as e:
                e = 'Failed to pack fast data : ' + str(e)
                print(e)
                self.failure(e)
                        
                                              
            # PACK SLOW READINGS TO BYTES
            # ONLY IF NEW DATA HAS BEEN RECEIVED AND POSITION FIX HAS OBTAINED ATLEAST ONCE
            try:
                if self.gps_counter > self.last_gps_counter and (self.latitude[0] != 0 and self.longitude[0] != 0):
                                                                    
                    ustruct.pack_into( self.packing_str_slow,
                                       self.data_slow,
                                       0,
                                       b'S',                     # S FOR SLOW READINGS
                                       (int)(self.latitude[0]),
                                       (int)(self.latitude[1]),
                                       (float)(self.latitude[2]),
                                       (int)(ord(self.latitude[3])),
                                       (int)(self.longitude[0]),
                                       (int)(self.longitude[1]),
                                       (float)(self.longitude[2]),
                                       (int)(ord(self.longitude[3])),
                                       (int)(self.speed*self.gps_mult),
                                       (int)(self.course*self.gps_mult),
                                       (int)(self.hdop*self.gps_mult),
                                       (int)(self.vdop*self.gps_mult),
                                       self.sentence_type,
                                       (float)(self.gps_altitude),
                                       (float)(self._fix_time - self.calib_time),
                                       (float)(self.time_since_fix)
                                       )
            except Exception as e:
                e = 'Failed to pack GPS data : ' + str(e)
                print(e)
                self.failure(e)
            
            # ONLY LOG DATA WHEN - NOT ON PAD or NOT TOUCHED DOWN or MORE THAN 1kB OF SAPCE IS AVAILABLE (SHOULD NEVER GET THIS CLOSE)
            if self.state != 0 and self.state != 5 and self.free_bytes - self.size > 1000:
                try:
                    self.data_file.write(self.data_fast)
                    self.size += len(self.data_fast)
                except Exception as e:
                    e = 'Failed to write fast data : ' + str(e)
                    print(e)
                    self.failure(e)
                        
                # WRITE SLOW DATA TO FLASH ONLY IF NEW FIX IS ACQUIRED      
                if self.gps_counter > self.last_gps_counter and (self.latitude[0] != 0 and self.longitude[0] != 0):
                    try:
                        self.data_file.write(self.data_slow)
                        self.size += len(self.data_slow)
                    except Exception as e:
                        e = 'Failed to write GPS data : ' + str(e)
                        print(e)
                        self.failure(e)
            
            if self.state == 0:

                if self.gps_counter > self.last_gps_counter and pad_loc_count < 10 and (self.latitude[0] != 0 and self.longitude[0] != 0):
                    try:
                        self.data_file.write(self.data_slow)
                        pad_loc_count += 1
                    except Exception as e:
                        e = 'Failed to write GPS data at launch pad : ' + str(e)
                        print(e)
                        self.failure(e)
                        
                try:
                    if len(self.data_buffer) < 5000:
                        self.data_buffer += self.data_fast
                    else:
                        self.data_buffer = self.data_buffer[50:] + self.data_fast
                except Exception as e:
                    e = 'Failed to store fast data in pre-flight buffer : ' + str(e)
                    print(e)
#                     self.failure(e)
            
            await asyncio.sleep_ms(0)        
     
             
    # COMMUNICATION BETWEEN ROCKET AND GROUND STATION   
    async def comms(self):
        
        while True:
                    
            t = ticks_ms()
            
            if self.send_calib:
                self.xbee.write(self.calib_data)
                self.send_calib = False
            elif self.state != 5:
                self.xbee.write(self.data_fast + ustruct.pack('!f',self.x))
                if self.gps_counter > self.last_gps_counter:
                    await asyncio.sleep_ms(self.tel_delay)
                    self.xbee.write(self.data_slow)   
            else:
                self.xbee.write(self.data_slow)
                self.beep()
                
            try:    
                if self.xbee.any():
                    
                    # A - GPS coordinates
                    # B - Launch course 
                    # C - Runtime 
                    # D - Calib gap 
                    # E - Max calibrations 
                    # F - Liftoff accel 
                    # G - Min liftoff alt 
                    # H - Force liftoff alt 
                    # I - Force burnout time 
                    # J - Force drogue time 
                    # K - Drogue lockout 
                    # L - Main altitude 
                    # M - Drogue to main lockout
                    # N - Touchdown altitude
                    # O - Touchdown velocity limit
                    # P - Main to touchdown lockout
                    # Q - Buffer length
                    # R - Telemetry delay slow
                    # S - Telemetry delay fast
                    # T - Ram barometer scale
                    # U - Dry mass of rocket
                    # V - Target Apogee
                    # / - End of message
                    
                    data = str(self.xbee.read()).split(',')
                    if data != ["b'\\x00'"]:    
                        for i in range(1,41):
                            if(data[i]=='B'):
                                self.track_init = data[i+1]
                                print('Launch Course : ' + str(self.track_init))
                            elif(data[i]=='Q'):
                                self.buf_len = data[i+1]
                                print('Buffer Length : ' + str(self.buf_len))
                            elif(data[i]=='P'):
                                self.main_to_touchdown_lockout = data[i+1]
                                print('Main to Touchdown Lockout : ' + str(self.main_to_touchdown_lockout))
                            elif(data[i]=='A'):
                                if float(data[i+1]) > 0:
                                    self.latitude = [int(float(data[i+1])),int((float(data[i+1]) - int(float(data[i+1])))*60),((float(data[i+1]) - int(float(data[i+1])))*60 - int((float(data[i+1]) - int(float(data[i+1])))*60))*60,'N'] 
                                else:
                                    self.latitude = [int(float(data[i+1])),int((float(data[i+1]) - int(float(data[i+1])))*60),((float(data[i+1]) - int(float(data[i+1])))*60 - int((float(data[i+1]) - int(float(data[i+1])))*60))*60,'S']  
                                
                                if float(data[i+2]) > 0:   
                                    self.longitude = [int(float(data[i+2])),int((float(data[i+2]) - int(float(data[i+2])))*60),((float(data[i+2]) - int(float(data[i+2])))*60 - int((float(data[i+2]) - int(float(data[i+2])))*60))*60,'E']
                                else:
                                    self.longitude = [int(float(data[i+2])),int((float(data[i+2]) - int(float(data[i+2])))*60),((float(data[i+2]) - int(float(data[i+2])))*60 - int((float(data[i+2]) - int(float(data[i+2])))*60))*60,'W']                            
                                    
                                print('Latitude : ' + str(self.latitude))
                                print('Longitude : ' + str(self.longitude))
                                    
                            elif(data[i]=='C'):
                                self.runtime = data[i+1]
                                print('Runtime : ' + str(self.runtime))
                            elif(data[i]=='D'):
                                self.calib_gap = data[i+1]
                                print('Calibration Gap : ' + str(self.calib_gap))
                            elif(data[i]=='E'):
                                self.calib_max = data[i+1]
                                print('Max Calibrations : ' + str(self.calib_max))
                            elif(data[i]=='F'):
                                 self.liftoff_accel = data[i+1]
                                 print('Liftoff Acceleration : ' + str(self.liftoff_accel))
                            elif(data[i]=='G'):
                                self.min_liftoff_alt = data[i+1]
                                print('Minimum Liftoff Altitude : ' + str(self.min_liftoff_alt))
                            elif(data[i]=='H'):
                                self.force_liftoff_alt = data[i+1]
                                print('Force Liftoff Altitude : ' + str(self.force_liftoff_alt))
                            elif(data[i]=='I'):
                                self.force_burnout_time = data[i+1]
                                print('Force Burnout Time : ' + str(self.force_burnout_time))
                            elif(data[i]=='J'):
                                self.force_drogue_time = data[i+1]
                                print('Force Drogue Time : ' + str(self.force_drogue_time))
                            elif(data[i]=='K'):
                                self.lockout_drogue_time = data[i+1]
                                print('Drogue Lockout : ' + str(self.lockout_drogue_time))
                            elif(data[i]=='L'):
                                self.main_alt = data[i+1]
                                print('Main Alt : ' + str(self.main_alt))
                            elif(data[i]=='M'):
                                self.drogue_to_main_lockout = data[i+1]
                                print('Drogue to Main Lockout : ' + str(self.drogue_to_main_lockout))
                            elif(data[i]=='N'):
                                self.touchdown_alt = data[i+1]
                                print('Touchdown Alt : ' + str(self.touchdown_alt))
                            elif(data[i]=='O'):
                               self.touchdown_vel_limit = data[i+1]
                               print('Touchdown Velocity Limit : ' + str(self.touchdown_vel_limit))
                            elif(data[i]=='R'):
                                self.tel_delay_slow = data[i+1]
                                print('Slow Tel Delay : ' + str(self.tel_delay_slow))
                            elif(data[i]=='S'):
                                self.tel_delay_fast = data[i+1]
                                print('Fast Tel Delay : ' + str(self.tel_delay_fast))
                            elif(data[i]=='T'):
                                self.ram_baro_scale = data[i+1]
                                print('Ram Baro Scale : ' + str(self.ram_baro_scale))
                            elif(data[i]=='U'):
                                self.mass = data[i+1]
                                print('Dry Mass : ' + str(self.mass))
                                for i in range(3):
                                    try:
                                        self.mc.writeto(0x41,b'M' + ustruct.pack('!f',self.mass))
                                        sleep_ms(self.mc_delay)
                                    except Exception as e:
                                        e = 'Motor Controller not available for mass update : ' + str(e)
                                        print(e)
                                        self.failure(e)
                            elif(data[i]=='V'):
                                self.target = data[i+1]
                                print('Target : ' + str(self.target))
                                for i in range(3):
                                    try:
                                        self.mc.writeto(0x41,b'N' + ustruct.pack('!f',self.target))
                                        sleep_ms(self.mc_delay)
                                    except Exception as e:
                                        e = 'Motor Controller not available for target update : ' + str(e)
                                        print(e)
                                        self.failure(e)
                            elif(data[i]=='/'):
                                print('No data ahead')
                                break
                
            except Exception as e:
                e = 'Failed to parse commands from ground station : ' + str(e)
                print(e)
                self.failure(e)
            
            await asyncio.sleep_ms(self.tel_delay)

    # NAV FILTER
    async def nav(self):
        
        counter = 0
        
        X_A = np.full((3,1),0.)        # ORIENTATION MATRIX
        C1 = np.full((3,3),0.)         # ROTATION MATRIX TO CONVERT TO 'Z-AXIS VERTICAL' ORIENTATION

        X = np.full((5,1),0.)          # STATE MATRIX
        W = np.full((5,1),0.)          # IDK WHAT YOU CALL THIS
        F = np.eye(5)                  # STATE TRANSITION MATRIX
        P = np.full((5,5),0.)          # UNCERTAINITY MATRIX
        Q = np.full((5,5),0.)          # UNCERTAINITY TRANSITION MATRIX
        R = np.eye(5)                  # SENSOR NOISE MATRIX OR SOMETHING
        Z = np.full((5,1),0.)          # MEASUREMENT MATRIX
        U = np.full((5,1),0.)          # CONTROL MATRIX
        
        dt = 1/30
        nx = ny = 1
        init = False
                     
        Q[0][0] = 10
        Q[1][1] = 10
        Q[2][2] = 0.1
        Q[3][3] = 0.01
        Q[4][4] = 1
        
        vx = 0
        airspeed = 0
                     
        while True:
            
            # EVEYTHING INSIDE TRY-EXCEPT IN CASE IT DECIDES TO CRASH MID-FLIGHT
            if counter > 0:
                
                dt = (self.t_log - self.last_loop_t)/1000
                
                try:
                    if self.bno_working and self.kx_working:
                        ax = (self.bno_accel[2] + self.kx_accel[2])/2
                        ay = (-self.bno_accel[1] + self.kx_accel[0])/2
                        az = (self.bno_accel[0] + self.kx_accel[1])/2

                    elif self.bno_working:
                        ax = self.bno_accel[2]
                        ay = -self.bno_accel[1]
                        az = self.bno_accel[0]
                        
                    elif self.kx_working:
                        ax = self.kx_accel[2]
                        ay = self.kx_accel[0]
                        az = self.kx_accel[1]
                                
                    a = sqrt(ax*ax + ay*ay + az*az)
                    
                    gx = self.gyro[2]*pi/180
                    gy = -self.gyro[1]*pi/180
                    gz = -self.gyro[0]*pi/180
                    
                    # RAM BAROMETER SCALE(RAW READING TO DIFFERENTIAL PRESSURE)
                    k = 1/self.ram_baro_scale
                
                except Exception as e:
                    e = 'Error in pulling raw sensor readings in KF : ' + str(e) 
                    print(e)
                    self.failure(e)
                            
                # CALCULATE AIRSPEED
                try:
                    
                    if k*self.ram_diff >= 0:
                        dp = k*self.ram_diff
                        p = pow(8.9611 - (self.alt + self.calib_altitude)/4947.19,5.2561)
                        if sqrt(7*p/self.density*(pow(1 + dp/p,0.2857) - 1)) < 400:
                            airspeed = sqrt(7*p/self.density*(pow(1 + dp/p,0.2857) - 1))
                        
                except Exception as e:
                    
                    airspeed = 0
                    
                    e = 'Error in calculating airspeed : ' + str(e)
                    print(e)
                    self.failure(e)

                # ATTITUDE KF ----------------------------------------------------------------------------------------------      
                # WAS SUPPOSED TO BE A KF BUT BNO DECIDED TO BE A LITTLE BITCH (WON'T LET MAGNETOMETER WORK IN HIGH-G MODE)                    
                # SO WE JUST INTEGRATE THE GYROS NOW

                e = abs(a-self.g)/self.g

                cutoff = 0.05
                
                try:
                    # USE ACCELEROMETER TO CALCULATE PITCH AND ROLL IF ACCELERATION IS LOW AND LIFTOFF IS NOT DETECTED. ELSE GYRO.
                    if e < cutoff and not self.t_events[0]:
                        X_A[0][0] = atan2(ay,az)    
                        X_A[1][0] = atan2(-ax,sqrt(pow(ay,2) + pow(az,2)))
                    else:
                        X_A[0][0] += nx*gx*dt
                        X_A[1][0] += ny*gy*dt

                    # IF LIFTOFF IS DETECTED THEN USE GYRO FOR YAW (SECOND CONDITION FOR INSTANT DETECTION ON IGNITION). ELSE NO YAW.
                    if self.t_events[0] or e > cutoff:
                        X_A[2][0] += gz*dt
                    else: 
                        X_A[2][0] = 0
                        
                    if abs(X_A[0][0] + nx*gx*dt) >= pi/2:
                        nx *= -1
                    if abs(X_A[1][0] + ny*gy*dt) >= pi/2:
                        ny *= -1
                    
                    # UPDATE ROTATION MATRIX
                    C1[0][0] = cos(X_A[1][0])
                    C1[0][1] = 0
                    C1[0][2] = sin(X_A[1][0])
                    
                    C1[1][0] = sin(X_A[0][0])*sin(X_A[1][0])
                    C1[1][1] = cos(X_A[0][0])
                    C1[1][2] = -sin(X_A[0][0])*cos(X_A[1][0])
             
                    C1[2][0] = -sin(X_A[1][0])*cos(X_A[0][0])
                    C1[2][1] = sin(X_A[0][0])
                    # WAIT FOR ROCKET TO PICK UP SPEED BECAUSE WE'RE TAKING RATIO OF VELOCITIES
                    if self.state <= 1:
                        C1[2][2] = cos(X_A[0][0])*cos(X_A[1][0])
                    else:
                        if abs(X[3][0]) < abs(X[4][0]):
                            C1[2][2] = X[3][0]/X[4][0]
                        else:
                            C1[2][2] += - pow(sin(acos(C1[2][2])),2)*self.g/X[4][0]*dt
                    
                    if C1[2][2] > 1:
                        C1[2][2] = 1
                    elif C1[2][2] < 0:
                        C1[2][2] = 0
                    
                except Exception as e:
                    
                    C1[2][2] = 1
                    
                    e = 'Error in calculating attitude : ' + str(e)
                    print(e)
                    self.failure(e)
        # -------------------------------------------------------------------------------------------------------------------
                
                last_alt = Z[2][0]
                
                # CALCULATE GRAVITY VECTOR
                try:
                    gravity = np.dot(C1,np.array([[0],[0],[-self.g]]))
                
                    # CALCULATE ACCELERATION WRT GROUND
                    lin_acc_x = - ax + gravity[0][0]
                    lin_acc_y = - ay + gravity[1][0]
                    lin_acc_z = az + gravity[2][0]
                    
                except Exception as e:
                    e = 'Error in calculating gravity vector : ' + str(e)
                    print(e)
                    self.failure(e)
                
                try:
                    if self.state == 1:
                        Q[3][3] = 0.01
                        Q[3][4] = 3
                    elif self.state != 0:
                        if Z[3][0] > 100:
                            Q[3][3] = 0.00005
                            Q[3][4] = 5  
                        elif Z[3][0] > 50:
                            Q[3][3] = 0.00005
                            Q[3][4] = 7 
                        else:
                            Q[3][3] = 0.001
                            Q[3][4] = -15
                
                except Exception as e:
                    e = 'Error in updating KF uncertainity : ' + str(e)
                    print(e)
                    self.failure(e)
                
                try:
                    # ACCELERATIONS IN ROTATED FRAME (Z AXIS VERTICAL)
                    if np.linalg.det(C1) > pow(10,-6):
                        a_r = np.dot(np.linalg.inv(C1),np.array([[lin_acc_x],[lin_acc_y],[lin_acc_z]]))
                    else:
                        a_r = np.array([[0.],[0.],[0.]])
                    
                    dv = sqrt(pow(a_r[0][0],2) + pow(a_r[1][0],2))*dt
                
                except Exception as e:
                    e = 'Error in rotating frame of reference : ' + str(e)
                    print(e)
                    self.failure(e)
                    
                
                try:
                    # SET GPS COORDINATES DIRECTLY WHEN FIX IS ACCQUIRED
                    if self.latitude[0] != 0 and self.longitude[0] != 0 and init == False:
                        X[0][0] = (self.latitude[0] + self.latitude[1]/60 + self.latitude[2]/3600)*pi/180
                        X[1][0] = (self.longitude[0] + self.longitude[1]/60 + self.longitude[2]/3600)*pi/180
                        init = True
                        
                except Exception as e:
                    e = 'Error in GPS jump-start in KF : ' + str(e)
                    print(e)
                    self.failure(e)
                
                try:
                    # STATE TRANSITION MATRIX UPDATE
                    F[2][3] = dt
                    
                    # CONTROL MATRIX UPDATE
                    U[0][0] = cos(self.track_init)*vx*dt/self.r
                    if abs(Z[0][0]*180/pi - 90) > 10:
                        U[1][0] = sin(self.track_init)*vx*dt/(self.r*cos(Z[0][0]))
                    else:
                        U[1][0] = 0
                    U[2][0] = a_r[2][0]*dt*dt/2
                    U[3][0] = a_r[2][0]*dt
                    U[4][0] = lin_acc_z*dt
                    
                except Exception as e:
                    e = 'Error in updating Control/State Transition matrix : ' + str(e)
                    print(e)
                    self.failure(e)
                
                try:                
                    Xp = np.dot(F,X) + U

                    Pp = np.dot(np.dot(F,P),F.T) + Q
                
                except Exception as e:
                    e = 'Error in calculating Predicted State matrix : ' + str(e)
                    print(e)
                    self.failure(e)
                    
                
                try:
                    # ALTITUDE AND VERTICAL VELOCTY READINGS
                    if self.bmp_working:
                        Z[2][0] = self.alt
                        Z[3][0] = (Z[2][0] - last_alt)/dt
                    elif self.bno_working:
                        Z[2][0] += (Z[3][0] + a_r[2][0]*dt/2)*dt
                        Z[3][0] += a_r[2][0]*dt
                        
                    if self.new_ram_data:
                        if airspeed >= X[3][0]:
                            Z[4][0] = airspeed
                        else:
                            Z[4][0] += lin_acc_z*dt
                    else:
                        Z[4][0] += lin_acc_z*dt
                        
                except Exception as e:
                    e = 'Error in updating Raw State in KF : ' + str(e)
                    print(e)
                    self.failure(e)
                    
                
                try:
                    # IF GPS FIX
                    if self.gps_counter > self.last_gps_counter and ('GGA' in self.sentence_type or 'GLL' in self.sentence_type or 'RMC' in self.sentence_type or 'ROV' in self.sentence_type):
                        # UPDATE COORDINATES FROM GPS
                        # MAKING SURE LATITUDE DOESN'T GO NEAR 90 DEGRESS BECAUSE THEN DEAD RECKONING MIGHT BLOW UP
                        # BECAUSE OF cos(LATITUDE) IN DENOMINATOR
                        if abs((self.latitude[0] + self.latitude[1]/60 + self.latitude[2]/3600) - 90) > 10:
                            Z[0][0] = (self.latitude[0] + self.latitude[1]/60 + self.latitude[2]/3600)*pi/180
                        else:
                            Z[0][0] += vx*dt*cos(Z[5][0])/self.r
                            
                        Z[1][0] = (self.longitude[0] + self.longitude[1]/60 + self.longitude[2]/3600)*pi/180
                    else:
                        if abs(Z[0][0]*180/pi - 90) > 10:
                            Z[1][0] += vx*dt*sin(self.track_init)/(self.r*cos(Z[0][0]))
                        Z[0][0] += vx*dt*cos(self.track_init)/self.r
                        
                except Exception as e:
                    e = 'Error in GPS update in KF : ' + str(e)
                    print(e)
                    self.failure(e)

                try:
                    K = np.dot(Pp,np.linalg.inv(Pp + R))
                except Exception as e:
                    e = 'Error in updating Kalman Gain : ' + str(e)
                    print(e)
                    self.failure(e)

                try:
                    X = Xp + np.dot(K,Z - Xp)
                except Exception as e:
                    e = 'Error in updating State : ' + str(e)
                    print(e)
                    self.failure(e)
                
                try:    
                    P = np.dot(np.eye(len(K)) - K,Pp)
                except Exception as e:
                    e = 'Error in updating State Uncertainity : ' + str(e)
                    print(e)
                    self.failure(e)
                    
                try:
                    if abs(X[4][0]) > abs(X[3][0]):
                        vx = sqrt(X[4][0]**2 - X[3][0]**2)
                    else:
                        vx += dv
                
                except Exception as e:
                    e = 'Error in updating horizontal velocity : ' + str(e)
                    print(e)
                    self.failure(e)
                    
                    
                try:
                    if self.state == 1 or self.state == 2:
                        self.x += vx*dt
                
                except Exception as e:
                    e = 'Error in updating dead reckoning horizontal distance : ' + str(e)
                    print(e)
                    self.failure(e)
                
                # WRITE DATA TO MOTOR CONTROLLER. DOESN'T LIKE RECEIVING MORE THEN 18-19 BYTES AT A TIME SO NEED TO BREAK DOWN DATA INTO PACKETS.
                # RAW DATA IS BACKED UP ON MOTOR CONTROLLER (MUCH SLOWER RATE THOUGH BECAUSE IT HAS TO DO AIRBRAKE CALCULATIONS).
                try:
                    if self.send_calib:
                        self.mc.writeto(0x41,b'A' + self.calib_data[:16])
                        sleep_ms(self.mc_delay)
                        self.mc.writeto(0x41,b'B' + self.calib_data[16:])
                        sleep_ms(self.mc_delay)
                        
                    self.mc.writeto(0x41,b'C' + self.data_fast[:16])
                    sleep_ms(self.mc_delay)
                    self.mc.writeto(0x41,b'D' + self.data_fast[16:30])
                    sleep_ms(self.mc_delay)
                    self.mc.writeto(0x41,b'E' + self.data_fast[30:46])
                    sleep_ms(self.mc_delay)
                    self.mc.writeto(0x41,b'F' + self.data_fast[46:])
                    sleep_ms(self.mc_delay)
                    
                    if self.gps_counter > self.last_gps_counter:
                                                    
                        self.mc.writeto(0x41,b'G' + self.data_slow[:15])
                        sleep_ms(self.mc_delay)
                        self.mc.writeto(0x41,b'H' + self.data_slow[15:30])
                        sleep_ms(self.mc_delay)
                        self.mc.writeto(0x41,b'I' + self.data_slow[30:38])
                        sleep_ms(self.mc_delay)
                        
                    self.mc.writeto(0x41,b'J' + ustruct.pack('!ffff',X_A[0][0],X_A[1][0],X_A[2][0],X[0][0]))
                    sleep_ms(self.mc_delay)
                    self.mc.writeto(0x41,b'K' + ustruct.pack('!ffff',X[1][0],X[2][0],X[3][0],X[4][0]))
                    sleep_ms(self.mc_delay)
                    self.mc.writeto(0x41,b'L' + ustruct.pack('!f',C1[2][2]))
                    sleep_ms(self.mc_delay)
                                            
                except Exception as e:
                    self.mc_missing()
                                                
            counter += 1   
               
            
            self.last_loop_t = self.t_log   
            self.last_gps_counter = self.gps_counter        
         
            await asyncio.sleep(0)
            
            
    async def fast_core(self):
        
        print('fast core init')
        
        # OPEN FILE WITH UNIQUE NAME USING INDEX FROM index.txt
        index_file = open('/index.txt','r')
        self.index = int(index_file.read())
        index_file.close()
        
        index_file = open('/index.txt','w')
        index_file.write(str(self.index + 1))
        index_file.close()

        self.data_file = open('/data_' + str(self.index) + '.bin','wb')
        
        print("starting event loop")
        
        self.async_loop = asyncio.get_event_loop()
        self.async_loop.create_task(self.calibrate())        # GET CALIBRATION DATA
        self.async_loop.create_task(self.get_data())         # GET SENSOR DATA
        self.async_loop.create_task(self.state_machine())    # RUN THE STATE MACHINE
        self.async_loop.create_task(self.nav())              # RUN THE NAVIGATION FILTER
        self.async_loop.create_task(self.comms())            # TRANSMIT TO GROUND STATION
        self.async_loop.create_task(self.log_data())         # LOG THE DATA
        self.async_loop.run_forever()                        # REPEAT
        
        self.data_file.write(self.data_buffer)
        
        # WRITE CALIBRATION DATA IF ALL THE CODE ABOVE THIS ACTUALLY SOMEHOW WORKS
        try:
            self.data_file.write(b'C' + self.calib_data)
            self.size += len(self.calib_data)
            print('Calibration data written')
        except Exception as e:
            e = 'Failed to write Calibration Data : ' + str(e)
            print('Failed to write Calibration Data')
            self.failure(e)
            pass
        
        self.data_file.close()
        
        print("logging done, now sending only GPS")
        
        # POST TOUCHDOWN LOOP
        self.async_loop = asyncio.new_event_loop()
        self.async_loop.create_task(self.comms())          # TRANSMIT TO GROUND STATION
        self.async_loop.create_task(self.blink(1000))      # BLINKY BLINKY
        self.async_loop.run_forever()


if __name__ == "__main__":
    test_instance = async_test()                    # START INSTANCE OF CLASS
    test_instance.init()                            # INITIALISE SOFTWARE
    test_instance.init_board()                      # INITIALISE SENSORS
    try:
        asyncio.run(test_instance.fast_core())      # START THE FAST CORE ASYNC LOOP
    except KeyboardInterrupt as e:
        print("User has ended loop, closing asyncio")
        test_instance.async_loop.stop()
        test_instance.async_loop.close()
    finally:
        print("done")
        pass
