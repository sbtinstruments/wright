import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)

index = 15
GPIO.setup(index, GPIO.OUT)
GPIO.output(index, GPIO.LOW)
