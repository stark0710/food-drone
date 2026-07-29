"""
Runs on the drone's onboard Raspberry Pi in production; also runnable
directly on a Windows/Mac/Linux laptop against ArduPilot SITL for testing,
since GPIO is optional (auto-skipped if RPi.GPIO isn't available/no hardware).

FLIGHT LIFECYCLE (per assignment):
  1. Poll backend for a new assignment.
  2. On a new assignment: upload a 3-item OUTBOUND mission
     (TAKEOFF -> WAYPOINT -> LAND at the destination).
  3. Wait for a HUMAN to arm + switch to AUTO (via RC or Mission Planner).
     This script still does NOT arm or change mode for the outbound leg -
     someone has to physically launch it. That part of the original design
     is unchanged.
  4. Once armed+AUTO is detected -> tell the backend the order is "in_flight".
  5. Once the vehicle disarms after that (i.e. it landed at the
     destination) -> tell the backend the order is "delivered", then wait
     UNLOAD_DWELL_SECONDS (simulates/allows time for unloading).
  6. Build a return mission back to the recorded home position
     (TAKEOFF -> WAYPOINT -> LAND), upload it, and this time the Pi ITSELF
     arms and switches to AUTO -> fully autonomous return, no human input.
  7. Once it disarms again (back home) -> ready for the next assignment.

>>> SAFETY - READ BEFORE RUNNING ON REAL HARDWARE <<<
Step 6 is a real change from the earlier version of this script, which
never armed or changed mode under any circumstances. From here on, the Pi
will autonomously arm a real aircraft and fly it home with no one holding
a transmitter. Before ever enabling AUTO_RETURN_ENABLED against a physical
Pixhawk:
  - Confirm geofence is configured and enabled (Config -> Geofence).
  - Confirm failsafes are configured (Config -> Failsafe: RC loss, battery,
    GCS loss, EKF) so a bad return leg fails safe instead of just flying
    off.
  - Test the entire round trip repeatedly in SITL first.
  - Consider keeping a human with a transmitter in RC-override range for
    early real-world flights even though the software no longer requires
    one.
This script has no knowledge of your fence/failsafe setup and will happily
arm and fly home even if you haven't configured either.

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
# drone's actual wiring/baud before using on real hardware).

CRUISE_ALTITUDE_M = 30.0  # AGL. Not derived from terrain/anything real yet -
                           # sanity-check this manually per site before flying.

UNLOAD_DWELL_SECONDS = 15  # time to sit landed at the destination before
                            # auto-launching the return leg. Tune to how
                            # long unloading actually takes.

# Set False to keep the return leg manual too (mission gets uploaded, but
# the Pi will wait for a human to arm it, same as the outbound leg).
AUTO_RETURN_ENABLED = True

LED_PIN = 17  # BCM numbering, GPIO17 = physical pin 11

# ArduCopter custom_mode numbers we care about (from the ArduCopter
# flight-mode enum, not a general MAVLink constant).
COPTER_MODE_AUTO = 3

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    LED_AVAILABLE = True
except (ImportError, RuntimeError):
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


def upload_mission(conn, lat, lng, altitude_m):
    """
    Uploads a 3-item mission: NAV_TAKEOFF to altitude_m, NAV_WAYPOINT at the
    given coordinates, then NAV_LAND at the same coordinates.

    The takeoff item is required, not optional - ArduCopter's AUTO mode
    refuses to arm from the ground ("Auto: Missing Takeoff Cmd") unless the
    first mission item is a takeoff command. The land item is required for
    the vehicle to actually touch down instead of loitering forever over
    the destination.
    """
    items = [
        # (seq, frame, command, current, autocontinue, p1, p2, p3, p4, x, y, z)
        (0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
         0, 1, 0, 0, 0, 0, 0, 0, altitude_m),
        (1, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
         0, 1, 0, 0, 0, 0, int(lat * 1e7), int(lng * 1e7), altitude_m),
        (2, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_LAND,
         0, 1, 0, 0, 0, 0, int(lat * 1e7), int(lng * 1e7), 0),
    ]

    conn.mav.mission_count_send(conn.target_system, conn.target_component, len(items))

    for _ in range(len(items)):
        msg = conn.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True, timeout=10)
        if msg is None:
            print("[mavlink] ERROR: vehicle stopped requesting mission items - upload failed")
            return False
        seq = msg.seq
        conn.mav.mission_item_int_send(conn.target_system, conn.target_component, *items[seq])

    ack = conn.recv_match(type="MISSION_ACK", blocking=True, timeout=10)
    if ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
        print(f"[mavlink] mission uploaded and accepted: takeoff to {altitude_m}m -> {lat}, {lng} -> land")
        return True
    else:
        print(f"[mavlink] ERROR: mission upload not accepted (ack={ack})")
        return False


def arm_and_start_auto(conn):
    """Autonomously arms the vehicle and switches it to AUTO. Only ever
    called for the RETURN leg - the outbound leg is still human-armed."""
    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        COPTER_MODE_AUTO,
    )
    time.sleep(1)
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0,
    )
    print("[mavlink] auto-return: mode set to AUTO, arm command sent")


def notify_backend(path):
    try:
        resp = requests.post(f"{API_BASE_URL}/drones/{DRONE_ID}/{path}", timeout=5)
        if resp.status_code >= 400:
            print(f"[warn] backend rejected {path}: {resp.status_code} {resp.text}")
        else:
            print(f"[backend] reported {path}")
    except requests.RequestException as e:
        print(f"[warn] failed to report {path}: {e}")


def poll_assignment(had_assignment: bool):
    """Returns (now_has_assignment, new_assignment_data_or_None)."""
    try:
        resp = requests.get(f"{API_BASE_URL}/drones/{DRONE_ID}/assignment", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[warn] poll failed: {e}")
        return had_assignment, None

    now_has_assignment = data.get("has_assignment", False)
    is_new = now_has_assignment and not had_assignment
    return now_has_assignment, (data if is_new else None)


class FlightState:
    """Tracks armed/mode edges across heartbeats so we only act once per
    transition, plus which leg of the round trip we're on."""

    def __init__(self):
        self.armed_prev = False
        self.leg = None  # None | "outbound" | "return"
        self.home_lat = None
        self.home_lng = None
        self.dwell_until = None

    def handle_heartbeat(self, conn, msg):
        armed_now = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

        if armed_now and not self.armed_prev:
            if self.leg == "outbound":
                print("[flight] outbound leg armed/launched")
                notify_backend("report-in-flight")
            elif self.leg == "return":
                print("[flight] return leg armed/launched")

        if (not armed_now) and self.armed_prev:
            if self.leg == "outbound":
                print("[flight] landed at destination - delivery complete")
                notify_backend("report-delivered")
                self.dwell_until = time.time() + UNLOAD_DWELL_SECONDS
                self.leg = "awaiting_return"
            elif self.leg == "return":
                print("[flight] landed back at home - round trip complete")
                self.leg = None

        self.armed_prev = armed_now

    def handle_home_position(self, msg):
        self.home_lat = msg.latitude / 1e7
        self.home_lng = msg.longitude / 1e7

    def maybe_launch_return(self, conn):
        if self.leg != "awaiting_return" or self.dwell_until is None:
            return
        if time.time() < self.dwell_until:
            return
        if self.home_lat is None:
            print("[warn] no HOME_POSITION captured yet - can't build return mission, retrying")
            return
        if not upload_mission(conn, self.home_lat, self.home_lng, CRUISE_ALTITUDE_M):
            print("[warn] return mission upload failed, will retry")
            return
        self.leg = "return"
        self.dwell_until = None
        if AUTO_RETURN_ENABLED:
            arm_and_start_auto(conn)
        else:
            print("[flight] return mission uploaded - waiting for human to arm (AUTO_RETURN_ENABLED=False)")


def main():
    conn = connect_mavlink()
    print(f"[poll] watching {API_BASE_URL}/drones/{DRONE_ID}/assignment every {POLL_INTERVAL_SECONDS}s")
    state = FlightState()
    had_assignment = False
    next_poll = 0.0

    try:
        while True:
            now = time.time()

            if now >= next_poll:
                had_assignment, new_data = poll_assignment(had_assignment)
                next_poll = now + POLL_INTERVAL_SECONDS
                if new_data is not None:
                    dest_name = new_data.get("destination_hub_name", "unknown destination")
                    lat, lng = new_data.get("destination_lat"), new_data.get("destination_lng")
                    print(f"[assigned] order {new_data.get('order_id')} -> {dest_name} ({lat}, {lng})")
                    led_blink()
                    if lat is not None and lng is not None:
                        if upload_mission(conn, lat, lng, CRUISE_ALTITUDE_M):
                            state.leg = "outbound"
                    else:
                        print("[warn] no destination coordinates on this order - skipping waypoint upload")
                    led_on()
                elif not had_assignment:
                    led_off()

            msg = conn.recv_match(type=["HEARTBEAT", "HOME_POSITION"], blocking=True, timeout=0.5)
            if msg is not None:
                if msg.get_type() == "HEARTBEAT":
                    state.handle_heartbeat(conn, msg)
                elif msg.get_type() == "HOME_POSITION":
                    state.handle_home_position(msg)

            state.maybe_launch_return(conn)

    except KeyboardInterrupt:
        pass
    finally:
        led_off()
        if LED_AVAILABLE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()
