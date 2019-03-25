#!/bin/sh
#
# This script increases ring buffers of network interface to max.
# It's works with networkd-dispatcher and should be located in unmanaged.d and configured.d
#
# requirements: ethtool, awk;
#

# IFACE is environment variable witch is transfered by networkd-dispatcher into the called script.
iface=$IFACE
readlink /sys/class/net/$iface | grep -q virtual
if [ $? -eq 0 ] ; then
   exit 1
fi

max_rx=$(ethtool -g $iface | awk '/RX:/{print $2; exit}')
max_tx=$(ethtool -g $iface | awk '/TX:/{print $2; exit}')

ethtool -G $iface rx $max_rx tx $max_tx > /dev/null 2>&1

exit 0
