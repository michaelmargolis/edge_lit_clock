# Edge Lit Clock

MicroPython firmware for an ESP32-S3 edge-lit clock.

This project uses a Seeed XIAO ESP32S3, two chained STP16CP05 LED drivers, an ambient light sensor, Wi-Fi/NTP time synchronisation, and a simple TCP debug interface.

The current application entry point is `led_digit_driver_test.py`.

## Features

- Drives 32 outputs using two daisy-chained STP16CP05 LED drivers.
- Displays four clock digits using edge-lit acrylic digits.
- Keeps the RTC in UTC and displays local time using a UTC offset and optional UK/EU DST correction.
- Synchronises time using NTP.
- Automatically adjusts display brightness from ambient light.
- Scales brightness using a potentiometer.
- Supports either a WS2812/SK6812 status pixel or a discrete indicator LED.
- Provides a TCP line-based debug interface.
- Uses a small cooperative scheduler based on `uheapq`.
- Provides modular status and error reports.
- Includes a digit cycle test command for checking LED output mapping.

## Hardware Overview

Main hardware:

- Seeed XIAO ESP32S3
- 2 x STP16CP05 LED driver ICs
- VEML7700 ambient light sensor
- Potentiometer on ADC input
- Optional WS2812/SK6812 status pixel or discrete indicator LED

Current pin assignments used by `led_digit_driver_test.py`:

```python
POT_PIN = 1
INDICATOR_PIN = 4

sck_pin = 7
mosi_pin = 9
le_pin = 44
stp_oe_pin = 43
```

The first STP16CP05 receives SPI data from the XIAO MOSI pin. The SDO of the first driver feeds the SDI of the second driver. Both drivers share clock, latch enable, and output enable signals.

## File Overview

| File | Purpose |
| --- | --- |
| `led_digit_driver_test.py` | Current main application and test harness |
| `led_digits_driver.py` | STP16CP05 LED driver and indicator control |
| `encode_time.py` | Maps time strings to LED output indices |
| `ambient_light_sensor.py` | Reads and smooths VEML7700 ambient light values |
| `clock_network.py` | Wi-Fi connection and TCP line server |
| `time_utils.py` | NTP sync, UTC RTC handling, local time formatting, UK/EU DST |
| `simple_scheduler.py` | Small cooperative scheduler |
| `system_status.py` | Assembles status and error reports from registered modules |
| `pixel.py` | Minimal WS2812/SK6812 helper class |
| `boot.py` | Boot/startup file |
| `main_.py` | Older or alternate main file retained in the repo |

## Time Encoding

The clock display is controlled by LED output indices.

The current mapping constants are:

```python
MINUTES_UNITS = 0
MINUTES_TENS  = 10
HOURS_UNITS   = 20
HOURS_TENS    = 29
```

Examples:

```python
encode_time("20:00")  # (31, 20, 10, 0)
encode_time("10:00")  # (30, 20, 10, 0)
encode_time("0:00")   # (20, 10, 0)
```

The tens-of-hours position only supports digits 1 and 2.

## Brightness Control

Brightness is controlled by two inputs:

1. Ambient light sensor output, scaled to 0..100%.
2. Potentiometer value, used as a multiplier.

The application updates brightness periodically:

```python
brightness = ambient_sensor.update() * pot_scale
driver.set_brightness(brightness)
```

The STP16CP05 `!OE` signal is PWM controlled. If a status pixel is used, its brightness follows the display brightness.

## Status Indicator

The driver supports these status strings:

| Status | Meaning |
| --- | --- |
| `not connected` | Wi-Fi is not connected |
| `not synced` | Wi-Fi is connected but time is not synchronised or is stale |
| `synced` | Normal operation |
| `scheduler fatal` | Repeated scheduler task exceptions |

With a WS2812/SK6812 indicator, the status is shown as colour. With a discrete LED, colour is ignored.

## TCP Debug Interface

The firmware starts a TCP line server on port `2323`.

After boot, the program prints a connection hint similar to:

```text
Connect using:
  nc <ip-address> 2323
```

Example connection:

```bash
nc 192.168.1.160 2323
```

Commands are newline terminated.

### Commands

| Command | Action |
| --- | --- |
| `status` | Show status report |
| `error` | Show error report |
| `errors` | Show error report |
| `help` | Show command list |
| `lux` | Toggle periodic lux reporting |
| `lux on` | Enable periodic lux reporting |
| `lux off` | Disable periodic lux reporting |
| `cycle` | Run one digit cycle test |
| `HH:MM` | Display a test time, for example `12:31` |

## Digit Cycle Test

Sending:

```text
cycle
```

runs a one-shot test pattern that cycles through digit values.

For each digit value, the test lights equivalent outputs across the available digit groups:

- minutes units
- minutes tens, for 0..5
- hours units
- hours tens, only for 1 and 2

The test is blocking and intended for quick LED/display verification. After the cycle completes, the clock display resumes.

## Scheduler

The project uses `SimpleScheduler`, a small cooperative scheduler based on `uheapq`.

The main test harness schedules tasks for:

- TCP network polling
- Wi-Fi retry
- brightness update
- clock display update
- status update
- optional lux reporting
- fatal indicator flashing

The scheduler tracks both total and consecutive task exceptions. Repeated task exceptions set a fatal state. During current debug builds, this flashes the indicator red rather than rebooting.

## Status and Error Reporting

Modules self-register status and error report callbacks with `SystemStatus`.

`SystemStatus` only assembles reports. Each module owns its own state, failure counters, and last-error information.

Timestamps are emitted by modules using an `@ts:` marker and formatted centrally by `SystemStatus`.

## Timekeeping

`TimeUtils` keeps the RTC in UTC.

Displayed time is calculated from:

```text
UTC + UTC_OFFSET_HOURS + DST offset
```

Current defaults in the test harness:

```python
UTC_OFFSET_HOURS = 0
DST_REGION = "UK"
```

UK/EU DST rules are supported.

## Wi-Fi Credentials

Wi-Fi credentials are expected in `secrets.py`:

```python
SSID = "your_wifi_name"
PASSWORD = "your_wifi_password"
```

Do not commit real Wi-Fi credentials to the repository.

## Running

Copy the project files to the MicroPython filesystem on the XIAO ESP32S3.

For current testing, run:

```python
led_digit_driver_test.py
```

For final use, this file may be renamed or replaced by `main.py`.

## Development Notes

The code favours clarity and maintainability over abstraction.

Current design choices:

- No full `uasyncio` dependency.
- Simple cooperative scheduler.
- RAM/status based diagnostics.
- Flash logging avoided except for future fatal-error capture.
- TCP debug interface used for testing and setup.
- Module-owned status and error counters.

## Suggested Test Checklist

Before final installation:

1. Boot the clock and verify the display lights.
2. Confirm Wi-Fi connects and TCP accepts commands.
3. Send `status`, `error`, and `help`.
4. Send test times such as `0:00`, `10:00`, `12:31`, and `20:00`.
5. Send `cycle` and verify digit outputs.
6. Cover and illuminate the ambient sensor and verify brightness changes smoothly.
7. Disconnect the ambient sensor and confirm error reporting.
8. Disable and re-enable Wi-Fi and confirm reconnect behaviour.
9. Test NTP failure and recovery.
10. Run an extended soak test.

## License

This repository includes an MIT license.
