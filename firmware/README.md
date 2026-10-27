> **公開版說明**：韌體原始碼（`.ino`、`config.h*`）不公開，本 repo 只提供 [`release/`](./release/) 的預編譯二進位檔。
> 下面的建置與目錄說明保留作為設計文件；其中提到的原始碼資料夾在本 repo 中不存在。

# 韌體

Arduino IDE sketch，目標板 **Seeed XIAO ESP32C6**（esp32 core 3.x，已驗證 3.3.7 可編譯）。

## 建置

1. 把 `envirosense-node/config.h.example` 複製成 `config.h`。MQTT 欄位只是設定頁的預填值，可留空
   （WiFi、間隔、broker 都在執行期由設定頁寫進 NVS，見下方「設定流程」）
2. 函式庫管理員安裝 **WiFiManager**（tzapu，2.0.17）與 **OneButton**（2.6.1）
3. Arduino IDE 開啟 `envirosense-node/envirosense-node.ino`
4. 「工具」選單設定：

| 項目 | release（量功耗用） | debug（看 log） |
|---|---|---|
| 開發板 | XIAO_ESP32C6 | 同左 |
| Partition Scheme | **No OTA (2MB APP/2MB SPIFFS)** | 同左 |
| `config.h` 的 `ENVIROSENSE_DEBUG` | `0` | `1` |
| USB CDC On Boot | **Disabled** | Enabled |
| CPU Frequency | 160MHz | 同左 |
| Flash Mode / Frequency | QIO / 80MHz | 同左 |
| Core Debug Level | None | 同左（或 Info） |

- **量測功耗一定要用 release**：USB CDC 會拉長開機時間，debug 還會為了等 CDC 列舉多等 1.5 秒
- 「USB CDC On Boot」只決定 `Serial` 走 USB 序列埠還是 UART0（D6/D7），C6 的 USB 序列埠是晶片內建硬體，
  選 Disabled 電腦一樣認得到 COM port。release 不印 log，選 Disabled 只是省掉 CDC 驅動初始化
- ⚠ 節點大部分時間在深睡，直接按上傳會燒不進去，見下方「燒錄」
- **分割區一定要選 No OTA**：加入 WiFiManager 後韌體約 1.27 MB，預設的 1.2MB APP 只剩約 2%。
  韌體目前沒有 OTA 功能，不需要第二個 app 分割區
- SHT40 驅動寫在 sketch 裡，MQTT 用 core 內建的 esp-mqtt

命令列建置（CI 用同一組參數）：

```bash
arduino-cli compile -b esp32:esp32:XIAO_ESP32C6:CDCOnBoot=default,PartitionScheme=no_ota firmware/envirosense-node
```

## 燒錄

節點大部分時間在深睡，深睡時 USB 跟著斷電、COM port 消失，IDE 直接按上傳會燒不進去。
要先讓晶片保持醒著（release / debug 都一樣），兩種方法：

**A. 設定頁法（日常更新用，不必拔電池）**

1. Arduino IDE 按「上傳」，開始編譯
2. 趁編譯時按一下 **RESET**（= 冷開機）
3. **等 LED 亮**，10 秒內按一下 **BOOT** → 設定頁開啟、LED 恆亮，晶片保持醒著最多 180 秒
4. 編譯完 IDE 會經 USB 自動重置進燒錄模式並寫入，燒完自動重開

- 裝著電池時只拔插 USB **不會**重開機（晶片仍由電池供電、繼續深睡），要按 RESET
- ⚠ 按住 BOOT 的同時按 RESET 或上電會直接進燒錄模式（等於方法 B），不會開設定頁
- 一直卡在 `Connecting...` 就改用方法 B

**B. 手動進 bootloader（最保險）**

按住 **BOOT** → 按一下 **RESET** → 放開 BOOT，晶片停在燒錄模式，再按上傳。
不論韌體目前狀態如何都能用（韌體當掉、反覆重開、正在深睡）。燒完若沒有自動重開，按一次 RESET 執行新韌體。

兩種方法都不會清除 NVS，WiFi / MQTT / 間隔設定燒錄後都會保留（換分割區配置除外）。

## 設定流程

| 情境 | 行為 |
|---|---|
| 首次燒錄（NVS 沒有設定） | 自動開設定頁 |
| 冷開機（上電 / 按 RESET / 換電池） | LED 亮 **10 秒**，期間**按一下 BOOT 鍵** → 開設定頁；沒按就照常上傳 |
| 深睡計時器喚醒（例行上傳） | 完全不等按鍵，零延遲 |
| 任何連線失敗 | **絕不**開設定頁，存 pending、退避、回去睡 |

- 手機連上 AP「`EnviroSense-<MAC 後 6 碼>`」→ 自動跳出設定頁 → 選 WiFi、填 broker、選間隔與 IP 策略 → 存檔
- 設定頁開著時 LED 恆亮。**180 秒**沒存檔就關閉回去睡
- **只改參數**（不選 WiFi、密碼欄留空）→ 存檔後設定頁立刻關閉，用新參數照常上傳，不會重開機。
  有選 WiFi 時要試連成功才關閉；試連失敗會回到設定頁（⚠ 選了 SSID 卻沒填密碼欄，等於以空白試連，一定失敗）
- ⚠ **等 LED 亮了再按 BOOT**：按住 BOOT 再上電 / RESET 會進燒錄模式
- 電池低於 3.5 V 拒絕開設定頁；低於 3.3 V 永久深睡（充電後按 RESET 恢復；主程式 0.2.0 與 HA 版 0.2.0 起，例行喚醒要連續兩次低於才關）。
  沒裝電池、由 USB 供電（BAT < 2.5 V）時電池保護全部跳過，可在 USB 下完成設定
- 遠端也能叫它開設定頁：對 `envirosense/<id>/cmd` 發 retain 的 `{"portal": true}`，
  節點約一天收一次指令，收到後立刻開（人要在旁邊）

## 目錄

| 路徑 | 用途 |
|---|---|
| `envirosense-node/envirosense-node.ino` | 主程式（檔名必須與資料夾同名） |
| `envirosense-node/config.h.example` | 設定範本。複製成 `config.h`（不入版控） |
| `envirosense-node-0.2.0/` | **主程式 0.2.0**：原版加上 0.2.0-ha 的可靠性修正，見下方 |
| `envirosense-node-ha/` | **HA 相容版 0.1.0-ha**，建置與燒錄方式同上（`config.h` 一樣從範本複製），見下方 |
| `envirosense-node-ha-0.2.0/` | **HA 相容版 0.2.0-ha**：0.1.0-ha 加上可靠性修正，見下方 |
| `envirosense-node-ha-0.2.1/` | **HA 相容版 0.2.1-ha**：0.2.0-ha 的 payload 加上 `bssid` / `ch`，見下方 |
| `envirosense-node-ha-0.2.2/` | **HA 相容版 0.2.2-ha**：0.2.1-ha 的 HA 探索加上作者資訊，見下方 |
| `release/0.2.2-ha/` | **預編譯二進位檔 + 內建 esptool + `flash.bat` / `flash.sh`**（不含任何登入資料），只需知道 COM port 即可燒錄，見 [`release/0.2.2-ha/README.md`](./release/0.2.2-ha/README.md) |
| `solder-check/solder-check.ino` | 載板焊接驗證，見下方 |

## 主程式 0.2.0（envirosense-node-0.2.0）

原版原封不動保留在 `envirosense-node/`，兩個資料夾可以各自燒錄、互相切換。建置方式同上，
`arduino-cli compile` 的路徑改成 `firmware/envirosense-node-0.2.0`。移植自 0.2.0-ha 的修正：

- 中文節點名稱不會再被切成半個字（上限 63 byte = 中文 21 字）
- 例行喚醒要**連續兩次**低於 3.3 V 才永久深睡
- payload 組裝有邊界檢查，放不下時改帶 `payload_trunc` 旗標
- 設定頁的「韌體」欄改顯示版號 `0.2.0`（原版顯示編譯日期）

主程式的探索前綴固定，所以沒有 0.2.0-ha 的前綴驗證。協定差異見
[`../docs/mqtt-protocol.md`](../docs/mqtt-protocol.md)「主程式 0.2.0 的差異」。
NVS 設定與 `unique_id` 共用；RTC 狀態結構換版，第一次喚醒會帶 `boot` 旗標。
用原版存過中文名稱、而且已經被切壞的節點，要進設定頁重新存一次。

## HA 相容版（envirosense-node-ha）

協定跟主程式相同（state topic、欄位、status/LWT 都沒有改），所以不用 HA 的客戶端可以直接沿用。
多出來的部分都是給 Home Assistant 用的：

- state 改成 **retain**：新訂閱者和 HA 重啟後會立刻拿到最後一筆
- HA 探索多帶 `sug_dsp_prc`（顯示的小數位數）、`def_ent_id`（讓 entity_id 維持 ASCII）、`dev.sw`、origin（`o`）
- 設定頁的「MQTT」分組可以**關閉 HA 探索**（只發 state）和**修改探索前綴**；改完後下次上傳會重發探索
- 探索不帶 `avty_t`，HA 只用 `exp_aft` 判斷離線（理由見 [`../docs/mqtt-protocol.md`](../docs/mqtt-protocol.md) 最後一節）
- **進設定頁改成連按兩次 RESET，不用 BOOT 鍵**：冷開機後 LED 亮著的 10 秒（`DRD_WINDOW_S`）內再按一次 RESET → 開設定頁。
  旗標存 NVS（`drd`）。原因：有一片板子 BOOT（GPIO9）與 3V3 短路，按 BOOT 等於 3V3 對地短路。
  上面「燒錄 A」與「設定流程」表裡的「按 BOOT」在這一版都改成「再按一次 RESET」；不需要 OneButton 函式庫

從主程式換成這一版時 NVS 設定會保留，`unique_id` 也一樣，HA 的歷史不會斷。

### 0.2.0-ha（envirosense-node-ha-0.2.0）

0.1.0-ha 原封不動保留在 `envirosense-node-ha/`，兩個資料夾可以各自燒錄、互相切換。0.2.0 多了這些修正：

- 中文節點名稱不會再被切成半個字（上限 63 byte = 中文 21 字）；探索前綴含 `+`、`#`、空白或頭尾 `/` 會退回預設
- 例行喚醒要**連續兩次**低於 3.3 V 才永久深睡
- payload 組裝有邊界檢查，放不下時改帶 `payload_trunc` 旗標

協定差異見 [`../docs/mqtt-protocol.md`](../docs/mqtt-protocol.md)「0.2.0-ha 的差異」。
NVS 設定與 `unique_id` 共用，兩版之間切換 HA 的歷史不會斷。
用 0.1.0 存過中文名稱、而且已經被切壞的節點，要進設定頁重新存一次。

### 0.2.1-ha（envirosense-node-ha-0.2.1）

以 0.2.0-ha 為基礎，state payload 多帶 `bssid`（連上的 AP MAC）與 `ch`（channel），
用來在同 SSID 的 mesh 環境分辨 RSSI 跳動是換了 AP 還是訊號變化。其餘行為與 0.2.0-ha 相同，
NVS 設定、RTC 狀態結構與 `unique_id` 都沒變，直接覆蓋燒錄即可。
協定差異見 [`../docs/mqtt-protocol.md`](../docs/mqtt-protocol.md)「0.2.1-ha 的差異」。

### 0.2.2-ha（envirosense-node-ha-0.2.2）

以 0.2.1-ha 為基礎，HA 探索訊息加入作者資訊：裝置的製造商（`dev.mf`）顯示 `HoDZadkiel`，
origin 的 `url` 指向 <https://github.com/HoDZadkiel>。state payload 與其餘行為不變，
NVS、RTC 狀態與 `unique_id` 都沒變，直接覆蓋燒錄即可。HA 要等節點重發探索才會更新製造商欄位。
預編譯二進位檔與 esptool 指令見 [`release/0.2.2-ha/`](./release/0.2.2-ha/README.md)。
協定差異見 [`../docs/mqtt-protocol.md`](../docs/mqtt-protocol.md)「0.2.2-ha 的差異」。

## 焊接驗證（solder-check）

獨立 sketch，不需 `config.h`、不連 WiFi。「USB CDC On Boot」選 **Enabled**，燒錄後開序列埠（115200），按 `r` + Enter 可重跑。
沒開序列埠也能看板載 LED：**恆亮 = 全過、慢閃 = 有警告、快閃 = 有失敗**。

| 項目 | 驗到什麼 |
|---|---|
| 腳位卡死 | D0~D10 對 GND / 對電源的錫橋；D4/D5 的 10kΩ 上拉有沒有焊上 |
| 互相短路 | 任兩支 D 腳之間的錫橋（castellated 焊點最常見） |
| I²C / SHT40 | 位址 0x44、讀序號 CRC、量測值合理、加熱 1 秒後溫度有上升 |
| 電池分壓 | D3 開閘後 A0 有下降（2N7002 + 兩顆 2MΩ）、Vbat 換算、C1 100nF 的時間常數 |

驗不到的：**DW01A / 8205A 保護電路**（沒有電芯就不會上電）。
沒有電池時 BAT 焊盤由充電 IC 供電，可能反覆充停而跳動（會出現「BAT 穩定度」WARN，屬正常）或是 0 V。
要驗保護電路與準確的 Vbat，可用電源供應器 **3.7 V、限流 200 mA** 接到電池座（**注意極性**），
再跑一次，並用電錶量 BAT 焊盤比對 Vbat 換算值。

Arduino IDE 只編譯 sketch 根目錄與 `src/` 子資料夾。之後拆模組時，放在根目錄的 `.h` / `.cpp`。

## 實作要點

架構與狀態機見專案根目錄 [`README.md`](../README.md)，
連線優化手段見 [`../docs/wifi-optimization.md`](../docs/wifi-optimization.md)。

**這個專案的韌體工作有 80% 是在縮短喚醒視窗。** 幾件最容易踩雷的事：

1. **狀態存 RTC memory，不要存 NVS。** WiFi cache 每次都可能更新，
   寫 NVS 既耗電又會磨損 flash。NVS 只放幾乎不變的設定
2. **RTC memory 要做 CRC 校驗。** 異常重開（brownout、watchdog）後內容可能是垃圾，
   校驗失敗就整個歸零重來
3. **`WiFi.config()` 必須在 `WiFi.begin()` 之前呼叫**，否則靜態 IP 不生效，
   會安靜地退回 DHCP —— 症狀是視窗莫名多 1 秒，很難發現。
   這一項單獨就值 +37%~+80% 續航，一定要在 M2 確認真的生效
4. **每次都要量並回報 `up`（視窗耗時）。** 這是唯一能長期監控續航劣化的手段
5. **不要為了省電降頻到 80 MHz。** 能量 = 功率 × 時間，這種短衝刺工作降頻是淨虧損
6. **絕不可用 WiFiManager 的 `autoConnect()` 預設行為。** 它會在連不上時自動開設定
   入口網站，開 3 分鐘就吃掉 15 分鐘模式一整天的電；若反覆誤開，電池 6 天見底。
   連線失敗一律回去睡，設定模式只能由人明確觸發 —— 見
   [`../docs/provisioning.md`](../docs/provisioning.md)
7. **設定鍵的等待要先看開機原因。** `esp_reset_reason() == ESP_RST_DEEPSLEEP` 是例行上傳，
   直接跳過；否則每次喚醒都要多等 10 秒，比整個 WiFi 優化省下的還多
8. **每次喚醒都會變的東西不准寫 NVS**（BSSID 快取、seq、pending）→ 放 RTC memory。
   一天寫 288 次、跑兩年就是 20 萬次寫入，會把 flash 磨壞

## Arduino framework 的限制

`CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP`、`CONFIG_ESP_PHY_CALIBRATION_AND_DATA_STORAGE`、
`CONFIG_RTC_CLK_CAL_CYCLES` 這幾項是 **ESP-IDF 的 sdkconfig 選項**，
而 Arduino core 與 bootloader 是預先編譯好的二進位檔 —— **從 Arduino IDE 端改不動**。

這三項合計只省約 250 ms，而純 Arduino 就能拿到的優化（靜態 IP、BSSID 快取、IP 直連）
可省約 2000 ms。**先走純 Arduino**，M2 實測後若還差臨門一腳再考慮換 ESP-IDF。
