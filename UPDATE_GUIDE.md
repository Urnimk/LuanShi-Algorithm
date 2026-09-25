# 後續版本更新教學

你目前的 GitHub Repository 建議維持這個規則：

- `versions/`：永久保存每一個歷史版本。
- `current/`：只放最新版。
- `CHANGELOG.md`：簡短寫本版改了什麼。
- Git Commit：記錄這次修改。
- Git Tag / GitHub Release：標示正式版本。

---

## 方法 A：最簡單，使用 GitHub Desktop

假設你新完成：

`亂世演算_V8_7_1_某某修正版`

### 1. 把新版資料夾放進 `versions/`

結果：

```text
versions/
├─ 亂世演算_V8_7_0_戰爭集結與戒嚴版/
└─ 亂世演算_V8_7_1_某某修正版/
```

**不要覆蓋 V8_7_0。**

### 2. 更新 `current/`

刪除 `current/` 裡舊版程式，再把 V8_7_1 的主要程式、啟動器及相依模組複製進 `current/`。

不要複製：

- `saves/`
- `__pycache__/`
- `*.pyc`
- 執行 Log
- 暫存檔

### 3. 更新 `CHANGELOG.md`

在最上方增加：

```markdown
## 亂世演算_V8_7_1_某某修正版

- 修正……
- 新增……
- 調整……
```

### 4. 用 GitHub Desktop Commit

開啟 GitHub Desktop 後，左側會出現 Changed files。

Summary 建議填：

```text
Add V8.7.1 某某修正版
```

按：

`Commit to main`

再按：

`Push origin`

這樣 GitHub 上就更新完成。

### 5. 建立正式 Tag / Release（推薦）

到 GitHub 網頁：

`Repository → Releases → Draft a new release`

選：

`Choose a tag → Create new tag`

例如：

`v8.7.1`

Release title：

`V8.7.1 某某修正版`

說明直接貼 CHANGELOG 的本版內容即可。

---

## 方法 B：使用本專案內附工具

在 Repository 根目錄開啟 PowerShell / CMD：

```text
python tools/add_version.py "D:\你的新版資料夾\亂世演算_V8_7_1_某某修正版"
```

工具會：

1. 把新版複製到 `versions/`。
2. 自動排除 `saves`、`__pycache__`、`.pyc` 等執行資料。
3. 把 ZIP/RAR 套件移到 `release-packages/legacy/<版本>/`。
4. 更新 `current/`。
5. 若 CHANGELOG 尚無該版本，加入待填寫骨架。
6. 顯示下一步建議的 Git Commit / Tag 名稱。

它**不會自動 Push**，所以最後仍由你在 GitHub Desktop 按 Commit / Push，較安全。

---

## 版本命名建議

維持你現在的規則：

- 大版本：`V9`、`V10`
- 功能版：`V8_7`
- 小修：`V8_7_1`、`V8_7_2`

Git Tag 建議使用點號：

- `V8_7_1` → `v8.7.1`
- `V9_0` → `v9.0`

---

## 一句話記住

**新版放 `versions/` → 同步最新版到 `current/` → 改 CHANGELOG → Commit → Push → 正式版再建立 Tag/Release。**
