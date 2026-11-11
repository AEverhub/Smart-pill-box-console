hx = HX711(dt=16, sck=17)

input("秤上保持空的，按 Enter 歸零...")
hx.tare()
print("歸零完成，offset =", hx.offset)

known = float(input("輸入你要放的已知重量（克，例如 100）："))
input("放好後按 Enter...")
time.sleep(1)

raw = hx.read_avg(30) - hx.offset
print("原始差值 =", raw)

if abs(raw) < 100:
    print("差值太小，荷重元幾乎沒反應，請檢查接線與機構")
else:
    hx.scale = raw / known      # 正負號會自動處理
    open("scale.txt", "w").write(str(hx.scale))
    print("校正完成 scale =", hx.scale)
    while True:
        print("{:.1f} g".format(hx.grams()))
        time.sleep_ms(500)