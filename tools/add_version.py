#!/usr/bin/env python3
import argparse
import os
import re
import shutil
from pathlib import Path

IGNORE_DIRS = {"__pycache__", "saves", ".pytest_cache"}
IGNORE_EXTS = {".pyc", ".pyo", ".log", ".tmp", ".bak"}
PACKAGE_EXTS = {".zip", ".rar"}

def copy_clean(src: Path, dst: Path, package_dst: Path):
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if p.is_dir():
            continue
        if p.suffix.lower() in IGNORE_EXTS:
            continue
        if p.suffix.lower() in PACKAGE_EXTS:
            package_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, package_dst / p.name)
            continue
        q = dst / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, q)

def tag_from_name(name: str):
    m = re.search(r"_V(\d+)(?:_(\d+))?(?:_(\d+))?", name)
    if not m:
        return None
    nums = [m.group(1)]
    if m.group(2) is not None:
        nums.append(m.group(2))
    if m.group(3) is not None:
        nums.append(m.group(3))
    return "v" + ".".join(nums)

def main():
    ap = argparse.ArgumentParser(description="把新版本加入亂世演算 GitHub Repository")
    ap.add_argument("source", help="新版資料夾完整路徑")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"找不到資料夾：{src}")

    repo = Path(__file__).resolve().parents[1]
    name = src.name
    version_dst = repo / "versions" / name
    current = repo / "current"
    package_dst = repo / "release-packages" / "legacy" / name

    if version_dst.exists():
        raise SystemExit(f"版本已存在，為避免覆蓋已停止：{version_dst}")

    version_dst.mkdir(parents=True)
    copy_clean(src, version_dst, package_dst)

    if current.exists():
        shutil.rmtree(current)
    current.mkdir(parents=True)
    copy_clean(src, current, package_dst)

    changelog = repo / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8") if changelog.exists() else "# CHANGELOG\n\n"
    if name not in text:
        insert = (
            f"## {name}\n"
            "- TODO：填寫本版新增功能\n"
            "- TODO：填寫修正內容\n"
            "- TODO：填寫平衡調整\n\n"
        )
        if text.startswith("# CHANGELOG"):
            pos = text.find("\n\n")
            text = text[:pos+2] + insert + text[pos+2:]
        else:
            text = insert + text
        changelog.write_text(text, encoding="utf-8")

    tag = tag_from_name(name)
    print("完成新增版本：", name)
    print("歷史版本：", version_dst)
    print("最新版：", current)
    print()
    print("下一步請在 GitHub Desktop：")
    print(f'  Summary: Add {tag or name} {name}')
    print("  Commit to main")
    print("  Push origin")
    if tag:
        print(f"正式發布時建立 Tag / Release：{tag}")

if __name__ == "__main__":
    main()
