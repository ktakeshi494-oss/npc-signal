#!/usr/bin/env bash
# Encrypt or decrypt the SQLite state with AES-256-CBC (OpenSSL, PBKDF2).
# Key comes from STATE_KEY (environment). Never write the key to disk or logs.
set -euo pipefail
usage() { echo "usage: $0 encrypt <in.sqlite> <out.enc> | decrypt <in.enc> <out.sqlite>" >&2; exit 2; }
[[ $# -eq 3 ]] || usage
[[ -n "${STATE_KEY:-}" ]] || { echo "STATE_KEY is not set" >&2; exit 1; }
# Reject obviously weak keys (empty already caught). 16+ chars required.
[[ ${#STATE_KEY} -ge 16 ]] || { echo "STATE_KEY must be at least 16 characters" >&2; exit 1; }
cmd=$1; src=$2; dst=$3
[[ -f "$src" ]] || { echo "missing $src" >&2; exit 1; }
mkdir -p "$(dirname "$dst")"
case $cmd in
  encrypt)
    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in "$src" -out "$dst" -pass env:STATE_KEY
    ;;
  decrypt)
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$src" -out "$dst" -pass env:STATE_KEY
    ;;
  *) usage ;;
esac
