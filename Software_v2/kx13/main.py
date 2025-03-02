# SPDX-FileCopyrightText: Copyright (c) 2023 Jose D. Montoya
#
# SPDX-License-Identifier: MIT

import time
from machine import Pin, I2C
import kx132

i2c = I2C(0, sda=Pin(0), scl=Pin(1))
print(i2c.scan())

kx = kx132.KX132(i2c)
print(kx)
kx.acc_range = kx132.ACC_RANGE_16
while True:
    accx, accy, accz = kx.acceleration
    print(f"x:{accx:.2f}g, y:{accy:.2f}g, z:{accz:.2f}g")
    print()
    time.sleep(0.1)