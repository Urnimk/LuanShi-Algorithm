# MIGRATION REPORT

來源：`版本更新_完整整理(1).zip`

## 結果

- 原始 ZIP 項目：393
- 辨識版本資料夾：49
- 最新版本快照：亂世演算_V8_7_0_戰爭集結與戒嚴版
- 已移出版本原始碼資料夾的 ZIP/RAR 套件：12
- 排除的執行期／快取檔案：14

## 整理原則

- 歷史程式碼保留在 `versions/`。
- 最新版另複製到 `current/`。
- `__pycache__`、`saves`、`.pyc`、Log、暫存檔排除。
- 歷史 ZIP/RAR 套件移至 `release-packages/legacy/`，避免和原始碼混在一起。
- 原始版本說明集中到 `docs/version-notes/`。
- 原本是空資料夾的版本，以 README 保留其存在紀錄。

## GitHub 限制檢查

本整理包未包含單檔超過 100 MB 的檔案。
