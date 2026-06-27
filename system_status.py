# system_status.py

import gc
import time


class SystemStatus:
    def __init__(self):
        self.reporters = []
        self.start_time_s = time.time()

    def register_reporter(self, name, status_callback, error_callback=None):
        self.reporters.append((name, status_callback, error_callback))

    def uptime_s(self):
        return int(time.time() - self.start_time_s)

    def free_mem(self):
        return gc.mem_free()

    def _format_timestamp(self, timestamp):
        if timestamp is None:
            return ""

        try:
            t = time.localtime(int(timestamp))
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                t[0], t[1], t[2],
                t[3], t[4], t[5],
            )
        except Exception:
            return str(timestamp)

    def _format_line(self, line):
        marker = "@ts:"

        if marker not in line:
            return line

        prefix, value = line.split(marker, 1)

        try:
            return prefix + self._format_timestamp(int(value))
        except Exception:
            return prefix + value

    def _format_lines(self, lines):
        return [self._format_line(line) for line in lines]

    def _section(self, lines, title):
        lines.append("")
        lines.append(title)

    def as_text(self):
        lines = []

        lines.append("System:")
        lines.append(f"  Uptime: {self.uptime_s()}")
        lines.append(f"  Free mem: {self.free_mem()}")

        for name, status_callback, error_callback in self.reporters:
            self._section(lines, name + ":")
            try:
                lines.extend(self._format_lines(status_callback()))
            except Exception as e:
                lines.append(f"  status report failed: {e}")

        return "\r\n".join(lines)

    def errors_as_text(self):
        lines = []
        have_errors = False

        for name, status_callback, error_callback in self.reporters:
            if error_callback is None:
                continue

            try:
                error_lines = error_callback()
            except Exception as e:
                error_lines = ["  error report failed: {}".format(e)]

            if error_lines:
                have_errors = True
                self._section(lines, name + ":")
                lines.extend(self._format_lines(error_lines))

        if not have_errors:
            lines.append("No reported faults")

        return "\r\n".join(lines)
