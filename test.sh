#!/bin/sh

beanstalkd=$(sed -nr "/^\[Beanstalkd\]/ { :l /^host[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)
slaves=$(sed -nr "/^\[Slave\]/ { :l /^hosts[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)

ssh $beanstalkd -t beanstalkd &
sleep 3

cd slave && python3 ./run.py &
cd master && python3 ./run.py &
