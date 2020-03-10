# bci_logger

This project is a standalone disk logger for OpenBCI EEG data.  It does not
depend on the OpenBCI GUI or Hub components; instead it talks directly to the
wifi board via REST and UDP.  Also included is a python module for working
with the on-disk format, a tool for plotting logged data, and a tool for
converting logged data to csv.

In its current form, it assumes a 16-channel Cyton+Daisy+Wifi configuration,
and attempts to sample at 2kHz.  In the future, these parameters could become
configurable.

The timestamp stored in the on-disk format is the lower 32 bits of the UTC
system epoch time in ms.  This timestamp rolls over every 49.7 days; if this
ambiguity is a problem, additional date/time info will have to be stored
externally.  In my use case, I find putting the date in the log filename is
sufficient.

## Dependencies

This utility depends on numpy, scipy, and matplotlib.  Under Ubuntu, these can
be installed with:

`sudo apt install python3-numpy python3-scipy python3-matplotlib`
