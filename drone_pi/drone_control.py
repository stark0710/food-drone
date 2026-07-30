"""
Runs on the drone's onboard Raspberry Pi in production; also runnable
directly on a Windows/Mac/Linux laptop against ArduPilot SITL for testing,
since GPIO is optional (auto-skipped if RPi.GPIO isn't available/no hardware).

FLIGHT LIFECYCLE (per assignment):
  1. Poll backend for a new assignment.
  2. On a new assignment: upload a 3-item OUTBOUND mission
     (TAKEOFF -> WAYPOINT -> LAND at the destination).
  3. If AUTO_LAUNCH_OUTBOUND_ENABLED (default True): the Pi itself arms and
     switches to AUTO immediately - fully autonomous, no human involved.
     Set this False to go back to the original design where a human must
     arm + switch to AUTO manually via RC or Mission Planner.
  4. Once armed+AUTO is detected (however it happened) -> tell the backend
     the order is "in_flight".
  5. Once the vehicle disarms after that (i.e. it landed at the
     destination) -> tell the backend the order is "delivered", then wait
     UNLOAD_DWELL_SECONDS (simulates/allows time for unloading).
  6. If AUTO_RETURN_ENABLED (default True): arm and switch to ArduCopter's
     native RTL mode - the flight controller handles climb-out, navigate
     home, descent, and landing entirely on its own using the home
     position it recorded automatically at first arm. No mission upload or
     coordinate tracking needed from this script for the return leg at all.
  7. Once it disarms again (back home) -> ready for the next assignment.

>>> SAFETY - READ BEFORE RUNNING ON REAL HARDWARE <<<
With both AUTO_LAUNCH_OUTBOUND_ENABLED and AUTO_RETURN_ENABLED True (the
default), this script arms and flies a real aircraft with ZERO human
involvement at any point in the round trip - a bigger step than the
original design, where at minimum a human had to physically launch the
outbound leg. Before ever running this against a real Pixhawk:
  - Confirm geofence is configured and enabled (Config -> Geofence).
  - Confirm failsafes are configured (Config -> Failsafe: RC loss, battery,
    GCS loss, EKF) so a bad leg fails safe instead of just flying off.
  - Test the entire round trip repeatedly in SITL first.
  - Consider keeping a human with a transmitter in RC-override range for
    early real-world flights even though the software no longer requires
    one.
  - The re-arm/re-launch moment after landing at a destination (whether
    outbound auto-launch or the return leg) is the highest-risk point in
    this whole design - nothing here confirms the area around the landed
    aircraft is actually clear of people before it takes off again. A
    fixed dwell timer (UNLOAD_DWELL_SECONDS) is not a real safety check;
    for anything beyond SITL testing, that needs to become an actual
    clear-to-launch confirmation (a physical button, a camera check, etc.),
    not just "enough seconds have passed."
This script has no knowledge of your fence/failsafe setup and will happily
arm and fly with either flag True even if you haven't configured either.

Requires: pip install pymavlink requests
On a real Pi, also: pip install RPi.GPIO
"""
import time
import requests
from pymavlink import mavutil


def ts():
    """HH:MM:SS timestamp prefix so log lines show real elapsed time between
    events - without this, a mission that took 6 real minutes and one that
    took 6 seconds look identical in the console."""
    return time.strftime("%H:%M:%S")

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

# Set False to require a human to arm+AUTO the OUTBOUND leg (original
# design). Set True and the Pi arms and launches the outbound leg itself
# the moment a mission uploads successfully - no human involved at all,
# for either leg. Read the safety note above before setting this True
# against real hardware.
AUTO_LAUNCH_OUTBOUND_ENABLED = True

# Set False to keep the return leg manual too (mission gets uploaded, but
# the Pi will wait for a human to arm it, same as the outbound leg).
AUTO_RETURN_ENABLED = True

LED_PIN = 17  # BCM numbering, GPIO17 = physical pin 11

# ArduCopter custom_mode numbers (from the ArduCopter flight-mode enum,
# not a general MAVLink constant).
COPTER_MODE_AUTO = 3
COPTER_MODE_GUIDED = 4
COPTER_MODE_RTL = 6
LAND_ITEM_SEQ = 3  # index of the LAND command in the fixed 4-item mission
                    # built by upload_mission() (0=home placeholder,
                    # 1=takeoff, 2=waypoint, 3=land)
DESTINATION_WAYPOINT_SEQ = LAND_ITEM_SEQ - 1  # the actual destination
                    # coordinates. ArduCopter sends MISSION_ITEM_REACHED
                    # for regular NAV_WAYPOINT items (arrival-radius based)
                    # but NOT for NAV_LAND, which is a continuous descent
                    # with no "reached" event of its own - waiting on
                    # LAND_ITEM_SEQ here would never fire even on a fully
                    # successful delivery. The waypoint immediately before
                    # LAND is what actually confirms arrival at the
                    # destination; the subsequent LAND+disarm is just the
                    # descent, confirmed separately via the disarm itself.

# Number of consecutive disarmed heartbeats required before a "disarmed"
# transition is treated as real. Heartbeats arrive roughly 1/sec, so 3
# means a landing/abort is confirmed within ~2-3s - long enough to reject
# a single flaky/out-of-order packet, short enough not to meaningfully
# delay reporting a genuine delivery.
DISARM_CONFIRM_COUNT = 3

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    LED_AVAILABLE = True
except (ImportError, RuntimeError):
    LED_AVAILABLE = False
    print(f"[{ts()}] [info] RPi.GPIO not available - LED disabled, running poll+mission logic only")


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
    print(f"[{ts()}] [mavlink] connecting to {MAVLINK_CONNECTION} ...")
    conn = mavutil.mavlink_connection(MAVLINK_CONNECTION)
    conn.wait_heartbeat(timeout=15)
    print(f"[{ts()}] [mavlink] heartbeat received (system {conn.target_system}, component {conn.target_component})")
    return conn


def upload_mission(conn, lat, lng, altitude_m):
    """
    Uploads a 4-item mission: a placeholder at seq 0, then NAV_TAKEOFF to
    altitude_m, NAV_WAYPOINT at the given coordinates, then NAV_LAND at the
    same coordinates.

    IMPORTANT: seq 0 in the ArduPilot/MAVLink mission protocol is always
    treated as the home-position placeholder - whatever command you put
    there gets silently discarded/ignored by the flight controller, which
    substitutes its own recorded home info instead. Real commands have to
    start at seq 1. An earlier version of this script put NAV_TAKEOFF at
    seq 0, which the FC quietly dropped - the mission still "uploaded and
    accepted" (no error), but the takeoff command was gone, which is why
    AUTO mode refused to arm ("Missing Takeoff Cmd") even though the
    upload appeared to succeed.
    """
    items = [
        # (seq, frame, command, current, autocontinue, p1, p2, p3, p4, x, y, z)
        (0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
         0, 1, 0, 0, 0, 0, 0, 0, 0),  # seq 0 placeholder - content ignored by the FC, home info substituted
        (1, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
         0, 1, 0, 0, 0, 0, 0, 0, altitude_m),
        (2, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
         0, 1, 0, 0, 0, 0, int(lat * 1e7), int(lng * 1e7), altitude_m),
        (3, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, mavutil.mavlink.MAV_CMD_NAV_LAND,
         0, 1, 0, 0, 0, 0, int(lat * 1e7), int(lng * 1e7), 0),
    ]

    conn.mav.mission_count_send(conn.target_system, conn.target_component, len(items))

    for _ in range(len(items)):
        msg = conn.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True, timeout=10)
        if msg is None:
            print(f"[{ts()}] [mavlink] ERROR: vehicle stopped requesting mission items - upload failed")
            return False
        seq = msg.seq
        conn.mav.mission_item_int_send(conn.target_system, conn.target_component, *items[seq])

    ack = conn.recv_match(type="MISSION_ACK", blocking=True, timeout=10)
    if ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
        print(f"[{ts()}] [mavlink] mission uploaded and accepted: takeoff to {altitude_m}m -> {lat}, {lng} -> land")
        return True
    else:
        print(f"[{ts()}] [mavlink] ERROR: mission upload not accepted (ack={ack})")
        return False


def launch_return_leg(conn, altitude_m):
    """
    ArduCopter refuses to arm directly into RTL mode from the ground
    ("Arm: RTL mode not armable") - RTL only makes sense as a mode to
    switch INTO while already flying, not as a takeoff mode. An earlier
    version of this script called arm_and_set_mode(conn, COPTER_MODE_RTL,
    ...) for the return leg, which always got rejected for this reason -
    the vehicle just sat there disarmed at the destination forever.

    Correct sequence: arm in GUIDED, command an explicit takeoff, wait for
    it to actually leave the ground, THEN switch to RTL. Once in RTL,
    ArduCopter handles the climb-to-RTL_ALT, navigate home, descent, and
    landing on its own.
    """
    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        COPTER_MODE_GUIDED,
    )
    time.sleep(1)

    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0,
    )
    arm_ack = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if not (arm_ack and arm_ack.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM
            and arm_ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED):
        print(f"[{ts()}] [mavlink] *** ARM REJECTED for return leg (GUIDED): ack={arm_ack} - "
              f"check STATUSTEXT above for the PreArm reason ***")
        return False
    print(f"[{ts()}] [mavlink] return leg armed in GUIDED")

    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, altitude_m,
    )
    takeoff_ack = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if not (takeoff_ack and takeoff_ack.command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
            and takeoff_ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED):
        print(f"[{ts()}] [mavlink] *** TAKEOFF REJECTED for return leg: ack={takeoff_ack} ***")
        return False
    print(f"[{ts()}] [mavlink] return-leg takeoff accepted, climbing to {altitude_m}m before switching to RTL")

    # Give it a few seconds to actually leave the ground before handing off
    # to RTL - switching mode the instant takeoff is merely ACCEPTED (not
    # yet executed) can race with the climb.
    time.sleep(5)

    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        COPTER_MODE_RTL,
    )
    print(f"[{ts()}] [mavlink] return leg: mode set to RTL - ArduCopter will navigate home and land on its own")
    return True


def arm_and_set_mode(conn, mode_id: int, mode_name: str):
    """Arms the vehicle and switches it to the given custom_mode. Used for
    both outbound auto-launch (AUTO) and return (RTL), depending on which
    caller invokes it and whether the relevant *_ENABLED flag allows it.

    Returns True only if the vehicle actually ACKed the arm command with
    MAV_RESULT_ACCEPTED. Previously this function fired the arm command and
    assumed it worked - if ArduCopter's PreArm checks rejected it (e.g. a
    geofence breach because the vehicle is now sitting at the destination
    hub, far from where the fence is centered), the script had no way of
    knowing and would just sit there forever waiting for an armed
    heartbeat that was never coming.
    """
    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id,
    )
    time.sleep(1)
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0,
    )
    ack = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if ack and ack.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
        if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            print(f"[{ts()}] [mavlink] mode set to {mode_name}, arm ACCEPTED")
            return True
        else:
            print(f"[{ts()}] [mavlink] *** ARM REJECTED for {mode_name}: MAV_RESULT={ack.result} - "
                  f"check the [vehicle] STATUSTEXT line just above/below this for the specific PreArm "
                  f"reason (common cause: geofence enabled and vehicle is outside it at this location) ***")
            return False
    else:
        print(f"[{ts()}] [mavlink] *** ARM command got no ACK within 5s for {mode_name} - "
              f"connection issue or vehicle unresponsive ***")
        return False


def notify_backend(path):
    try:
        resp = requests.post(f"{API_BASE_URL}/drones/{DRONE_ID}/{path}", timeout=5)
        if resp.status_code >= 400:
            print(f"[{ts()}] [warn] backend rejected {path}: {resp.status_code} {resp.text}")
        else:
            print(f"[{ts()}] [backend] reported {path}")
    except requests.RequestException as e:
        print(f"[{ts()}] [warn] failed to report {path}: {e}")


def poll_assignment(had_assignment: bool):
    """Returns (now_has_assignment, new_assignment_data_or_None)."""
    try:
        resp = requests.get(f"{API_BASE_URL}/drones/{DRONE_ID}/assignment", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[{ts()}] [warn] poll failed: {e}")
        return had_assignment, None

    now_has_assignment = data.get("has_assignment", False)
    is_new = now_has_assignment and not had_assignment
    return now_has_assignment, (data if is_new else None)


class FlightState:
    """Tracks armed/mode edges across heartbeats so we only act once per
    transition, plus which leg of the round trip we're on."""

    def __init__(self):
        self.armed_prev = False
        self.leg = None  # None | "outbound" | "awaiting_return" | "return"
        self.dwell_until = None
        self.last_progress_print = 0.0
        self.reached_destination = False  # was MISSION_ITEM_REACHED seen for the destination waypoint?
        self.destination_item_seq = None  # set by main() right after each upload_mission() call
        self._disarmed_streak = 0      # consecutive heartbeats reporting disarmed since last armed

    def handle_mission_item_reached(self, msg):
        if self.leg not in ("outbound", "return"):
            return
        print(f"[{ts()}] [progress] leg={self.leg} mission item reached: seq={msg.seq}")
        if self.destination_item_seq is not None and msg.seq == self.destination_item_seq:
            self.reached_destination = True

    def handle_statustext(self, msg):
        # ArduPilot pushes fence breaches, failsafe triggers, arming
        # failures etc. here as free text - this is the message type that
        # will actually say *why* a leg went to RTL early (e.g. "Failsafe:
        # GCS", "Fence breached"). Always worth printing, not just on error.
        text = msg.text if isinstance(msg.text, str) else msg.text.decode("utf-8", "ignore")
        print(f"[{ts()}] [vehicle] {text.rstrip(chr(0))}")

    def handle_nav_controller_output(self, msg):
        """Prints periodic distance-to-waypoint/altitude while airborne, so
        the log actually shows the vehicle covering ground over time instead
        of just an arm event and a disarm event with nothing in between -
        that gap is what made an earlier run look like it "teleported"."""
        if self.leg not in ("outbound", "return"):
            return
        now = time.time()
        if now - self.last_progress_print < 5:
            return
        self.last_progress_print = now
        print(f"[{ts()}] [progress] leg={self.leg} wp_dist={msg.wp_dist}m alt_error={msg.alt_error:.1f}m")

    def handle_heartbeat(self, conn, msg):
        armed_now = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

        if armed_now:
            self._disarmed_streak = 0
            if not self.armed_prev:
                if self.leg == "outbound":
                    print(f"[{ts()}] [flight] outbound leg armed/launched")
                    notify_backend("report-in-flight")
                elif self.leg == "return":
                    print(f"[{ts()}] [flight] return leg armed/launched")
            self.armed_prev = True
            return

        # armed_now is False from here on. Don't act on a single disarmed
        # reading - a solitary flaky/out-of-order heartbeat right after
        # arming was previously enough to make the script think the
        # vehicle had landed 2 seconds into a 3-minute flight, even though
        # ArduCopter kept flying the real mission to completion regardless.
        # Require DISARM_CONFIRM_COUNT consecutive disarmed heartbeats
        # before treating it as real.
        if self.armed_prev:
            self._disarmed_streak += 1
            if self._disarmed_streak < DISARM_CONFIRM_COUNT:
                return  # not confirmed yet, wait for more heartbeats

            if self.leg == "outbound":
                if self.reached_destination:
                    print(f"[{ts()}] [flight] landed at destination - delivery complete")
                    notify_backend("report-delivered")
                    self.dwell_until = time.time() + UNLOAD_DWELL_SECONDS
                    self.leg = "awaiting_return"
                else:
                    # Disarmed without ever reaching the destination waypoint
                    # - this is an abort (failsafe RTL, fence breach, manual
                    # override, etc.), not a delivery. Do NOT report
                    # delivered and do NOT auto-relaunch anything: check the
                    # [vehicle] STATUSTEXT lines above for the actual reason,
                    # fix it, then dispatch a fresh assignment once sorted.
                    print(f"[{ts()}] [flight] *** ABORT: disarmed without reaching destination "
                          f"(never saw waypoint {self.destination_item_seq} reached). Check STATUSTEXT "
                          f"lines above for the failsafe/fence reason. NOT reporting delivered, "
                          f"NOT auto-relaunching. ***")
                    self.leg = None
            elif self.leg == "return":
                print(f"[{ts()}] [flight] landed back at home - round trip complete")
                self.leg = None

            self.armed_prev = False

    def maybe_launch_return(self, conn):
        if self.leg != "awaiting_return" or self.dwell_until is None:
            return
        if time.time() < self.dwell_until:
            return
        if not AUTO_RETURN_ENABLED:
            print(f"[{ts()}] [flight] awaiting return - AUTO_RETURN_ENABLED=False, waiting for human to arm+RTL manually")
            self.leg = "return"
            self.dwell_until = None
            return
        # RTL is a built-in ArduCopter mode - the flight controller already
        # knows its own home position (recorded automatically at first arm)
        # and handles climb-out, navigate-home, descent, and landing on its
        # own. No mission upload needed for the return leg.
        if launch_return_leg(conn, CRUISE_ALTITUDE_M):
            self.leg = "return"
            self.dwell_until = None
        else:
            # Arm/takeoff was rejected (see the ARM/TAKEOFF REJECTED /
            # STATUSTEXT lines above for why - most likely PreArm/geofence).
            # Stay in "awaiting_return" and retry in 10s rather than giving
            # up silently and leaving the vehicle stranded at the destination.
            print(f"[{ts()}] [flight] return-leg launch failed, will retry in 10s")
            self.dwell_until = time.time() + 10


def main():
    conn = connect_mavlink()
    print(f"[{ts()}] [poll] watching {API_BASE_URL}/drones/{DRONE_ID}/assignment every {POLL_INTERVAL_SECONDS}s")
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
                    print(f"[{ts()}] [assigned] order {new_data.get('order_id')} -> {dest_name} ({lat}, {lng})")
                    led_blink()
                    if lat is not None and lng is not None:
                        if upload_mission(conn, lat, lng, CRUISE_ALTITUDE_M):
                            state.leg = "outbound"
                            state.destination_item_seq = DESTINATION_WAYPOINT_SEQ
                            state.reached_destination = False
                            if AUTO_LAUNCH_OUTBOUND_ENABLED:
                                if not arm_and_set_mode(conn, COPTER_MODE_AUTO, "AUTO"):
                                    print(f"[{ts()}] [warn] outbound arm was rejected - mission is uploaded "
                                          f"and waiting, but nothing will launch until this is armed "
                                          f"(manually via Mission Planner, or fix the PreArm issue and "
                                          f"this will still be picked up next time you retry)")
                            else:
                                print(f"[{ts()}] [flight] mission uploaded - waiting for human to arm+AUTO (AUTO_LAUNCH_OUTBOUND_ENABLED=False)")
                    else:
                        print(f"[{ts()}] [warn] no destination coordinates on this order - skipping waypoint upload")
                    led_on()
                elif not had_assignment:
                    led_off()

            msg = conn.recv_match(
                type=["HEARTBEAT", "NAV_CONTROLLER_OUTPUT", "MISSION_ITEM_REACHED", "STATUSTEXT"],
                blocking=True, timeout=0.5,
            )
            if msg is not None:
                t = msg.get_type()
                if t == "HEARTBEAT":
                    state.handle_heartbeat(conn, msg)
                elif t == "NAV_CONTROLLER_OUTPUT":
                    state.handle_nav_controller_output(msg)
                elif t == "MISSION_ITEM_REACHED":
                    state.handle_mission_item_reached(msg)
                elif t == "STATUSTEXT":
                    state.handle_statustext(msg)

            state.maybe_launch_return(conn)

    except KeyboardInterrupt:
        pass
    finally:
        led_off()
        if LED_AVAILABLE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()