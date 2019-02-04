#!/bin/sh

beanstalkd=$(sed -nr "/^\[Beanstalkd\]/ { :l /^host[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)
slaves=$(sed -nr "/^\[Slave\]/ { :l /^hosts[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)

cd master/front && ./run.sh
cd .. && cd ..

nohup ~/beanstalkd/beanstalkd &
sleep 3

cd slave && nohup python3 ./run.py > slave.log 2>&1 &
cd master && nohup python3 ./run.py > master.log 2>&1 &
