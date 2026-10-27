# CLAUDE.md — EnviroSense

本檔給進入這個專案的 AI agent 看，**內容自足，不依賴任何特定機器上的設定**。執行環境若另有全域指示，那是額外的；照本檔做就能正確參與這個專案。

## 專案目標

以 Seeed XIAO ESP32C6、單顆 21700 鋰電池與 MQTT 打造的低功耗環境溫濕度感測節點。

背景：節點每次醒來就量測並立即上傳（不做批次緩衝），目標是單次充電運作 6 個月以上。
耗電幾乎全花在喚醒視窗（WiFi 連線 + MQTT），所以專案的技術重心是縮短視窗與驗證續航。
專案直接做 PCB，不經洞洞板驗證。公開 repo 提供文件、硬體設計與**預編譯韌體**，韌體原始碼不公開。

## 專案性質與技術棧

| 項目 | 內容 |
|------|------|
| 類型 | `embedded`（板子加程式都自己做） |
| 技術棧 | 硬體：EasyEDA Pro；韌體：Arduino（esp32 core 3.x）+ XIAO ESP32C6；通訊：WiFi + MQTT（esp-mqtt）；整合：Home Assistant；燒錄：esptool / ESP Web Tools |
| 建立日期 | 2026-08-19 |

## 資料夾用途

```
EnviroSense/
├── README.md            給人看的簡介、快速開始、規格
├── CLAUDE.md            本檔
├── CHANGELOG.md         版本異動
├── docs/                設計文件與研究（一份文件一個主題）
│   ├── overview.md      原 README 的完整設計說明
│   ├── power-budget.md  功耗模型、續航、實測計畫、現場遙測推估
│   ├── data/            遙測資料快照（CSV）與驗算公式
│   └── images/
├── hardware/            載板
│   ├── EnviroSense_Node/  EasyEDA Pro 專案（設計來源）
│   ├── gerber/ bom/       由 EasyEDA 匯出的產出物
│   └── README.md        組裝注意事項
├── firmware/            預編譯韌體與燒錄工具（原始碼不在 repo）
│   └── release/<版本>/  bins/、tools/（esptool）、flash.bat、flash.sh
├── web-flasher/         網頁燒錄頁模板（由 Pages 部署）
├── deploy/              Mosquitto 與 Home Assistant 設定範例
├── scripts/             power_budget.py（功耗數字的唯一來源）
└── .github/workflows/   pages.yml（手動觸發部署）、no-source-guard.yml
```

寫東西前先確認要寫進哪個目錄。不確定就問，不要自己開新的頂層目錄。

## 開發約定

- **文件用繁體中文**；程式碼、識別字、檔名、指令照原樣
- **功耗相關的數字由 `scripts/power_budget.py` 產生**，不要手改文件裡的月數；要改就改腳本參數重跑。
  `docs/power-budget.md` 的「現場遙測推估」是 2026-10-28 的一次性快照，不由腳本產生
- **估算與實測要分清楚**：平均電流（75.8 mA）是模型值，還沒用 PPK2 量過；文件裡凡用到都要標明「估算」
- **韌體版本一版一個資料夾**（`firmware/release/<版本>/`），版號格式 `0.2.2-ha`；發佈檔名用不含 `-ha` 的數字版號（`envirosense-ha-0.2.2-esp32c6-*.bin`）
- 韌體用 `config.h.example`（不含任何登入資料）編譯後才能發佈，並確認映像裡沒有帳密與內網位址
- 網頁燒錄頁由 `web-flasher/index.html` 與 `manifest.template.json` 產生，`__VERSION__` / `__BIN__` 在部署時填入；整合映像不進 git
- 發佈新版：建立 GitHub Release（附燒錄包、merged.bin、app.bin、`SHA256SUMS.txt`）→ 發佈後從 `main` 手動執行 `pages` workflow（`github-pages` 環境只允許 `main`，tag 觸發會被擋）
- 硬體以 `hardware/EnviroSense_Node/` 為設計來源；`docs/hardware.md` 的 BOM 是排版前的規劃版，**已打樣的板子以 `hardware/bom/` 為準**

## 版控

- 公開 repo：<https://github.com/HoDZadkiel/EnviroSense>，分支 `main`，直接在 `main` 上提交
- **push 前一定先做機密檢查**（repo 內沒有 `.env`、金鑰、`config.h`，也不能有內網位址與 broker 登入資料）。環境有 `safe-push` skill 就用它
- `.gitignore` 已排除：韌體原始碼（`*.ino`、`config.h*`）、`DEVLOG.md`、`RELEASING.md`、`hardware/datasheets/`、`web-flasher/firmware/`、`*.zip`
- `no-source-guard` workflow 會在原始碼或 `DEVLOG.md` 被追蹤時讓檢查失敗，不要為了讓它通過而改它
- 專案目前**沒有 LICENSE**（尚未決定）；不要自行新增或選擇授權

## 禁止事項

- **不 commit 韌體原始碼**（`.ino`、`.cpp`、`.h`、`config.h*`）。一旦進了公開 repo 的歷史就收不回來
- **不 commit 內網資訊、帳密、token、`.env`**，也不要把它們寫進文件或 commit 訊息
- `hardware/gerber/` 與 `hardware/bom/` 是 EasyEDA 匯出的產出物，不手改；要改就回去改設計檔重新匯出
- `docs/data/` 的 CSV 是資料快照，不手改；要更新就重新匯出並換新日期的檔名
- 已發佈的 Release 附件不要覆寫；有修正就發新版號
- 不要為了省電降頻、或在連線失敗時自動開設定頁（見 `docs/provisioning.md`）；這兩項是刻意的設計決定
- 不替使用者選授權、不替使用者決定發佈或對外推送

## 變更紀錄

每次涉及檔案修改、除錯或決策的對話結束前，把工作記錄追加到專案根目錄的 `DEVLOG.md`（不存在就建立；它被 `.gitignore` 排除，只存在於維護者的本機，**不會進 repo**）。純唯讀的問答可略過。

格式如下 —— 用當天日期當標題，當天已有記錄就往其下追加，不重複建標題：

```markdown
## YYYY-MM-DD

### 修改內容（Changes）
- 改了哪些檔案、做了什麼

### 問題與解法（Problems & Solutions）
- 遇到的障礙與最終採用的解法

### 待辦事項（TODO）
- 未完成或需要後續跟進的事項
```

只寫條列，不寫段落。
