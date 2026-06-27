# simple_scheduler.py

import time

try:
    import uheapq as heapq
except ImportError:
    import heapq


class SimpleScheduler:
    def __init__(self, max_exceptions=5, on_fatal=None, register_reporter=None):
        self._heap = []
        self._seq = 0

        self.max_exceptions = max_exceptions
        self.total_exceptions = 0
        self.consecutive_exceptions = 0
        self.fatal_active = False
        self.on_fatal = on_fatal

        self.last_error = ""
        self.last_error_time = None

        if register_reporter is not None:
            register_reporter("Scheduler", self.status_lines, self.error_lines)

    def add(self, run_at_ms, callback):
        self._seq += 1
        heapq.heappush(self._heap, (run_at_ms, self._seq, callback))

    def add_periodic(self, interval_ms, callback):
        def wrapper():
            try:
                callback()
                self.consecutive_exceptions = 0
            except Exception as e:
                self._record_exception(callback, e)
            finally:
                self.add(time.ticks_add(time.ticks_ms(), interval_ms), wrapper)

        self.add(time.ticks_add(time.ticks_ms(), interval_ms), wrapper)

    def read(self):
        if not self._heap:
            return None
        run_at_ms, seq, callback = self._heap[0]
        return run_at_ms, callback

    def pop(self):
        if not self._heap:
            return None
        run_at_ms, seq, callback = heapq.heappop(self._heap)
        return run_at_ms, callback

    def run_due(self):
        now_ms = time.ticks_ms()

        while self._heap:
            run_at_ms, callback = self.read()
            if time.ticks_diff(now_ms, run_at_ms) < 0:
                break

            self.pop()
            self._run_callback(callback)

    def _run_callback(self, callback):
        try:
            callback()
        except Exception as e:
            self._record_exception(callback, e)

    def _record_exception(self, callback, error):
        self.total_exceptions += 1
        self.consecutive_exceptions += 1

        name = getattr(callback, "__name__", "callback")
        self.last_error = "{} failed: {}".format(name, error)
        self.last_error_time = int(time.time())

        print(
            "Scheduler exception {} consecutive, {} total: {}".format(
                self.consecutive_exceptions,
                self.total_exceptions,
                self.last_error,
            )
        )

        if self.consecutive_exceptions >= self.max_exceptions:
            self.fatal_active = True
            if self.on_fatal is not None:
                try:
                    self.on_fatal()
                except Exception as fatal_e:
                    print("Scheduler fatal callback failed:", fatal_e)

    def is_fatal(self):
        return self.fatal_active

    def _format_time(self, timestamp):
        if timestamp is None:
            return ""

        try:
            t = time.localtime(timestamp)
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                t[0], t[1], t[2],
                t[3], t[4], t[5],
            )
        except Exception:
            return str(timestamp)

    def status_lines(self):
        return [
            "  Queued tasks: {}".format(len(self._heap)),
            "  Fatal active: {}".format(self.fatal_active),
            "  Consecutive exceptions: {}".format(self.consecutive_exceptions),
            "  Max consecutive exceptions: {}".format(self.max_exceptions),
        ]

    def error_lines(self):
        return [
            "  Total exceptions: {}".format(self.total_exceptions),
            "  Consecutive exceptions: {}".format(self.consecutive_exceptions),
            "  Last: {}".format(self.last_error),
            "  Last time: @ts:{}".format(self.last_error_time),
        ]
