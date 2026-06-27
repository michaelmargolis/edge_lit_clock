from machine import I2C, Pin
import time
import math


class AmbientLightSensor:
    DEFAULT_I2C_ID = 0
    DEFAULT_SDA_PIN = 5
    DEFAULT_SCL_PIN = 6
    DEFAULT_I2C_FREQ = 100000

    VEML7700_ADDR = 0x10
    REG_ALS_CONF = 0x00
    REG_ALS_DATA = 0x04
    ALS_GAIN_X2 = 0b01 << 11
    ALS_IT_800MS = 0b0011 << 6
    LUX_PER_COUNT = 0.0036

    def __init__(
        self,
        i2c=None,
        lower_lux=20,
        upper_lux=150,
        transition_time_s=5.0,
        i2c_id=DEFAULT_I2C_ID,
        sda_pin=DEFAULT_SDA_PIN,
        scl_pin=DEFAULT_SCL_PIN,
        i2c_freq=DEFAULT_I2C_FREQ,
        register_reporter=None,
    ):
        self.available = False
        self.i2c = None
        self.owns_i2c = False

        self.lower_lux = lower_lux
        self.upper_lux = upper_lux
        self.transition_time_s = transition_time_s

        self.lux = 0.0
        self.current_percent = 0.0
        self.smoothed_percent = 0.0
        self.last_update_ms = None

        self.failures = 0
        self.last_error = ""
        self.last_error_time = None

        if register_reporter is not None:
            register_reporter("Ambient sensor", self.status_lines, self.error_lines)

        try:
            if i2c is None:
                self.i2c = I2C(
                    i2c_id,
                    sda=Pin(sda_pin),
                    scl=Pin(scl_pin),
                    freq=i2c_freq,
                )
                self.owns_i2c = True
            else:
                self.i2c = i2c

            self._write_reg16(self.REG_ALS_CONF, self.ALS_GAIN_X2 | self.ALS_IT_800MS)
            time.sleep(1)
            self.available = True

        except Exception as e:
            self._record_error("Sensor init failed: {}".format(e))
            self.available = False

    def _record_error(self, message):
        print(message)
        self.failures += 1
        self.last_error = message
        self.last_error_time = int(time.time())

    def _write_reg16(self, reg, value):
        data = bytes([value & 0xFF, (value >> 8) & 0xFF])
        self.i2c.writeto_mem(self.VEML7700_ADDR, reg, data)

    def _read_reg16(self, reg):
        data = self.i2c.readfrom_mem(self.VEML7700_ADDR, reg, 2)
        return data[0] | (data[1] << 8)

    def read_lux(self):
        if not self.available:
            return self.lux
        raw = self._read_reg16(self.REG_ALS_DATA)
        return raw * self.LUX_PER_COUNT

    def _lux_to_perceived_percent(self, lux):
        if lux <= self.lower_lux:
            return 0.0
        if lux >= self.upper_lux:
            return 100.0

        p = math.log(lux / self.lower_lux) / math.log(self.upper_lux / self.lower_lux)
        return p * 100.0

    def update(self):
        now_ms = time.ticks_ms()

        try:
            if self.available:
                self.lux = self.read_lux()
                self.current_percent = self._lux_to_perceived_percent(self.lux)

            if self.last_update_ms is None:
                self.smoothed_percent = self.current_percent
                self.last_update_ms = now_ms
                return self.smoothed_percent

            dt_ms = time.ticks_diff(now_ms, self.last_update_ms)
            self.last_update_ms = now_ms
            dt_s = dt_ms / 1000.0
            max_change = 100.0 * dt_s / self.transition_time_s

            if self.current_percent > self.smoothed_percent:
                self.smoothed_percent = min(
                    self.smoothed_percent + max_change,
                    self.current_percent,
                )
            else:
                self.smoothed_percent = max(
                    self.smoothed_percent - max_change,
                    self.current_percent,
                )

        except Exception as e:
            self._record_error("Sensor update failed: {}".format(e))

        return self.smoothed_percent

    def get_lux(self):
        return self.lux

    def get_current_percent(self):
        return self.current_percent

    def get_smoothed_percent(self):
        return self.smoothed_percent

    def status_lines(self):
        return [
            "  Available: {}".format(self.available),
            "  Lux: {:.1f}".format(self.lux),
            "  Current: {:.1f}".format(self.current_percent),
            "  Smoothed: {:.1f}".format(self.smoothed_percent),
        ]

    def error_lines(self):
        return [
            "  Failures: {}".format(self.failures),
            "  Last: {}".format(self.last_error),
            "  Last time: @ts:{}".format(self.last_error_time),
        ]
