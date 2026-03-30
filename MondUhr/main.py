# Vollständiger MicroPython-Code Mondlampe + Uhrzeit (LED0=6Uhr, Europa-Mondphasen)
# NTP:192.168.178.1 | CET/CEST | 93 LEDs | test_mode & show_time via config.json
# Mond: weiß, max 50% Helligkeit; LEDs von 3Uhr (LED69) symmetrisch nach oben/unten
# Easter-Egg: bei 11:11, 22:22, 4:44 usw. läuft ein Regenbogen 3x um den Ring

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

test_moon_phase = 0.0

# Config laden
try:
    with open('config.json') as f:
        config = ujson.load(f)
    SSID = config['SSID']
    WLAN_PW = config['WLAN_PW']
    API_KEY = config['API_KEY']
    LAT = config['LATITUDE']
    LON = config['LONGITUDE']
    NTP_SERVER = config['NTPServer']
    test_mode = config.get('test_mode', False)
    show_time = config.get('show_time', False)   # Default: Uhr-Aus
    print(f"Config: test_mode={test_mode}, show_time={show_time}")
except:
    test_mode = True
    show_time = False
    machine.reset()


np = neopixel.NeoPixel(Pin(LED_PIN), NUM_LEDS)
rtc = RTC()


def status_led(count=1, color=(0, 255, 0)):
    for i in range(min(count, NUM_LEDS)):
        np[i] = color
    np.write()


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, WLAN_PW)
    timeout = 0
    while not wlan.isconnected() and timeout < 30:
        print('WLAN...')
        time.sleep(3)
        timeout += 1
        status_led(timeout, (255, 255, 0))
    print('WLAN:', wlan.ifconfig())
    if not wlan.isconnected():
        print('WLAN Fehler'); machine.reset()
    status_led(3, (0, 255, 0))


def get_ntp_time():
    ntptime.host = NTP_SERVER
    for attempt in range(1, 4):
        try:
            ntptime.settime()
            print(f'NTP OK {attempt}')
            status_led(attempt, (0, 255, 255))
            return True
        except Exception as e:
            print(f'NTP {attempt}:', e)
            status_led(attempt, (255, 0, 0))
            time.sleep(10)
    return False


def get_local_time():
    t = time.localtime()
    year, month, day, hour = t[0], t[1], t[2], t[3]

    def last_sunday(y, m):
        wd = weekday(y, m, 31)
        return 31 - ((wd + 1) % 7) if wd != 6 else 31

    dst = False
    if 4 <= month <= 9:
        dst = True
    elif month == 3:
        ls = last_sunday(year, 3)
        if day > ls or (day == ls and hour >= 2):
            dst = True
    elif month == 10:
        ls = last_sunday(year, 10)
        if day < ls or (day == ls and hour < 3):
            dst = True

    offset = 3600 if not dst else 7200
    return time.localtime(time.time() + offset), dst


def weekday(year, month, day):
    if month < 3: month += 12; year -= 1
    return (day + (13*(month+1)//5) + year + year//4 + 5*year//100 + 4*year//400) % 7


def get_moon_data(test=False):
    global test_moon_phase

    if test:
        test_moon_phase = (test_moon_phase + 0.01) % 1.0
        illum = test_moon_phase
        #phase_age = illum * 29.53
        print(f"TEST [{int(illum*100):02d}%]: {illum:.3f}")
        return illum

    # LIVE API
    local_t, _ = get_local_time()
    url = "https://api.freeastroapi.com/api/v1/moon/phase"
    params = f"?date={local_t[0]:04d}-{local_t[1]:02d}-{local_t[2]:02d}T{local_t[3]:02d}:{local_t[4]:02d}&lat={LAT}&lon={LON}&include_visuals=false&include_zodiac=false&include_rise_set=true&include_interpretation=false"
    full_url = url + params
    headers = {"x-api-key": API_KEY}

    try:
        resp = requests.get(full_url, headers=headers, timeout=10)
        data = ujson.loads(resp.text)
        print(f"API Antwort: {data}")
        resp.close()
        phase = data.get('phase', {})
        illum = phase.get('illumination', 1)
        print(f"LIVE: Illum={illum:.2f}")
        return illum
    except Exception as e:
        print('API Fehler:', e)
        return 0.5


def set_moon_lamp(illum_pct):
    def moon_color():
        local_t, _ = get_local_time()
        base = 12

        # Tagsüber etwas heller, nachts gedämpft (Mond nicht zu dominant)
        if local_t[3] >= 6 and local_t[3] <= 22:
            base = 20
        else:
            base = 4

        return (base, base, base)

    np.fill((0, 0, 5))  # minimaler Hintergrund

    max_leds = NUM_LEDS // 2        # ca. 180° Gesamtbogen
    leds_on = int(illum_pct * max_leds * 2.0)  # 0–100% -> 0–max_leds*2
    color = moon_color()
    print(f"Illum {illum_pct:.2f} -> {leds_on} LEDs, Color {color}")

    center = 69  # 3Uhr als Startpunkt

    for i in range(leds_on):
        # symmetrisch um 0° (3Uhr) nach oben und unten
        angle = i - leds_on // 2
        idx = (center + angle) % NUM_LEDS
        np[idx] = color

    np.write()


def print_time_overlay(h, m, s, moon_color):
    time_bright = 0.6
    blue  = (0, 0, int(255 * time_bright))
    red   = (int(255 * time_bright), 0, 0)
    green = (0, int(255 * time_bright), 0)

    h_pos = int((h % 12) * (NUM_LEDS / 12)) % NUM_LEDS
    m_pos = int((m // 5) * (NUM_LEDS / 12) + 24) % NUM_LEDS
    s_pos = int((s // 15) * (NUM_LEDS / 8) + 48) % NUM_LEDS

    np[h_pos] = mix_color(np[h_pos], blue,  moon_color)
    np[m_pos] = mix_color(np[m_pos], red,   moon_color)
    np[s_pos] = mix_color(np[s_pos], green, moon_color)
    np.write()
    print(f"Zeit: H{h_pos} M{m_pos} S{s_pos}")


def mix_color(current, overlay, moon):
    # Mondfarbe nur leicht einmischen, Overlay dominant
    r = min(255, int(current[0] * 0.2 + overlay[0] * 0.7 + moon[0] * 0.1))
    g = min(255, int(current[1] * 0.2 + overlay[1] * 0.7 + moon[1] * 0.1))
    b = min(255, int(current[2] * 0.2 + overlay[2] * 0.7 + moon[2] * 0.1))
    return (r, g, b)


# --- Easter-Egg / Rainbow ----------------------------------------------------

def wheel(pos):
    # 0–255 → Farbe im Farbkreis (rot→grün→blau→rot)
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos*3, pos*3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos*3, pos*3)
    pos -= 170
    return (pos*3, 0, 255 - pos*3)


def rainbow_cycle(repeat=1, delay_ms=10):
    # x-Mal Regenbogen über den Ring
    for r in range(repeat):
        print(f"Regenbogen-Durchlauf {r+1}/{repeat}")
        for i in range(NUM_LEDS):
            print(f"    LED {i+1}/{NUM_LEDS}")
            rc_index = (i * 256 // NUM_LEDS) % 255
            np[i] = wheel(rc_index)
            np.write()
            utime.sleep_ms(delay_ms)

        for i in range(NUM_LEDS):
            print(f"    LED {i+1}/{NUM_LEDS} aus")
            rc_index = (i * 256 // NUM_LEDS) % 255
            np[i] = (0, 0, 0)  # nach Regenbogen kurz aus
            np.write()
            utime.sleep_ms(delay_ms)


def check_easter_egg(h, m):
    # 11:11 => 1 1 1 1 => alle gleich
    t = f"{h:d}{m:d}"
    digits = [c for c in t]
    return all(d == digits[0] for d in digits)


# START
print('=== Mondlampe LED0=6Uhr (Europa Phasen) ===')
status_led(1, (0, 255, 255) if test_mode else (0, 255, 0))
print(f"{'TEST 10s Zyklus' if test_mode else 'LIVE API 4h'} | 3Uhr=LED69, show_time={show_time}")


connect_wifi()

if get_ntp_time():
    last_moon_update = -999999
    last_ntp_sync = utime.time()
#    illum, elev = get_moon_data(test=test_mode)


running_easter_egg = False   # verhindert doppelten Regenbogen während eines Durchlaufs

while True:
    now = utime.time()

    if now - last_ntp_sync >= 86400:
        get_ntp_time()
        last_ntp_sync = now

    interval = 5 if test_mode else 3600
    if now - last_moon_update >= interval:
        illum = get_moon_data(test=test_mode)
        last_moon_update = now

    local_t, dst = get_local_time()
    h, m, s = local_t[3], local_t[4], local_t[5]

    # Easter-Egg: Regenbogen wenn 11:11, 22:22, 00:00, 4:44 usw.
    if not running_easter_egg and s == 0 and m < 60 and h < 24:
        if check_easter_egg(h, m):
            print(f"Easter-Egg: {h:02d}:{m:02d} -> Regenbogen 3x")
            running_easter_egg = True
            rainbow_cycle(repeat=3, delay_ms=10)
            running_easter_egg = False

    if s % 10 == 0:
        print(f'{h:02d}:{m:02d}:{s:02d} {"CEST" if dst else "CET"}')
        set_moon_lamp(illum)
        moon_color = np[0]  # Center 6Uhr (falls nötig)

        if show_time:
            print_time_overlay(h, m, s, moon_color)

    utime.sleep(1)
