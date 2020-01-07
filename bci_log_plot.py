#!/usr/bin/env python3
# Copyright 2019 Brad Martin.  All rights reserved.

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
        plt.plot(1e-3 * p[AVG_LEN // 2:-AVG_LEN // 2, 0],
                 hp[AVG_LEN // 2:-AVG_LEN // 2],
                 color=COLORS[(i - 1) % len(COLORS)],
                 linewidth=0.5)
    plt.xlabel('s')
    plt.show()


if __name__ == '__main__':
    main()
