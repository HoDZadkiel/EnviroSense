# 網頁燒錄（ESP Web Tools）

在瀏覽器按一個按鈕就能把 EnviroSense HA 版燒進 Seeed XIAO ESP32C6。
原理與各專案的做法見 [`../docs/online-flashing.md`](../docs/online-flashing.md)。

| 檔案 | 說明 |
|---|---|
| `index.html` | 燒錄頁，載入 [ESP Web Tools](https://esphome.github.io/esp-web-tools/) **10.2.1**（固定版本，從 unpkg 載入） |
| `manifest.json` | `ESP32-C6`、整合映像寫到 offset `0`；`new_install_prompt_erase: true`（安裝時詢問是否清除 flash） |
| `firmware/*-merged.bin` | 與 `../firmware/release/0.2.2-ha/bins/` 內相同的整合映像（`SHA256SUMS.txt` 可比對） |

## 本機預覽

Web Serial 只在 **HTTPS 或 localhost** 可用：

```bash
cd web-flasher
python -m http.server 8765
# 瀏覽器開 http://localhost:8765/
```

## 發佈到 GitHub Pages

1. 把 `web-flasher/` 的內容放到 repo 的 Pages 來源（例如 `docs/` 或 `gh-pages` 分支根目錄）
2. repo → Settings → Pages 選該來源；網址會是 `https://<使用者>.github.io/<repo>/`（HTTPS，符合 Web Serial 要求）
3. **同源託管**：`manifest.json` 與 `.bin` 要和 `index.html` 在同一站台，否則要另外設 CORS

## 出新版韌體時

1. 重新編譯，更新 `../firmware/release/<版本>/`
2. 把新的 merged.bin 複製到 `firmware/`，更新 `manifest.json` 的 `version` 與 `path`，`index.html` 的版本文字
3. 舊的 .bin 刪掉，避免 repo 越長越大（每份 4 MB）

## 使用者端

桌面版 Chrome / Edge。進燒錄模式（**按住 BOOT → 按一下 RESET → 放開 BOOT**）後按按鈕、選 COM port。
節點平常在深睡，USB 序列埠不會出現，所以這一步不能省。

## 已驗證 / 未驗證

- 已驗證：頁面在 localhost 載入、`<esp-web-install-button>` 元件已註冊、`navigator.serial` 可用、manifest 可讀、console 無錯誤
- 已確認 ESP Web Tools 10.2.1 的套件內含 `esp32c6` 模組
- **未驗證：實際連接裝置並燒錄**（沒有接板子），清除選項與燒錄進度都沒走過
