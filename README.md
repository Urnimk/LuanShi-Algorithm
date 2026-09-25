# 亂世演算（LuanShi-Algorithm）

《亂世演算》是一個以 Python 製作的多國家長期戰略模擬專案，包含人口、資源、國家發展、聯盟、戰爭、世界局勢、強化學習（Q 值）與歷代版本保存機制。

## 目錄

```text
LuanShi-Algorithm/
├─ current/                 
│  └─ 目前最新版程式與啟動檔，使用者要直接執行遊戲時主要進入這裡
│
├─ versions/                
│  └─ 歷代版本完整保存區，每個版本獨立留存，方便回溯、比較與還原
│
├─ docs/                    
│  ├─ version-notes/        
│  │  └─ 各版本原始更新說明與功能調整紀錄
│  │
│  ├─ VERSION_CATALOG.csv   
│  │  └─ 歷代版本索引表，記錄版本名稱、檔案數、對應說明與摘要
│  │
│  ├─ FILE_MAP.csv          
│  │  └─ 原始整理包與 GitHub 新目錄位置的對照表
│  │
│  └─ EXCLUDED_FILES.csv    
│     └─ 整理過程中未納入 GitHub 的快取、暫存、存檔等排除檔案清單
│
├─ release-packages/        
│  └─ legacy/               
│     └─ 舊版 ZIP / RAR 完整套件備份，與可直接閱讀的原始碼分開保存
│
├─ tools/                   
│  └─ add_version.py        
│     └─ 後續新增版本的輔助工具，可自動整理 versions、current 與 CHANGELOG
│
├─ CHANGELOG.md             
│  └─ 各版本新增功能、修正內容與平衡調整的快速摘要
│
├─ VERSION_HISTORY.md       
│  └─ 完整歷代版本演進紀錄與版本說明索引
│
├─ UPDATE_GUIDE.md          
│  └─ 開發者後續新增版本、Commit、Push、Tag 與 Release 的操作教學
│
├─ README.md
│  └─ 專案首頁，說明安裝、啟動方式、檔案用途與基本操作
│
├─ START_HERE.md
│  └─ 第一次把整理好的專案匯入 GitHub 時的快速操作說明
│
├─ MIGRATION_REPORT.md
│  └─ 歷史版本整理與 GitHub 遷移過程的整理報告
│
├─ requirements.txt
│  └─ Python 額外套件需求，可用 pip 一次安裝
│
└─ .gitignore               
   └─ 指定不提交到 GitHub 的檔案，例如 saves、__pycache__、Log、暫存檔等
```
---

## 目前版本

目前整理後的最新版為：

**亂世演算 V8_7｜戰爭集結與戒嚴版**

本版重點包含：

- 宣戰後先經過 3～5 年集結期，再進入正式交戰
- 守方可在敵軍集結期間徵兵、築城與調整政策
- 本屆後段前五名提高主動決策機會
- 士兵比例過低時自動進入戒嚴
- 戒嚴期間提高徵兵速度與軍事維持壓力
- 加入復名政變機制
- 修正部分重建政權保護判斷

詳細內容請參閱：

```text
current/亂世演算_V8_7_戰爭集結與戒嚴版_說明.txt
```

---

# 安裝與執行

## 1. 安裝 Python

建議使用 Windows 上的 Python 3。

本遊戲介面使用 `tkinter`。若使用 python.org 官方 Windows 安裝程式，通常已包含 Tcl/Tk / tkinter。

安裝 Python 時建議勾選：

```text
Add Python to PATH
```

可在命令提示字元確認：

```bat
python --version
```

---

## 2. 安裝套件

Repository 根目錄若有 `requirements.txt`，請執行：

```bat
python -m pip install -r requirements.txt
```

目前 V8.7 主程式主要使用 Python 標準函式庫與專案內附模組；`requirements.txt` 中的額外套件主要用來兼容部分歷史版本。

---

## 3. 開啟最新版遊戲

進入：

```text
current/
```

請確認以下檔案放在同一個資料夾：

```text
current/
├─ 亂世演算_V8_7_啟動.py
├─ 亂世演算_V8_7_戰爭集結與戒嚴版.py
├─ decision_analysis.py
├─ experience_view.py
├─ fiscal_policy.py
├─ policy_index.py
├─ strategy_states.py
└─ 亂世演算_V8_7_戰爭集結與戒嚴版_說明.txt
```

### 方法 A：直接開啟

若 Windows 已將 `.py` 關聯到 Python，可以直接雙擊：

```text
亂世演算_V8_7_啟動.py
```

### 方法 B：使用命令提示字元（推薦）

先切換到 `current` 資料夾：

```bat
cd /d "你的路徑\LuanShi-Algorithm\current"
```

再執行：

```bat
python "亂世演算_V8_7_啟動.py"
```

例如：

```bat
cd /d "D:\GitHub\LuanShi-Algorithm\current"
python "亂世演算_V8_7_啟動.py"
```

> 建議從「啟動.py」開啟，不要直接執行主引擎檔。啟動器會同時啟動背景模擬與圖形介面。

---

# 遊戲介面使用方式

啟動後，主程式會在背景執行模擬，Tkinter UI 負責顯示即時資料。

主要介面包括：

### 🌐 國家總覽

查看所有國家的基本狀態，例如：

- 國家名稱
- 世代
- 戰力
- 人口
- 貨幣狀態
- 冠軍數
- 存活／滅亡狀態

可點擊國家名稱進入詳細資訊。

### 🤝 聯盟總覽

查看：

- 聯盟名稱
- 聯盟總戰力
- 成員數
- 圍剿目標

可由聯盟名稱進一步查看聯盟資料。

### 🔍 國家詳細查詢

可查看單一國家的：

- 基本狀態
- 人口與資源
- 戰爭狀態
- 外交與戰績
- 奪冠紀錄
- 國家相關事件 LOG

其中另有：

```text
📜 編年史
```

用來查看該國歷代重大事件。

以及：

```text
🧠 經驗
```

用來查看該國「目前戰略狀態」的 Q 值與 AI 經驗。

### 🛡️ 聯盟詳細查詢

查看：

- 聯盟摘要
- 聯盟戰爭
- 成員明細
- 聯盟事件

### 💹 世界報價系統

此分頁同時放置模擬控制功能。

目前 V8.7 預設：

```python
MARKET_ECONOMY_ENABLED = False
```

因此世界貨幣／市場功能預設關閉，但介面仍保留相關欄位。

控制按鈕包括：

```text
⏸ 暫停
⏭ 單步
速度
```

目前 V8.7 預設：

```text
1 回合 = 1 年
2 秒 = 1 年
500 年 = 1 屆
```

---

# `current/` 各檔案用途

## `亂世演算_V8_7_啟動.py`

**遊戲啟動器與 GUI。**

主要負責：

- 啟動背景模擬執行緒
- 建立 Tkinter 遊戲介面
- 國家總覽
- 聯盟總覽
- 國家／聯盟詳細查詢
- 世界排名
- 即時 LOG
- 編年史
- Q 值「經驗」查詢
- 暫停、單步與速度控制
- 讀取 `saves/` 中的即時資料

一般玩家應由這個檔案開啟遊戲。

---

## `亂世演算_V8_7_戰爭集結與戒嚴版.py`

**遊戲核心模擬引擎。**

這是整個《亂世演算》的主要規則所在，負責：

- 世界時間
- 國家建立與重建
- 人口與職業
- 糧食、木材、金屬等資源
- 生育與生產
- 基礎建設
- 軍隊與徵兵
- 戰爭與攻城
- 宣戰集結期
- 戒嚴
- 聯盟
- 反霸權圍剿
- 國際忌憚值
- 世界局勢
- 政變與政權更替
- 強化學習
- Reward / Q 值
- 排行與冠軍
- 存檔與續跑
- 遊戲 LOG

若要調整遊戲規則，通常主要修改這個檔案。

---

## `decision_analysis.py`

**國家決策分析層。**

包含多個只讀分析模組，例如：

- 經濟分析
- 軍事分析
- 外交分析
- 人口分析
- 內政分析
- 情報分析
- 戰略分析

這些分析會輸出訊號給既有的 Q 決策系統使用，但本身不直接增加資源、不直接執行 Action。

---

## `strategy_states.py`

**戰略狀態壓縮與可讀化。**

目前戰略層使用：

```text
4 × 4 × 4 × 4 = 256 種狀態
```

主要將複雜世界資訊整理成：

- 安全狀態
- 軍事狀態
- 發展狀態
- 爭冠狀態

供戰略 Q-learning 使用。

也負責把 Q 值轉換成較容易閱讀的中文報表。

---

## `experience_view.py`

**UI 的 Q 值／經驗顯示工具。**

負責：

- 讀取目前國家的戰略狀態
- 找到該狀態對應的 Q 值
- 顯示各 Action 的目前估計值
- 提供 UI 的「🧠 經驗」功能

它不負責學習本身，只負責顯示。

---

## `fiscal_policy.py`

**財政政策與銀行流動性決策模組。**

主要負責：

- 財政狀態判斷
- 財政 Action 有效性
- 財政 Q 值報告
- 世界銀行既有貨幣回流
- 延遲財政 Reward

當貨幣／市場功能啟用時，此模組的重要性會提高。

---

## `policy_index.py`

**貨幣與政策價格指數模組。**

主要負責：

- 政策成本倍率
- 初始貨幣發行量基準
- 發行量／初始發行量的價格指數
- 屆末政策價格結算
- 市場實際成交觀察
- 貨幣名稱／面額相關處理

目前 V8.7 預設市場關閉，但程式仍保留這套系統。

---

## `亂世演算_V8_7_戰爭集結與戒嚴版_說明.txt`

**本版本更新說明。**

記錄：

- 新增功能
- 規則修改
- 修正內容
- 重要參數
- 測試結果
- 後續觀察重點

---

# `saves/` 是什麼？

第一次執行後，引擎會在 `current/` 旁自動建立：

```text
saves/
```

這裡是遊戲執行期資料，不是程式原始碼。

常見檔案包括：

### `war_live_countries.json`

目前所有國家的即時資料與世界狀態。

### `war_live_alliances.json`

目前聯盟與圍剿聯盟相關資料。

### `rl_agents_q_tables.json`

各國強化學習 Agent 的 Q-table / 經驗資料。

### `rl_strategic_q_readable.txt`

較容易人工閱讀的戰略 Q 值報表。

### `rl_monitor_latest.json`

最新一次 RL 監測結果。

### `rl_monitor_history.csv`

RL 監測歷史資料。

### `Live_Ranking.txt`

UI 右側即時世界排名的資料來源。

### `game.log`

即時遊戲事件 LOG。

### `亂世演算_執行進度.json`

程式用的執行進度與續跑資料。

### `亂世演算_執行進度.txt`

方便人工查看目前執行進度的文字版。

> `saves/` 已列入 `.gitignore`，一般情況不要提交到 GitHub。

---

# 如何重新開始一個全新世界？

請先關閉遊戲。

若想保留舊世界，先備份：

```text
current/saves/
```

之後將 `saves/` 移到其他地方或刪除，再重新啟動遊戲。

程式會重新建立需要的執行期檔案。

> 這會清除目前世界、Q 值與續跑資料，請先備份。

---

# Repository 其他資料夾用途

## `current/`

目前最新版。

想直接玩遊戲，通常只需要進這裡。

---

## `versions/`

歷代版本保存區。

每個版本各自保留一份完整程式，例如：

```text
versions/
├─ 亂世演算_V5_...
├─ 亂世演算_V6_...
├─ 亂世演算_V7_...
└─ 亂世演算_V8_...
```

這個資料夾的目的主要是：

- 追蹤歷史演進
- 比較版本差異
- 回退舊版
- 保存實驗分支

請不要用新版直接覆蓋舊版本資料夾。

---

## `docs/version-notes/`

歷代版本的原始更新說明。

若想了解某一版本當時修改了什麼，可以先查看這裡。

---

## `docs/VERSION_CATALOG.csv`

整理後的版本目錄。

可快速查看：

- 版本資料夾
- 版本號
- 檔案數
- 對應版本說明
- 簡要摘要

---

## `docs/FILE_MAP.csv`

記錄原始整理包中的檔案後來被放到 Repository 哪裡。

主要用於 GitHub 遷移與整理追蹤。

---

## `docs/EXCLUDED_FILES.csv`

記錄整理時未放入 GitHub 的檔案，例如：

- 快取
- 暫存
- 執行期資料

---

## `release-packages/legacy/`

保存歷史版本原本附帶的 ZIP / RAR 完整套件。

它們與 `versions/` 裡的可閱讀原始碼分開保存，避免 Repository 結構混亂。

---

## `tools/add_version.py`

**後續新增版本的輔助工具。**

例如完成：

```text
亂世演算_V8_7_1_某某修正版
```

可以在 Repository 根目錄執行：

```bat
python tools/add_version.py "D:\你的新版資料夾\亂世演算_V8_7_1_某某修正版"
```

工具會協助：

- 將新版複製到 `versions/`
- 排除 `saves/`
- 排除 `__pycache__/`
- 排除 `.pyc`、Log、暫存檔
- 將 ZIP / RAR 移到 `release-packages/legacy/`
- 更新 `current/`
- 在 `CHANGELOG.md` 建立新版項目骨架

工具不會自動 Push 到 GitHub。

---

# 其他重要文件

## `CHANGELOG.md`

快速記錄每一版：

- 新功能
- 修正
- 平衡調整

---

## `VERSION_HISTORY.md`

完整的歷代版本整理與版本說明索引。

---

## `UPDATE_GUIDE.md`

說明開發者完成新版本後，要如何：

```text
加入 versions
→ 更新 current
→ 更新 CHANGELOG
→ Commit
→ Push
→ 建立 Tag / Release
```

---

## `START_HERE.md`

第一次將專案整理包匯入 GitHub 時的操作說明。

---

## `MIGRATION_REPORT.md`

記錄這次從歷史整理包搬移到 GitHub Repository 時採用的整理規則與結果。

---

## `.gitignore`

告訴 Git 哪些檔案不應加入版本控制。

目前主要排除：

```text
saves/
__pycache__/
*.pyc
*.log
*.tmp
*.bak
```

以及部分執行期 JSON、IDE 快取等資料。

---

## `requirements.txt`

列出需要透過 `pip` 安裝的 Python 第三方套件。

安裝：

```bat
python -m pip install -r requirements.txt
```

---

# 開發者：後續版本更新流程

假設新版本為：

```text
亂世演算_V8_7_1_戰爭平衡修正版
```

建議流程：

```text
1. 完成並測試新版本
2. 放入 versions/
3. 更新 current/
4. 更新 CHANGELOG.md
5. GitHub Desktop Commit
6. Push origin
7. 正式版本建立 Git Tag / GitHub Release
```

GitHub Desktop 的 Commit Summary 可寫：

```text
Add V8.7.1 戰爭平衡修正版
```

正式 Release Tag 建議：

```text
v8.7.1
```

---

# 注意事項

- 不要直接修改 `saves/` 內正在被程式使用的 JSON。
- 不要把 API Key、Token、密碼或私人登入憑證寫入公開 Repository。
- 不要把 `__pycache__/`、`.pyc`、大量 Log 提交到 GitHub。
- 執行歷史版本前，建議先閱讀該版本資料夾與對應版本說明。
- 不同歷史版本的相依檔案可能不同；不要把不同版本的主引擎與啟動器隨意混用。
- 若使用公開 GitHub Repository，請在 Push 前確認沒有私人存檔、帳號資訊或密鑰。

---

# 快速開始

如果只想直接玩最新版：

```bat
git clone <你的 GitHub Repository URL>
cd LuanShi-Algorithm
python -m pip install -r requirements.txt
cd current
python "亂世演算_V8_7_啟動.py"
```

遊戲啟動後：

```text
左側：國家／聯盟／詳細資訊／市場與控制
右側：世界排名與即時 LOG
```

即可開始觀察《亂世演算》的世界發展。
