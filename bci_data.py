# Copyright 2019-2020 Brad Martin.  All rights reserved.

import numpy
import scipy.stats


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

        if (data[0] != BciData.START_BYTE) or \
           (data[BciData.PKT_LEN] != BciData.START_BYTE):
            print('Invalid start bytes (0x%02X, 0x%02X)' %
                  (data[0], data[BciData.PKT_LEN]))
            return False

        if (data[BciData.PKT_LEN - 1] not in BciData.STOP_BYTES) or \
           (data[BciData.PAIR_LEN - 1] not in BciData.STOP_BYTES):
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
    def to_numpy(data, separated=False):
        """Parses binary log data into numpy format.

        Given the binary contents of a log file, parses the file data, and
        returns an (N, 17) numpy array, where N is the number of records in
        the input file, the first column is the system timestamp in seconds
        corresponding to a sample, and the remaining 16 columns are the
        channel readings for that sample.

        If `separated` is True, then the result is instead a python list of
        such numpy arrays.  Any non-sequential samples (due to packet loss
        etc) will trigger a break into a new array.  If `separated` is False,
        then such losses will be hidden within the one result array, with the
        available data directly concatenated.

        """
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
        s_no = parsed['packet'][:, 0]['sample_number'].astype('int64')
        assert numpy.all(s_no == parsed['packet'][:, 1]['sample_number'])

        sys_ms = parsed['sys_timestamp_ms']
        hw_ms = parsed['packet'][:, 0]['hw_timestamp_ms']
        sys_elapsed_ms = sys_ms[-1] - sys_ms[0]
        hw_elapsed_ms = hw_ms[-1] - hw_ms[0]
        assert sys_elapsed_ms > 0  # TODO(bmartin) This could wrap
        assert hw_elapsed_ms > 0   # This shouldn't wrap
        assert hw_elapsed_ms > 0.8 * sys_elapsed_ms
        assert hw_elapsed_ms < 1.2 * sys_elapsed_ms

        # Sample number is only 8 bit.  Reconstruct an unwrapped sample index
        # to remove aliasing.
        #
        # This can still be wrong if we've dropped more than 256 samples.  It
        # is necessary to compare with the HW timestamp to determine this, but
        # we need to know at least an approximate sample rate before we can do
        # that, and we don't know the sample rate without an estimate of the
        # number of samples spanned.  For this reason we may have to iterate
        # until we find a solution that makes sense.
        s_step_raw = s_no[1:] - s_no[:-1]
        wraps = (s_step_raw <= 0).astype('int')
        while True:
            s_step = s_step_raw + 256 * wraps
            fixed_s_no = s_no[0] + numpy.cumsum(numpy.insert(s_step, 0, 0.))
            assert numpy.all(fixed_s_no[1:] > fixed_s_no[:-1])
            n_samples = fixed_s_no[-1] - fixed_s_no[0]
            assert parsed.shape[0] > 0.9 * n_samples
            assert parsed.shape[0] < 1.1 * n_samples

            samples_per_ms = n_samples / hw_elapsed_ms
            s_step_from_hw = samples_per_ms * (hw_ms[1:] - hw_ms[:-1])
            hw_gaps = (s_step_from_hw - s_step) > 100
            if not numpy.any(hw_gaps):
                break
            print('Fixing >256 gap')
            wraps += hw_gaps

        # hw_ms is truncated to integer ms, which will result in multiple
        # samples per time index at rates above 1kHz.  Try to reconstruct a
        # higher-precision hardware time index.
        #
        # This is tricky, because for some reason the sample rate does not
        # appear to be perfectly fixed, which can cause 10's of ms of drift
        # over a half-hour log if a fixed sample rate is assumed.
        rate_interval = int(round(10000 * samples_per_ms))
        if fixed_s_no.shape[0] > rate_interval:
            samples_per_ms = (
                (fixed_s_no[rate_interval:] - fixed_s_no[:-rate_interval]) /
                (hw_ms[rate_interval:] - hw_ms[:-rate_interval]))
            samples_per_ms = numpy.concatenate(
                (samples_per_ms[0] * numpy.ones(rate_interval // 2),
                 samples_per_ms,
                 samples_per_ms[-1] * numpy.ones((rate_interval + 1) // 2)))
            assert samples_per_ms.shape[0] == fixed_s_no.shape[0]
        else:
            samples_per_ms = samples_per_ms * numpy.ones(fixed_s_no.shape)
        fixed_hw_ms = numpy.insert(
            numpy.cumsum((fixed_s_no[1:] - fixed_s_no[:-1]) /
                         samples_per_ms[1:]),
            0, 0.)
        fixed_hw_ms += numpy.mean(hw_ms - fixed_hw_ms)
        d_hw = fixed_hw_ms - hw_ms
        assert numpy.all(numpy.abs(d_hw) < 5.)

        # sys_ms is even coarser, since samples have been grouped into packets
        # with variable delay.  Try to reconstruct an accurate system
        # timestamp for each sample, since system timestamps are what we will
        # use to correlate with label data.
        sys_hw_slope, _i, _, _, _ = scipy.stats.linregress(fixed_hw_ms, sys_ms)
        # NOTE: Disregard the fit intercept, since it will try to find the
        # average offset, but we know all samples have a positive latency, so
        # it's best to use an offset that minimizes the latency instead.
        fixed_sys_ms = sys_hw_slope * fixed_hw_ms
        sys_hw_intercept = numpy.min(sys_ms - fixed_sys_ms)
        fixed_sys_ms += sys_hw_intercept
        d_sys = fixed_sys_ms - sys_ms
        assert numpy.all(d_sys > -500.)
        assert numpy.all(d_sys <= 0.)

        ch_in = parsed['packet']['channel_data']
        channel_data = (ch_in['h8'] * 65536 + ch_in['l16']).reshape(
            (ch_in.shape[0], ch_in.shape[1] * ch_in.shape[2]))

        combined = numpy.concatenate(
            (numpy.expand_dims(fixed_sys_ms * 1e-3, axis=1),
             channel_data),
            axis=1)
        if not separated:
            return combined

        region_idxs = BciLogData._get_contiguous_regions(fixed_s_no)
        start_idx = 0
        result = []
        for idx in region_idxs:
            result.append(combined[start_idx:idx, :])
            start_idx = idx
        result.append(combined[start_idx:, :])
        return result

    @staticmethod
    def _get_contiguous_regions(fixed_sample_nos):
        """Finds regions of contiguous sample data in a log.

        Given an array of unwrapped sample numbers found in a log, returns an
        array representing the indexes into the input array where sample
        number discontinuities are found.
        """
        steps = fixed_sample_nos[1:] - fixed_sample_nos[:-1]
        return 1 + numpy.nonzero(steps != 1)[0]
