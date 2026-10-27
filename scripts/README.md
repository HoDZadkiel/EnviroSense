# scripts

| 檔案 | 用途 |
|---|---|
| `power_budget.py` | 功耗預算試算。`docs/` 與 `README.md` 裡所有續航月數都由它產生 |

```bash
python scripts/power_budget.py
```

**不要手改文件裡的數字。** 改腳本的 `BOARDS` / `BATTERIES` / `MODES` 參數，
重跑，再把輸出填回文件。M0 實測完成後第一件事就是回填這裡的參數。
