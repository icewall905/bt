#!/bin/bash
cd "$(dirname "$0")"
bash manage.sh "$@"
result=$?
read -r -p 'Press Enter to close this window.' _
exit "$result"
