#!/bin/sh

PY_DIR=/pycommax
PY_FILE="commax.py"
DEV_FILE="commax_devinfo.json"

# start server
echo "[Info] Start commax_mqtt2elfin_python.."

python -u $PY_DIR/$PY_FILE
