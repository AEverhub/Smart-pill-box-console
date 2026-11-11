from machine import Pin, disable_irq, enable_irq
import time

# ===== 設定 =====
DT_PIN = 16
SCK_PIN = 17
LED_PIN = 21               # 指示燈
CAL_WEIGHT_G = 100         # 校正用重物重量（克），請改成你實際用的砝碼
SCALE_FILE = "scale.txt"

led = Pin(LED_PIN, Pin.OUT, value=0)
boot = Pin(0, Pin.IN, Pin.PULL_UP)     # 板子上的 BOOT 按鈕


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


def blink(times, on_ms=150, off_ms=150):
    for _ in range(times):
        led.value(1)
        time.sleep_ms(on_ms)
        led.value(0)
        time.sleep_ms(off_ms)


def countdown(seconds, msg, led_mode):
    """led_mode: 'blink' 慢閃 / 'on' 恆亮 / 'off' 熄滅"""
    print(msg)
    for s in range(seconds, 0, -1):
        print("  剩 {} 秒".format(s))
        if led_mode == "blink":
            led.value(1)
            time.sleep_ms(500)
            led.value(0)
            time.sleep_ms(500)
        else:
            led.value(1 if led_mode == "on" else 0)
            time.sleep(1)
    led.value(0)


def want_recalibrate(window_s=5):
    print("LED 亮起的 {} 秒內按一下 BOOT 鍵可重新校正".format(window_s))
    led.value(1)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < window_s * 1000:
        if boot.value() == 0:
            led.value(0)
            while boot.value() == 0:   # 等放開按鍵
                time.sleep_ms(20)
            return True
        time.sleep_ms(20)
    led.value(0)
    return False


def load_scale():
    try:
        with open(SCALE_FILE) as f:
            return float(f.read())
    except (OSError, ValueError):
        return None


def calibrate(hx):
    # 步驟 1：LED 慢閃 5 秒，秤上保持空的，然後歸零
    countdown(5, "【校正 1/3】請保持秤上為空（LED 慢閃）", "blink")
    hx.tare(30)
    print("歸零完成 offset =", hx.offset)

    # 步驟 2：LED 恆亮 10 秒，把砝碼放上去
    countdown(10, "【校正 2/3】請輕放 {} g 重物在上板中央（LED 恆亮）".format(CAL_WEIGHT_G), "on")

    # 步驟 3：量測並算出比例
    raw = hx.read_avg(40) - hx.offset
    print("原始差值 =", raw)
    if abs(raw) < 100:
        raise RuntimeError("差值太小，荷重元幾乎沒反應，請檢查接線與機構")

    hx.scale = raw / CAL_WEIGHT_G
    with open(SCALE_FILE, "w") as f:
        f.write(str(hx.scale))
    print("校正完成 scale =", hx.scale, "（已存檔）")
    blink(3)                           # 閃 3 下 = 成功

    countdown(8, "【校正 3/3】請移開重物（LED 熄滅）", "off")


# ===== 主程式 =====
hx = HX711(DT_PIN, SCK_PIN)

saved = load_scale()
if saved is None or want_recalibrate():
    while True:
        try:
            calibrate(hx)
            break
        except Exception as e:
            print("校正失敗：", e, "，5 秒後重試")
            blink(10, 80, 80)          # 快閃 10 下 = 失敗
            time.sleep(5)
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

    if abs(g) < 0.5:                   # 死區，避免空秤時一直跳 0.x
        g = 0
    last = g if last == 0 else last * 0.5 + g * 0.5   # 簡單平滑
    print("{:.1f} g".format(last))
    time.sleep_ms(300)