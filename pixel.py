# pixel.py

from machine import Pin
import neopixel


class Pixel:
    """
    Simple WS2812B / SK6812 driver. All LEDs set to same color.

    Color values: (r, g, b)  where each value is 0..255
    Brightness:  0..100 %
    """

    def __init__(self, pin_num, num_leds=1):

        self.num_leds = num_leds

        self._brightness = 100
        self._color = (0, 0, 0)

        self.strip = neopixel.NeoPixel(Pin(pin_num, Pin.OUT), num_leds)

        self._update()

    def _update(self):
        """
        Apply current color and brightness.
        """

        r, g, b = self._color

        scale = self._brightness / 100.0

        r = int(r * scale)
        g = int(g * scale)
        b = int(b * scale)

        for i in range(self.num_leds):
            self.strip[i] = (r, g, b)

        self.strip.write()

    def set_brightness(self, brightness):
        """
        Set strip brightness.

        Args: brightness (0..100)
        """

        self._brightness = max(0, min(100, int(brightness)))

        self._update()

    def get_brightness(self):
        return self._brightness

    def set_color(self, rgb):
        """
        Set strip color.

        Args: rgb = (r, g, b)  values 0..255
        """

        r, g, b = rgb

        self._color = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b))),
        )

        self._update()

    def get_color(self):
        return self._color

    def off(self):
        self.set_color((0, 0, 0))