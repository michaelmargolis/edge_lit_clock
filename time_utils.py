# time_utils.py

import ntptime
import time


class TimeUtils:
    SYNC_INTERVAL_S = 3600
    STALE_SYNC_AGE_S = 6 * 3600
    STALE_RETRY_INTERVAL_S = 300
    INITIAL_SYNC_RETRY_INTERVAL_S = 30
    LOCAL_NTP_HOST = "192.168.50.1" 
    REMOTE_NTP_HOSE = "pool.ntp.org"
    NTP_HOST = LOCAL_NTP_HOST

    def __init__(self, register_reporter=None):
        self.next_sync_time = None
        self.last_successful_sync_time = None
        self.sync_stale = True
        self.initial_sync_done = False
        self.dst_region = None
        self.dst_active = False

        self.failures = 0
        self.last_error = ""
        self.last_error_time = None

        if register_reporter is not None:
            register_reporter("Time", self.status_lines, self.error_lines)

    def _record_error(self, message):
        print(message)
        self.failures += 1
        self.last_error = message
        self.last_error_time = int(time.time())

    def sync_time(self):
        try:
            ntptime.host = self.NTP_HOST
            ntptime.settime()

            now = time.time()
            self.last_successful_sync_time = now
            self.sync_stale = False
            self.initial_sync_done = True
            return True

        except Exception as e:
            self._record_error("NTP sync failed: {}".format(e))
            return False

    def resync_time(self):
        try:
            now = time.time()

            if not self.initial_sync_done:
                if self.next_sync_time is None or now >= self.next_sync_time:
                    if self.sync_time():
                        now = time.time()
                        self.next_sync_time = now + self.SYNC_INTERVAL_S
                    else:
                        now = time.time()
                        self.next_sync_time = (
                            now + self.INITIAL_SYNC_RETRY_INTERVAL_S
                        )
                return

            if self.last_successful_sync_time is not None:
                age = now - self.last_successful_sync_time
                self.sync_stale = age > self.STALE_SYNC_AGE_S

            if now >= self.next_sync_time:
                self.sync_time()
                now = time.time()
                if self.sync_stale:
                    self.next_sync_time = now + self.STALE_RETRY_INTERVAL_S
                else:
                    self.next_sync_time = now + self.SYNC_INTERVAL_S

        except Exception as e:
            self._record_error("Time resync failed: {}".format(e))
            self.sync_stale = True

    def has_valid_time(self):
        return self.initial_sync_done

    def is_time_stale(self):
        return (not self.initial_sync_done) or self.sync_stale

    def seconds_since_last_sync(self):
        if self.last_successful_sync_time is None:
            return None
        return time.time() - self.last_successful_sync_time

    def seconds_until_next_sync(self):
        if self.next_sync_time is None:
            return None
        return max(0, self.next_sync_time - time.time())

    def get_time_string(self, utc_offset_hours=0, dst_region=None, is_24hr=True):
        try:
            utc_ts = time.time()
            dst_offset_hours = self.get_dst_offset_hours(utc_ts, dst_region)
            self.dst_region = dst_region
            self.dst_active = dst_offset_hours != 0

            display_ts = utc_ts + int((utc_offset_hours + dst_offset_hours) * 3600)
            t = time.localtime(display_ts)
            hour = t[3]
            minute = t[4]
            second = t[5]

            if not is_24hr:
                if hour == 0:
                    hour = 12
                elif hour > 12:
                    hour -= 12

            return "{:02d}:{:02d}.{:02d}".format(hour, minute, second)

        except Exception as e:
            self._record_error("Time string failed: {}".format(e))
            return "00:00.00"

    def _last_sunday_day(self, year, month):
        if month == 12:
            next_month_year = year + 1
            next_month = 1
        else:
            next_month_year = year
            next_month = month + 1

        ts = time.mktime((next_month_year, next_month, 1, 0, 0, 0, 0, 0))
        ts -= 24 * 3600

        while time.localtime(ts)[6] != 6:
            ts -= 24 * 3600

        return time.localtime(ts)[2]

    def _uk_eu_dst_bounds(self, year):
        march_day = self._last_sunday_day(year, 3)
        oct_day = self._last_sunday_day(year, 10)
        start = time.mktime((year, 3, march_day, 1, 0, 0, 0, 0))
        end = time.mktime((year, 10, oct_day, 1, 0, 0, 0, 0))
        return start, end

    def is_uk_eu_dst(self, utc_ts=None):
        if utc_ts is None:
            utc_ts = time.time()
        year = time.gmtime(utc_ts)[0]
        start, end = self._uk_eu_dst_bounds(year)
        return start <= utc_ts < end

    def get_dst_offset_hours(self, utc_ts=None, dst_region=None):
        if dst_region is None:
            return 0
        if dst_region not in ("UK", "EU"):
            raise ValueError("Unsupported DST region: {}".format(dst_region))
        if self.is_uk_eu_dst(utc_ts):
            return 1
        return 0

    def _fmt_age(self, value):
        if value is None:
            return "None"
        return "{}s".format(int(value))

    def status_lines(self):
        return [
            "  Initial sync done: {}".format(self.initial_sync_done),
            "  Synced: {}".format(self.last_successful_sync_time is not None),
            "  Stale: {}".format(self.is_time_stale()),
            "  Last sync age: {}".format(
                self._fmt_age(self.seconds_since_last_sync())
            ),
            "  Next sync in: {}".format(
                self._fmt_age(self.seconds_until_next_sync())
            ),
            "  DST active: {}".format(self.dst_active),
            "  DST region: {}".format(self.dst_region),
        ]

    def error_lines(self):
        return [
            "  Failures: {}".format(self.failures),
            "  Last: {}".format(self.last_error),
            "  Last time: @ts:{}".format(self.last_error_time),
        ]
