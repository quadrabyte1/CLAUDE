---
title: Script to create (1) a local certificate authority, (2) a host certificate
  signed by that authority for the hostname of your choice
uid: 20241203T2304
created: '2024-12-03'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes1
tags: []
aliases: []
source_url: https://gist.github.com/dobesv/13d4cb3cbd0fc4710fa55f89d1ef69be
---

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

|  |  |
|---:|----|
| 1 | \#!/usr/bin/env bash |
| 2 | \# |
| 3 | \# Usage: dev_signed_cert.sh HOSTNAME |
| 4 | \# |
| 5 | \# Creates a CA cert and then generates an SSL certificate signed by that CA for the |
| 6 | \# given hostname. |
| 7 | \# |
| 8 | \# After running this, add the generated dev_cert_ca.cert.pem to the trusted root |
| 9 | \# authorities in your browser / client system. |
| 10 | \# |
| 11 |  |
| 12 | set -x |
| 13 |  |
| 14 | DIR="\$( cd "\$( dirname "\${BASH_SOURCE\[0\]}" )" && pwd )" |
| 15 | NAME=\${1:-localhost} |
| 16 |  |
| 17 | CA_KEY=\$DIR/dev_cert_ca.key.pem |
| 18 |  |
| 19 | \[ -f \$CA_KEY \] \|\| openssl genrsa -des3 -out \$CA_KEY 2048 |
| 20 |  |
| 21 | CA_CERT=\$DIR/dev_cert_ca.cert.pem |
| 22 |  |
| 23 | \[ -f \$CA_CERT \] \|\| openssl req -x509 -new -nodes -key \$CA_KEY -sha256 -days 365 -out \$CA_CERT |
| 24 |  |
| 25 | HOST_KEY=\$DIR/\$NAME.key.pem |
| 26 |  |
| 27 | \[ -f \$HOST_KEY \] \|\| openssl genrsa -out \$HOST_KEY 2048 |
| 28 |  |
| 29 | HOST_CERT=\$DIR/\$NAME.cert.pem |
| 30 |  |
| 31 | if ! \[ -f \$HOST_CERT \] ; then |
| 32 | HOST_CSR=\$DIR/\$NAME.csr.pem |
| 33 | \[ -f \$HOST_CSR \] \|\| openssl req -new -key \$HOST_KEY -out \$HOST_CSR |
| 34 | HOST_EXT=\$DIR/\$NAME.ext |
| 35 | echo \>\$HOST_EXT |
| 36 | echo \>\>\$HOST_EXT authorityKeyIdentifier=keyid,issuer |
| 37 | echo \>\>\$HOST_EXT basicConstraints=CA:FALSE |
| 38 | echo \>\>\$HOST_EXT keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment |
| 39 | echo \>\>\$HOST_EXT subjectAltName = @alt_names |
| 40 | echo \>\>\$HOST_EXT |
| 41 | echo \>\>\$HOST_EXT \[alt_names\] |
| 42 |  |
| 43 | NAME_N=1 |
| 44 | for ALT_NAME in "\$@" ; do |
| 45 | echo \>\>\$HOST_EXT DNS.\$NAME_N = \$NAME |
| 46 | NAME_N=\$(( NAME_N + 1 )) |
| 47 | done |
| 48 |  |
| 49 | openssl x509 -req -in \$HOST_CSR -CA \$CA_CERT -CAkey \$CA_KEY -CAcreateserial |
| 50 | -out \$HOST_CERT -days 365 -sha256 -extfile \$HOST_EXT |
| 51 |  |
| 52 | rm \$HOST_EXT |
| 53 | fi |
| 54 |  |
| 55 |  |

\

## See also

- [[Software Development]]
