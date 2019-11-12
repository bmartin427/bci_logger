#!/usr/bin/env python3
# Copyright 2019 Brad Martin.  All rights reserved.

# Some of this code is based on or inspired by the wifi module in pyOpenBCI.
# TODO(bmartin) Assess license implications of this.

import argparse
import math
import requests
import select
import socket
import struct
import time


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
        self._do_post('tcp', json={
            'ip': ip,
            'port': port,
            'output': 'raw',
            'latency': latency_us})
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
    _START_BYTE = 0xA0
    _STOP_BYTES = [0xC5, 0xC6]
    _PKT_LEN = 33
    _PAIR_LEN = 2 * _PKT_LEN

    def __init__(self, filename):
        self._file = open(filename, 'wb')
        self._socket = socket.socket()
        self._socket.bind(('', 0))
        self._socket.listen()
        self._conn = None
        self._data = bytes()
        self._time_fmt = struct.Struct('>d')
        self._last_sample = None
        self._spinner_idx = 0
        self._spinner_time = None

    def get_port(self):
        return self._socket.getsockname()[1]

    def close(self):
        if self._conn is not None:
            self._conn.close()
        self._socket.close()
        self._file.close()

    def rlist(self):
        if self._conn is not None:
            return [self._conn]
        return [self._socket]

    def handle_event(self, obj, now):
        if obj == self._socket:
            self._conn, addr = self._socket.accept()
            print('Got stream connection from %s:%d' % addr)
            self._conn.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            return
        if (self._conn is None) or (obj != self._conn):
            print('Unrecognized wait object!')
            return

        self._data += self._conn.recv(4096)

        any_data = False
        while len(self._data) >= self._PAIR_LEN:
            if ((self._data[0] != self._START_BYTE) or
                (self._data[self._PKT_LEN] != self._START_BYTE)):
                print('Invalid start bytes (0x%02X, 0x%02X)' %
                      (self._data[0], self._data[self._PKT_LEN]))
                self._discard_junk()
                continue
            if ((self._data[self._PKT_LEN - 1] not in self._STOP_BYTES) or
                (self._data[self._PAIR_LEN - 1] not in self._STOP_BYTES)):
                print('Invalid stop bytes (0x%02X, 0x%02X)' %
                      (self._data[self._PKT_LEN - 1],
                       self._data[self._PAIR_LEN - 1]))
                self._discard_junk()
                continue
            if self._data[1] != self._data[self._PKT_LEN + 1]:
                print('Sample number mismatch! (%d != %d)' %
                      (self._data[1], self._data[self._PKT_LEN + 1]))
                self._discard_junk()
                continue

            if self._last_sample is not None:
                expected_sample = (self._last_sample + 1) & 0xFF
                if self._data[1] not in [self._last_sample, expected_sample]:
                    lost = self._data[1] - expected_sample
                    if lost < 0:
                        lost += 256
                    print('Dropped %d samples' % lost)
            self._last_sample = self._data[1]

            self._file.write(self._time_fmt.pack(now) + self._data)
            self._data = self._data[self._PAIR_LEN:]
            any_data = True

        if any_data and ((self._spinner_time is None) or
                         (now >= self._spinner_time + 0.2)):
            print('Logging... %s\r' % self._spinner(), end='')
            self._spinner_time = now

    def _discard_junk(self):
        idx = self._data[1:].find(self._START_BYTE)
        if idx < 0:
            self._data = bytes()
        else:
            self._data = self._data[idx + 1:]

    def _spinner(self):
        i = self._spinner_idx
        self._spinner_idx = (self._spinner_idx + 1) % len(self._SPINNER)
        return self._SPINNER[i]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--ip', required=True,
                        help='IP address of wifi shield')
    parser.add_argument('-o', '--output', required=True,
                        help='File name of .bci log file to write')
    parser.add_argument('-l', '--latency-us', type=int, default=10000,
                        help='Latency in usec to request')
    args = parser.parse_args()

    iface = OpenBCIWifi(args.ip)
    iface.send_command('~0')
    iface.send_command('/4')
    iface.send_command('<')

    logger = Logger(args.output)
    local_ip = get_local_ip(args.ip)
    port = logger.get_port()
    print('Listening on %s:%d' % (local_ip, port))
    iface.start_stream(local_ip, port, args.latency_us)
    try:
        f, last_sec = math.modf(time.time())
        last_sec = int(last_sec)
        while True:
            rlist, _, _ = select.select(logger.rlist(), [], [], 1. - f)
            now = time.time()
            f, sec = math.modf(now)
            sec = int(sec)
            if sec != last_sec:
                #iface.send_command('`' + chr(sec & 0xFF))
                last_sec = sec
            for obj in rlist:
                logger.handle_event(obj, now)

    finally:
        iface.stop_stream()
        logger.close()


if __name__ == '__main__':
    main()
