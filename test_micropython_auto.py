# Smart Pillbox V-3.8 - automatic staged test for ESP32 MicroPython
# Board LED: GPIO2 (change STATUS_LED_PIN if your board uses another pin)
# Test order: power GPIO states -> buzzer -> SV1 -> SV2 -> SV3 -> HX711 -> sensor inputs
# During test: board LED flashes quickly. PASS: LED stays ON. FAIL: LED flashes slowly.
# Safety: use current-limited 5 V; do not connect USB and external 5 V together.
# TDS GPIO5 is tested only as a digital input because GPIO5 is not an ADC pin.

from machine import Pin, PWM
import time

STATUS_LED_PIN = 2
SERVO_PINS = (25, 26, 27)
SERVO_NAMES = ("SV1", "SV2", "SV3")
BUZZER_Q2_PIN = 15
BUZZER_RETURN_PIN = 32
PIR_PIN = 23
TDS_DIGITAL_PIN = 5
HX711_SCK = 18
HX711_DOUT = 19

AUTO_RUN_ON_BOOT = True
SERVO_PULSE_US = 1500
SERVO_TEST_MS = 300
BUZZER_TEST_MS = 150

led = Pin(STATUS_LED_PIN, Pin.OUT, value=0)
servos = [PWM(Pin(p), freq=50, duty_ns=0) for p in SERVO_PINS]
buzzer_q2 = Pin(BUZZER_Q2_PIN, Pin.OUT, value=0)
buzzer_return = Pin(BUZZER_RETURN_PIN, Pin.OUT, value=1)
pir = Pin(PIR_PIN, Pin.IN)
tds_digital = Pin(TDS_DIGITAL_PIN, Pin.IN)
hx_sck = Pin(HX711_SCK, Pin.OUT, value=0)
hx_dout = Pin(HX711_DOUT, Pin.IN)


def safe_stop():
    for s in servos:
        s.duty_ns(0)
    buzzer_q2.value(0)
    buzzer_return.value(1)


def led_test_flash():
    led.value(not led.value())


def led_fail():
    led.value(0)
    while True:
        led.value(1)
        time.sleep_ms(150)
        led.value(0)
        time.sleep_ms(850)


def buzzer_test():
    print("TEST 1: buzzer")
    # Current schematic: Q2 ON plus GPIO32 LOW makes BZ1 conduct.
    buzzer_return.value(1)
    buzzer_q2.value(1)
    time.sleep_ms(10)
    buzzer_return.value(0)
    time.sleep_ms(BUZZER_TEST_MS)
    buzzer_return.value(1)
    buzzer_q2.value(0)
    print("  electrical sequence complete; confirm sound by ear")
    return True


def servo_test(index):
    print("TEST: {}".format(SERVO_NAMES[index]))
    for i, s in enumerate(servos):
        s.duty_ns(0)
    servos[index].duty_ns(SERVO_PULSE_US * 1000)
    time.sleep_ms(SERVO_TEST_MS)
    servos[index].duty_ns(0)
    print("  PWM sequence complete; confirm movement mechanically")
    return True


def hx711_read(timeout_ms=500):
    start = time.ticks_ms()
    while hx_sck.value() == 0 and hx_dout.value() == 1:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None
    value = 0
    for _ in range(24):
        hx_sck.value(1)
        value = (value << 1) | hx_dout.value()
        hx_sck.value(0)
    hx_sck.value(1)
    hx_sck.value(0)
    if value & 0x800000:
        value -= 1 << 24
    return value


def automatic_test():
    safe_stop()
    led.value(0)
    print("=== Smart Pillbox V-3.8 AUTOMATIC TEST ===")
    print("LED flashing = test in progress")
    print("WARNING: BZ1 current returns through GPIO32; use current limiting")

    # Give the power rail time to settle.
    for _ in range(5):
        led_test_flash()
        time.sleep_ms(100)

    passed = True
    passed = buzzer_test() and passed
    for i in range(3):
        passed = servo_test(i) and passed
        led_test_flash()

    print("TEST: HX711")
    hx_values = []
    for _ in range(3):
        value = hx711_read()
        if value is None:
            print("  FAIL: HX711 timeout; check 3V3/GND/DOUT19/SCK18")
            passed = False
            break
        hx_values.append(value)
        time.sleep_ms(80)
    if hx_values:
        print("  PASS: raw samples", hx_values)

    print("TEST: sensor input levels")
    print("  PIR GPIO23 =", pir.value())
    print("  TDS GPIO5 digital level =", tds_digital.value(), "(not ADC)")
    print("  Sensor level test is informational; no sensor state is forced.")

    safe_stop()
    if passed:
        led.value(1)
        print("=== TEST PASS: LED ON ===")
        print("Confirm buzzer sound and servo motion manually.")
    else:
        print("=== TEST FAIL: LED slow flash ===")
        led_fail()


def manual_console():
    print("Commands: auto, beep, sv1, sv2, sv3, hx, status, stop")
    while True:
        try:
            parts = input("pillbox> ").strip().lower().split()
            if not parts:
                continue
            if parts[0] == "auto":
                automatic_test()
            elif parts[0] == "beep":
                buzzer_test()
            elif parts[0] in ("sv1", "sv2", "sv3"):
                servo_test(int(parts[0][-1]) - 1)
            elif parts[0] == "hx":
                print("HX711 raw:", hx711_read())
            elif parts[0] == "status":
                print("PIR", pir.value(), "TDS-digital", tds_digital.value(),
                      "HX711-DOUT", hx_dout.value())
            elif parts[0] == "stop":
                safe_stop()
                led.value(0)
            else:
                print("unknown command")
        except Exception as exc:
            safe_stop()
            led.value(0)
            print("ERROR:", exc)


safe_stop()
if AUTO_RUN_ON_BOOT:
    # LED flashing and test start automatically after reset.
    automatic_test()
else:
    led.value(0)
manual_console()
