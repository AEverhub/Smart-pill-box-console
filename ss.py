from machine import ADC, Pin
import time

LED_PIN = 21
BUZZ_PIN = 32      # Low 才響
TDS_PIN = 34

TOL_RATIO = 0.20   # 偏離基準超過 20% 就報警
TOL_MIN = 0.05     # 最小容許偏差 (V)，避免基準太小時誤報
VREF = 3.3

led = Pin(LED_PIN, Pin.OUT, value=0)
buzz = Pin(BUZZ_PIN, Pin.OUT, value=1)

adc = ADC(Pin(TDS_PIN))
adc.atten(ADC.ATTN_11DB)
adc.width(ADC.WIDTH_12BIT)


def read_v(samples=40):
    vals = []
    for _ in range(samples):
        vals.append(adc.read())
        time.sleep_ms(2)
    vals.sort()
    trimmed = vals[8:-8]                      # 去掉極端值
    raw = sum(trimmed) / len(trimmed)
    return raw, raw / 4095 * VREF


def alarm(on):
    led.value(1 if on else 0)
    buzz.value(0 if on else 1)


# ===== 學習水的基準：探頭請先泡在水裡 =====
print("請把探頭放進水裡，等待讀值穩定...")
hist = []
t0 = time.ticks_ms()
base = None
while base is None:
    raw, v = read_v()
    hist.append(v)
    hist = hist[-10:]
    spread = max(hist) - min(hist)
    led.value(1 - led.value())
    print("raw={:.0f}  {:.3f}V  波動={:.3f}V".format(raw, v, spread))
    waited = time.ticks_diff(time.ticks_ms(), t0)
    if len(hist) == 10 and v > 0.05 and (spread < 0.02 or waited > 20000):
        base = sum(hist) / len(hist)
    time.sleep_ms(300)

led.value(0)
print("水基準: {:.3f} V".format(base))

# ===== 測試主迴圈 =====
while True:
    raw, v = read_v()
    limit = max(base * TOL_RATIO, TOL_MIN)
    diff = v - base
    if abs(diff) > limit:
        alarm(True)
        state = "偏離水 -> 報警（{}）".format("高於" if diff > 0 else "低於")
    else:
        alarm(False)
        state = "水 -> 正常"
    print("raw={:.0f}  {:.3f}V  基準={:.3f}V  {}".format(raw, v, base, state))
    time.sleep_ms(300)