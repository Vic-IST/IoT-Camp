# =============================================================================
# main.py  --  ESP32 MicroPython MQTT LED Controller
# =============================================================================
#
# WHAT THIS PROGRAM DOES:
#   1. Connects the ESP32 to your Wi-Fi network.
#   2. Connects to an MQTT "broker" (a message relay running on the Raspberry Pi).
#   3. Listens for color commands like "red", "green", "blue", "white", or "off".
#   4. Changes the WS2812B LED strip to that color.
#
# HOW TO USE:
#   - Fill in YOUR_WIFI_SSID, YOUR_WIFI_PASSWORD, and YOUR_PI_IP_ADDRESS below.
#   - Save this file as main.py ON THE ESP32 (File -> Save as -> MicroPython device).
#   - Press the reset button or run the file. The LEDs will glow dim blue when ready.
#   - From the Raspberry Pi terminal, send a command like:
#       mosquitto_pub -h localhost -t led/cmd -m "red"
#
# =============================================================================

import time
import network          # handles Wi-Fi on the ESP32
from machine import Pin # lets us talk to the ESP32 hardware pins
import neopixel         # controls WS2812B (NeoPixel) LED strips
import ubinascii        # converts bytes to hex (used for a unique device ID)
import machine          # low-level hardware access
from umqtt.simple import MQTTClient  # sends/receives MQTT messages

# =============================================================================
# SECTION 1: SETTINGS  <-- YOU MUST EDIT THESE THREE VALUES
# =============================================================================

WIFI_SSID = "YOUR_WIFI_SSID"         # The name of your Wi-Fi network
WIFI_PASS = "YOUR_WIFI_PASSWORD"     # Your Wi-Fi password

MQTT_BROKER = "YOUR_PI_IP_ADDRESS"   # The Raspberry Pi's IP address
                                     # Find it by running:  hostname -I  on the Pi
                                     # Example: "192.168.1.42"
MQTT_PORT = 1883                     # Default MQTT port (don't change unless told to)

# =============================================================================
# SECTION 2: LED STRIP SETTINGS
# =============================================================================

LED_PIN = 5    # Which GPIO pin the LED strip's DIN wire is connected to
               # Default is GPIO 5 -- change only if your wiring is different

N_LEDS = 8     # How many LEDs are on your strip

TOPIC_CMD = b"led/cmd"  # The MQTT "topic" this device listens on
                        # The  b  means it's sent as bytes, not a regular string

# =============================================================================
# SECTION 3: SET UP THE LED STRIP
# =============================================================================

# neopixel.NeoPixel creates an object that knows how to talk to the LED strip.
# Pin(LED_PIN, Pin.OUT) sets GPIO 5 as an output pin.
np = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), N_LEDS)

# Brightness setting: 0 = off, 255 = full brightness
# We keep it low (40) so the ESP32's USB power can handle it safely.
# If you have an external 5V power supply, you can raise this.
BRIGHTNESS = 40

# =============================================================================
# SECTION 4: HELPER FUNCTIONS
# =============================================================================

def scale(color):
    """
    Dims a color by the BRIGHTNESS amount.
    Colors are stored as (Red, Green, Blue) tuples with values 0-255.
    This function multiplies each value by the brightness fraction.
    Example: scale((255, 0, 0)) with BRIGHTNESS=40 gives (40, 0, 0)
    """
    return (
        color[0] * BRIGHTNESS // 255,  # Red channel
        color[1] * BRIGHTNESS // 255,  # Green channel
        color[2] * BRIGHTNESS // 255   # Blue channel
    )


def fill(r, g, b):
    """
    Sets ALL LEDs to the same color (r, g, b), then pushes the data to the strip.
    r = red amount (0-255), g = green (0-255), b = blue (0-255)
    np[i] = color  sets the color in memory; np.write() actually sends it to the LEDs.
    """
    c = scale((r, g, b))     # dim the color to our safe brightness level
    for i in range(N_LEDS):  # loop through every LED (0, 1, 2, ... 7)
        np[i] = c            # set this LED's color in memory
    np.write()               # send all the colors to the strip at once


def clear():
    """Turns all LEDs off (sets them to black: 0, 0, 0)."""
    fill(0, 0, 0)


# =============================================================================
# SECTION 5: MQTT MESSAGE HANDLER
# =============================================================================

def on_msg(topic, msg):
    """
    This function runs automatically whenever an MQTT message arrives.
    'topic' is the channel the message came in on (we only subscribed to led/cmd).
    'msg'   is the actual message content, like b"red" or b"off".

    .decode() converts bytes to a regular string: b"red" -> "red"
    .strip()  removes any spaces or newlines at the edges
    .lower()  makes it lowercase so "Red" and "RED" also work
    """
    command = msg.decode().strip().lower()

    if command == "red":
        fill(255, 0, 0)      # full red, no green, no blue

    elif command == "green":
        fill(0, 255, 0)      # no red, full green, no blue

    elif command == "blue":
        fill(0, 0, 255)      # no red, no green, full blue

    elif command == "white":
        fill(255, 255, 255)  # all three channels on = white

    elif command == "off":
        clear()              # turn everything off

    # If the message doesn't match any of the above, nothing happens.
    # You could add more colors here! Try "yellow": fill(255, 255, 0)


# =============================================================================
# SECTION 6: WI-FI CONNECTION
# =============================================================================

def wifi_connect():
    """
    Turns on the ESP32's Wi-Fi radio and connects to your network.
    Returns True if connected, False if it timed out.

    network.WLAN(network.STA_IF) = Station mode (connecting TO a router, not being one)
    wlan.active(True)  = turns the radio on
    wlan.connect(...)  = starts connecting (this is NOT instant)
    We then wait up to 12 seconds (120 loops x 0.1 seconds) for it to finish.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to Wi-Fi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASS)

        for _ in range(120):          # try for up to 12 seconds
            if wlan.isconnected():
                break
            time.sleep(0.1)

    if wlan.isconnected():
        print("Wi-Fi connected! IP:", wlan.ifconfig()[0])
        return True
    else:
        print("Wi-Fi FAILED. Check SSID and password.")
        return False


# =============================================================================
# SECTION 7: MQTT CONNECTION
# =============================================================================

def mqtt_connect():
    """
    Connects to the MQTT broker on the Raspberry Pi and subscribes to our topic.

    Every MQTT client needs a unique ID. We use the ESP32's hardware ID
    (converted to hex) so it's always unique without us having to type one.

    c.set_callback(on_msg)  = "when a message arrives, call on_msg()"
    c.connect()             = opens the connection to the broker
    c.subscribe(TOPIC_CMD)  = tells the broker: "send me messages from led/cmd"
    """
    client_id = ubinascii.hexlify(machine.unique_id())  # unique hardware ID as hex string
    c = MQTTClient(client_id=client_id, server=MQTT_BROKER, port=MQTT_PORT, keepalive=30)
    c.set_callback(on_msg)
    c.connect()
    c.subscribe(TOPIC_CMD)
    print("MQTT connected to broker:", MQTT_BROKER)
    return c


# =============================================================================
# SECTION 8: MAIN PROGRAM FLOW
# =============================================================================

# --- Step 1: Turn off all LEDs at startup (clean state)
clear()

# --- Step 2: Connect to Wi-Fi
if not wifi_connect():
    # Wi-Fi failed -- blink the first LED dim red as an error signal, then stop.
    print("Blinking red to signal Wi-Fi failure. Fix SSID/password and reset.")
    while True:
        np[0] = (10, 0, 0)   # dim red on
        np.write()
        time.sleep(0.2)
        np[0] = (0, 0, 0)    # off
        np.write()
        time.sleep(0.2)

# --- Step 3: Connect to MQTT broker (keep trying until it works)
client = None
while client is None:
    try:
        client = mqtt_connect()
    except Exception as e:
        print("MQTT connection failed:", e, "-- retrying in 1 second...")
        time.sleep(1)

# --- Step 4: Show a "ready" indicator -- all LEDs dim blue
print("Ready! Listening for MQTT commands on topic:", TOPIC_CMD)
fill(0, 0, 30)  # dim blue = "I am connected and waiting"

# --- Step 5: Main loop -- keep checking for new MQTT messages forever
while True:
    try:
        # check_msg() looks for a new message WITHOUT blocking.
        # If a message arrived, it calls on_msg() automatically.
        # If no message, it returns immediately and we sleep briefly.
        client.check_msg()
        time.sleep(0.05)   # 50ms pause keeps the loop from running too fast

    except OSError:
        # If the network drops (Wi-Fi hiccup, broker restart, etc.),
        # we catch the error here and try to reconnect instead of crashing.
        print("Lost MQTT connection -- reconnecting...")
        time.sleep(1)
        try:
            client = mqtt_connect()
        except Exception:
            pass   # keep the loop going; next iteration will try again
