import network
import socket
import time
import struct
import machine
import random
import neopixel
#import Ntp

TEST = False

try:
    import ujson
    with open('config.json') as f:
        config = ujson.load(f)
    SSID = config['SSID']
    PASSWORD = config['WLAN_PW']
except Exception as e:
    # WLAN-Daten anpassen!
    SSID = ''  # Ersetze durch dein SSID
    PASSWORD = ''  # Ersetze durch dein Passwort

NTP_DELTA = 2208988800  # Unix-Zeit-Offset zu NTP-Epoche
host = "ntp.server.com"  # NTP-Server

defaultbrightness = 0.5  # Helligkeit der LEDs (0.0 - 1.0)
brightness = defaultbrightness

def set_time():
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(5)
        s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
        val = struct.unpack("!I", msg[40:44])[0]

        while val == 0:
            time.sleep(3)
            print("Ungültige NTP-Antwort, versuche erneut...")
            s.sendto(NTP_QUERY, addr)
            msg = s.recv(48)
            val = struct.unpack("!I", msg[40:44])[0]
        
        utc_t = val - NTP_DELTA  # UTC Unix timestamp

        # DST-Check für DE (CET/CEST)
        tm_utc = time.gmtime(utc_t)
        year = tm_utc[0]

        # Letzter Sonntag März (31. - 25. finden)
        last_sun_mar = 31
        while time.gmtime(time.mktime((year, 3, last_sun_mar, 0, 0, 0, 0, 0, 0)))[6] != 6:
            last_sun_mar -= 1
        cest_start = time.mktime((year, 3, last_sun_mar, 2, 0, 0, 0, 0, 0))  # 2:00 UTC

        # Letzter Sonntag Oktober
        last_sun_oct = 31
        while time.gmtime(time.mktime((year, 10, last_sun_oct, 0, 0, 0, 0, 0, 0)))[6] != 6:
            last_sun_oct -= 1
        cet_start = time.mktime((year, 10, last_sun_oct, 3, 0, 0, 0, 0, 0))  # 3:00 UTC

        if cest_start <= utc_t < cet_start:
            offset = 7200  # CEST +2h
            print("CEST erkannt (+2h)")
        else:
            offset = 3600  # CET +1h
            print("CET erkannt (+1h)")

        local_t = utc_t + offset
        tm_local = time.gmtime(local_t)
        if TEST:
            print("UTC Zeit:", time.gmtime(utc_t))
            print("Lokale Zeit (tm):", tm_local)
            # RTC erwartet: (              year,       month,         day,         weekday,           hour,      minute,      second, subseconds)
            machine.RTC().datetime((tm_local[0], tm_local[1], tm_local[2], tm_local[6] + 1, tm_local[4]%24, tm_local[5], tm_local[5], 0))
        else:
            # RTC erwartet: (year, month, day, weekday, hour, minute, second, subseconds)
            machine.RTC().datetime((tm_local[0], tm_local[1], tm_local[2], tm_local[6] + 1, tm_local[3], tm_local[4], tm_local[5], 0))
        print("Lokale Zeit gesetzt:", time.localtime())
    except OSError as e:
        print("NTP-Fehler:", e)
    finally:
        s.close()

def color_wheel(pos):
    # pos: 0-255 → RGB
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)

def display_animation(clock_display_hal, display_gif_duration=4):
    # Ignoriert gif_path, nutzt Matrixanimation
    width = ClockDisplayHAL.WIDTH
    height = ClockDisplayHAL.HEIGHT
    snake_len = 6
    t_start = time.time()
    step = 0

    # einfache Schlängel-Bahn: Zeile 0→10, dann zurück, serpentin
    path = []
    for y in range(height):
        if y % 2 == 0:
            for x in range(width):
                path.append((x, y))
        else:
            for x in range(width - 1, -1, -1):
                path.append((x, y))

    path_len = len(path)

    while time.time() - t_start < display_gif_duration:
        clock_display_hal.clear_pixels(show=False)

        for i in range(snake_len):
            idx = (step - i) % path_len
            x, y = path[idx]
            color_pos = (step * 5 + i * 20) & 255  # Regenbogen verschoben
            color = color_wheel(color_pos)
            clock_display_hal.set_pixel(x, y, color)

        clock_display_hal.show()
        step += 1
        time.sleep(0.05)

"""
Clock Display Hardware Abstraction Layer

Display letters and indexes
131 ESAISTHZEHNU 120
108 FÜNFDVIERTEL 119
107 EFZWANZIGGHI 096
084 MINUTENJNACH 095
083 OGVORYHALBKM 072
060 ZWÖLFMSIEBEN 071
059 QZNEUNJEINSK 048
036 EDREILFÜNFTM 047
035 ÄZZWEIHVIERZ 024
012 SECHSEACHThC 023
011 ELFVZEHNOUHR 000
"""
class ClockDisplayHAL:
    WIDTH = 12
    HEIGHT = 11
    NUM_LEDS = WIDTH * HEIGHT

    WORDS_TO_LEDS = {
        "HOUR_0": (50, 52),
        "HOUR_1": (49, 52),
        "HOUR_2": (30, 33),
        "HOUR_3": (37, 40),
        "HOUR_4": (25, 28),
        "HOUR_5": (42, 45),
        "HOUR_6": (12, 16),
        "HOUR_7": (66, 71),
        "HOUR_8": (18, 21),
        "HOUR_9": (54, 57),
        "HOUR_10": (4, 7),
        "HOUR_11": (9, 11),
        "HOUR_12": (60, 64),
        "OCLOCK": (0, 2),
        "PAST": (92, 95),
        "TO": (79, 81),
        "MINUTES": (84, 90),
        "THIRTY": (74, 77),
        "TWENTY": (99, 105),
        "TWENTYFIVE": (74, 77),
        "FIVE": (108, 111),
        "TEN": (121, 124),
        "FIFTEEN": (113, 119),
        "IS": (126, 128),
        "IT": (130, 131),
        "AM": (129, 129),
        "ERROR:": (0, 131)  # Alle LEDs für Fehler
    }

    def __init__(self, board_pin):
        self.pixels = neopixel.NeoPixel(machine.Pin(board_pin), self.NUM_LEDS)

    def display_word(self, word, color):
        if word in self.WORDS_TO_LEDS:
            start, end = ClockDisplayHAL.WORDS_TO_LEDS[word]
            for i in range(start, end + 1):
                self.pixels[i] = color

    def cartesian_to_word_clock_led_strip_index(self, x, y):
        if y % 2 == 0:
            row_index = ClockDisplayHAL.NUM_LEDS - (y * ClockDisplayHAL.WIDTH)
            index = row_index - (x + 1)
            #index = row_index - x
        else:
            row_index = ClockDisplayHAL.NUM_LEDS - ((y + 1) * ClockDisplayHAL.WIDTH)
            index = row_index + x
        if index < 0 or index >= ClockDisplayHAL.NUM_LEDS:
            raise ValueError(f"Invalid x={x}, y={y}. Hardware only supports x=0-11, y=0-10")
        return index

    def set_pixel(self, x, y, color, width=12):
        index = self.cartesian_to_word_clock_led_strip_index(x, y)
        # curcolor = (int(color[0] * brightness), int(color[1] * brightness), int(color[2] * brightness))
        self.pixels[index] = color

    def clear_pixels(self, show=True):
        self.pixels.fill((int(30*brightness), int(30*brightness), int(0*brightness)))
        if show:
            self.pixels.write()

    def show(self):
        self.pixels.write()

class WordClock:
    COLORS = [
        (255, 0, 0),  # Red
        # (0, 255, 0),  # Green
        # (0, 0, 255),  # Blue
        # (255, 255, 0),  # Yellow
        # (255, 0, 255),  # Magenta
        # (0, 255, 255),  # Cyan
        # (255, 255, 255),  # White
        # (165, 42, 42),  # Brown
    ]

    def __init__(self, clock_display_hal):
        self.last_hour = -1
        self.all_last_highlighted_words = ""
        self.clock_display_hal = clock_display_hal
        
    def highlight_word(self, word, color=(255, 255, 255)):
        if word in ClockDisplayHAL.WORDS_TO_LEDS:
            self.clock_display_hal.display_word(word, color)

    def get_minutes_word(self, minute):
        if minute < 5: 
            print ("Minute < 5, return OCLOCK")
            return "OCLOCK"
        elif minute < 10: 
            print ("Minute < 10, return FIVE")
            return "FIVE"
        elif minute < 15: 
            print ("Minute < 15, return TEN")
            return "TEN"
        elif minute < 20: 
            print ("Minute < 20, return FIFTEEN")
            return "FIFTEEN"
        elif minute < 25: 
            print ("Minute < 25, return TWENTY")
            return "TWENTY"
        elif minute < 30: 
            print ("Minute < 30, return TWENTYFIVE")
            return "TWENTYFIVE"
        elif minute < 35: 
            print ("Minute < 35, return THIRTY")
            return "THIRTY"
        elif minute < 40: 
            print ("Minute < 40, return THIRTY")
            return "TWENTYFIVE"
        elif minute < 45: 
            print ("Minute < 45, return THIRTY")
            return "TWENTY"
        elif minute < 50: 
            print ("Minute < 50, return THIRTY")
            return "FIFTEEN"
        elif minute < 55: 
            print ("Minute < 55, return THIRTY")
            return "TEN"
        else: 
            print ("Minute < 60, return THIRTY")
            return "FIVE"

    def get_random_color(self):
        index = random.randint(0, len(WordClock.COLORS) - 1)
        color = (int(WordClock.COLORS[index][0]*brightness), int(WordClock.COLORS[index][1]*brightness), int(WordClock.COLORS[index][2]*brightness))
        return color

    def display_time(self):
        global brightness
        if TEST:
            print("Aktuelle RTC Zeit:", time.localtime())
            set_time()  # Setze die Zeit erneut für Tests, damit sie sich ändert

        now = time.localtime()
        hour = now[3] % 12 or 12  # Ensure hour is 1-12
        minute = now[4]
        ampm = False

        if now[3] < 12:
            ampm = True
            if now[3] >= 7:
                brightness = defaultbrightness * 1.0
            else:
                brightness = defaultbrightness * 0.5
        else:
            if now[3] >= 8:
                brightness = defaultbrightness * 0.5
            else:
                brightness = defaultbrightness * 1.0
            ampm = False
        
        print("brightness:", brightness)

        self.clock_display_hal.clear_pixels(show=False)
        if hour != self.last_hour:
            if minute == 0:
                if not TEST:
                    display_animation(self.clock_display_hal, 10)
                
                self.clock_display_hal.clear_pixels(show=False)
                self.last_hour = hour
                # NTP abfragen und RTC setzen
                set_time()

        self.highlight_word("IT", self.get_random_color())
        self.highlight_word("IS", self.get_random_color())
        all_highlighted_words = "ITIS"

        if TEST:
            if ampm:
                self.highlight_word("AM", (0, 255, 0))
                all_highlighted_words += "AM"
            else:
                self.highlight_word("AM", (255, 0, 0))
                all_highlighted_words += "AM"

        if minute < 5:
            self.highlight_word("OCLOCK", self.get_random_color())
            all_highlighted_words += "OCLOCK"
        elif minute >= 15 and minute < 20:
            self.highlight_word("PAST", self.get_random_color())
            all_highlighted_words += "PAST"
        elif minute >= 25 and minute < 30:
            self.highlight_word("TO", self.get_random_color())
            all_highlighted_words += "TO"
            self.highlight_word("FIVE", self.get_random_color())
            all_highlighted_words += "FIVE"
            hour = (hour + 1) % 12 or 12  # Adjust hour for "to" display
        elif minute >= 30 and minute < 35:
            self.highlight_word("THIRTY", self.get_random_color())
            all_highlighted_words += "THIRTY"
            hour = (hour + 1) % 12 or 12  # Adjust hour for "to" display
        elif minute >= 35 and minute < 40:
            self.highlight_word("TWENTYFIVE", self.get_random_color())
            all_highlighted_words += "TWENTYFIVE"
            self.highlight_word("PAST", self.get_random_color())
            all_highlighted_words += "PAST"
            self.highlight_word("FIVE", self.get_random_color())
            all_highlighted_words += "FIVE"
            hour = (hour + 1) % 12 or 12
        elif minute < 35:
            self.highlight_word("PAST", self.get_random_color())
            all_highlighted_words += "PAST"
            self.highlight_word("MINUTES", self.get_random_color())
            all_highlighted_words += "MINUTES"
        elif minute >= 45 and minute < 50:
            self.highlight_word("TO", self.get_random_color())
            all_highlighted_words += "TO"
            self.highlight_word("FIFTEEN", self.get_random_color())
            all_highlighted_words += "FIFTEEN"
            hour = (hour + 1) % 12 or 12
        else:
            self.highlight_word("TO", self.get_random_color())
            all_highlighted_words += "TO"
            self.highlight_word("MINUTES", self.get_random_color())
            all_highlighted_words += "MINUTES"
            hour = (hour + 1) % 12 or 12  # Adjust hour for "to" display

        hour_word = f"HOUR_{hour}"
        self.highlight_word(self.get_minutes_word(minute), self.get_random_color())
        all_highlighted_words += self.get_minutes_word(minute)
        self.highlight_word(hour_word, self.get_random_color())
        all_highlighted_words += hour_word

        if self.all_last_highlighted_words != all_highlighted_words:
            self.clock_display_hal.show()
            self.all_last_highlighted_words = all_highlighted_words

# Color definitions
def main(pin, brightness):
    clock_display_hal = ClockDisplayHAL(pin)
    word_clock = WordClock(clock_display_hal)

    # WLAN verbinden
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    max_wait = 20
    while max_wait > 0:
        clock_display_hal.set_pixel((20-max_wait)%12,int((20-max_wait)/12),(255, 0, 0))
        clock_display_hal.show()
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('Warte auf Verbindung...')
        time.sleep(1)

    if wlan.status() != 3:
        for i in range(10):
            word_clock.highlight_word("ERROR:", (255, 0, 0))
            clock_display_hal.show()
            time.sleep(0.5)
            word_clock.highlight_word("ERROR:", (0, 0, 0))
            clock_display_hal.show()
            time.sleep(0.5)

        word_clock.highlight_word("ERROR:", (80, 0, 0))
        clock_display_hal.show()
        raise RuntimeError('WLAN-Verbindung fehlgeschlagen')
    else:
        print('Verbunden! IP:', wlan.ifconfig()[0])

    # NTP abfragen und RTC setzen
    set_time()

    try:
        while True:
            word_clock.display_time()
            if TEST:
                time.sleep(1)  # Schneller für Tests
            else:
                time.sleep(10)
    except KeyboardInterrupt:
        clock_display_hal.clear_pixels()

if __name__ == "__main__":
    main(0, 0.05)
