#!/bin/bash
    
echo ${WINDOWS_INSTALLER_CERTIFICATE} | base64 -d - > /tmp/authenticode-certificate.p12
/artifacts/build/dc/win64/conductor-companion.exe 
mv /artifacts/build/dc/win64/conductor-companion.exe /artifacts/build/dc/win64/conductor-companion.unsigned.exe
osslsigncode sign -pkcs12 /tmp/authenticode-certificate.p12 -pass ${WINDOWS_INSTALLER_CERTIFICATE_PWORD} -n "Conductor Client" -i "https://www.conductortech.com/" -in /artifacts/build/dc/win64/conductor-companion.unsigned.exe -out /artifacts/build/dc/win64/conductor-companion.exe
rm /artifacts/build/dc/win64/conductor-companion.unsigned.exe
