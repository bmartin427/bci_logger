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

import sys

import numpy as np
import matplotlib.pyplot as plt

from bci_data import BciLogData

AVG_LEN = 2000
COLORS = ['0.5', 'm', 'b', 'g', 'y', '#ff8000', 'r', '#804000']


def main():
    if len(sys.argv) != 2:
        print('Usage: %s <log.bci>' % sys.argv[0])
        sys.exit(1)
    with open(sys.argv[1], 'rb') as f:
        d = f.read()
    p = BciLogData.to_numpy(d)
    print('Loaded %r' % sys.argv[1])

    plt.figure()
    for i in range(1, p.shape[1]):
        print('Filtering channel %d' % i)
        hp = p[:, i] - np.convolve(
            p[:, i], np.ones(AVG_LEN) / AVG_LEN, mode='same')
        plt.plot(p[AVG_LEN // 2:-AVG_LEN // 2, 0],
                 hp[AVG_LEN // 2:-AVG_LEN // 2],
                 color=COLORS[(i - 1) % len(COLORS)],
                 linewidth=0.5)
    plt.xlabel('s')
    plt.show()


if __name__ == '__main__':
    main()
