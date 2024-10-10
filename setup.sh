#!/bin/bash
rw
cp -f ./main.py /opt/redpitaya/bin/
cp -f ./config.ini /opt/redpitaya/bin/

grep -q "/opt/redpitaya/bin/main.py" /opt/redpitaya/sbin/startup.sh

if [ $? -ne 0 ]; then
    echo "export PYTHONPATH=/opt/redpitaya/lib/python/:\$PYTHONPATH" >> /opt/redpitaya/sbin/startup.sh
    echo /opt/redpitaya/bin/main.py >> /opt/redpitaya/sbin/startup.sh
fi
