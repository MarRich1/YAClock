# Vollständiger MicroPython-Code Mondlampe + Uhrzeit (aktualisiert)
# NTP: 192.168.178.1 (lokaler Server)
# CET/CEST (Germany DST): TZ-Offset +1/+2
# 95 LEDs, Zeit mischt mit Mond

import network
import time
import ntptime
import urequests as requests
import neopixel
import machine
from machine import Pin, RTC
import ujson
import utime

NUM_LEDS = 93
LED_PIN = 0

# Initialisiere
np = neopixel.NeoPixel(Pin(LED_PIN), NUM_LEDS)
rtc = RTC()

def status_led(count=1, color=(0, 255, 0)):
    for i in range(count):
        np[i] = color
    np.write()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, WLAN_PW)
    timeout = 0
    while not wlan.isconnected() and timeout < 30:
        print('WLAN verbinden...')
        time.sleep(3)
        timeout += 1
        status_led(timeout, (255, 255, 0))  # Gelb: Verbindungsversuch
    print('WLAN:', wlan.ifconfig())
    if wlan.isconnected():
        status_led(3, (0, 255, 0))  # Grün: Verbunden
    else:
      print ('Fehler')

def get_ntp_time():
    ntptime.host = NTP_SERVER  # Lokaler NTP-Server
    for attempt in range(1, 10):
        try:
            ntptime.settime()
            print(f'NTP Zeit (UTC) gesetzt (Versuch {attempt})')
            status_led(attempt, (255, 255, 0)) 
            return True
        except Exception as e:
            print(f'NTP Fehler (Versuch {attempt}):', e)
            print(NTP_SERVER)
            status_led(attempt, (255, 0, 0)) 
            if attempt < 3:
                print('Warte 10 Sekunden und versuche erneut...')
                time.sleep(10)
    print('NTP Synchronisation nach 3 Versuchen abgebrochen.')
    return False

def get_local_time():
    """CET/CEST für Deutschland (letzter Sonntag März/Oktober)"""
    t = time.localtime()
    year, month, day, hour = t[0], t[1], t[2], t[3]
    
    # Sommerzeit? (letzter Sonntag März 2-3Uhr bis letzter Sonntag Okt 3Uhr)
    dst = False
    if month > 3 and month < 10:
        dst = True
    elif month == 3:
        if day >= 25:  # Vereinfacht, letzter Sonntag ~25-31
            last_sun_march = 31 - (weekday(year, 3, 31) + 1) % 7  # Näherung
            if day > last_sun_march or (day == last_sun_march and hour >= 2):
                dst = True
    elif month == 10:
        last_sun_oct = 31 - (weekday(year, 10, 31) + 1) % 7
        if day < last_sun_oct or (day == last_sun_oct and hour < 3):
            dst = True
    
    offset = 3600 if not dst else 7200  # CET +1h, CEST +2h
    local_t = time.localtime(time.time() + offset)
    return local_t, dst

def weekday(year, month, day):  # Vereinfachter Wochentag (Zeller)
    if month < 3:
        month += 12
        year -= 1
    return (day + (13*(month+1)//5) + year + year//4 + year//100*5 + year//400*4 - 6) % 7  # Vereinfacht

# Mond & Lamp-Funktionen wie zuvor (get_moon_data, set_moon_lamp, mix_color unverändert)
def get_moon_data(test=False):

    # API-Aufruf (GET)
    local_t, _ = get_local_time()
    url = "https://api.freeastroapi.com/api/v1/moon/phase"
    date_str = f"{local_t[0]:04d}-{local_t[1]:02d}-{local_t[2]:02d}"
    params = (
        f"date={date_str}"
        f"&lat={LAT}"
        f"&lon={LON}"
        f"&include_visuals=false"
        f"&include_zodiac=false"
        f"&include_rise_set=true"
        f"&include_interpretation=false"
    )
    full_url = url + "?" + params
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    try:
        resp = requests.get(full_url, headers=headers, timeout=10)
        data = resp.json()
        resp.close()
        phase = data.get('phase', {})
        illum = phase.get('illumination', 0.5)
        phase_age = phase.get('age_days', 0.5)
        # Rise/Set auslesen
        rise_str = phase.get('rise')
        set_str = phase.get('set')
        # Zeit in Sekunden seit Mitternacht
        def hms_to_sec(tstr):
            if not tstr:
                return None
            parts = tstr.split(':')
            if len(parts) < 2:
                return None
            return int(parts[0])*3600 + int(parts[1])*60
        rise_sec = hms_to_sec(rise_str)
        set_sec = hms_to_sec(set_str)
        now = time.localtime()
        now_sec = now[3]*3600 + now[4]*60 + now[5]
        # Interpolation
        if rise_sec is not None and set_sec is not None and rise_sec < set_sec:
            mid_sec = (rise_sec + set_sec) // 2
            if now_sec < rise_sec or now_sec > set_sec:
                brightness = 0.10
            elif now_sec <= mid_sec:
                brightness = 0.10 + 0.90 * (now_sec - rise_sec) / (mid_sec - rise_sec)
            else:
                brightness = 0.10 + 0.90 * (set_sec - now_sec) / (set_sec - mid_sec)
        else:
            brightness = 0.10  # Fallback, falls keine Daten
        print(f"Mond: Illum={illum:.2f}, Phase={phase_age:.2f}, Brightness={brightness:.2f}")
        return illum, phase_age, brightness
    except Exception as e:
        print('Mond: API Fehler, nutze Testwerte:', e)
        return 0.5, 0.5, 0.10

def set_moon_lamp(np, illum_pct, elevation):
    # Farbverlauf nach illumination und Helligkeit nach brightness (direkt)
    def moon_color(illum, brightness):
        def scale(val):
            return int(val * brightness)
        if illum <= 0.0:
            return (0, 0, 0)
        elif illum < 0.25:
            val = scale(40 + 80 * illum / 0.25)
            return (val, val, val)
        elif illum < 0.5:
            val = scale(80 + 100 * (illum-0.25)/0.25)
            return (val, val, val)
        elif illum < 0.75:
            val1 = scale(180 + 60 * (illum-0.5)/0.25)
            #val2 = scale(60 * (1-(illum-0.5)/0.25))
            return (val1, val1, val1)
        else:
            val = scale(240 + 15 * (illum-0.75)/0.25)
            return (val, val, val)

    for i in range(NUM_LEDS):
        np[i] = (0, 0, 5)

    center = NUM_LEDS // 4  # 9 Uhr
    max_leds = NUM_LEDS // 2
    leds_on = int(illum_pct * max_leds)
    color = moon_color(illum_pct, elevation)  # elevation ist jetzt brightness!
    for offset in range(leds_on + 1):
        idx1 = (center + offset) % NUM_LEDS
        idx2 = (center - offset) % NUM_LEDS
        np[idx1] = color
        np[idx2] = color
    np.write()

def print_time_overlay(hours, minutes, seconds, dst, show_time=False):
    if show_time:
        print(f'Lokal: {hours:02d}:{minutes:02d}:{seconds:02d} {"CEST" if dst else "CET"}')
        # Zeit-Overlay LEDs setzen
        time_bright = 0.8
        blue = (0, 0, int(255 * time_bright))
        red = (int(255 * time_bright), 0, 0)
        green = (0, int(255 * time_bright), 0)

        h_pos = int((hours % 12) * (NUM_LEDS / 12))
        np[h_pos] = mix_blue(np[h_pos], blue, (0,0,0))  # moon_color not available here, use dummy or pass as param

        m_pos = int((minutes // 5) * (NUM_LEDS / 12)) + 1
        np[m_pos % NUM_LEDS] = mix_red(np[m_pos % NUM_LEDS], red, (0,0,0))

        s_pos = int((seconds // 10) * (NUM_LEDS / 6)) + 2
        np[s_pos % NUM_LEDS] = mix_green(np[s_pos % NUM_LEDS], green, (0,0,0))
        np.write()

def mix_color(current, overlay, moon):
    r = min(255, current[0] + int(overlay[0] * 0.5))
    g = min(255, current[1] + int(overlay[1] * 0.5))
    b = min(255, current[2] + int(overlay[2] * 0.5))
    return (r, g, b)

def mix_blue(current, ov, moon):
    return mix_color(current, ov, moon)
def mix_red(current, ov, moon):
    return mix_color(current, ov, moon)
def mix_green(current, ov, moon):
    return mix_color(current, ov, moon)

# Start

# Konfiguration
try:
    import ujson
    with open('config.json') as f:
        config = ujson.load(f)
    SSID = config['SSID']
    WLAN_PW = config['WLAN_PW']
    API_KEY = config['API_KEY']
    LAT = config['LATITUDE']
    LON = config['LONGITUDE']
    NTP_SERVER = config['NTPServer']
except Exception as e:
    print('Fehler beim Laden der Konfiguration:', e)
    SSID = ''
    WLAN_PW = ''
    API_KEY = ''
    LAT = 0
    LON = 0
    NTP_SERVER = 'ntp.server.com'
    status_led(NUM_LEDS, (255, 0, 0))  # Rot: Fehler

print('Mondlampe + Uhr (CET/CEST)')
status_led(1, (0, 255, 0))  # Grün: Start
connect_wifi()
get_ntp_time()

# Mondphasen nur alle 4 Stunden abfragen
last_moon_update = -14400  # Erzwinge Update beim Start
last_ntp_sync = -86400    # Erzwinge NTP Sync beim Start
illum, phase_age, elev = get_moon_data(test=False)

np.fill((0, 0, 0))
set_moon_lamp(np, illum, elev)

while True:
    now = utime.time()
    # Einmal am Tag NTP synchronisieren (alle 24h)
    if now - last_ntp_sync >= 86400:
        if get_ntp_time():
            last_ntp_sync = now

    # Alle 4 Stunden oder beim Start: neue Mondphasen-Daten holen
    if now - last_moon_update >= 4*3600:
        illum, phase_age, elev = get_moon_data(test=False)
        last_moon_update = now

    local_t, dst = get_local_time()
    h, m, s = local_t[3], local_t[4], local_t[5]

    # LEDs nur einmal pro Minute aktualisieren
    if s == 0:
        set_moon_lamp(np, illum, elev)
        print_time_overlay(h, m, s, dst, show_time=False)
    utime.sleep(1)
