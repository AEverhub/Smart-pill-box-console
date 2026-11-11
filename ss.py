from machine import ADC, Pin
import time

LED_PIN = 21
BUZZ_PIN = 32     # Low 才響
TDS_PIN = 34      # 請依實際接線修改

VREF = 3.3
LEARN_SECONDS = 8
DROP_RATIO = 0.5  # 讀值低於水基準的 50% 就報警

led = Pin(LED_PIN, Pin.OUT, value=0)
buzz = Pin(BUZZ_PIN, Pin.OUT, value=1)   # High = 不響

adc = ADC(Pin(TDS_PIN))
adc.atten(ADC.ATTN_11DB)
adc.width(ADC.WIDTH_12BIT)


def read_tds(samples=15):
    vals = []
    for _ in range(samples):
        vals.append(adc.read())
        time.sleep_ms(5)
    vals.sort()
    v = vals[len(vals) // 2] / 4095 * VREF
    tds = (133.42 * v**3 - 255.86 * v**2 + 857.39 * v) * 0.5
    return v, tds


def alarm(on):
    led.value(1 if on else 0)
    buzz.value(0 if on else 1)


# ===== 開機學習：探頭請先放在水中 =====
print("學習中，請讓探頭泡在水裡...")
total, n = 0, 0
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < LEARN_SECONDS * 1000:
    _, t = read_tds()
    total += t
    n += 1
    led.value(n % 2)          # 學習期間 LED 閃爍
    time.sleep_ms(300)
led.value(0)

baseline = total / n
threshold = baseline * DROP_RATIO
print("水基準: {:.0f} ppm，報警門檻: < {:.0f} ppm".format(baseline, threshold))

if baseline < 30:
    print("警告：水的讀值太低，無法與酒精區分，請改用自來水或加少許鹽")

# ===== 測試主迴圈 =====
while True:
    v, tds = read_tds()
    if tds < threshold:
        alarm(True)
        state = "偵測到酒精/非水 -> 報警"
    else:
        alarm(False)
        state = "水 -> 正常"
    print("{:.3f} V  {:.0f} ppm  {}".format(v, tds, state))
    time.sleep_ms(300)