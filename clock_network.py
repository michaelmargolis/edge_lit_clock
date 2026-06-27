# clock_network.py

import network
import socket
import time

from secrets import SSID, PASSWORD


class ClockNetwork:
    def __init__(
        self,
        ssid=SSID,
        password=PASSWORD,
        port=2323,
        max_lines=20,
        register_reporter=None,
    ):
        self.ssid = ssid
        self.password = password
        self.port = port
        self.max_lines = max_lines

        self.wlan = network.WLAN(network.STA_IF)
        self.server_socket = None
        self.client_socket = None
        self.client_addr = None
        self.rx_buffer = b""
        self.lines = []

        self.wifi_failures = 0
        self.wifi_last_msg = ""
        self.wifi_last_msg_time = None
        self.socket_failures = 0
        self.socket_last_msg = ""
        self.socket_last_msg_time = None

        if register_reporter is not None:
            register_reporter("Network", self.status_lines, self.error_lines)

    def _record_error(self, source, message):
        print(message)
        now = int(time.time())

        if source == "wifi":
            self.wifi_failures += 1
            self.wifi_last_msg = message
            self.wifi_last_msg_time = now
        else:
            self.socket_failures += 1
            self.socket_last_msg = message
            self.socket_last_msg_time = now

    def connect_wifi(self, timeout_s=15):
        try:
            self.wlan.active(True)

            if not self.wlan.isconnected():
                print("Connecting to Wi-Fi...")
                self.wlan.connect(self.ssid, self.password)

                start = time.time()
                while not self.wlan.isconnected():
                    if time.time() - start > timeout_s:
                        raise RuntimeError("Wi-Fi connection timed out")
                    time.sleep(0.25)

            print("Wi-Fi connected")
            print("IP address:", self.ip_address())
            print("status   =", self.wlan.status())
            return True

        except Exception as e:
            self._record_error("wifi", "Wi-Fi connect failed: {}".format(e))
            return False

    def ensure_wifi(self, timeout_s=5):
        if self.wlan.isconnected():
            return True
        return self.connect_wifi(timeout_s=timeout_s)

    def ip_address(self):
        try:
            return self.wlan.ifconfig()[0]
        except Exception:
            return ""

    def start_server(self):
        try:
            addr = socket.getaddrinfo("0.0.0.0", self.port)[0][-1]
            self.server_socket = socket.socket()
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(addr)
            self.server_socket.listen(1)
            self.server_socket.setblocking(False)
            print("Line server listening on port", self.port)
            return True
        except Exception as e:
            self._record_error("socket", "Server start failed: {}".format(e))
            self.server_socket = None
            return False

    def update(self):
        if self.server_socket is None:
            return
        try:
            self._accept_client()
            self._read_client()
        except Exception as e:
            self._record_error("socket", "Network update failed: {}".format(e))
            self._close_client()

    def _accept_client(self):
        if self.client_socket is not None or self.server_socket is None:
            return

        try:
            client, addr = self.server_socket.accept()
        except OSError:
            return
        except Exception as e:
            self._record_error("socket", "Client accept failed: {}".format(e))
            return

        self.client_socket = client
        self.client_addr = addr
        self.client_socket.setblocking(False)
        self.rx_buffer = b""
        print("Client connected:", addr)

        if not self.send("Clock input server ready. Send time strings like 12:31"):
            self._close_client()

    def _read_client(self):
        if self.client_socket is None:
            return

        try:
            data = self.client_socket.recv(64)
        except OSError:
            return
        except Exception as e:
            self._record_error("socket", "Client read failed: {}".format(e))
            self._close_client()
            return

        if not data:
            self._close_client()
            return

        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        self.rx_buffer += data

        while b"\n" in self.rx_buffer:
            line, self.rx_buffer = self.rx_buffer.split(b"\n", 1)
            line = line.strip()

            if line:
                try:
                    text = line.decode()
                    self._add_line(text)
                except Exception as e:
                    self._record_error(
                        "socket", "Client decode failed: {}".format(e)
                    )

    def _add_line(self, line):
        self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)
        print("Received:", line)

    def get_line(self):
        if self.lines:
            return self.lines.pop(0)
        return None

    def has_line(self):
        return len(self.lines) > 0

    def send(self, text, newline=True):
        if self.client_socket is None:
            return False

        try:
            if newline:
                text += "\r\n"
            self.client_socket.send(text.encode())
            return True
        except Exception as e:
            self._record_error("socket", "Client send failed: {}".format(e))
            self._close_client()
            return False

    def is_connected(self):
        return self.client_socket is not None

    def _close_client(self):
        if self.client_socket is not None:
            print("Client disconnected")
            try:
                self.client_socket.close()
            except Exception:
                pass

        self.client_socket = None
        self.client_addr = None
        self.rx_buffer = b""

    def stop(self):
        self._close_client()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

    def status_lines(self):
        connected = self.wlan.isconnected()
        return [
            "  WiFi connected: {}".format(connected),
            "  IP: {}".format(self.ip_address() if connected else ""),
            "  TCP client: {}".format(self.client_socket is not None),
            "  Server active: {}".format(self.server_socket is not None),
        ]

    def error_lines(self):
        return [
            "  WiFi failures: {}".format(self.wifi_failures),
            "  WiFi last: {}".format(self.wifi_last_msg),
            "  WiFi last time: @ts:{}".format(self.wifi_last_msg_time),
            "  Socket failures: {}".format(self.socket_failures),
            "  Socket last: {}".format(self.socket_last_msg),
            "  Socket last time: @ts:{}".format(self.socket_last_msg_time),
        ]
