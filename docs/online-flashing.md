# 線上（瀏覽器）燒錄研究

目的：評估 EnviroSense 要不要提供「網頁上按一下就燒錄」，以及怎麼做。調查日期 2026-10-28。
目前的做法是 [`firmware/release/0.2.2-ha/`](../firmware/release/0.2.2-ha/README.md) 的 `flash.bat` + esptool。

## 它們怎麼做到的

瀏覽器本來不能碰 USB 序列埠。關鍵是 **Web Serial API**：網頁呼叫 `navigator.serial.requestPort()`，
瀏覽器跳出選擇視窗，使用者選裝置後，網頁的 JavaScript 就能直接對序列埠讀寫。
再把 Python 的 esptool 用 JavaScript 重寫一份，就能在網頁裡跟晶片的 ROM bootloader 對話。

```
網頁（HTTPS）
 └ <esp-web-install-button manifest="manifest.json">      ← ESP Web Tools（Web Component）
     ├ 讀 manifest.json：依晶片種類挑 build、每個 .bin 的 offset
     ├ esptool-js：Web Serial 上跑 esptool 協定，偵測晶片、寫 flash
     └ Improv Serial：燒完後從網頁直接設定裝置 WiFi
```

| 層 | 專案 | 做什麼 |
|---|---|---|
| 瀏覽器 API | Web Serial | 網頁存取序列埠；僅 Chromium 系（Chrome / Edge / Opera）穩定，iOS 不支援，頁面必須 HTTPS（localhost 例外） |
| 燒錄引擎 | [esptool-js](https://github.com/espressif/esptool-js)（Espressif 官方） | 用 `Transport` 包住序列埠、`ESPLoader.main()` 連線並重置、偵測晶片；`writeFlash` 傳入 `{data, address}` 陣列，可壓縮傳輸、可選 MD5 驗證；用 DTR/RTS 重置策略（`classicReset`、`hardReset`、`usbJTAGSerialReset`）把晶片拉進下載模式 |
| UI 外殼 | [ESP Web Tools](https://github.com/esphome/esp-web-tools)（ESPHome / Nabu Casa） | `<esp-web-install-button>` 一個標籤包好「選連接埠 → 偵測晶片 → 是否清除 → 燒錄進度 → Improv 設定 WiFi」整個流程 |
| 燒錄後設定 | [Improv Wi-Fi serial](https://github.com/improv-wifi/sdk-serial-js) | 網頁透過序列埠把 WiFi 設定送給裝置，裝置提供設定網址，免手機 captive portal |

esptool-js 的 README 沒有交代底層協定（SLIP 封包、stub loader）的細節，上表只寫文件確實有的部分。

### manifest.json（ESP Web Tools 的核心）

一個 JSON 描述「有哪些 build、每個 build 要寫哪些檔到哪個位址」，按鈕偵測到晶片後自動挑對應的 build：

```json
{
  "name": "EnviroSense",
  "version": "0.2.2-ha",
  "new_install_prompt_erase": true,
  "builds": [
    {
      "chipFamily": "ESP32-C6",
      "parts": [{ "path": "bins/envirosense-ha-0.2.2-esp32c6-merged.bin", "offset": 0 }]
    }
  ]
}
```

要點（來自官方文件）：
- `parts[].path` 相對於 manifest；檔案若在別的網站，伺服器要送 CORS 標頭。
- `new_install_prompt_erase: true` 讓使用者選擇首次安裝要不要清空 flash（預設會清）。
- 多晶片：同一份 manifest 放多個 `builds`，用 `chipFamily` 區分；`serialType: "cdc"|"uart"` 可再分原生 USB 與 USB-UART 橋接。
- **ESP32 系列（IDF v4 以上）必須先合併成單一 .bin**，因為 ESP Web Tools 無法即時修補 flash 設定——這正是我們已有的 `merged.bin`。
- 上面 manifest 的 `ESP32-C6` 與 offset 0 是依文件格式推出來的，**沒有實際測試過**。

### 各專案的實際做法

| 專案 | 做法 |
|---|---|
| **ESPHome** | 官方 Web Installer 用 ESP Web Tools，編譯好的 firmware 透過 manifest 提供；它也是 ESP Web Tools 的發起者 |
| **WLED** | [install.wled.me](https://install.wled.me) 用 ESP Web Tools + Improv；官方文件註明 flash 小於 4 MB 的板子（如 ESP-01）不支援 |
| **Tasmota** | [tasmota.github.io](https://tasmota.github.io) Web Installer，燒錄會**清掉**既有韌體；另有社群 fork（`tasmota-esp-web-tools`） |
| **M5Stack** 等硬體商 | 文件直接導向 ESPHome / ESP Web Tools 的網頁燒錄 |

共通模式：**CI 編譯 → 產生 merged bin + manifest → 放 GitHub Pages / 自家 HTTPS 站 → 網頁嵌 install button**。
（這個流程是從各專案文件與 ESP Web Tools 用法歸納的，我沒有逐一檢查它們的 CI 設定。）

## 限制與坑

- **只有 Chromium 系桌面瀏覽器最穩**；iOS 不行，Android 需 polyfill、支援有限。ESP Web Tools 文件另稱 Firefox 也可，但搜尋結果的說法不一致，選用前要實測。
- 要 HTTPS。GitHub Pages 預設就是 HTTPS，所以最常用的託管方式。
- 驅動：Windows 對 CH340 / CP210x 等 USB-UART 晶片可能要裝驅動；**XIAO ESP32C6 是原生 USB（USB-Serial/JTAG）**，通常免驅動，
  esptool-js 內建 `usbJTAGSerialReset` 重置策略。
- 晶片在深睡時 USB 不存在——本專案的節點平時就是這樣，網頁燒錄前同樣要先 **BOOT + RESET** 進下載模式。
- Linux Snap 版 Chromium 無法存取序列埠；一般 Linux 要把使用者加入 `dialout`。
- ESPHome 社群有討論把本機 USB 燒錄導向網頁燒錄器的疑慮（依賴線上服務）；回覆稱燒錄全程在本機經 USB 進行，
  網頁只提供程式與 .bin，但那是社群回覆不是官方文件。無論如何，**保留離線腳本**（本專案已有）仍有價值。

## 對 EnviroSense 的建議

> 已實作：[`../web-flasher/`](../web-flasher/README.md)（2026-10-28）。以下為當時的評估。

已經具備的條件：單一 `merged.bin`（C6、offset 0）、固定的晶片（只有 ESP32-C6）。要做網頁燒錄只需再加：

1. 一份 `manifest.json`（如上）＋一個放 `<esp-web-install-button>` 的 `index.html`
2. 用 GitHub Pages 託管，CI 編譯後自動更新 `bins/` 與 manifest 版本
3. 選用：韌體實作 Improv Serial，燒完直接在網頁設定 WiFi。**目前用 WiFiManager 的 captive portal**，
   且為了省電，設定入口只能由人明確觸發（見 [`provisioning.md`](./provisioning.md)）；Improv 要監聽序列埠，
   可能跟「喚醒視窗越短越好」衝突，建議不做，或只在進設定頁時才啟用

要不要做取決於使用者規模：少數自用的話現有 `flash.bat` 已足夠；若希望 GitHub 上的陌生使用者零安裝，網頁燒錄體驗最好。

## 資料來源

- [ESP Web Tools 官方文件](https://esphome.github.io/esp-web-tools/)、[GitHub](https://github.com/esphome/esp-web-tools)
- [esptool-js](https://github.com/espressif/esptool-js)
- [Improv Wi-Fi serial SDK](https://github.com/improv-wifi/sdk-serial-js)
- [WLED 安裝說明](https://kno.wled.ge/basics/install-binary/)、[WLED Web Installer](https://install.wled.me)
- [ESP-Web-Tools-Tutorial（witnessmenow）](https://github.com/witnessmenow/ESP-Web-Tools-Tutorial)
- [Home Assistant 社群：ESPHome 線上燒錄器討論](https://community.home-assistant.io/t/concern-about-esphome-usb-flashing-now-requiring-an-online-web-flasher/1018443)
