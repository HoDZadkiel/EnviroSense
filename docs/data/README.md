# 遙測資料快照（2026-10-28）

供驗算 [`../power-budget.md`](../power-budget.md)「現場遙測推估」一節。一次性輸出，不會自動更新。

- `telemetry-raw-20261028.csv`：InfluxDB `sensor-data` 的 `sensor_state` 逐筆資料（UTC，2026-10-16 ~ 10-27）。
  `excluded_charging=1` 是節點開機那筆（`seq 0` / `boot`，USB 供電充電中，vbat 4.07 V），統計時排除。
- `telemetry-summary-20261028.csv`：各節點彙總與續航推估，另有「新韌體合併」一列。
- 欄位 `fw_group`：payload 有 `bssid`（0.2.1-ha 以上）= `new(bssid)`（8e8f50、8f4700）；
  沒有 = `old(no bssid)`（8ef074、901ce4）。**續航估算只採 `new(bssid)`**，舊版因 `ip_recache` 偏多會高估耗電。
  韌體版本是由 `bssid` 有無推測，資料裡沒有 `fw` 欄位。

## 驗算公式

- 有效筆數：`excluded_charging=0`；到達率 = 有效筆數 ÷ (天數 × 1440 ÷ 間隔分鐘)；間隔 = 相鄰時間差中位數
- 平均喚醒 `awake_ms` = `uptime_ms` 平均 + 290 ms；合併列用兩台所有有效筆數的 `uptime_ms` 平均（MQTT 連線／送出／收尾，沿用模型值）
- 每日耗電 mAh = 75.8 mA × awake_ms ÷ 1000 ÷ 3600 × (1440 ÷ 間隔分鐘) + (14.3 + 3.0) µA × 24 ÷ 1000
- 續航月數 = 5000 × 0.8 ÷ (每日耗電 + 5000 × 1.5% ÷ 30.44) ÷ 30.44
- `vbat_daily_slope_mV`：每日 vbat 中位數對天數的線性回歸斜率，去掉首尾不完整日（逐筆 vbat 有 0.04~0.08 V 的 ADC 跳動，不能逐筆回歸）

75.8 mA、14.3 µA、3.0 µA 是模型值，不是這批資料量出來的（見 `scripts/power_budget.py`）。
