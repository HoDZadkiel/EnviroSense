# 網頁燒錄（ESP Web Tools）

在瀏覽器按一個按鈕就能把 EnviroSense HA 版燒進 Seeed XIAO ESP32C6。
原理與各專案的做法見 [`../docs/online-flashing.md`](../docs/online-flashing.md)。

| 檔案 | 說明 |
|---|---|
| `index.html` | 燒錄頁模板，載入 [ESP Web Tools](https://esphome.github.io/esp-web-tools/) **10.2.1**（固定版本，從 unpkg 載入）。`__VERSION__` 會在部署時換成 Release 版號 |
| `manifest.template.json` | `ESP32-C6`、整合映像寫到 offset `0`；`new_install_prompt_erase: true`（安裝時詢問是否清除 flash）。`__VERSION__`、`__BIN__` 部署時填入 |

**整合映像不放在 repo 裡**。發佈 Release 時，[`pages.yml`](../.github/workflows/pages.yml) 會下載該版的
`*-merged.bin` 與 `SHA256SUMS.txt`、驗證校驗碼，再把網站部署到 GitHub Pages。

## 啟用 Pages（一次性）

repo → Settings → Pages → Source 選 **GitHub Actions**。之後每次 Release 發佈都會自動部署；
也可以在 Actions 頁手動執行 `pages` 部署最新一版。

## 本機預覽

Web Serial 只在 **HTTPS 或 localhost** 可用。先從 Release 下載 merged.bin，再用模板產生網站：

```bash
mkdir -p site/firmware
gh release download <tag> --pattern '*-merged.bin' --dir site/firmware
BIN=$(basename site/firmware/*-merged.bin); VER=<版號，例如 0.2.2-ha>
sed "s/__VERSION__/$VER/g" web-flasher/index.html > site/index.html
sed -e "s/__VERSION__/$VER/g" -e "s#__BIN__#firmware/$BIN#g" web-flasher/manifest.template.json > site/manifest.json
cd site && python -m http.server 8765      # 開 http://localhost:8765/
```

## 使用者端

桌面版 Chrome / Edge。進燒錄模式（**按住 BOOT → 按一下 RESET → 放開 BOOT**）後按按鈕、選 COM port。
節點平常在深睡，USB 序列埠不會出現，所以這一步不能省。

## 已驗證 / 未驗證

- 已驗證（前一版）：頁面在 localhost 載入、元件已註冊、`navigator.serial` 可用、console 無錯誤
- 已確認 ESP Web Tools 10.2.1 的套件內含 `esp32c6` 模組
- **未驗證：實際連接裝置並燒錄**；`pages.yml` 還沒在 GitHub 上實際跑過
