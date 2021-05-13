set -e
for i in {1..100}; do
    python -m stork reset-device fw-3.0.0-and-sw-2.5.5.swu --device-type bactobox --branding sbt --hostname bb2045014 --jtag-usb-serial 210299AFB3C5
done
