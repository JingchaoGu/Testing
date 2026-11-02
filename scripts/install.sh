#!/bin/sh
set -eu

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.10+ is required; install python3 before running this script." >&2
    exit 1
fi

installer_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
exec python3 "$installer_dir/install_plugin.py"
