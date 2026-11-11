import bluetooth
import time
from machine import Pin, PWM
from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

SERVICE_UUID = bluetooth.UUID("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
RX_UUID = bluetooth.UUID("beb5483e-36e1-4688-b7f5-ea07361b26a8")
TX_UUID = bluetooth.UUID("1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e")

_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

UART_SERVICE = (
    SERVICE_UUID,
    (
        (RX_UUID, _FLAG_WRITE),
        (TX_UUID, _FLAG_NOTIFY),
    ),
)

# ===== 腳位 =====
CUP_MOTOR_PIN = 33
SLOT_PINS = [18, 19, 23, 4, 14, 5, 21, 32, 15]
SERVO_PINS = [25, 26, 27]


class Servo:
    """標準 180° 伺服馬達，50Hz，脈寬 0.5~2.5ms 對應 0~180°"""
    def __init__(self, pin_num):
        self.pwm = PWM(Pin(pin_num), freq=50, duty_u16=0)
        self.angle = 0
        self.release_at = 0
        self.move(0)

    def move(self, angle):
        angle = max(0, min(180, angle))
        pulse_ms = 0.5 + angle / 180 * 2.0
        self.pwm.duty_u16(int(pulse_ms / 20 * 65535))
        self.angle = angle
        self.release_at = time.ticks_add(time.ticks_ms(), 600)

    def toggle(self):
        self.move(90 if self.angle == 0 else 0)

    def update(self):
        # 轉到位後釋放訊號，避免抖動與發熱
        if self.release_at and time.ticks_diff(time.ticks_ms(), self.release_at) >= 0:
            self.pwm.duty_u16(0)
            self.release_at = 0


class ESP32PillBox:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        ((self.handle_rx, self.handle_tx),) = self.ble.gatts_register_services((UART_SERVICE,))
        self.connections = set()

        self.cup_motor = Pin(CUP_MOTOR_PIN, Pin.OUT, value=1)
        self.slot_pins = [Pin(p, Pin.IN, Pin.PULL_UP) for p in SLOT_PINS]
        self.servos = [Servo(p) for p in SERVO_PINS]

        self.device_enabled = False
        self.alarm_times = [""] * 9

        self._advertise()

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self.connections.discard(conn_handle)
            self._advertise()

        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self.handle_rx:
                rx_bytes = self.ble.gatts_read(self.handle_rx)
                msg = rx_bytes.decode('utf-8').strip()
                self.process_command(msg)

    def process_command(self, msg):
        if msg.startswith("DEV_ENABLE:"):
            self.device_enabled = (msg.split(":")[1] == "1")

        elif msg.startswith("CUP_CTRL:"):
            action = msg.split(":")[1]
            if action == "LOCK":
                self.cup_motor.value(1)
            elif action == "UNLOCK":
                self.cup_motor.value(0)

        elif msg.startswith("SET_ALARMS:"):
            raw_times = msg.replace("SET_ALARMS:", "").split(",")
            if len(raw_times) == 9:
                self.alarm_times = raw_times

        elif msg.startswith("SERVO:"):
            # SERVO:1:90 轉到90度 / SERVO:1:0 回0度 / SERVO:1:STEP 在0與90間切換
            parts = msg.split(":")
            if len(parts) == 3:
                try:
                    idx = int(parts[1]) - 1
                    if 0 <= idx < len(self.servos):
                        if parts[2] == "STEP":
                            self.servos[idx].toggle()
                        else:
                            self.servos[idx].move(int(parts[2]))
                        self.send_notify("SERVO_OK:%d:%d" % (idx + 1, self.servos[idx].angle))
                except ValueError:
                    pass

    def send_notify(self, text):
        data = (text + "\n").encode()
        for conn_handle in self.connections:
            try:
                self.ble.gatts_notify(conn_handle, self.handle_tx, data)
            except OSError:
                pass

    def _advertise(self):
        name = b'Smart pill box\xe6\x99\xba\xe6\x85\xa7\xe8\x97\xa5\xe7\x9b\x92'
        adv_data = bytearray(b'\x02\x01\x06') + bytearray([len(name) + 1, 0x09]) + name
        self.ble.gap_advertise(100000, adv_data=adv_data)

    def run(self):
        last_status = 0
        while True:
            for s in self.servos:
                s.update()

            now = time.ticks_ms()
            if time.ticks_diff(now, last_status) >= 2000:
                last_status = now
                if self.connections and self.device_enabled:
                    statuses = [str(p.value()) for p in self.slot_pins]
                    self.send_notify("SLOT_STATUS:" + ",".join(statuses))

            time.sleep_ms(50)


if __name__ == "__main__":
    box = ESP32PillBox()
    box.run()