#!/bin/sh

beanstalkd=$(sed -nr "/^\[Beanstalkd\]/ { :l /^host[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)
slaves=$(sed -nr "/^\[Slave\]/ { :l /^hosts[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)

for slave in $slaves; do
    ssh $slave -t "pkill -9 -f run.py"
done
ssh $beanstalkd -t "pkill -9 -f beanstalkd"

pkill -9 -f run.py
pkill -9 -f beanstalkd
