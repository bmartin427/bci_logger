#!/usr/bin/env python3
# Copyright 2019 Brad Martin.  All rights reserved.

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
    numpy.savetxt(args.output, BciLogData.to_numpy(d), delimiter=',', fmt='%d')


if __name__ == '__main__':
    main()
