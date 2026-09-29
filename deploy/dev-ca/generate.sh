#!/usr/bin/env bash
# Generates a THROWAWAY development CA for ULPF's mTLS-protected syslog
# collector path (ULPF-master-prompt.md Part D2). Not for production use --
# see docs/PKI.md for what a real deployment needs instead (an internal CA
# or a public one, a documented key ceremony, HSM-backed root key storage).
#
# Every file this script writes is gitignored (deploy/dev-ca/*.key/*.crt/*.srl)
# and regenerated fresh by running this script again -- nobody should be
# trusting a specific run of this dev CA across machines or over time.
#
# Usage: bash deploy/dev-ca/generate.sh [device-name ...]
#   Always creates: ca.key, ca.crt, server.key, server.crt (CN=localhost, for
#   the syslog listener / nginx TLS termination)
#   Plus one client cert per device name given (default: device1 device2)

set -euo pipefail
cd "$(dirname "$0")"

# Git Bash on Windows (MSYS) rewrites a leading "/X=..." in -subj as if it
# were a filesystem path -- disable that path-conversion for this script.
export MSYS_NO_PATHCONV=1

DEVICE_NAMES=("${@:-device1 device2}")
if [ "$#" -gt 0 ]; then
  DEVICE_NAMES=("$@")
else
  DEVICE_NAMES=(device1 device2)
fi

DAYS=825  # ~2.25 years -- CA/Browser Forum's own max validity guidance, a
          # reasonable, well-known default for a cert nobody will manually
          # renew; production certs should be shorter-lived with real rotation.

echo "== Generating throwaway dev CA (not for production -- see docs/PKI.md) =="

# 1. Root CA (self-signed)
openssl genrsa -out ca.key 4096 2>/dev/null
openssl req -x509 -new -nodes -key ca.key -sha256 -days $DAYS \
  -subj "/O=ULPF Dev (throwaway)/CN=ULPF Dev CA" \
  -out ca.crt

# 2. Server cert (nginx TLS termination / syslog listener), signed by the CA
openssl genrsa -out server.key 2048 2>/dev/null
openssl req -new -key server.key -subj "/O=ULPF Dev (throwaway)/CN=localhost" -out server.csr
cat > server.ext <<EOF
subjectAltName = DNS:localhost,DNS:ulp-backend,DNS:ulp-syslog-listener,IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days $DAYS -sha256 -extfile server.ext
rm -f server.csr server.ext

# 3. One client cert per device -- this is the actual per-device identity
# D2 asks for: a device without one of these cannot complete a handshake
# against a listener configured to require+verify a client cert.
for name in "${DEVICE_NAMES[@]}"; do
  openssl genrsa -out "device-${name}.key" 2048 2>/dev/null
  openssl req -new -key "device-${name}.key" -subj "/O=ULPF Dev (throwaway)/CN=${name}" -out "device-${name}.csr"
  cat > "device-${name}.ext" <<EOF
extendedKeyUsage = clientAuth
EOF
  openssl x509 -req -in "device-${name}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "device-${name}.crt" -days $DAYS -sha256 -extfile "device-${name}.ext"
  rm -f "device-${name}.csr" "device-${name}.ext"
  echo "  issued device cert: device-${name}.crt / device-${name}.key (CN=${name})"
done

chmod 600 ca.key server.key device-*.key 2>/dev/null || true

echo "== Done. ca.crt / server.{crt,key} / device-*.{crt,key} written to deploy/dev-ca/ =="
