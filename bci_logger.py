#!/usr/bin/env python3
# Copyright 2019-2020 Brad Martin.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Standalone utility to log OpenBCI data to disk."""

# Some of this code is based on or inspired by the wifi module in pyOpenBCI.

import argparse
import math
import requests
import select
import socket
import struct
import time

from bci_data import BciData


def get_local_ip(remote_ip):
    sock = socket.socket(type=socket.SOCK_DGRAM)
    sock.connect((remote_ip, 0))
    local_ip = sock.getsockname()[0]
    sock.close()
    return local_ip


class OpenBCIWifi:
    def __init__(self, ip):
        self._ip = ip
        self._session = requests.Session()

        self._check_board()

    def send_command(self, cmd):
        self._do_post('command', json={'command': cmd})

    def start_stream(self, ip, port, latency_us):
        self._do_post('udp', json={
            'ip': ip,
            'port': port,
            'output': 'raw',
            'latency': latency_us,
            'burst': False})
        self._do_get('stream/start')

    def stop_stream(self):
        self._do_get('stream/stop')

    def _check_board(self):
        board = self._do_get('board', response_is_json=True)
        assert board['board_connected']
        # TODO(bmartin) Support other variants
        assert board['board_type'] == 'daisy'
        assert board['num_channels'] == 16

    def _do_get(self, what, **kwargs):
        return self._do_request('get', what, **kwargs)

    def _do_post(self, what, **kwargs):
        return self._do_request('post', what, **kwargs)

    def _do_request(self, method, what, response_is_json=False, **kwargs):
        url = 'http://%s/%s' % (self._ip, what)
        result = self._session.request(method, url, timeout=5, **kwargs)
        if result.status_code != 200:
            raise RuntimeError('Error with %s request to %s: %d (%r)' %
                               (method, what, result.status_code, result.text))
        if response_is_json:
            return result.json()
        return result.text


class Logger:
    _SPINNER = '|/-\\'

    def __init__(self, filename):
        self._file = open(filename, 'xb')
        self._socket = socket.socket(type=socket.SOCK_DGRAM)
        self._socket.bind(('', 0))
        self._data = bytes()
        self._time_fmt = struct.Struct('>L')
        self._last_sample = None
        self._spinner_idx = 0
        self._spinner_time = None
        self._spinner_samples = 0

        self._socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)

    def get_port(self):
        return self._socket.getsockname()[1]

    def close(self):
        self._socket.close()
        self._file.close()

    def rlist(self):
        return [self._socket]

    def handle_event(self, obj, now):
        if obj != self._socket:
            print('Unrecognized wait object!')
            return

        self._data += self._socket.recv(4096)

        samples = 0
        while len(self._data) >= BciData.PAIR_LEN:
            if not BciData.validate(self._data):
                self._discard_junk()
                continue

            if self._last_sample is not None:
                expected_sample = (self._last_sample + 1) & 0xFF
                if self._data[1] not in [self._last_sample, expected_sample]:
                    lost = self._data[1] - expected_sample
                    if lost < 0:
                        lost += 256
                    samples += lost
                    f, _ = math.modf(now)
                    print('%s.%03d: Dropped %d samples (%d -> %d)' %
                          (time.strftime('%H:%M:%S', time.gmtime(now)),
                           int(1e3 * f), lost,
                           self._last_sample, self._data[1]))
            self._last_sample = self._data[1]

            self._file.write(self._time_fmt.pack(int(now * 1e3) & 0xFFFFFFFF) +
                             self._data[:BciData.PAIR_LEN])
            self._data = self._data[BciData.PAIR_LEN:]
            samples += 1

        self._spinner_samples += samples
        if samples and ((self._spinner_time is None) or
                        (now >= self._spinner_time + 0.2)):
            dt = (now - self._spinner_time) \
                 if self._spinner_time is not None else 1.
            print('Logging... %s (%.0f Hz)     \r' %
                  (self._spinner(), self._spinner_samples / dt),
                  end='')
            self._spinner_time = now
            self._spinner_samples = 0

    def _discard_junk(self):
        idx = self._data[1:].find(BciData.START_BYTE)
        if idx < 0:
            self._data = bytes()
        else:
            self._data = self._data[idx + 1:]

    def _spinner(self):
        i = self._spinner_idx
        self._spinner_idx = (self._spinner_idx + 1) % len(self._SPINNER)
        return self._SPINNER[i]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-i', '--ip', required=True,
                        help='IP address of wifi shield')
    parser.add_argument('-o', '--output', required=True,
                        help='File name of .bci log file to write')
    parser.add_argument('-l', '--latency-us', type=int, default=10000,
                        help='Latency in usec to request')
    args = parser.parse_args()

    iface = OpenBCIWifi(args.ip)
    iface.send_command('~3')  # 2 kHz; in practice faster rates don't work
    iface.send_command('/4')  # Marker mode
    iface.send_command('<')   # Enable timestamps
    for ch in '12345678QWERTYUI':
        # Power on channel at max gain, normal input type, include in BIAS,
        # connect to SRB2.
        iface.send_command('x%s060110X' % ch)

    logger = Logger(args.output)
    local_ip = get_local_ip(args.ip)
    port = logger.get_port()
    print('Listening on %s:%d' % (local_ip, port))
    iface.start_stream(local_ip, port, args.latency_us)
    try:
        while True:
            rlist, _, _ = select.select(logger.rlist(), [], [], 5.)
            if not rlist:
                raise RuntimeError('Data timeout!')
            now = time.time()
            for obj in rlist:
                logger.handle_event(obj, now)

    finally:
        iface.stop_stream()
        logger.close()


if __name__ == '__main__':
    main()
