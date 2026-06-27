# led_digits_driver.py

from machine import Pin, SPI, PWM
from time import sleep_ms
import time

USE_PIXEL = True

if USE_PIXEL:
    from pixel import Pixel


class LedDigitsDriver:
    STATUS_COLORS = {
        "not connected": (255, 0, 0),
        "not synced": (0, 128, 255),
        "synced": (0, 0, 255),
    }

    def __init__(
        self,
        encoder,
        spi_id=1,
        sck_pin=7,
        mosi_pin=9,
        le_pin=44,
        stp_oe_pin=43,
        indicator_pin=4,
        chips=2,
        baudrate=1_000_000,
        pwm_freq=2000,
        latch_delay_ms=1,
        register_reporter=None,
    ):
        self.encoder = encoder
        self.chips = chips
        self.bit_count = chips * 16
        self.byte_count = self.bit_count // 8
        self.latch_delay_ms = latch_delay_ms

        self.le = None
        self.spi = None
        self.stp_oe_pwm = None
        self.pixel = None
        self.indicator_pwm = None
        self.hardware_ok = False

        self.displayed_time = "00:00"
        self.brightness_percent = 0.0
        self.indicator_status = "not connected"

        self.failures = 0
        self.last_error = ""
        self.last_error_time = None

        if register_reporter is not None:
            register_reporter("Display", self.status_lines, self.error_lines)

        try:
            self.le = Pin(le_pin, Pin.OUT, value=0)
            self.spi = SPI(
                spi_id,
                baudrate=baudrate,
                polarity=0,
                phase=0,
                bits=8,
                sck=Pin(sck_pin),
                mosi=Pin(mosi_pin),
            )

            self.stp_oe_pwm = PWM(Pin(stp_oe_pin))
            self.stp_oe_pwm.freq(pwm_freq)

            if USE_PIXEL:
                self.pixel = Pixel(pin_num=indicator_pin)
            else:
                self.indicator_pwm = PWM(Pin(indicator_pin))
                self.indicator_pwm.freq(pwm_freq)

            self.hardware_ok = True
            self.clear()
            self.set_brightness(100)

        except Exception as e:
            self._record_error("Display init failed: {}".format(e))
            self.hardware_ok = False

    def _record_error(self, message):
        print(message)
        self.failures += 1
        self.last_error = message
        self.last_error_time = int(time.time())

    def latch(self):
        if not self.hardware_ok:
            return False
        try:
            self.le.value(1)
            sleep_ms(self.latch_delay_ms)
            self.le.value(0)
            return True
        except Exception as e:
            self._record_error("Display latch failed: {}".format(e))
            return False

    def write_bits(self, value):
        if not self.hardware_ok:
            return False
        try:
            data = value.to_bytes(self.byte_count, "big")
            self.le.value(0)
            self.spi.write(data)
            return self.latch()
        except Exception as e:
            self._record_error("Display write failed: {}".format(e))
            return False

    def leds_to_bits(self, leds):
        value = 0
        for led in leds:
            if led < 0 or led >= self.bit_count:
                raise ValueError("LED index out of range: {}".format(led))
            value |= 1 << led
        return value

    def write_leds(self, leds):
        return self.write_bits(self.leds_to_bits(leds))

    def display_time(self, time_string):
        leds = self.encoder(time_string)
        ok = self.write_leds(leds)
        if ok:
            self.displayed_time = time_string
        return ok

    def clear(self):
        return self.write_bits(0)

    def all_on(self):
        return self.write_bits((1 << self.bit_count) - 1)

    def set_brightness(self, percent):
        percent = max(0, min(100, percent))
        duty = int(percent * 65535 / 100)

        try:
            if self.stp_oe_pwm is not None:
                self.stp_oe_pwm.duty_u16(65535 - duty)

            if USE_PIXEL and self.pixel is not None:
                self.pixel.set_brightness(percent)
            elif self.indicator_pwm is not None:
                self.indicator_pwm.duty_u16(duty)

            self.brightness_percent = percent
            return True

        except Exception as e:
            self._record_error("Brightness update failed: {}".format(e))
            return False

    def set_indicator_color(self, rgb):
        try:
            if USE_PIXEL and self.pixel is not None:
                self.pixel.set_color(rgb)
            return True
        except Exception as e:
            self._record_error("Indicator color failed: {}".format(e))
            return False

    def indicator_off(self):
        try:
            if USE_PIXEL and self.pixel is not None:
                self.pixel.off()
            elif self.indicator_pwm is not None:
                self.indicator_pwm.duty_u16(0)
            return True
        except Exception as e:
            self._record_error("Indicator off failed: {}".format(e))
            return False

    def set_status(self, status):
        if status not in self.STATUS_COLORS:
            self._record_error("Unknown status: {}".format(status))
            return False

        self.set_indicator_color(self.STATUS_COLORS[status])
        self.indicator_status = status
        return True

    def walk_test(self, delay_ms=100):
        for led in range(self.bit_count):
            self.write_leds((led,))
            sleep_ms(delay_ms)
        self.clear()

    def pulse_test(self, delay_ms=100):
        self.all_on()
        sleep_ms(delay_ms)
        self.clear()
        sleep_ms(delay_ms)

    def status_lines(self):
        return [
            "  Hardware OK: {}".format(self.hardware_ok),
            "  Time: {}".format(self.displayed_time),
            "  Brightness: {:.1f}".format(self.brightness_percent),
            "  Indicator: {}".format(self.indicator_status),
        ]

    def error_lines(self):
        return [
            "  Failures: {}".format(self.failures),
            "  Last: {}".format(self.last_error),
            "  Last time: @ts:{}".format(self.last_error_time),
        ]
