#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EnviroSense 功耗預算試算（XIAO ESP32C6，醒來即量測即上傳）。

docs/ 與 README.md 裡所有續航月數、階段能量佔比都由這支腳本產生。
不要手改文件裡的數字 —— 改這裡的參數然後重跑。

用法:  python scripts/power_budget.py
"""

SLEEP_UA = 14.3   # XIAO ESP32C6 深睡實測（PPK2 從 BAT 焊盤供 3.8V）
PROTECT_UA = 3.0  # 載板 DW01A 靜態電流（typ 3.0 / max 6.0 µA @3.6V），常時耗電，與 XIAO 型號無關

# --- 三款 XIAO 對照（僅用於選型佐證，本專案已定案 C6）-------------------
# extra_ms / extra_ma: 相對 C6 在「開機 + WiFi init」階段的額外開銷。
# S3 有 8MB PSRAM 要初始化、雙核 Xtensa、8MB flash 載入 app，故較慢且較耗電。
BOARD_COMPARE = {
    "C3": dict(sleep_ua=45.1, extra_ms=0,   extra_ma=0),
    "S3": dict(sleep_ua=11.9, extra_ms=100, extra_ma=10),
    "C6": dict(sleep_ua=14.3, extra_ms=0,   extra_ma=0),
}

# --- 喚醒視窗的分階段模型 -----------------------------------------------
# (階段名稱, 毫秒, 平均電流 mA)
# 時間來自公開實測與 Espressif 文件，見 docs/wifi-optimization.md 的來源表。
# 電流為估計值，M0 實測後回填。
SCENARIOS = {
    "未優化": [
        ("開機 / 載入 app（含 image 驗證）",  250, 30),
        ("WiFi init + start（每次全 PHY 校正）", 300, 60),
        ("全頻掃描找 AP",                      800, 100),
        ("關聯 + WPA2 四次握手",              1100, 100),
        ("DHCP 取得 IP",                      1000, 80),
        ("DNS 查 broker 位址",                 200, 80),
        ("MQTT 連線 + publish + 斷線",         300, 90),
        ("收尾進睡",                            50, 30),
    ],
    "優化後": [
        ("開機 / 載入 app（skip validate）",   150, 30),
        ("WiFi init + start（PHY 部分校正）",  210, 60),
        ("關聯 + WPA2（已知 BSSID/channel）",  350, 100),
        ("MQTT 連線 + publish + 斷線（IP 直連）", 250, 90),
        ("收尾進睡",                            40, 30),
    ],
    "優化後（無靜態IP）": [
        ("開機 / 載入 app（skip validate）",   150, 30),
        ("WiFi init + start（PHY 部分校正）",  210, 60),
        ("關聯 + WPA2（已知 BSSID/channel）",  350, 100),
        ("DHCP 取得 IP",                      1000, 80),
        ("MQTT 連線 + publish + 斷線（IP 直連）", 250, 90),
        ("收尾進睡",                            40, 30),
    ],
    "ESP-NOW": [
        ("開機 / 載入 app（skip validate）",   150, 30),
        ("esp_wifi_init + start",              210, 60),
        ("ESP-NOW 送出 + ack",                  60, 110),
        ("收尾進睡",                            30, 30),
    ],
}

BATTERIES = {
    "18650 (3000mAh)": dict(nominal_mah=3000, usable_frac=0.80, self_pct_mo=1.5),
    "21700 (5000mAh)": dict(nominal_mah=5000, usable_frac=0.80, self_pct_mo=1.5),
}

INTERVALS_MIN = (5, 15, 30)
TARGET_MONTHS = 6


def window(scenario):
    """回傳 (總毫秒, 單次能量 mAh, 平均電流 mA)。"""
    ms = sum(p[1] for p in SCENARIOS[scenario])
    mas = sum(p[1] / 1000 * p[2] for p in SCENARIOS[scenario])   # mA·s
    return ms, mas / 3600, mas / (ms / 1000)


def months(daily_mah, battery):
    b = BATTERIES[battery]
    usable = b["nominal_mah"] * b["usable_frac"]
    selfd = b["nominal_mah"] * b["self_pct_mo"] / 100 / 30.44
    return usable / (daily_mah + selfd) / 30.44


def main():
    print("=== 喚醒視窗分階段能量 ===")
    for name in SCENARIOS:
        ms, e, avg = window(name)
        print(f"\n[{name}]  共 {ms} ms，平均 {avg:.1f} mA，單次 {e*1000:.2f} µAh")
        total_mas = sum(p[1] / 1000 * p[2] for p in SCENARIOS[name])
        for label, t, i in SCENARIOS[name]:
            mas = t / 1000 * i
            print(f"    {label:<38}{t:>5} ms {i:>4} mA {mas:>7.1f} mA·s {mas/total_mas*100:>5.1f}%")

    for battery in BATTERIES:
        b = BATTERIES[battery]
        selfd = b["nominal_mah"] * b["self_pct_mo"] / 100 / 30.44
        print(f"\n=== {battery} 續航（月）｜可用 {b['nominal_mah']*b['usable_frac']:.0f} mAh"
              f"，自放電 {selfd:.2f} mAh/day ===")
        print(f"{'間隔':<8}" + "".join(f"{n:>14}" for n in SCENARIOS))
        for iv in INTERVALS_MIN:
            row = f"{iv:>2} 分鐘  "
            for name in SCENARIOS:
                _, e, _ = window(name)
                daily = e * (1440 / iv) + (SLEEP_UA + PROTECT_UA) / 1000 * 24
                m = months(daily, battery)
                row += f"{m:>10.1f}{'  OK' if m >= TARGET_MONTHS else '  NG'}"
            print(row)

    # 反推：要達標，喚醒視窗最多多久
    print(f"\n=== 達成 {TARGET_MONTHS} 個月所需的喚醒視窗上限 ===")
    _, _, avg_opt = window("優化後")
    for battery in BATTERIES:
        b = BATTERIES[battery]
        usable = b["nominal_mah"] * b["usable_frac"]
        selfd = b["nominal_mah"] * b["self_pct_mo"] / 100 / 30.44
        for iv in INTERVALS_MIN:
            budget = usable / (TARGET_MONTHS * 30.44) - selfd - (SLEEP_UA + PROTECT_UA) / 1000 * 24
            t = budget / (1440 / iv) * 3600 / avg_opt
            print(f"  {battery}  {iv:>2} 分鐘 -> 視窗須 <= {t:5.2f} s"
                  f"（優化後實際 {window('優化後')[0]/1000:.2f} s）")

    for iv in (5, 30):
        breakdown("優化後", iv, "18650 (3000mAh)")

    board_table("優化後", "18650 (3000mAh)")


def board_table(scenario, battery):
    """三款板子在同一情境下的續航對照。"""
    ms, e, avg = window(scenario)
    b = BATTERIES[battery]
    print()
    print(f"=== 三款 XIAO 對照（{scenario} / {battery}）===")
    print(f"{'間隔':<8}" + "".join(f"{n:>10}" for n in BOARD_COMPARE))
    for iv in INTERVALS_MIN:
        row = f"{iv:>2} 分鐘  "
        for name, cfg in BOARD_COMPARE.items():
            e_b = e + cfg["extra_ms"] / 1000 * (avg + cfg["extra_ma"]) / 3600
            daily = e_b * (1440 / iv) + (cfg["sleep_ua"] + PROTECT_UA) / 1000 * 24
            row += f"{months(daily, battery):>10.1f}"
        print(row)


def breakdown(scenario, interval_min, battery):
    """單一組合的每日耗電佔比。"""
    _, e, _ = window(scenario)
    b = BATTERIES[battery]
    d = {
        "上傳": e * (1440 / interval_min),
        "自放電": b["nominal_mah"] * b["self_pct_mo"] / 100 / 30.44,
        "深睡": SLEEP_UA / 1000 * 24,
        "保護 IC": PROTECT_UA / 1000 * 24,
    }
    total = sum(d.values())
    print()
    print(f"=== 耗電佔比：{scenario} / {interval_min} 分鐘 / {battery} ===")
    for k, v in sorted(d.items(), key=lambda x: -x[1]):
        n = int(1440 / interval_min) if k == "上傳" else None
        tag = f"（{n} 次）" if n else ""
        print(f"  {k+tag:<14}{v:>6.2f} mAh/day {v/total*100:>6.1f}%")
    print(f"  {'合計':<14}{total:>6.2f} mAh/day")


if __name__ == "__main__":
    main()
