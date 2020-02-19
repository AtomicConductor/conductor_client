#!/bin/bash
    
echo ${WINDOWS_INSTALLER_CERTIFICATE} | base64 -d - > /tmp/authenticode-certificate.p12

mv /artifacts/build/windows/Conductor/conductor-companion.exe /artifacts/build/windows/Conductor/conductor-companion.unsigned.exe
osslsigncode sign -pkcs12 /tmp/authenticode-certificate.p12 -pass ${WINDOWS_INSTALLER_CERTIFICATE_PWORD} -n "Conductor Client" -i "https://www.conductortech.com/" -in /artifacts/build/windows/Conductor/conductor-companion.unsigned.exe -out /artifacts/build/windows/Conductor/conductor-companion2.exe
rm /artifacts/build/windows/Conductor/conductor-companion.unsigned.exe
