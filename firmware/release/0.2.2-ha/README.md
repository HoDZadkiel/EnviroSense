# EnviroSense HA 版 0.2.2-ha — 預編譯韌體與燒錄工具

作者：[HoDZadkiel](https://github.com/HoDZadkiel)。目標板 **Seeed XIAO ESP32C6**（`esp32:esp32:XIAO_ESP32C6`，4 MB flash），
**不能**燒在 C3 / S3 或其他板子。Home Assistant 裝置頁的製造商顯示作者名，探索訊息的 `origin.url` 指向作者 GitHub。

這是 release 版（`ENVIROSENSE_DEBUG 0`），用 `config.h.example` 編譯，**不含任何 WiFi / MQTT 帳密**；
WiFi、broker、間隔都在燒錄後由設定頁填寫（見 [`../../README.md`](../../README.md)）。

## 最快的燒錄方式：只需要知道 COM port

整個資料夾下載下來（**不要拆開、保持資料夾結構**），不需要安裝 Python 或 esptool。

### Windows

1. 讓晶片進燒錄模式：**按住 BOOT → 按一下 RESET → 放開 BOOT**（節點大部分時間在深睡，USB 序列埠不會出現）
2. 裝置管理員 →「連接埠 (COM 和 LPT)」找出 COM 編號
3. 在資料夾裡開終端機：

```bat
flash.bat COM5
```

沒帶參數會互動式詢問。會問你選哪種：

| 選項 | 做什麼 | 設定會保留嗎 |
|---|---|---|
| **1 全新安裝** (`full`) | 整合映像寫到 `0x0`，整顆 flash 都被覆蓋 | ❌ 會清掉 WiFi / MQTT 設定 |
| **2 更新** (`update`) | 只寫 app 到 `0x10000` | ✅ 保留（要先裝過本韌體） |

也可以直接帶第二個參數：`flash.bat COM5 full` / `flash.bat COM5 update`。
腳本的提示訊息是英文（避免 cmd 在不同系統語系下亂碼），說明以本文件為準。

### Linux / macOS

需要先 `pip install esptool`（本資料夾只內建 Windows 版執行檔）：

```bash
./flash.sh /dev/ttyACM0            # macOS: /dev/cu.usbmodemXXXX
./flash.sh /dev/ttyACM0 update
```

Linux 若出現 permission denied：`sudo usermod -aG dialout $USER` 後重新登入。

### 燒完之後

按一次 RESET 執行新韌體。**首次安裝**：RESET 後等 LED 亮，10 秒內再按一次 RESET → 開設定頁（AP 名稱 `EnviroSense-<MAC 後 6 碼>`）。

### 失敗了怎麼辦

- 卡在 `Connecting...` 或找不到連接埠：重新進燒錄模式（BOOT + RESET），確認 USB 線可傳資料
- `port is busy`：關掉 Arduino IDE 序列埠監控、PuTTY 等占用序列埠的程式
- COM 編號不對：拔掉再插上，看裝置管理員哪一項消失又出現

## 資料夾內容

| 路徑 | 說明 |
|---|---|
| `flash.bat` / `flash.sh` | 燒錄腳本 |
| `tools/windows/esptool.exe` | esptool v5.3.1 Windows 執行檔（取自 Espressif esp32 Arduino core 的工具包，**未修改**） |
| `tools/LICENSE-esptool-GPLv2.txt` | esptool 授權（GPL-2.0），原始碼：<https://github.com/espressif/esptool> |
| `bins/*-merged.bin` | 整合映像（bootloader + 分割表 + app），燒到 `0x0` |
| `bins/*-app.bin` | 只有應用程式，燒到 `0x10000` |
| `bins/*-bootloader.bin` / `-partitions.bin` / `-boot_app0.bin` | 分開燒時用：`0x0` / `0x8000` / `0xe000` |
| `SHA256SUMS.txt` | 校驗碼，驗證：`cd bins && sha256sum -c ../SHA256SUMS.txt` |

## 手動指令（不用腳本）

```bash
esptool --chip esp32c6 -p COM5 -b 460800 write-flash 0x0 bins/envirosense-ha-0.2.2-esp32c6-merged.bin      # 全新安裝
esptool --chip esp32c6 -p COM5 -b 460800 write-flash 0x10000 bins/envirosense-ha-0.2.2-esp32c6-app.bin     # 更新
```

舊版 esptool（v4 以下）指令寫 `esptool.py` 與 `write_flash`。

## 原始碼

韌體原始碼**不公開**，只提供本資料夾的預編譯二進位檔。
編譯環境為 Arduino `esp32:esp32:XIAO_ESP32C6`（esp32 core 3.3.12、WiFiManager 2.0.17，`PartitionScheme=no_ota`）。
