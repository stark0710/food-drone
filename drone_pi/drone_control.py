"""
Runs on the drone's onboard Raspberry Pi in production; also runnable
directly on a Windows/Mac/Linux laptop against ArduPilot SITL for testing,
since GPIO is optional (auto-skipped if RPi.GPIO isn't available/no hardware).

What it does, every poll cycle:
  1. Ask the backend: does this drone_id have an active assignment right now?
  2. If a NEW assignment just appeared:
       - blink the LED (skipped gracefully if no GPIO/Pi present)
       - upload a SINGLE-WAYPOINT mission to the Pixhawk via MAVLink

IMPORTANT - what this script deliberately does NOT do:
  - It does NOT arm the vehicle.
  - It does NOT change flight mode.
  - It does NOT command takeoff.
  It only uploads the destination as a waypoint and stops there. A human
  still has to physically switch to AUTO (or otherwise choose to fly) via
  RC or Mission Planner. This is intentional - covered in the conversation
  that led to this design, not an oversight.

SAFETY: before ever running this against a real Pixhawk (not SITL), confirm
in Mission Planner that geofence (Config -> Geofence) and failsafes
(Config -> Failsafe: RC loss, battery, GCS loss) are actually configured.
This script has no knowledge of your fence or failsafe setup and will
happily upload a waypoint outside a fence you haven't set.

Requires: pip install pymavlink requests
On a real Pi, also: pip install RPi.GPIO
"""
import time
import requests
from pymavlink import mavutil

# ---- Config - edit these for your setup ----
API_BASE_URL = "https://hubdrone-backend.onrender.com"
DRONE_ID = "drone_042"                  # must match this drone's printed QR sticker
POLL_INTERVAL_SECONDS = 3

# For SITL testing (this laptop, Mission Planner running Simulation tab):
MAVLINK_CONNECTION = "tcp:127.0.0.1:5762"
# For the real Pi talking to a physical Pixhawk over serial, swap to
# something like: "/dev/serial0" with baud=57600 (confirm against your
# firefighter drone's actual wiring/baud before using on real hardware).

CRUISE_ALTITUDE_M = 30.0  # AGL. Not derived from terrain/anything real yet -
                           # sanity-check this manually per site before flying.

LED_PIN = 17  # BCM numbering, GPIO17 = physical pin 11

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    LED_AVAILABLE = True
except (ImportError, RuntimeError):
    # Not on a Pi (e.g. running this on a laptop against SITL) - LED calls
    # below become no-ops instead of crashing the script.
    LED_AVAILABLE = False
    print("[info] RPi.GPIO not available - LED disabled, running poll+mission logic only")


def led_on():
    if LED_AVAILABLE:
        GPIO.output(LED_PIN, GPIO.HIGH)


def led_off():
    if LED_AVAILABLE:
        GPIO.output(LED_PIN, GPIO.LOW)


def led_blink(times=6, on_seconds=0.15, off_seconds=0.15):
    if not LED_AVAILABLE:
        return
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(on_seconds)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(off_seconds)


def connect_mavlink():
    print(f"[mavlink] connecting to {MAVLINK_CONNECTION} ...")
    conn = mavutil.mavlink_connection(MAVLINK_CONNECTION)
    conn.wait_heartbeat(timeout=15)
    print(f"[mavlink] heartbeat received (system {conn.target_system}, component {conn.target_component})")
    return conn


def upload_single_waypoint(conn, lat, lng, altitude_m):
    """
    Uploads a one-item mission: a single NAV_WAYPOINT at (lat, lng, altitude).
    Does NOT arm or change mode - just gets the waypoint onto the vehicle so
    a human can choose AUTO mode whenever they're ready to fly it.
    """
    conn.mav.mission_count_send(conn.target_system, conn.target_component, 1)

    msg = conn.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True, timeout=10)
    if msg is None:
        print("[mavlink] ERROR: vehicle never requested the mission item - upload failed")
        return False

    conn.mav.mission_item_int_send(
        conn.target_system,
        conn.target_component,
        0,                                          # seq
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
        0,                                          # current (0 = not current, don't auto-fly it)
        1,                                          # autocontinue
        0, 0, 0, 0,                                 # param1-4 (hold time, accept radius, pass radius, yaw)
        int(lat * 1e7),
        int(lng * 1e7),
        altitude_m,
    )

    ack = conn.recv_match(type="MISSION_ACK", blocking=True, timeout=10)
    if ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
        print(f"[mavlink] waypoint uploaded and accepted: {lat}, {lng} @ {altitude_m}m")
        return True
    else:
        print(f"[mavlink] ERROR: mission upload not accepted (ack={ack})")
        return False


def poll_once(conn, had_assignment: bool) -> bool:
    try:
        resp = requests.get(f"{API_BASE_URL}/drones/{DRONE_ID}/assignment", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[warn] poll failed: {e}")
        return had_assignment  # don't change state on a dropped poll

    now_has_assignment = data.get("has_assignment", False)

    if now_has_assignment and not had_assignment:
        dest_name = data.get("destination_hub_name", "unknown destination")
        lat, lng = data.get("destination_lat"), data.get("destination_lng")
        print(f"[assigned] order {data.get('order_id')} -> {dest_name} ({lat}, {lng})")
        led_blink()
        if lat is not None and lng is not None:
            upload_single_waypoint(conn, lat, lng, CRUISE_ALTITUDE_M)
        else:
            print("[warn] no destination coordinates on this order - skipping waypoint upload")
        led_on()
    elif now_has_assignment:
        led_on()
    else:
        if had_assignment:
            print("[cleared] assignment ended (delivered/cancelled)")
        led_off()

    return now_has_assignment


def main():
    conn = connect_mavlink()
    print(f"[poll] watching {API_BASE_URL}/drones/{DRONE_ID}/assignment every {POLL_INTERVAL_SECONDS}s")
    had_assignment = False
    try:
        while True:
            had_assignment = poll_once(conn, had_assignment)
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        led_off()
        if LED_AVAILABLE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()
