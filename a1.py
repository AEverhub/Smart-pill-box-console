import bluetooth
import time
from machine import Pin
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

class ESP32PillBox:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        
        ((self.handle_rx, self.handle_tx),) = self.ble.gatts_register_services((UART_SERVICE,))
        self.connections = set()
        
        self.cup_motor = Pin(25, Pin.OUT, value=1)
        self.slot_pins = [Pin(pin_num, Pin.IN, Pin.PULL_UP) for pin_num in [18, 19, 23, 26, 27, 5, 21, 32, 15]]
        
        self.device_enabled = False
        self.alarm_times = [""] * 9
        
        self._advertise()

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self.connections.remove(conn_handle)
            self._advertise()

        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self.handle_rx:
                rx_bytes = self.ble.gatts_read(self.handle_rx)
                msg = rx_bytes.decode('utf-8').strip()
                self.process_command(msg)

    def process_command(self, msg):
        if msg.startswith("DEV_ENABLE:"):
            state = msg.split(":")[1]
            self.device_enabled = (state == "1")
            
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

    def send_notify(self, text):
        for conn_handle in self.connections:
            self.ble.gatts_notify(conn_handle, self.handle_tx, text + "\n")

    def _advertise(self):
        name = b'Smart pill box\xe6\x99\xba\xe6\x85\xa7\xe8\x97\xa5\xe7\x9b\x92'
        adv_data = bytearray(b'\x02\x01\x06') + bytearray([len(name) + 1, 0x09]) + name
        self.ble.gap_advertise(100000, adv_data=adv_data)

    def run(self):
        while True:
            if self.connections and self.device_enabled:
                statuses = [str(pin.value()) for pin in self.slot_pins]
                status_str = "SLOT_STATUS:" + ",".join(statuses)
                self.send_notify(status_str)
            time.sleep(2)

if __name__ == "__main__":
    box = ESP32PillBox()
    box.run()
