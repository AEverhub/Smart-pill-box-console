from machine import Pin, disable_irq, enable_irq
import time

class HX711:
    def __init__(self, dt, sck):
        self.dt = Pin(dt, Pin.IN)
        self.sck = Pin(sck, Pin.OUT, value=0)
        self.offset = 0
        self.scale = 1

    def read_raw(self):
        t0 = time.ticks_ms()
        while self.dt.value():
            if time.ticks_diff(time.ticks_ms(), t0) > 1000:
                raise OSError("HX711 無回應，請檢查接線")
            time.sleep_ms(1)
        irq = disable_irq()        # 避免 BLE 中斷打斷時脈
        v = 0
        for _ in range(24):
            self.sck.value(1)
            self.sck.value(0)
            v = (v << 1) | self.dt.value()
        self.sck.value(1)          # 第 25 脈衝：通道 A、增益 128
        self.sck.value(0)
        enable_irq(irq)
        if v & 0x800000:
            v -= 1 << 24
        return v

    def read_avg(self, n=10):
        return sum(self.read_raw() for _ in range(n)) / n

    def tare(self):
        self.offset = self.read_avg(20)

    def grams(self):
        return (self.read_avg(5) - self.offset) / self.scale


hx = HX711(dt=16, sck=17)

print("歸零中，請讓秤上保持空的...")
hx.tare()

# 校正：先把 scale 設 1，放上已知重量（例如 100g），
# 讀到的數值 ÷ 100 就是 scale
hx.scale = 1
while True:
    print("原始差值: {:.0f}  =>  {:.1f} g".format(hx.read_avg(5) - hx.offset, hx.grams()))
    time.sleep_ms(500)