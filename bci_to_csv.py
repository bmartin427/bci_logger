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

import argparse

import numpy

from bci_data import BciLogData


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True,
                        help='.bci log file to read')
    parser.add_argument('-o', '--output', required=True,
                        help='.csv file to write')
    args = parser.parse_args()

    with open(args.input, 'rb') as f:
        d = f.read()
    np_d = BciLogData.to_numpy(d)
    numpy.savetxt(args.output, np_d, delimiter=',',
                  fmt=(['%.6f'] + ['%d'] * (np_d.shape[1] - 1)))


if __name__ == '__main__':
    main()
