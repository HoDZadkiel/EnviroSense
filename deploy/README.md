# 伺服器端佈署

**目前實際運作**：Mosquitto broker，Home Assistant 直接訂閱 MQTT；另有橋接程式把資料寫進 InfluxDB（橋接程式不在本專案內）。
接既有的 Home Assistant 內建 broker 或另架 Mosquitto 都可行。

| 路徑 | 內容 |
|---|---|
| `mosquitto/config/` | Mosquitto broker 設定與登入檔（`passwd` 不入版控） |
| `homeassistant/` | HA MQTT 整合設定範例 |

## 節點端的兩個要求

1. **broker 必須是靜態 IP**。節點直接用 IP 連線以省掉 DNS 查詢（約 200 ms）。
   broker 換 IP 就要重燒韌體
2. **不開 TLS**。TLS 握手會讓喚醒視窗多 300~800 ms，5 分鐘模式承受不起。
   改用 broker 登入驗證 + 把 IoT 裝置放獨立 VLAN

## 存活監控要在這裡做

節點每次上傳完就主動斷線，**這是正常斷線不會觸發 LWT**，
而且節點 99% 以上時間都離線。所以 `status` topic 判斷不出節點死活。

真正的監控是**看 `state` 的到達間隔**，超過 2~3 個上傳週期沒收到就告警。
用 HA 的話，MQTT 自動探索設定裡的 `expire_after` 直接就能做到。

## 建議也記錄 up 與 rssi

payload 裡的 `up`（喚醒視窗毫秒數）與 `rssi` 不是感測資料，但值得存進資料庫 ——
喚醒視窗變長是電池提早耗盡的前兆，能提早幾個月看出來。
詳見 [`../docs/mqtt-protocol.md`](../docs/mqtt-protocol.md)。
