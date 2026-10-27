# Changelog

格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版號採用 [語意化版本](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### Added
- 專案初始架構、目錄結構與設計文件
- XIAO ESP32 系列選型比較（C3 / S3 / C6），結論選用 C6
- **WiFi 連線優化研究** `docs/wifi-optimization.md`：喚醒視窗分階段拆解、
  11 項優化手段、Arduino framework 限制、ESP-NOW 替代方案、A/B 驗證清單
- 分階段功耗模型與試算腳本 `scripts/power_budget.py`
- MQTT 協定規格、PlatformIO 專案骨架、CI 建置流程
- **WiFiManager 設定與佈建設計** `docs/provisioning.md`：
  設定入口網站的耗電陷阱與對策、三段式 IP 策略（自動 / 手動 / 關閉）、
  每日 DHCP 續約與失敗自我修復、NVS 與 RTC memory 的分工、首次佈建流程
- **M1 最小韌體** `firmware/envirosense-node/envirosense-node.ino`：未優化基準線
  （DHCP + 全頻掃描 → SHT40 → esp-mqtt QoS1 → 深睡），含電池電壓、I²C bus recovery
- **M3 韌體強健化**：RTC 狀態加 magic + CRC32 校驗（失敗即歸零並帶 `boot` 旗標）、
  上傳失敗存 `pending` 下次補送（最多 4 筆，滿了丟最舊）、連續失敗 `min(2^n, 8)` 倍間隔退避
- **完整版韌體**（待實板驗證）：
  - WiFiManager 設定頁（WiFi、間隔、broker、節點名稱、IP 策略），設定存 NVS；
    首次燒錄自動開，之後只能在冷開機 10 秒內按 BOOT 鍵（OneButton）或 MQTT `{"portal": true}` 觸發
  - 依開機原因分流：深睡計時器喚醒完全跳過按鍵等待
  - M2：三段式 IP 策略（自動記住 / 手動 / 關閉）、每日 DHCP 續約、失敗退回 DHCP（`ip_recache`）、
    BSSID + channel 快取（`cache_miss` / `wifi_retry`）、WiFi 關聯與 SHT40 讀取並行、`WIFI_PS_NONE`
  - M4：四段式電池處理（正常 / ×2 / ×4 / 永久深睡），USB 供電無電池時自動跳過
  - HA 自動探索（溫度、濕度、電池、RSSI），`cmd` 下行指令（interval / reboot / portal）

### Changed
- 分割區改用 No OTA（2MB APP）：加入 WiFiManager 後預設 1.2MB APP 只剩約 2%
- CI 安裝 WiFiManager 2.0.17、OneButton 2.6.1
- 設定模式觸發由「雙擊 reset」改為「冷開機 10 秒內按 BOOT 鍵」
- `config.h` 移除 M1 寫死的 WiFi / broker，改為設定頁預填值 `DEFAULT_MQTT_*`

### Changed
- **韌體工具鏈由 PlatformIO 改為 Arduino IDE**；CI 改用 arduino-cli，固定 esp32 core 3.3.7
- MQTT 由 PubSubClient 改為 core 內建 esp-mqtt（PubSubClient 無法 QoS1 publish）
- SHT40 改用 sketch 內建驅動，不再依賴 Sensirion 函式庫
- 功耗模型納入載板 DW01A 靜態電流 3 µA，全部續航數字重算（18650 / 15 分鐘：20.5 → 20.1 月）
- 設定改由 WiFiManager captive portal 在執行期提供（WiFi 憑證、上傳間隔、broker、IP 策略），
  `config.h` 縮減為編譯期預設值與安全參數
- **架構改為「醒來即量測即上傳」，取消批次緩衝**。間隔改為 5 / 15 / 30 分鐘三選一
- 功耗模型從「單一平均電流」改為「分階段模型」，才能看出優化該打哪個階段
- MQTT payload 改為單筆（移除相對時間戳與資料陣列）；
  失敗補送改用 `pending` 欄位，正常情況不出現
- **HA 版 0.2.1-ha**（新資料夾 `firmware/envirosense-node-ha-0.2.1/`，以 0.2.0-ha 為基礎）：
  state payload 加入 `bssid`、`ch`，分辨 mesh 環境下 RSSI 跳動是否為換 AP；payload 最長約 430 bytes
- **HA 版 0.2.2-ha**（新資料夾 `firmware/envirosense-node-ha-0.2.2/`，以 0.2.1-ha 為基礎）：
  HA 探索訊息加入作者資訊（`dev.mf` = `HoDZadkiel`、`o.url` = `https://github.com/HoDZadkiel`）；
  新增預編譯二進位檔 `firmware/release/0.2.2-ha/`（整合映像 + 分開的各段 + SHA256SUMS + 內建 esptool.exe + `flash.bat` / `flash.sh`，只需 COM port 即可燒錄）；新增網頁燒錄頁 `web-flasher/`（ESP Web Tools 10.2.1 + manifest，可放 GitHub Pages）

### Fixed
以下為 **HA 版 0.2.0-ha**，放在新資料夾 `firmware/envirosense-node-ha-0.2.0/`；
0.1.0-ha 原封不動留在 `firmware/envirosense-node-ha/`。
- 中文節點名稱被 WiFiManager 按 byte 截斷、切壞 UTF-8，HA 會丟棄探索訊息。
  `sanitize()` 改成丟掉結尾殘缺的字元與控制字元，名稱上限 31 → 63 byte（中文 21 字）
- 探索前綴含 `+`、`#`、空白或頭尾 `/` 時退回 `homeassistant`
- 例行喚醒要連續兩次低於截止電壓才永久深睡，避免負載下的單次低讀值誤關機（RTC_MAGIC 換版）
- payload 組裝改成有邊界檢查的 `appendf()`，放不下時丟掉補送資料並帶 `payload_trunc`，不再越界寫入

以下為 **主程式 0.2.0**，放在新資料夾 `firmware/envirosense-node-0.2.0/`；
原版原封不動留在 `firmware/envirosense-node/`。移植 0.2.0-ha 的修正（主程式探索前綴固定，不需要前綴驗證）：
- `sanitize()` 逐 byte 過濾並丟掉結尾殘缺的 UTF-8，節點名稱上限 31 → 63 byte（中文 21 字）
- 例行喚醒要連續兩次低於截止電壓才永久深睡（RTC_MAGIC 0x45535638 → 0x45535639）
- payload 組裝改用 `appendf()`，放不下時帶 `payload_trunc`
- 新增 `FW_VERSION "0.2.0"`，設定頁的韌體欄由編譯日期改顯示版號

### Removed
- 批次緩衝相關設計（RTC memory 取樣佇列、相對時間戳、伺服器端時間回填）
- 因取消批次而不再需要的 NTP 校時與 Home Assistant 資料庫橋接

### 尚未實作
- 全部韌體程式碼（里程碑 M1~M4）
- 硬體載板（M5）
- 伺服器端佈署設定（broker 尚未定案）
