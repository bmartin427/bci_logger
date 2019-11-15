# Copyright 2019 Brad Martin.  All rights reserved.

import numpy


class BciData:
    """Group of data format-related constants and functions.

    This applies to the wire protocol.  The on-disk format precedes this
    format with a 32-bit system timestamp.
    """
    # TODO(bmartin) Could support non-Daisy, and other packet types.

    START_BYTE = 0xA0
    STOP_BYTES = [0xC5, 0xC6]
    PKT_LEN = 33
    PAIR_LEN = 2 * PKT_LEN

    @staticmethod
    def validate(data):
        """Returns True if the given data appears to be a valid data entry."""
        if len(data) < BciData.PAIR_LEN:
            return False

        if ((data[0] != BciData.START_BYTE) or
            (data[BciData.PKT_LEN] != BciData.START_BYTE)):
            print('Invalid start bytes (0x%02X, 0x%02X)' %
                  (data[0], data[BciData.PKT_LEN]))
            return False

        if ((data[BciData.PKT_LEN - 1] not in BciData.STOP_BYTES) or
            (data[BciData.PAIR_LEN - 1] not in BciData.STOP_BYTES)):
            print('Invalid stop bytes (0x%02X, 0x%02X)' %
                  (data[BciData.PKT_LEN - 1],
                   data[BciData.PAIR_LEN - 1]))
            return False

        if data[1] != data[BciData.PKT_LEN + 1]:
            print('Sample number mismatch! (%d != %d)' %
                  (data[1], data[BciData.PKT_LEN + 1]))
            return False

        return True


class BciLogData:
    """Constants and functions specific to a log file of BCI data."""
    TIMESTAMP_SIZE = 4
    RECORD_LEN = TIMESTAMP_SIZE + BciData.PAIR_LEN

    @staticmethod
    def to_numpy(data):
        dt = numpy.dtype([
            ('sys_timestamp_ms', '>u4'),
            ('packet', [
                ('start_byte', 'B'),
                ('sample_number', 'B'),
                ('channel_data', [
                    ('h8', 'b'),
                    ('l16', '>u2')
                ], (8,)),
                ('aux', 'B', (2,)),
                ('hw_timestamp_ms', '>u4'),
                ('stop_byte', 'B'),
            ], (2,))
        ])
        assert dt.itemsize == BciLogData.RECORD_LEN
        parsed = numpy.frombuffer(data, dtype=dt)

        # Every packet must start with a valid start byte.
        assert numpy.all(parsed['packet']['start_byte'] == BciData.START_BYTE)
        # Every packet must end with one of the valid stop bytes.
        assert numpy.all(
            numpy.any(
                numpy.stack(
                    [parsed['packet']['stop_byte'] == b
                     for b in BciData.STOP_BYTES],
                    axis=2),
                axis=2))
        # Every record must have the same sample number in both packets.
        assert numpy.all(parsed['packet'][:, 0]['sample_number'] ==
                         parsed['packet'][:, 1]['sample_number'])

        sys_ms = parsed['sys_timestamp_ms']
        hw_ms = parsed['packet'][:, 0]['hw_timestamp_ms']

        ch_in = parsed['packet']['channel_data']
        channel_data = (ch_in['h8'] * 65536 + ch_in['l16']).reshape(
            (ch_in.shape[0], ch_in.shape[1] * ch_in.shape[2]))

        return numpy.concatenate((numpy.expand_dims(sys_ms, axis=1),
                                  numpy.expand_dims(hw_ms, axis=1),
                                  channel_data), axis=1)
