#!/bin/bash

# Login and get token
LOGIN_RESP=$(curl -s -D /tmp/login_headers -X POST \
  "https://drseguros.merlin.insure/multi/multitarificador4-servicios/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"DANIEL","password":"Merlin2021"}')

TOKEN=$(grep -i "Authorization:" /tmp/login_headers | tr -d '\r' | sed 's/Authorization: //')
echo "Token: ${TOKEN:0:60}..."
echo "Login body: $LOGIN_RESP"

echo ""
echo "=== CURL POST /proyecto/nuevo (verbose) ==="
curl -v -X POST "https://drseguros.merlin.insure/multi/multitarificador4-servicios/proyecto/nuevo" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/plain, */*" \
  -d '{"idsPlantillasSeleccionadas":["62f109514b22d912058b1732","628b8d681861ee59091322cf"],"idsPlantillasComplementarioSeleccionadas":[],"complementarioTarificacion":{"aplicacionObligatoria":false,"seguroComplementarioIncluido":false,"importeDesglosado":true,"ramosComplementarios":[],"seguroComplementarioActivo":true}}' 2>&1

echo ""
echo "=== CURL with ALL browser headers ==="
curl -v -X POST "https://drseguros.merlin.insure/multi/multitarificador4-servicios/proyecto/nuevo" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/plain, */*" \
  -H "Origin: https://drseguros.merlin.insure" \
  -H "Referer: https://drseguros.merlin.insure/multitarificador4-servicios/" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36" \
  -H "sec-ch-ua: \"Chromium\";v=\"134\", \"Not:A-Brand\";v=\"24\", \"Google Chrome\";v=\"134\"" \
  -H "sec-ch-ua-mobile: ?0" \
  -H "sec-ch-ua-platform: \"Windows\"" \
  -H "Sec-Fetch-Dest: empty" \
  -H "Sec-Fetch-Mode: cors" \
  -H "Sec-Fetch-Site: same-origin" \
  -d '{"idsPlantillasSeleccionadas":["62f109514b22d912058b1732","628b8d681861ee59091322cf"],"idsPlantillasComplementarioSeleccionadas":[],"complementarioTarificacion":{"aplicacionObligatoria":false,"seguroComplementarioIncluido":false,"importeDesglosado":true,"ramosComplementarios":[],"seguroComplementarioActivo":true}}' 2>&1

echo ""
echo "DONE"
