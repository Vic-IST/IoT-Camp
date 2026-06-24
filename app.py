# =============================================================================
# app.py  --  Flask Web Server for LED Control
# =============================================================================
#
# WHAT THIS DOES:
#   Runs a small web server on the Raspberry Pi.
#   When someone visits the page in a browser and clicks a color button,
#   this server sends an MQTT message to the ESP32 to change the LEDs.
#
# HOW TO RUN:
#   1. Install dependencies (one time only):
#        pip install flask paho-mqtt
#   2. Start the server:
#        python3 app.py
#   3. Open a browser on any device on the same Wi-Fi network and go to:
#        http://<your-pi-ip>:5000
#      Example: http://192.168.1.42:5000
#
# FILE STRUCTURE (keep these together in the same folder):
#   app.py
#   templates/
#       index.html    <-- the web page campers will edit
#
# =============================================================================

from flask import Flask, render_template, jsonify, request
import paho.mqtt.publish as mqtt_publish

# Create the Flask application
app = Flask(__name__)

# ---- SETTINGS ---------------------------------------------------------------
MQTT_BROKER = "localhost"   # The broker is running right here on the Pi
MQTT_PORT   = 1883          # Default MQTT port (matches classroom.conf)
MQTT_TOPIC  = "led/cmd"     # Must match the topic in main.py on the ESP32
# -----------------------------------------------------------------------------

# Valid colors the ESP32 understands (matches the on_msg function in main.py)
# Add new colors here if you add them to main.py!
ALLOWED_COLORS = {"red", "green", "blue", "white", "off"}


def send_mqtt(message):
    """
    Publishes a single MQTT message to the broker.
    paho.mqtt.publish.single() connects, sends, then disconnects automatically.
    This is the simplest way to send one message without keeping a connection open.
    """
    try:
        mqtt_publish.single(
            topic    = MQTT_TOPIC,
            payload  = message,
            hostname = MQTT_BROKER,
            port     = MQTT_PORT
        )
        return True
    except Exception as e:
        print("MQTT error:", e)
        return False


# =============================================================================
# ROUTES
# =============================================================================
# A "route" is a URL path. When a browser visits that URL, Flask runs the
# function below it and returns a response.

@app.route("/")
def index():
    """
    The home page. Flask looks for index.html inside the templates/ folder
    and sends it to the browser.
    """
    return render_template("index.html")


@app.route("/color/<color_name>")
def set_color(color_name):
    """
    Handles a color command.
    URL example: http://192.168.1.42:5000/color/red
    The <color_name> part is captured from the URL automatically.

    Returns JSON so the browser can read the result without reloading the page.
    Example response: {"status": "ok", "color": "red"}
    """
    color = color_name.lower().strip()

    if color not in ALLOWED_COLORS:
        # Return an error if the color isn't recognized
        return jsonify({"status": "error", "message": "Unknown color: " + color}), 400

    success = send_mqtt(color)

    if success:
        return jsonify({"status": "ok", "color": color})
    else:
        return jsonify({"status": "error", "message": "MQTT publish failed"}), 500


@app.route("/custom", methods=["POST"])
def custom_color():
    """
    STRETCH GOAL ROUTE: Accepts a custom RGB color from the browser.
    The browser sends JSON like: {"r": 255, "g": 128, "b": 0}
    This route formats it as "rgb:255,128,0" and sends it to the ESP32.

    NOTE: For this to work, you also need to handle "rgb:..." in main.py!
    See the stretch goal section in the student instructions.
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON body"}), 400

    try:
        r = int(data.get("r", 0))
        g = int(data.get("g", 0))
        b = int(data.get("b", 0))
        # Clamp values to 0-255
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid RGB values"}), 400

    message = "rgb:%d,%d,%d" % (r, g, b)
    success = send_mqtt(message)

    if success:
        return jsonify({"status": "ok", "message": message})
    else:
        return jsonify({"status": "error", "message": "MQTT publish failed"}), 500


# =============================================================================
# START THE SERVER
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("LED Controller Web Server")
    print("Open your browser and go to:")
    print("  http://localhost:5000  (on this Pi)")
    print("  http://<your-pi-ip>:5000  (from another device)")
    print("Press Ctrl+C to stop the server.")
    print("=" * 50)

    # host="0.0.0.0" means "accept connections from any device on the network"
    # debug=True    means Flask will show helpful error messages (fine for camp)
    app.run(host="0.0.0.0", port=5000, debug=True)
