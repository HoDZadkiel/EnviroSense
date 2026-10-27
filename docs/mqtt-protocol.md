# MQTT 協定

設計原則：**payload 越小、往返次數越少，喚醒視窗越短，續航越長。**
在 5 分鐘模式下，MQTT 這段佔了整個喚醒視窗能量的 **29.7%** ——
多一次往返約 30~50 ms，看似不多，但視窗每延長 100 ms，續航就掉約 8%。

## 架構：醒來即傳，不做批次

節點量測完立刻上傳，所以 **broker 收到的時間就是量測時間**（誤差 < 1 秒）。
這帶來三個直接的簡化，都是取消批次緩衝換來的：

| | 若做批次緩衝 | 現在（醒來即傳） |
|---|---|---|
| 時間戳 | 每筆要帶相對秒數，由伺服器回推 | **不需要**，用 broker 收到時間 |
| RTC 計時漂移（±3~5%） | 會累積成資料時間誤差 | **不影響資料**，只影響取樣間隔 |
| Home Assistant | 只取得到最新一筆，其餘丟掉 | **完全相容**，一筆就是一筆 |

也不需要每天做 NTP 校時 —— 節點根本不需要知道現在幾點。

## Topic 結構

| Topic | 方向 | QoS | Retain | 說明 |
|---|---|---|---|---|
| `envirosense/<node_id>/state` | 上行 | 1 | 否 | 感測資料 |
| `envirosense/<node_id>/status` | 上行 / LWT | 1 | **是** | `online` / `offline` |
| `envirosense/<node_id>/cmd` | 下行 | 1 | 是 | 指令（預設不訂閱，見下方） |
| `homeassistant/sensor/<node_id>_<key>/config` | 上行 | 1 | **是** | HA 自動探索 |

`<node_id>` 用 MAC 後 6 碼，例如 `envirosense/a1b2c3/state`。
不用人工命名是為了避免燒錄時打錯字造成兩台節點撞名。

## 上行 Payload

```json
{"id":"a1b2c3","seq":1234,"t":24.31,"h":58.2,"vbat":3.92,"rssi":-58,"up":980,"flags":[]}
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 節點 ID，WiFi STA MAC 後 3 byte 的 hex（6 碼） |
| `seq` | int | 喚醒序號，存 RTC memory。**每次喚醒都遞增，上傳失敗也遞增**，所以收端看到跳號就是漏了哪幾筆。冷開機或 RTC 校驗失敗時歸零（此時 `flags` 帶 `boot`） |
| `t` | float | 溫度 °C（SHT40） |
| `h` | float | 相對濕度 %（SHT40） |
| `vbat` | float | 電池電壓 V，小數 2 位 |
| `rssi` | int | 本次連線的 RSSI（dBm）。**同時是續航診斷指標** |
| `up` | int | 本次喚醒視窗耗時 ms（`millis()`），從 app 啟動到準備 publish。**不是開機累計時間** |
| `flags` | array | 本次喚醒的異常 / 事件旗標，正常時為 `[]`，見下表 |

| flag | 觸發條件 |
|---|---|
| `boot` | 冷開機，或深睡喚醒但 RTC 狀態校驗失敗（`seq` 隨之歸零） |
| `sensor_err` | SHT40 讀取失敗，此時 `t`、`h` 為 `null`（其餘欄位照送，`vbat`/`up` 仍有診斷價值） |
| `low_batt` | 電量偏低、上傳間隔已被拉長；或已達截止電壓（送完這筆即永久休眠） |
| `wifi_retry` | 快速連線失敗，改走全頻掃描 + DHCP 重試 |
| `cache_miss` | 快速路徑用了 BSSID/channel 快取但連線失敗 |
| `ip_recache` | 自動 IP 模式下重新走 DHCP 取得並快取 IP（或靜態快取失效後重來） |
| `wdt` | 之前有喚醒卡住超過 `WAKE_TIMEOUT_S`，被看門狗強制深睡；送成功後清除 |
| `payload_trunc` | payload 超過緩衝區，這筆丟掉了 `pending` / `wifi_err`（主程式 0.2.0、HA 0.2.0-ha 起；正常不會出現） |

另有條件性欄位 `pending`，只在有補送資料時出現，見[失敗處理](#失敗處理)。

條件性欄位 `wifi_err`（int）：只在之前有喚醒 WiFi 連不上時出現，是**最近一次**失敗的原因，送成功後清除。
值存在 RTC memory，撐得過深睡，但冷開機（RESET / 換電池）會清掉。不用接電腦就能看出現場為什麼連不上：

| 值 | 意義 |
|---|---|
| 1~255 | ESP-IDF 斷線原因 `wifi_err_reason_t`，常見：`201` 找不到 AP、`15` 四次握手逾時（密碼錯或訊號弱）、`2` 驗證過期、`204` 握手逾時 |
| `1000` | 已關聯上 AP，但逾時（`WIFI_SCAN_TIMEOUT_MS`）前沒拿到 IP —— DHCP 太慢或失敗 |
| `1001` | 逾時，期間沒有任何斷線事件（一直在掃描 / 嘗試） |

整個 payload 約 90 bytes，一個 TCP 封包裝得下。

### `up` 和 `rssi` 是這個專案最重要的兩個診斷欄位

[`power-budget.md`](./power-budget.md) 顯示喚醒視窗直接決定續航：
5 分鐘模式下視窗必須 ≤ 1.85 秒才能撐半年。把 `up` 記進時序資料庫，
就能在圖上直接看到「哪天開始 WiFi 變慢了」，在電池真的沒電之前先發現。

`rssi` 則是 `up` 變長的最常見原因 —— 訊號差導致重傳，握手時間拉長。
兩個欄位一起看就能判斷是「訊號劣化」還是「AP 或網路出問題」。

**成本是 8 bytes，價值是提早幾個月預警。**

`cache_miss` 旗標同理：記錄 BSSID/channel 快取失效的頻率。
如果失效率高（例如 AP 開了自動換頻道），這項優化就是負收益，該關掉。

## LWT（Last Will and Testament）

```
topic:   envirosense/<node_id>/status
payload: offline
qos:     1
retain:  true
```

連上後立刻 publish `online`（retain）。

⚠ **注意**：本專案的節點會主動 `disconnect()`，這是**正常斷線，不會觸發 LWT**。
節點 99% 以上的時間都是離線的，所以 `status` 對判斷節點死活幫助有限。

**真正的存活監控必須在伺服器端做**：監控 `state` 的到達間隔，
超過 2~3 個上傳週期沒收到就告警。節點自己做不到這件事。

## 下行指令：預設不訂閱

訂閱 topic 要多一次 SUBSCRIBE/SUBACK 往返，而且要**等待**可能根本不存在的訊息，
與低功耗設計直接衝突。因此：

- **預設完全不訂閱**
- 每 **N 次上傳**才訂閱一次 `cmd`，等 200 ms 收指令。N 依間隔調整，讓檢查頻率約一天一次：

| 上傳間隔 | N | 指令生效延遲 |
|---|---|---|
| 5 分鐘 | 288 | ≤ 24 小時 |
| 15 分鐘 | 96 | ≤ 24 小時 |
| 30 分鐘 | 48 | ≤ 24 小時 |

- 指令用 `retain: true` 發布，節點下次檢查時才會收到

支援的指令（JSON）：

| 指令 | 效果 |
|---|---|
| `{"interval": 15}` | 改上傳間隔（分鐘，1 / 5 / 15 / 30；1 = 續航測試用） |
| `{"ota": true}` | 標記下次喚醒進入 OTA 模式（**尚未實作**，收到會忽略並清掉） |
| `{"reboot": true}` | 重開機（冷開機 → RTC 狀態歸零、有 10 秒設定鍵窗口） |
| `{"portal": true}` | 立刻開設定頁（180 秒逾時，電池 < 3.5 V 拒絕） |

節點執行後把 `cmd` 清空（publish 空字串 retain），避免重複執行。

## 連線參數

| 參數 | 值 | 理由 |
|---|---|---|
| broker 位址 | **用 IP，不用主機名** | 省掉 DNS 查詢約 200 ms |
| Clean session | `true` | 不讓 broker 保留離線訊息，否則連上瞬間會收到一堆東西拉長視窗 |
| Keepalive | 15 s | 連線只有 1 秒，keepalive 用不到，設短一點讓 broker 早點清掉 |
| QoS（state） | 1 | 多 ~30 ms 換到送達確認，值得 |
| Retain（state） | `false` | 時序資料，retain 沒有意義而且會誤導 |
| TLS | **關閉** | 握手要多 300~800 ms，5 分鐘模式承受不起 |

**QoS 1 而非 QoS 0**：QoS 0 送出就走、省一次往返，但節點無從知道 broker 收到沒有。
用 QoS 1 收到 PUBACK 才算成功，失敗時把資料留在 RTC memory 下次補送 ——
這樣才能在 WiFi 短暫異常時不掉資料。

**實作用 ESP-IDF 的 esp-mqtt**（Arduino core 3.x 內建，`#include "mqtt_client.h"`），
不用 PubSubClient —— 後者只支援 QoS0 publish，拿不到 PUBACK，上面的補送機制做不出來。
esp-mqtt 是事件驅動的非同步 API，要注意：

- `esp_mqtt_client_publish()` 回傳 `msg_id`，**要等到同一個 `msg_id` 的 `MQTT_EVENT_PUBLISHED`**
  才算成功；逾時（`MQTT_TIMEOUT_MS`）就當失敗存進 pending
- 設 `network.disable_auto_reconnect = true`，否則連線失敗時它會在背景自己重試，拖長喚醒視窗
- 進深睡前依序 `esp_mqtt_client_disconnect()` → `esp_mqtt_client_stop()` → `esp_mqtt_client_destroy()`

**不開 TLS 的取捨**：內網佈署改用 broker 帳密 + 網段隔離（把 IoT 裝置放獨立 VLAN）。
如果環境要求必須加密，那 5 分鐘模式基本上不用考慮，改 15 或 30 分鐘。

## 失敗處理

上傳失敗時把該筆資料留在 RTC memory，下次喚醒一併送出（最多保留 4 筆，滿了丟最舊的）。

**這不是批次上傳** —— 正常情況下每次只送一筆，只有前一次失敗時才會多帶。
所以 payload 需要能容納「偶爾多筆」的情況：

```json
{"id":"a1b2c3","seq":1235,"t":24.28,"h":58.5,"vbat":3.91,"rssi":-61,"up":1420,
 "flags":["wifi_retry"],
 "pending":[{"age":300,"t":24.31,"h":58.2}]}
```

`pending` 只在有補送資料時才出現，`age` 是該筆資料的秒數年齡。
正常情況下這個欄位不存在，payload 維持在 90 bytes。

重試採指數退避：連續失敗 n 次就把下次上傳延後 `min(2^n, 8)` 個間隔，
避免 AP 掛掉時節點瘋狂重試把電池耗光。

## Home Assistant 自動探索

只在**首次開機**（`flags` 含 `boot`）發送一次，retain 到 broker。
之後每次上傳都不再發 —— 探索訊息比資料本身大好幾倍，每次都發等於白白拉長視窗。

```
topic: homeassistant/sensor/a1b2c3_temperature/config
{
  "name": "溫度",
  "uniq_id": "a1b2c3_temperature",
  "stat_t": "envirosense/a1b2c3/state",
  "val_tpl": "{{ value_json.t }}",
  "unit_of_meas": "°C",
  "dev_cla": "temperature",
  "stat_cla": "measurement",
  "exp_aft": 2400,
  "dev": {"ids": ["a1b2c3"], "name": "EnviroSense a1b2c3", "mdl": "XIAO ESP32C6", "mf": "DIY"}
}
```

`exp_aft`（expire_after）韌體設成上傳間隔的 **5 倍**（上方範例 2400 是早期的 2~3 倍設計）：
低電量時間隔會拉長到 4 倍，設太短會在省電模式下一直顯示 unavailable。超過就顯示為 unavailable ——
這就是前面說的「伺服器端存活監控」，HA 內建可以直接用。

同樣方式再發 `_humidity`、`_battery`（`dev_cla: voltage`）、`_rssi`
（`dev_cla: signal_strength`、`ent_cat: diagnostic`）。

**因為不做批次緩衝，HA 完全相容，不需要額外的資料庫橋接。**
若之後想保留更長歷史或做更細的分析，再另接 InfluxDB / Grafana 即可，
但那是加分項不是必要條件。

## 待決事項

- [ ] 伺服器端用既有的 Home Assistant，還是新架 Mosquitto？
      （不論哪個都可行，只影響 `deploy/` 的內容）
- [ ] 節點數量上限，以及 topic 是否需要加場域前綴（如 `envirosense/home/<id>/state`）
- [ ] `pending` 補送機制的上限 4 筆是否足夠，要看實際的 WiFi 失敗率（M6 觀察）

## 主程式 0.2.0 的差異

`firmware/envirosense-node-0.2.0/` 是主程式 0.2.0，移植 0.2.0-ha 的三項修正；原版原封不動留在 `firmware/envirosense-node/`。
state topic、欄位與 retain 設定都不變，只有下面幾點不同：

| 項目 | 主程式原版 | 主程式 0.2.0 |
|---|---|---|
| 截止電壓永久深睡 | 單次讀值低於 3.3 V 就關 | 例行喚醒要**連續兩次**低於 3.3 V 才關（冷開機仍是單次） |
| `payload_trunc` 旗標 | — | payload 超過緩衝區時丟掉 `pending` / `wifi_err`，改帶這個旗標（正常不會出現） |
| 節點名稱 | 最多 31 byte | 最多 63 byte（中文 21 字）；結尾被截斷的半個 UTF-8 字元會丟掉 |

探索前綴在主程式是固定的 `homeassistant`，所以沒有 0.2.0-ha 的前綴驗證。
截止電壓為什麼要確認兩次，見下方「0.2.0-ha 的差異」。

## envirosense-node-ha 的差異

`firmware/envirosense-node-ha/` 是 HA 相容版。上面的協定全部照舊，只有下面幾點不同：

| 項目 | 主程式 | HA 相容版 |
|---|---|---|
| state 的 Retain | 否 | **是** |
| 探索前綴 | 固定 `homeassistant` | 可在設定頁修改（NVS 鍵 `dpfx`） |
| 是否發 HA 探索 | 一律發 | 可在設定頁關閉（NVS 鍵 `disc`），關掉後只發 state |
| 探索的額外欄位 | — | `sug_dsp_prc`、`def_ent_id`、`dev.sw`、`o`（origin） |
| 探索重發時機 | 冷開機、設定頁存檔 | 相同 |

**state 改成 retain 的理由**：HA 重啟後和新訂閱者可以立刻拿到最後一筆。
retain 不會讓舊資料看起來像新資料：HA 由 `exp_aft` 判斷過期，非 HA 的客戶端則照本文件
「LWT」一節的做法，監控 state 的到達間隔。

**status / LWT 保留，但探索不帶 `avty_t`**：節點每次都是主動斷線，不會觸發 LWT，
所以 status 會一直停在 `online`。如果 HA 依 status 判斷可用性，就永遠不會顯示離線。
保留 status 是為了跟舊版的非 HA 客戶端相容。

**探索為什麼不改成「這輩子只發一次」**：broker 只要遺失 retain 訊息（重灌、沒開 persistence、換 broker），
實體就會消失，而且沒辦法自動恢復。冷開機一年頂多幾次，每次只多約 2 KB；需要時按一下 RESET 就會重發。

`def_ent_id` 只在 HA 第一次建立實體時生效（`sensor.envirosense_<id>_<key>`）。
從主程式升級上來的節點，既有的實體和歷史都不受影響。

### 0.2.0-ha 的差異

`firmware/envirosense-node-ha-0.2.0/` 是 HA 版 0.2.0。0.1.0-ha 原封不動留在 `firmware/envirosense-node-ha/`。
協定相同，只有下面幾點不同（主程式原版與 0.1.0-ha 都是左欄的行為；主程式 0.2.0 除了探索前綴驗證，都是右欄）：

| 項目 | 0.1.0-ha | 0.2.0-ha |
|---|---|---|
| 截止電壓永久深睡 | 單次讀值低於 3.3 V 就關 | 例行喚醒要**連續兩次**低於 3.3 V 才關（冷開機仍是單次） |
| `payload_trunc` 旗標 | — | payload 超過緩衝區時丟掉 `pending` / `wifi_err`，改帶這個旗標（目前最長約 385 bytes，正常不會出現） |
| 節點名稱 | 最多 31 byte | 最多 63 byte（中文 21 字）；結尾被截斷的半個 UTF-8 字元會丟掉 |
| 探索前綴驗證 | — | 含 `+`、`#`、空白或頭尾 `/` → 退回 `homeassistant` |

**截止電壓為什麼要確認兩次**：例行喚醒是在 WiFi 連上後才讀電壓，這時電芯正在供電給無線電。
天冷時電芯內阻變大，負載下的讀值會被拉低，單次讀值可能讓還有電的電池誤觸發永久深睡。
第一次低讀值時上傳間隔已經是 ×4，確認最多只延後一個長間隔。

### 0.2.1-ha 的差異

`firmware/envirosense-node-ha-0.2.1/` 是 HA 版 0.2.1，以 0.2.0-ha 為基礎，只在 state payload 多兩個欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `bssid` | string | 本次連上的 AP MAC，12 碼小寫 hex 不含冒號，例如 `"a1b2c3d4e5f6"` |
| `ch` | int | 本次連線的 WiFi channel |

```json
{"id":"a1b2c3","seq":1234,"t":24.31,"h":58.2,"vbat":3.92,"rssi":-58,"bssid":"a1b2c3d4e5f6","ch":6,"up":980,"flags":[]}
```

**為什麼要加**：同一個 SSID 的 mesh 有多台 AP，`rssi` 跳一個台階時，分不出是「訊號變了」還是「換了一台 AP」。
2026-10-16 的資料裡，`901ce4` 的 RSSI 在 -80 和 -64 兩個狀態間切換，而且 `ip_recache` 只出現在 -64 那段；
`vbat` 也跟著同步跳動 80 mV（無線電負載不同），沒有 BSSID 無法確認是哪台 AP 出問題。

兩個欄位放在基本欄位裡，觸發 `payload_trunc` 時也會保留。payload 最長由約 400 增為約 430 bytes，緩衝區 512 bytes 仍夠。

### 0.2.2-ha 的差異

`firmware/envirosense-node-ha-0.2.2/` 是 HA 版 0.2.2，以 0.2.1-ha 為基礎。**state payload 不變**，
只改 HA 探索（`homeassistant/sensor/<id>_<key>/config`）加入作者資訊：

| 欄位 | 0.2.1-ha | 0.2.2-ha |
|---|---|---|
| `dev.mf`（製造商） | `"DIY"` | `"HoDZadkiel"` |
| `o.url`（origin 支援連結） | 無 | `"https://github.com/HoDZadkiel"` |

探索 JSON 最壞情況（節點名稱 63 byte、state topic 66 byte）約 568 bytes，緩衝區 640 bytes 仍夠。
探索只在首次開機或重新設定後發送，已存在的 HA 裝置要重發探索（重新設定一次存檔，或冷開機狀態歸零）才會更新製造商欄位。
