from machine import Pin, disable_irq, enable_irq
import time

# ===== 設定 =====
DT_PIN = 16
SCK_PIN = 17
FORCE_CALIBRATE = False    # 想重新校正時改成 True（需用 Thonny 的 Shell 操作）
SCALE_FILE = "scale.txt"


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
        irq = disable_irq()            # 避免中斷打斷時脈
        v = 0
        for _ in range(24):
            self.sck.value(1)
            self.sck.value(0)
            v = (v << 1) | self.dt.value()
        self.sck.value(1)              # 第 25 脈衝：通道 A、增益 128
        self.sck.value(0)
        enable_irq(irq)
        if v & 0x800000:
            v -= 1 << 24
        return v

    def read_avg(self, n=10):
        vals = sorted(self.read_raw() for _ in range(n))
        cut = n // 5                   # 去掉最高、最低各 20%
        vals = vals[cut:n - cut] if n >= 5 else vals
        return sum(vals) / len(vals)

    def tare(self, n=20):
        self.offset = self.read_avg(n)

    def grams(self, n=5):
        return (self.read_avg(n) - self.offset) / self.scale


def load_scale():
    try:
        with open(SCALE_FILE) as f:
            return float(f.read())
    except (OSError, ValueError):
        return None


def calibrate(hx):
    input("【校正】秤上保持空的，按 Enter 歸零...")
    hx.tare(30)
    print("歸零完成 offset =", hx.offset)

    known = float(input("輸入已知重量（克，例如 100）："))
    input("把重物輕放在上板中央，穩定後按 Enter...")
    time.sleep(1)

    raw = hx.read_avg(30) - hx.offset
    print("原始差值 =", raw)
    if abs(raw) < 100:
        raise RuntimeError("差值太小，荷重元幾乎沒反應，請檢查接線與機構")

    hx.scale = raw / known
    with open(SCALE_FILE, "w") as f:
        f.write(str(hx.scale))
    print("校正完成 scale =", hx.scale, "（已存檔）")
    input("請移開重物，按 Enter 繼續...")


# ===== 主程式 =====
hx = HX711(DT_PIN, SCK_PIN)

saved = load_scale()
if FORCE_CALIBRATE or saved is None:
    calibrate(hx)
else:
    hx.scale = saved
    print("載入校正值 scale =", saved)

print("開機歸零中，請保持秤上為空...")
hx.tare(30)
print("開始量測")

last = 0
while True:
    try:
        g = hx.grams()
    except OSError as e:
        print(e)
        time.sleep(1)
        continue

    if abs(g) < 0.5:               # 死區，避免空秤時一直跳 0.x
        g = 0
    # 簡單平滑，減少數值抖動
    last = g if last == 0 else last * 0.5 + g * 0.5
    print("{:.1f} g".format(last))
    time.sleep_ms(300)