set -e
for i in {1..100}; do
    python -m stork reset-hw fw-3.0.0-and-sw-2.5.5.swu --hardware bactobox --branding sbt --hostname bb2045014
done