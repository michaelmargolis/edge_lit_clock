from time import sleep_ms
from machine import Pin, ADC

from simple_scheduler import SimpleScheduler
from led_digits_driver import LedDigitsDriver
from encode_time import encode_time
from ambient_light_sensor import AmbientLightSensor
from clock_network import ClockNetwork
from time_utils import TimeUtils
from system_status import SystemStatus
from encode_time import MINUTES_UNITS, MINUTES_TENS, HOURS_UNITS, HOURS_TENS


POT_PIN = 1
INDICATOR_PIN = 4

NETWORK_MS = 20
WIFI_RETRY_MS = 30000
BRIGHTNESS_MS = 100
CLOCK_MS = 1000
STATUS_MS = 1000
FATAL_FLASH_MS = 500

UTC_OFFSET_HOURS = 0
DST_REGION = "UK"

status = SystemStatus()
show_lux = False
fatal_led_on = False
pot_percent = 0.0


def make_driver():
    return LedDigitsDriver(
        encoder=encode_time,
        sck_pin=7,
        mosi_pin=9,
        le_pin=44,
        stp_oe_pin=43,
        indicator_pin=INDICATOR_PIN,
        register_reporter=status.register_reporter,
    )


def update_indicator_status(driver, net, time_util, sched):
    if sched.is_fatal():
        return
    if not net.wlan.isconnected():
        driver.set_status("not connected")
    elif time_util.is_time_stale():
        driver.set_status("not synced")
    else:
        driver.set_status("synced")


def help_text():
    lines = [
        "Commands:",
        "  status       show status report",
        "  error        show error report",
        "  errors       show error report",
        "  help         show this help",
        "  lux          toggle lux messages",
        "  lux on       enable lux messages",
        "  lux off      disable lux messages",
        "  HH:MM        display a test time, e.g. 12:31",
    ]
    return "\r\n".join(lines)


def process_tcp_command(line, net, driver):
    global show_lux

    line = line.strip()
    if not line:
        return

    print("Application received:", line)

    if line == "status":
        net.send(status.as_text())
    elif line in ("error", "errors"):
        net.send(status.errors_as_text())
    elif line == "help":
        net.send(help_text())
    elif line == "lux":
        show_lux = not show_lux
        net.send("Lux display: {}".format("on" if show_lux else "off"))
    elif line == "lux on":
        show_lux = True
        net.send("Lux display: on")
    elif line == "lux off":
        show_lux = False
        net.send("Lux display: off")
    elif line == "cycle":
        net.send("Starting digit cycle")
        cycle_test(driver)
        net.send("Digit cycle complete")
        display_task()
    else:
        try:
            if driver.display_time(line):
                print("Displayed:", line)
                net.send("Displayed: {}".format(line))
            else:
                net.send("Display write failed")
        except ValueError as e:
            print("Invalid time:", e)
            net.send("Invalid time: {}".format(e))


def app_status_lines():
    return [
        "  Pot percent: {:.1f}".format(pot_percent),
        "  Lux messages: {}".format(show_lux),
    ]

def cycle_test(driver):
    CYCLE_ON_MS = 500
    CYCLE_OFF_MS = 150
    
    for digit in range(10):
        leds = []

        if digit in (1, 2):
            leds.append(HOURS_TENS + digit)
        leds.append(HOURS_UNITS + digit)
        leds.append(MINUTES_TENS + digit)
        leds.append(MINUTES_UNITS + digit)

        driver.write_leds(tuple(leds))
        sleep_ms(CYCLE_ON_MS)

        driver.clear()
        sleep_ms(CYCLE_OFF_MS)
        
def main():
    global fatal_led_on, pot_percent

    status.register_reporter("Application", app_status_lines)

    pot = ADC(Pin(POT_PIN))
    pot.atten(ADC.ATTN_11DB)

    driver = make_driver()
    net = ClockNetwork(port=2323, register_reporter=status.register_reporter)
    ambient_sensor = AmbientLightSensor(
        register_reporter=status.register_reporter
    )
    time_util = TimeUtils(register_reporter=status.register_reporter)

    sched = SimpleScheduler(
        max_exceptions=5,
        register_reporter=status.register_reporter,
    )

    driver.set_brightness(50)
    driver.set_status("not connected")
    driver.display_time("0:00")

    net.connect_wifi()
    if net.wlan.isconnected():
        driver.set_status("not synced")
        time_util.sync_time()
        net.start_server()

    update_indicator_status(driver, net, time_util, sched)

    print("Connect using:")
    print("  nc {} 2323".format(net.ip_address()))
    print("Then type lines such as:")
    print("  12:31")
    print("Or type 'status' for the status report")
    print("type 'error' for the error report")
    print("type 'help' for more help")

    def wifi_task():
        if not net.wlan.isconnected():
            net.ensure_wifi(timeout_s=5)

        if net.wlan.isconnected():
            if net.server_socket is None:
                net.start_server()

            if not time_util.has_valid_time():
                time_util.sync_time()

    def network_task():
        net.update()
        while net.has_line():
            process_tcp_command(net.get_line(), net, driver)

    def brightness_task():
        global pot_percent
        adc = pot.read_u16()
        pot_scale = adc / 65535
        pot_percent = pot_scale * 100
        brightness = ambient_sensor.update() * pot_scale
        driver.set_brightness(brightness)

    def clock_task():
        if not time_util.has_valid_time():
            if driver.displayed_time != "0:00":
                driver.display_time("0:00")
            return

        snapshot = time_util.get_time_string(
            utc_offset_hours=UTC_OFFSET_HOURS,
            dst_region=DST_REGION,
        ).split(".")

        display_time = snapshot[0]
        if display_time != driver.displayed_time:
            print("updating clock with:", display_time)
            driver.display_time(display_time)

    def status_task():
        update_indicator_status(driver, net, time_util, sched)

    def lux_task():
        if show_lux and net.is_connected():
            net.send(
                "Lux={:.1f} Current={:.1f}% Smoothed={:.1f}% "
                "Scaled={:.1f}%".format(
                    ambient_sensor.get_lux(),
                    ambient_sensor.get_current_percent(),
                    ambient_sensor.get_smoothed_percent(),
                    driver.brightness_percent,
                )
            )

    def fatal_flash_task():
        global fatal_led_on
        if not sched.is_fatal():
            return
        fatal_led_on = not fatal_led_on
        if fatal_led_on:
            driver.set_indicator_color((255, 0, 0))
            driver.indicator_status = "scheduler fatal"
        else:
            driver.indicator_off()

    sched.add_periodic(NETWORK_MS, network_task)
    sched.add_periodic(WIFI_RETRY_MS, wifi_task)
    sched.add_periodic(BRIGHTNESS_MS, brightness_task)
    sched.add_periodic(CLOCK_MS, clock_task)
    sched.add_periodic(STATUS_MS, status_task)
    sched.add_periodic(STATUS_MS, lux_task)
    sched.add_periodic(FATAL_FLASH_MS, fatal_flash_task)

    while True:
        sched.run_due()
        sleep_ms(10)


main()
