# StockValuation.io × ah-disclosure-kit：A股 External Valuation 整合

記錄 2026-08 完成的整合工作：把 [ah-disclosure-kit](https://github.com/) 產出的中國 A 股財務質量分析報告，接入 fork 版 [stockvaluation_io_china_stock](https://github.com/codenong/stockvaluation_io_china_stock) 既有的 `external valuation` 路徑，端對端跑出 DCF 估值結果。

---

## 1. 架構總覽

```
ah-disclosure-kit 分析報告 (JSON)
        │
        │  company_data_from_ah_disclosure()
        ▼
valuation-agent/ah_disclosure.py          ← 新增：JSON → CompanyDataDTO 轉換 + review gate 輔助函式
        │
        │  MCP tool: stockvaluation.extract_ah_disclosure
        ▼
valuation-agent/mcp_tools.py              ← 修改：新增兩個 MCP tool
        │  (review_status=reviewed 之後)
        │  MCP tool: stockvaluation.value_external
        ▼
valuation-agent/service_client.py         ← 修改：修正 URL 組裝 bug
        │  POST /api/v1/automated-dcf-analysis/external/valuation
        ▼
valuation-service (Java / Spring Boot)
  ├─ AutomatedDCFAnalysisController.getExternalValuationOutput()  (已存在，來自你原本的 diff)
  ├─ ValuationWorkflowServiceImpl.getExternalValuation()          (已存在)
  └─ OptionValueService.calculateOptionValue()                    ← 修改：不再無條件依賴 ticker provider
        │
        ▼
   DCF 估值結果 (FCFF, 15年投影, 敏感度分析, market-implied expectations)
```

**設計原則**：`CompanyDataDTO`（歷史財務事實）來自 ah-disclosure JSON + akshare 市場數據；`overrides`（`FinancialDataInput`，前瞻性假設）留給 guided-question 流程或人工輸入。整條流程沿用既有 `extract_prospectus` / `value_prospectus` 的「extract → 人工 review → value」三段式 gate 機制，不是另外發明一套。

---

## 2. 新增與修改的檔案

| 檔案 | 狀態 | 說明 |
|---|---|---|
| `valuation-agent/ah_disclosure.py` | **新增** | 核心轉換邏輯：JSON → `CompanyDataDTO`；CAPM WACC 估算；review token/payload 輔助函式 |
| `valuation-agent/mcp_tools.py` | 修改 | 新增 `stockvaluation.extract_ah_disclosure`、`stockvaluation.value_external` 兩個 MCP tool，含 review gate |
| `valuation-agent/service_client.py` | 修改（1處） | 修正 `value_external()` 的 URL 組裝 bug |
| `valuation-service/.../service/OptionValueService.java` | 修改 | 新增 overload，接受直接傳入的 `stockPrice`/`riskFreeRate`，不再無條件查 ticker provider |
| `valuation-service/.../service/ValuationWorkflowServiceImpl.java` | 修改（4處） | 4 個呼叫 `calculateOptionValue` 的地方改用新 overload |
| `test_ah_disclosure_e2e.py` | 新增（本機測試用，未進 repo） | 端對端測試腳本 |
| `fetch_market_data_sina.py` | 新增（本機工具腳本） | akshare 抓股價/股本/市值 |
| `fetch_risk_free_rate.py` | 新增（本機工具腳本） | akshare 抓中國10年期國債殖利率 |

---

## 3. 過程中發現並修正的 Bug（依發現順序）

### 3.1 `service_client.py`：URL 組裝錯誤
`value_external()` 誤用 `_api_v1_url("/external/valuation")`，把 URL 砍成 `/api/v1/external/valuation`，少了 `automated-dcf-analysis` 這段路徑，導致請求連 Spring Security 白名單都匹配不到，回傳 403。

**修法**：改用 `f"{self.base_url}/external/valuation"`，跟 ticker-based valuation 用同一種組法。

### 3.2 `companyDriveDataDTO` 不能是 `null`
`ValuationWorkflowServiceImpl.initializeFinancialDataInput()` 無條件解引用 `companyData.getCompanyDriveDataDTO()`，null 會直接 NPE。這個欄位在正常 ticker 流程裡由 Yahoo Finance 分析師預期填入，是「粗略起點」，不是最終答案。

**修法**：`ah_disclosure.py` 用 ah-disclosure 的歷史數據自己算一個起點：
- `operatingMarginNextYear` = EBIT margin（EBIT/營收）
- `revenueNextYear` = 今年YoY成長率
- `salesToCapitalYears1To5/6To10` = 真實資產負債表算出的 營收/投入資本
- `riskFreeRate`、`initialCostCapital` 見 3.4、3.5

⚠️ **單位陷阱**：`CompanyDriveDataDTO` 的欄位是**小數**（0.15 = 15%），跟 `FinancialDataDTO` 的「百分比數值」慣例（25.0 = 25%）不一樣。

### 3.3 `OptionValueService` 無條件依賴 ticker provider
`calibrateToMarketPrice`（市場價格校準）內部呼叫 `OptionValueService.calculateOptionValue(ticker, ...)`，該方法**無條件**重新呼叫 `commonService.getCompanyDataFromProvider(ticker)` 去打 yfinance provider——完全忽略呼叫方已經準備好的 `financialDataInput` 裡的股價/風險利率。A股 ticker 在 yfinance provider 裡查不到，直接 `Connection refused`。

**修法**：新增 overload `calculateOptionValue(double currentStockPrice, double riskFreeRate, ...)`，4個呼叫點全部改用 `financialDataInput.getFinancialDataDTO().getStockPrice()` / `getCompanyDriveDataDTO().getRiskFreeRate()`。這個修法對 ticker-based 流程也是淨改善（少一次多餘的 provider 重複呼叫）。

### 3.4 `effectiveTaxRate` 單位不一致
`FinancialDataDTO.effectiveTaxRate` 實際上用**小數**儲存（跟同一個 DTO 裡 `marginalTaxRate` 的「百分比數值」慣例不一樣）。原本直接傳 `etr_2025_pct = 1.7002`（代表1.70%），被當成小數乘以100，跑出離譜的 `170.02%` 早期年稅率。

**修法**：`ah_disclosure.py` 裡 `effectiveTaxRate` 改成 `etr_2025_pct / 100` 再傳。

### 3.5 `riskFreeRate` / `initialCostCapital` 從佔位符換成真實數據
- **`riskFreeRate`**：一開始用 2.0% 佔位符，後改用 `akshare.bond_zh_us_rate()` 抓中國10年期國債殖利率真實值（1.6887%，2026-08-26收盤）
- **`initialCostCapital`**：一開始用 9.0% 佔位符。發現本機空白 Postgres 沒有種子資料（`cost_of_capital`、`sector_mapping`、`industry_averages_*` 全部是 0 筆），連正常 ticker 流程本地都拿不到真正的 Damodaran 產業 WACC 查表結果，於是改用標準 CAPM 公式自建估算：半導體 unlevered beta 1.49（Damodaran 2026年1月數據）→ 用公司真實 D/E 和稅率 relever → 加上中國股權風險溢價（app 的 4.23% mature-market-erp 基準 + ~0.73pp 中國國家風險溢價增量，來自 Damodaran 2026年7月更新）算出 cost of equity → 用真實資本結構加權算出 WACC ≈ 9.08%

---

## 4. 本機環境設置（從零開始）

```bash
# 1. PostgreSQL（Homebrew，trust 認證，密碼隨便填但不能是空字串）
brew install postgresql@16
brew services start postgresql@16
createdb stockvaluation_io

# 2. akshare（Python 側抓市場數據）
pip install akshare --break-system-packages

# 3. 啟動 valuation-service（另開一個 terminal，會持續佔用前台）
cd valuation-service
export DATASOURCE_URL="jdbc:postgresql://localhost:5432/stockvaluation_io"
export DATASOURCE_USERNAME="$(whoami)"
export DATASOURCE_PASSWORD="local_dev_password"   # 不能是空字串，RequiredRuntimePropertiesValidator 會擋
export DEFAULT_PASSWORD="local_dev_password"
export DEFAULT_USERNAME="local_admin"
export DEFAULT_FIRSTNAME="Local"
export DEFAULT_LASTNAME="Admin"
export DEFAULT_CONTACT="0000000000"
export SEC_USER_AGENT="StockValuationLocal test@example.com"
export YFINANCE_BASE_URL="http://localhost:5001"   # external valuation 路徑用不到，隨便填
./mvnw spring-boot:run
```

`/api/v1/automated-dcf-analysis/external/valuation` (POST) 已在 `SecurityConfig.java` 的 `permitAll` 白名單裡（因為跟 `/{ticker}/valuation` 共用 `*/valuation` 這個 pattern），**不需要**額外認證。`/actuator/health` 以外的自訂 `/health` endpoint **沒有**在白名單裡，測試時不要浪費時間戳它。

---

## 5. 端對端測試流程

```bash
# 1. 抓市場數據（股價/股本/市值/beta）
python fetch_market_data_sina.py 603986

# 2. 抓無風險利率
python fetch_risk_free_rate.py

# 3. 把數字填進 test_ah_disclosure_e2e.py 的 market_data / risk_free_rate 參數後執行
python test_ah_disclosure_e2e.py path/to/ah_disclosure_report.json
```

腳本內部依序呼叫：
1. `stockvaluation.extract_ah_disclosure` → 回傳 `companyData`（`reviewStatus: pending_review`）+ `review_reference` + `gaps` 清單
2. `stockvaluation.value_external`（`review_status: reviewed`）→ 呼叫 Java `/external/valuation` → 回傳完整 DCF 估值結果

---

## 6. 兆易創新（603986.SH）驗證結果

| 項目 | 數值 |
|---|---|
| 營收（2025） | ¥92.03億 |
| EBIT margin | 17.0% |
| 營收 YoY | 25.12% |
| 股價（2026-08-26） | ¥392.50 |
| 市值 | ¥2,623.83億 |
| 無風險利率（中國10Y國債） | 1.6887% |
| WACC（CAPM估算） | 9.08% |
| **模型內在價值** | **¥523.58** |
| 對比市價 | 低估約 33.4% |

---

## 7. 尚未解決的 Gap（`extract_ah_disclosure` 的 `gaps` 欄位會持續列出）

| 項目 | 現況 | 需要什麼才能解決 |
|---|---|---|
| `growthDto`（統計量） | `null` | 多年（建議 5年以上）ah-disclosure 報告序列 |
| `researchAndDevelopmentMap` | 只有2025一年 | 同上 |
| `revenueNextYear` / `compoundAnnualGrowth2_5` | 單年YoY直接當起點 | 多年數據擬合成長曲線，或 guided-question 人工修正 |
| `operatingIncomeTTM` 口徑 | 含公允價值變動收益的 EBIT | 人工決定要不要剔除（`ah_disclosure.py` 的 gaps 裡已算好剔除後的替代值） |
| `beta`（`BasicInfoDataDTO` 層級） | `null` | 若要用公司自身迴歸 beta，注意題材股行情期間的迴歸結果不可靠（已驗證：兆易創新算出 3.16，明顯失真）；建議維持用產業 beta |
| `initialCostCapital` 的 CAPM 估算 | 用單一半導體產業 beta，非 app 原生的 DB 查表 | 種子 `cost_of_capital`/`sector_mapping`/`industry_averages_*` 資料表後，改用 app 原生邏輯 |
| `dividendDataDTO` | 完全未串接 | 視需求另外設計 |

---

## 8. 後續可能方向

1. **多年報告整合**：抓 2021–2025 的 ah-disclosure 報告，補齊 `growthDto` 和 `researchAndDevelopmentMap`
2. **種子 Damodaran 參考資料表**：讓 `initialCostCapital` 改用 app 原生的 DB 查表邏輯，不用自建 CAPM
3. **擴展到其他 A 股 ticker**：目前的 `ah_disclosure.py` 是通用邏輯（`infer_a_share_suffix` 支援滬/深/北交所），理論上換一份 ah-disclosure JSON 就能跑，但 `initial_cost_capital` 目前寫死用「半導體」產業 beta，換產業要調整 `_SEMICONDUCTOR_UNLEVERED_BETA` 常數（之後應該做成依 `industryGlobal` 動態查表）
4. **`guided_question_planner.py` 整合**：讓 `plan_guided_questions` 認得 `workflow_type: "ah_disclosure"`，把 `gaps` 清單轉成結構化的引導問題
