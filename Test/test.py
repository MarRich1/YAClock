import machine
import neopixel
import time

# Anzahl der LEDs
NUM_LEDS = 92
PIN_NUM = 0  # GPIO Pin für Neopixel (anpassen falls nötig)

# Neopixel initialisieren
np = neopixel.NeoPixel(machine.Pin(PIN_NUM), NUM_LEDS)

# Helligkeit (10% von 255)
BRIGHTNESS = 25

# Alle LEDs ausschalten
for i in range(NUM_LEDS):
  np[i] = (0, 0, 0)
np.write()

# LEDs nacheinander einschalten
for i in range(NUM_LEDS):
  # Jede 50. LED grün, jede 10. rot, sonst weiß
  if (i + 1) % 50 == 0:
    color = (0, BRIGHTNESS, 0)  # Grün
  elif (i + 1) % 10 == 0:
    color = (BRIGHTNESS, 0, 0)  # Rot
  else:
    color = (BRIGHTNESS, BRIGHTNESS, BRIGHTNESS)  # Weiß

  np[i] = color
  np.write()
  print("LED Nummer:", i + 1)
  time.sleep(0.1)  # Kurze Pause, damit man das Einschalten sieht

# Hinweis: Bitte auf echter Hardware testen!