#!/bin/sh

CRED_FILE=$(realpath "${PWD}/${CREDENTIALS_FILE}")
[ "${CRED_FILE}" = "${PWD}" ] && CRED_FILE=$(realpath "${PWD}/data/credentials.json")

# Bootstrap credentials file is missing
[ -e "${CRED_FILE}" ] || python /app/auth.py

python /app/proxy.py