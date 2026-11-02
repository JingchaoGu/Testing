#!/bin/sh
# Self-contained bootstrap: also works when piped to sh without a local checkout.
set -eu

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.10+ is required; install python3 first." >&2
    exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to download the installer." >&2
    exit 1
fi

bootstrap_dir=$(mktemp -d "${TMPDIR:-/tmp}/playbook-bootstrap-XXXXXX")
trap 'rm -f "$bootstrap_dir/install_plugin.py"; rmdir "$bootstrap_dir"' 0
trap 'exit 130' INT
trap 'exit 143' TERM

curl --fail --silent --show-error --location \
    'https://raw.githubusercontent.com/JingchaoGu/Testing/main/scripts/install_plugin.py' \
    --output "$bootstrap_dir/install_plugin.py"
python3 "$bootstrap_dir/install_plugin.py"
