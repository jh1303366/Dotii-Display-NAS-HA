#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 docker/provision_mac.py
