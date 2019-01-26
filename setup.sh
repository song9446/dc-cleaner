#!/bin/sh

slaves=$(sed -nr "/^\[Slave\]/ { :l /^hosts[ ]*=/ { s/.*=[ ]*//; p; q;}; n; b l;}" ./config.ini)

for slave in $slaves; do
    ssh $slave -t sudo yum install -y python36
    ssh $slave -t pip-3.6 install --user aiohttp greenstalk tenacity 
    scp -r ../dc-cleaner $slave:./
done
