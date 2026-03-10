@echo off
if "%1" == "" goto flash
if "%1" == "flash" goto flash
if "%1" == "debug" goto debug

:flash
@echo Generating certificate make sure UID in x509_debug.txt matches your SoC
@echo off
openssl req -new -x509 -key smpk.pem -nodes -outform der -out debug_unlock_cert.bin -config x509_debug.txt -sha512
goto end

:debug
@echo Generating certificate for HSM debug
@echo off
openssl req -new -x509 -key smpk.pem -nodes -outform der -out debug_unlock_cert_M4.bin -config x509_debug_M4.txt -sha512

:end