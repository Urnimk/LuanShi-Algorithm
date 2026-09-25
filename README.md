# 亂世演算（LuanShi-Algorithm）

這個 Repository 用來保存《亂世演算》的歷代版本與目前最新版。

## 目前整理狀態

- 歷史版本資料夾：**49 個**
- 目前最新版快照：**亂世演算_V8_7_0_戰爭集結與戒嚴版**
- 歷史版本位置：`versions/`
- 目前最新版位置：`current/`
- 歷代版本說明：`docs/version-notes/`
- 舊版壓縮套件：`release-packages/legacy/`
- 後續更新教學：`UPDATE_GUIDE.md`

## 目錄

```text
LuanShi-Algorithm/
├─ current/                 # 目前最新版，方便直接查看與執行
├─ versions/                # 每一個歷史版本完整保存
├─ docs/
│  ├─ version-notes/        # 原始版本說明
│  ├─ VERSION_CATALOG.csv
│  ├─ FILE_MAP.csv
│  └─ EXCLUDED_FILES.csv
├─ release-packages/
│  └─ legacy/               # 舊版 ZIP/RAR 套件，與原始碼分開
├─ tools/
│  └─ add_version.py        # 後續新增版本的小工具
├─ CHANGELOG.md
├─ VERSION_HISTORY.md
├─ UPDATE_GUIDE.md
└─ .gitignore
```

## 版本管理原則

1. `versions/` 永遠保留每個版本的歷史原貌。
2. `current/` 永遠只放目前最新版。
3. 新版本完成後，新增一個版本資料夾，不覆蓋舊版。
4. `saves/`、`__pycache__/`、`.pyc`、Log、暫存檔不提交 Git。
5. 每次版本更新後 Commit，建議再建立 Git Tag / GitHub Release。

## 最新版

目前由本次整理資料判定的最高版本為：

**亂世演算_V8_7_0_戰爭集結與戒嚴版**

> 注意：這是依資料夾版本號排序所得，不代表我替你判定哪一條實驗分支最適合繼續開發。
