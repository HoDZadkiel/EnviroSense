# 硬體

設計說明、選型理由、接線與 BOM 見 [`../docs/hardware.md`](../docs/hardware.md)。

| 路徑                  | 內容                                           |
|---------------------|----------------------------------------------|
| `EnviroSense_Node/` | EasyEDA Pro 專案（載板：XIAO 座 + 電池座 + SHT40 + 分壓） |
| `datasheets/`       | 元件規格書                                        |
| `bom/`              | BOM 匯出檔                                      |
| `gerber/`           | Gerber 打樣檔匯出                                 |

目前狀態：**M5 進行中，PCB 已打樣**
（`gerber/Gerber_PCB1_2026-08-21.zip`、`bom/BOM_Board1_PCB1_2026-08-21.xlsx`）。
BOM 已於 2026-09-30 對照 `gerber/FlyingProbeTesting.json` 還原的網表核對：
DW01A 週邊（R5 100Ω、R6 1kΩ、C4 100nF）已補齊，接法與 datasheet 一致。

組裝與 M0 前要注意（詳見 [`../docs/hardware.md`](../docs/hardware.md)）：

- **C2（470µF）先不焊**，量完深睡電流再焊上，確認其漏電
- 焊 Q3（8205A SOT-23-6）前先確認腳位對應
- 分壓讀值要等閘極開啟 ≥ 500 ms（韌體處理，不需改板）
- 2N7002 閘極無下拉，深睡電流偏高時補焊 1MΩ 於 Q2 G–S

本專案**直接做 PCB，不經洞洞板驗證**。這代表 M0（深睡電流實測）、
M1（最小韌體）等原本規劃在洞洞板上跑的驗證，改成在打樣回來的實體板上進行 ——
韌體或接線的問題還能靠改韌體/飛線修正，但**走線本身的錯誤要重新打樣**。
排版時要格外注意 [`../docs/hardware.md`](../docs/hardware.md) 裡標記
「M0 需確認」的項目（RF switch 控制腳、I²C 深睡漏電等），
盡量把相關訊號都拉出測試點，降低事後才發現問題的成本。