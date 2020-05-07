# Bluefruit Playground server program, to run on CLUE

import array
import time

import board
from digitalio import DigitalInOut
import neopixel_write
import ulab

from micropython import const

from adafruit_ble import BLERadio

from adafruit_ble_adafruit.adafruit_service import AdafruitServerAdvertisement

from adafruit_ble_adafruit.accelerometer_service import AccelerometerService
from adafruit_ble_adafruit.addressable_pixel_service import AddressablePixelService
from adafruit_ble_adafruit.barometric_pressure_service import BarometricPressureService
from adafruit_ble_adafruit.button_service import ButtonService
from adafruit_ble_adafruit.humidity_service import HumidityService
from adafruit_ble_adafruit.light_sensor_service import LightSensorService
from adafruit_ble_adafruit.microphone_service import MicrophoneService
from adafruit_ble_adafruit.temperature_service import TemperatureService
from adafruit_ble_adafruit.tone_service import ToneService

from adafruit_clue import clue

accel_svc = AccelerometerService()
accel_svc.measurement_period = 100
accel_last_update = 0

# Even though the CLUE only has one NeoPixel, the Bluefruit Playground
# app is sending data for 10 pixels, so expect that many. Only the
# first pixel data will be visible, obviously.
NEOPIXEL_BUF_LENGTH = const(3 * 10)
neopixel_svc = AddressablePixelService(NEOPIXEL_BUF_LENGTH)
neopixel_buf = bytearray(NEOPIXEL_BUF_LENGTH)
# Take over NeoPixel control from clue.
clue._pixel.deinit()  # pylint: disable=protected-access
neopixel_out = DigitalInOut(board.NEOPIXEL)
neopixel_out.switch_to_output()

baro_svc = BarometricPressureService()
baro_svc.measurement_period = 100
baro_last_update = 0

button_svc = ButtonService()
button_svc.set_pressed(False, clue.button_a, clue.button_b)

humidity_svc = HumidityService()
humidity_svc.measurement_period = 100
humidity_last_update = 0

light_svc = LightSensorService()
light_svc.measurement_period = 100
light_last_update = 0

# Send 256 16-bit samples at a time.
MIC_NUM_SAMPLES = const(256)
mic_svc = MicrophoneService(MIC_NUM_SAMPLES)
mic_svc.number_of_channels = 1
mic_svc.measurement_period = 100
mic_last_update = 0
mic_samples = ulab.zeros(MIC_NUM_SAMPLES, dtype=ulab.uint16)

temp_svc = TemperatureService()
temp_svc.measurement_period = 100
temp_last_update = 0

tone_svc = ToneService()

ble = BLERadio()

# Adafruit CLUE USB PID:
# Arduino: 0x8071,  CircuitPython: 0x8072, app supports either
adv = AdafruitServerAdvertisement(0x8072)

while True:
    # Advertise when not connected.
    ble.start_advertising(adv)
    while not ble.connected:
        pass
    ble.stop_advertising()

    while ble.connected:
        now_msecs = time.monotonic_ns() // 1000000

        if now_msecs - accel_last_update >= accel_svc.measurement_period:
            accel_svc.acceleration = clue.acceleration
            accel_last_update = now_msecs

        if now_msecs - baro_last_update >= baro_svc.measurement_period:
            baro_svc.pressure = clue.pressure
            baro_last_update = now_msecs

        button_svc.set_pressed(False, clue.button_a, clue.button_b)

        if now_msecs - humidity_last_update >= humidity_svc.measurement_period:
            humidity_svc.humidity = clue.humidity
            humidity_last_update = now_msecs

        if now_msecs - light_last_update >= light_svc.measurement_period:
            # Return "clear" color value from color sensor.
            light_svc.light_level = clue.color[3]
            light_last_update = now_msecs

        if now_msecs - mic_last_update >= mic_svc.measurement_period:
            clue._mic.record(
                mic_samples, len(mic_samples)
            )  # pylint: disable=protected-access
            mic_svc.sound_samples = mic_samples - 32768
            mic_last_update = now_msecs

        neopixel_values = neopixel_svc.values
        if neopixel_values is not None:
            start = neopixel_values.start
            if start > NEOPIXEL_BUF_LENGTH:
                continue
            data = neopixel_values.data
            data_len = min(len(data), NEOPIXEL_BUF_LENGTH - start)
            neopixel_buf[start : start + data_len] = data[:data_len]
            if neopixel_values.write_now:
                neopixel_write.neopixel_write(neopixel_out, neopixel_buf)

        if now_msecs - temp_last_update >= temp_svc.measurement_period:
            temp_svc.temperature = clue.temperature
            temp_last_update = now_msecs

        tone = tone_svc.tone
        if tone is not None:
            freq, duration = tone
            if freq != 0:
                if duration != 0:
                    # Note that this blocks. Alternatively we could
                    # use now_msecs to time a tone in a non-blocking
                    # way, but then the other updates might make the
                    # tone interval less consistent.
                    clue.play_tone(freq, duration)
                else:
                    clue.stop_tone()
                    clue.start_tone(freq)
            else:
                clue.stop_tone()
        last_tone = tone
