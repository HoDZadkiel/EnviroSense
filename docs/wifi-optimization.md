# WiFi 連線優化

## 為什麼這是本專案的核心問題

決定「醒來就上傳、不做批次緩衝」之後，**上傳佔了電路總耗電的 97.6%**（5 分鐘模式）。
深睡電流、感測器耗電、板子選型全部加起來也只有 2.4%。

換句話說：**喚醒視窗的長度幾乎就是唯一的設計變數。**

反推達標所需的視窗長度（由 [`../scripts/power_budget.py`](../scripts/power_budget.py) 產生）：

| 電池 | 5 分鐘 | 15 分鐘 | 30 分鐘 |
|---|---|---|---|
| 18650 (3000mAh) | **≤ 1.85 s** | ≤ 5.56 s | ≤ 11.13 s |
| 21700 (5000mAh) | ≤ 3.14 s | ≤ 9.41 s | ≤ 18.82 s |

未優化的 Arduino 寫法（`WiFi.begin(ssid, pass)` + DHCP + DNS）大約要 **4 秒**。
**5 分鐘模式在未優化的狀態下不可能達標**，15 / 30 分鐘則有餘裕。

## 時間花在哪

| 階段 | 未優化 | 能量佔比 | 優化後 | 手段 |
|---|---|---|---|---|
| 開機 / 載入 app | 250 ms | 2.2% | 150 ms | skip validate + QIO 80MHz |
| WiFi init + start | 300 ms | 5.3% | 210 ms | PHY 部分校正 |
| **全頻掃描找 AP** | 800 ms | 23.5% | **0 ms** | 快取 BSSID + channel |
| **關聯 + WPA2 四次握手** | 1100 ms | **32.4%** | 350 ms | 已知 BSSID/channel + 訊號好 |
| **DHCP 取得 IP** | 1000 ms | 23.5% | **0 ms** | 靜態 IP |
| DNS 查 broker | 200 ms | 4.7% | **0 ms** | 直接用 IP |
| MQTT 連線+送出+斷線 | 300 ms | 7.9% | 250 ms | 不開 TLS、payload 小 |
| 收尾進睡 | 50 ms | 0.4% | 40 ms | |
| **合計** | **4000 ms** | | **1000 ms** | **能量降為 22%** |

單次上傳能量：**94.44 µAh → 21.06 µAh**。

> ⚠ **1000 ms 是把多份獨立公開實測拼起來的估計值，不是同一台機器量出來的。**
> 各階段時間有文獻依據（見下方來源表），但平均電流全是估計。
> M2 的工作就是實測這張表並回填 `scripts/power_budget.py`。

## 優化手段逐項

### 1. 靜態 IP —— 省 ~1000 ms（單項最大）

DHCP 要走 DISCOVER → OFFER → REQUEST → ACK 四次往返，每次都要等路由器回應。
這段時間 WiFi 全開著，是純浪費。

```cpp
IPAddress ip(192,168,1,50), gw(192,168,1,1), mask(255,255,255,0), dns(192,168,1,1);
WiFi.config(ip, gw, mask, dns);     // 必須在 WiFi.begin() 之前
WiFi.begin(ssid, pass);
```

這一項單獨就值 **+37% ~ +80%** 續航（間隔越短效益越大），
**在 5 分鐘模式是達標與否的分界線**（5.5 → 9.9 個月）。

IP 從哪來有三種做法，本專案用 WiFiManager 讓使用者選，預設「自動」：

| 模式 | 做法 | 風險 |
|---|---|---|
| 自動（預設） | 首次 DHCP 後記住配到的 IP | 租約過期後可能被別人占用 → 需續約與退路機制 |
| 手動 | 使用者填路由器保留的 IP | 無，**最安全**，但新手不會設路由器 |
| 關閉 | 每次都 DHCP | 無，但每次多約 1 秒 |

⚠ **「自動」模式的假設沒有表面上那麼安全** —— 節點深睡時不會回應路由器的
衝突偵測探測，所以路由器會把過期的 IP 安心地發給別人。
完整分析與對策（每日 DHCP 續約 + 失敗自動退回）見 [`provisioning.md`](./provisioning.md)。

- **不設 DNS 也可以**（下面第 3 點會讓 DNS 完全用不到），但填了不花時間

### 2. 快取 BSSID + channel —— 宣稱省 ~800 ms（但有爭議，必須 A/B 實測）

把上次成功連上的 AP MAC 與頻道存進 RTC memory，下次直接指定，跳過全頻段掃描：

```cpp
RTC_DATA_ATTR uint8_t  rtc_bssid[6];
RTC_DATA_ATTR uint8_t  rtc_channel;
RTC_DATA_ATTR uint32_t rtc_crc;

WiFi.begin(ssid, pass, rtc_channel, rtc_bssid);   // 指定頻道與 BSSID
```

連上後從 `WiFi.BSSID()` / `WiFi.channel()` 更新快取；連不上就清空快取、走一次全頻掃描。

**⚠ 這一項有互相矛盾的證據，不要當成理所當然：**

- 大量社群文章宣稱可把連線從 3 秒降到 1 秒以下，甚至 500 ms
- 但 **Espressif 官方 FAQ 明確說**：ESP32 不像 ESP8266，指定 BSSID 搭配 fast scan
  **無法**加速連線
- 而且有一份 arduino-esp32 的回報：**已經用了靜態 IP + BSSID + channel，連線仍花 3201 ms**

三者無法同時為真。合理推測是「有沒有效取決於 AP 行為與 IDF 版本」。
**因此 M2 必須做 A/B 對照實測**：同一顆節點、同一個 AP，開關這項設定各跑 50 次記錄連線時間。
如果實測無效就別留著 —— 快取失效時的 fallback 邏輯反而會讓失敗情境變慢。

### 3. 用 IP 直連 MQTT broker —— 省 ~200 ms

`client.setServer("mqtt.local", 1883)` 會觸發 DNS 查詢（mDNS 更慢）。
broker 在內網、IP 固定，直接寫 IP：

```cpp
client.setServer(IPAddress(192,168,1,10), 1883);
```

代價是 broker 換 IP 時要重燒韌體。內網環境把 broker 也設成靜態 IP 即可。

### 4. 跳過開機時的映像檔驗證 —— 省 ~100 ms

`CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP`

首次開機時 bootloader 把 app 位址存進 RTC FAST memory，之後從深睡醒來直接跳過去執行，
不做完整性檢查。官方說明是「可顯著加快載入」，社群回報開機時間可到 **~86 ms**。

代價：**放棄了映像檔完整性檢查**。只有 Secure Boot 關閉時能用。
對電池供電的環境感測器來說這個取捨划算，但要知道自己放棄了什麼。

### 5. PHY 射頻校正用部分校正 —— 省 ~100 ms

`CONFIG_ESP_PHY_CALIBRATION_AND_DATA_STORAGE`

啟用後把完整校正結果存進 NVS，之後只做部分校正。官方明確寫著**比完整校正省 100 ms**。
另外「不校正」模式官方說明**只建議用在深睡喚醒後** —— 正好是本專案的情境，值得測。

### 6. 開機速度：CPU 160 MHz + Flash QIO 80 MHz

公開實測：240 MHz + QIO 80 MHz + 關閉開機 UART 輸出 → 開機 **~138 ms**；
80 MHz + DIO 40 MHz → **~180 ms**。

C6 最高就是 160 MHz。重點是 **flash 用 QIO 80 MHz**（載入 app 的速度）以及**關掉開機 log**。

```ini
board_build.f_cpu = 160000000L
board_build.flash_mode = qio
board_build.f_flash = 80000000L
```

**不要為了省電降頻到 80 MHz。** 能量 = 功率 × 時間，降頻會讓每個階段都變慢，
在這種「短時間衝刺」的工作型態下通常是淨虧損。

### 7. `esp_wifi_set_ps(WIFI_PS_NONE)`

視窗只有 1 秒，WiFi 省電模式（DTIM 睡眠）在這裡只會拖慢流程。全程不省電、儘快做完再深睡。

### 8. 不開 TLS —— 省 ~300~800 ms

TLS 握手要多幾次往返加上憑證運算。內網佈署改用 broker 帳密 + 網段隔離。
若一定要 TLS，5 分鐘模式基本上就別想了。

### 9. 關掉 Serial 與板載 LED

`CORE_DEBUG_LEVEL=0`、`ARDUINO_USB_CDC_ON_BOOT=0`。
USB CDC 初始化本身就要時間，而且**開著 USB CDC 時量到的電流完全沒有參考價值**。

### 10. 感測器讀取與 WiFi 啟動並行

SHT40 高精度量測要 8.2 ms，I²C 初始化也要一點時間。
先呼叫 `WiFi.begin()`，趁 WiFi 在背景關聯的時候讀感測器，等要 publish 時才等待連線完成 ——
這 10~20 ms 本來是白等的。

### 11. `CONFIG_RTC_CLK_CAL_CYCLES = 0`

關掉開機時的 RTC 慢速時鐘校正可省下少量時間。
**代價是 RTC 計時精度變差** —— 但本專案的睡眠間隔本來就容許 ±3~5% 誤差，可以接受。

## 最大的陷阱：Arduino framework 改不了 sdkconfig

上面第 4、5、11 項全是 **ESP-IDF 的 sdkconfig 選項**。
用 Arduino IDE + esp32 core 時，**Arduino core 與 bootloader 是預先編譯好的二進位檔**，
這些選項已經被燒死在裡面，從 Arduino IDE 端改不動。

三條路：

| 做法 | 能拿到的優化 | 代價 |
|---|---|---|
| **A. 純 Arduino** | 第 1、2、3、6~10 項（約 4000 → 1250 ms） | 最簡單，仍可達標 |
| **B. Arduino + 自建 bootloader** | 再加第 4 項 | 要自己編 `bootloader.bin` 換掉 |
| **C. 改用 ESP-IDF** | 全部（→ ~1000 ms） | 重寫韌體，開發時間大增 |

**建議走 A**，因為：**跳過驗證 + PHY 校正 + RTC 校正三項加起來只省約 250 ms**，
而第 1~3 項（靜態 IP、BSSID 快取、IP 直連）光是純 Arduino 就能省 2000 ms。
先把便宜的拿走，M2 實測後若 5 分鐘模式還差臨門一腳，再考慮 B 或 C。

## 剩下的大頭：WPA2 四次握手（消不掉）

優化到 1000 ms 之後，**關聯 + WPA2 握手佔了 46.2%**，是最大的單項。這段包含：

- 802.11 認證與關聯（跟 AP 來回）
- WPA2 四次握手（4 個封包來回，每個都要等 AP）
- PMK 推導（PBKDF2-SHA1，4096 次迭代）

前兩項**取決於 AP 的回應速度，節點端無能為力**。這也解釋了為什麼同樣的程式碼在不同路由器上
連線時間可以差好幾倍 —— 以及為什麼「換一台 AP」有時比改任何程式碼都有效。

實務上能做的只有：

- **改善訊號品質**（外接天線、佈署點 RSSI 優於 -70 dBm）。訊號差 → 重傳 → 握手拉長
- **選一台反應快的 AP**，並在 M2 用同一顆節點對照測試不同 AP
- **避免把 AP 的頻道設成自動** —— 頻道變動會讓 BSSID/channel 快取失效

## 真正的下一個數量級：ESP-NOW

如果 1000 ms 還不夠，**唯一能再降一個數量級的方法是不要建立 WiFi 連線**。

ESP-NOW 是 Espressif 的 2.4GHz 直連協定：不掃描、不關聯、不握手、不要 IP，
初始化完就能直接對指定 MAC 發送。公開實測：從深睡到可發送約 **248 ms**
（38 ms 開機 + 58 ms `esp_wifi_init` + 152 ms `esp_wifi_start`），送一筆約 **60 ms**。

| | 優化後 WiFi | ESP-NOW |
|---|---|---|
| 喚醒視窗 | 1000 ms | **450 ms** |
| 單次能量 | 21.06 µAh | **6.83 µAh** |
| 5 分鐘 / 18650 | 9.9 個月 | **20.4 個月** |

**代價是需要一台常供電的 gateway**：一顆 ESP32 同時開 ESP-NOW 接收與 WiFi，
把收到的資料轉發成 MQTT。MQTT 這一段沒有消失，只是搬到 gateway 上做。

取捨：

- ✅ 續航翻倍、對 AP 完全免疫（不受路由器慢、頻道變動、DHCP 問題影響）
- ❌ 多一台裝置要供電與維護，多一個故障點
- ❌ ESP-NOW 節點與 gateway 必須在同一個 WiFi 頻道
- ❌ 沒有 TCP 的重傳保證，需自己做確認與重試

**建議**：先做 WiFi 版（M2），實測拿到真實視窗長度之後再決定。
如果 15 或 30 分鐘就夠用，WiFi 版已經有 20~28 個月，不需要 gateway 的複雜度。
ESP-NOW 只有在「非要 5 分鐘、又要一年以上續航」時才划算。

## 優化後的續航（XIAO ESP32C6）

| 間隔 | 未優化 (4.0s) | 優化後 (1.0s) | ESP-NOW (0.45s) |
|---|---|---|---|
| **18650 (3000mAh)** | | | |
| 5 分鐘 | 2.7 個月 ❌ | **9.9 個月** ✅ | 20.4 個月 ✅ |
| 15 分鐘 | 7.2 個月 ✅ | **20.1 個月** ✅ | 30.9 個月 ✅ |
| 30 分鐘 | 12.3 個月 ✅ | **27.1 個月** ✅ | 35.5 個月 ✅ |
| **21700 (5000mAh)** | | | |
| 5 分鐘 | 4.4 個月 ❌ | 14.7 個月 ✅ | 27.1 個月 ✅ |
| 15 分鐘 | 11.0 個月 ✅ | 26.8 個月 ✅ | 37.2 個月 ✅ |
| 30 分鐘 | 17.7 個月 ✅ | 33.8 個月 ✅ | 41.0 個月 ✅ |

**優化把 5 分鐘模式從不可行（2.7 個月）變成可行（9.9 個月）。**
這就是為什麼這份文件存在。

## 怎麼驗證

### 每次上傳都回報 `up` 欄位

MQTT payload 帶 `up`（本次喚醒視窗毫秒數），存進時序資料庫。
這是零成本的長期監控 —— 可以直接在圖上看到「哪天開始 WiFi 變慢」，
在電池真的沒電之前先發現。

### 分階段打時間戳（debug build）

```cpp
uint32_t t0     = millis();
// ... WiFi.begin() / 等待連線
uint32_t t_wifi = millis();
// ... MQTT connect + publish
uint32_t t_mqtt = millis();
```

debug build 從 Serial 印出來，或塞進 MQTT payload 的 debug 欄位。
**注意 `millis()` 從 app 開始才計時，量不到 bootloader 那段** ——
那段只能靠示波器看電流波形的起點。

### 示波器量完整波形

電池負極串 10 Ω 1% 電阻，示波器量壓降（1 mV = 0.1 mA）。
可以看到完整的階段輪廓：開機 → WiFi 啟動 → 關聯（TX 尖峰）→ MQTT → 進睡。
這是唯一能同時拿到「時間」與「電流」的方法，也是回填模型參數的唯一途徑。

### A/B 對照清單（M2）

每項單獨開關，同一 AP、同一位置各跑 50 次取**中位數**（不要取平均，離群值會失真）：

- [ ] 靜態 IP vs DHCP
- [ ] BSSID + channel 快取 開 / 關 ← **最需要驗證，證據互相矛盾**
- [ ] broker 用 IP vs 用主機名
- [ ] MQTT QoS 0 vs QoS 1
- [ ] CPU 160 MHz vs 80 MHz
- [ ] 外接天線 vs 板載天線（若 C6 兩者皆有）
- [ ] 不同 AP / 不同 RSSI 位置

## 來源

| 數據 | 來源 |
|---|---|
| 靜態 IP 省 1~3 秒、BSSID 快取可降到 1 秒內 | 多份社群實測（與官方 FAQ 衝突，見上） |
| 靜態 IP + BSSID + channel 仍花 3201 ms | [arduino-esp32 issue #1675](https://github.com/espressif/arduino-esp32/issues/1675) |
| ESP32 無法靠 BSSID 加速連線 | [ESP-FAQ - Wi-Fi](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/wifi.html) |
| 開機 138 ms (240MHz/QIO 80MHz)、180 ms (80MHz/DIO 40MHz) | [ESP-IDF Speed Optimization](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-guides/performance/speed.html) |
| `CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP` | [ESP-IDF Bootloader](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-guides/bootloader.html) |
| 部分校正比完整校正省 100 ms | [ESP-IDF RF Calibration](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-guides/RF_calibration.html) |
| 自建 bootloader 開機 ~86 ms | [Hackaday - Bootloader Wake Time Improvements](https://hackaday.io/project/174898/log/183782-bootloader-wake-time-improvements) |
| ESP-NOW 就緒 248 ms、送出 60 ms | [ThingPulse - Ultra-Long Battery Life With ESP-NOW](https://thingpulse.com/esp32-ultra-long-battery-life-with-espnow/) |
| C6 深睡 14.3 µA | [Seeed 論壇睡眠電流實測](https://forum.seeedstudio.com/t/comparison-of-sleep-currents-for-xiao-esp32c6-s3-and-c3/276444) |
