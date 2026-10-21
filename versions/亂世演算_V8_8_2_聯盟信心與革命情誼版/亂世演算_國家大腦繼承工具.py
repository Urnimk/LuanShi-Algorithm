# -*- coding: utf-8 -*-
"""
亂世演算｜國家大腦繼承工具
用途：將 rl_agents_q_tables.json 中某國的 RL 學習資料複製給另一國。
不需要第三方套件。執行前請先關閉《亂世演算》，避免遊戲同時寫入檔案。
"""

import copy
import json
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_FILENAME = "rl_agents_q_tables.json"


def choose_file():
    """優先使用本工具所在資料夾的 JSON；找不到時讓使用者輸入路徑。"""
    default_path = Path(__file__).resolve().parent / DEFAULT_FILENAME
    if default_path.exists():
        answer = input(
            f"找到預設檔案：\n{default_path}\n"
            "直接按 Enter 使用，或輸入其他 JSON 檔案路徑："
        ).strip()
        return Path(answer.strip('"')) if answer else default_path

    print(f"目前資料夾找不到 {DEFAULT_FILENAME}。")
    raw = input("請輸入 rl_agents_q_tables.json 的完整路徑：").strip().strip('"')
    return Path(raw)


def main():
    print("=" * 54)
    print("  亂世演算｜國家大腦繼承工具")
    print("=" * 54)
    print("功能：把來源國家的 Q-Table、造訪次數、決策統計等資料")
    print("      複製給目標國家；原始 JSON 會先建立備份。")
    print("提醒：請先關閉遊戲，避免遊戲同時存檔。\n")

    json_path = choose_file()
    if not json_path.is_file():
        print(f"錯誤：找不到檔案：{json_path}")
        input("按 Enter 結束……")
        return

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"讀取 JSON 失敗：{exc}")
        input("按 Enter 結束……")
        return

    if not isinstance(data, dict):
        print("錯誤：JSON 最外層不是物件，無法辨識國家資料。")
        input("按 Enter 結束……")
        return

    countries = list(data.keys())
    if not countries:
        print("這份 JSON 沒有任何國家資料。")
        input("按 Enter 結束……")
        return

    print("\n目前檔案中的國家：")
    for i, name in enumerate(countries, start=1):
        record = data.get(name, {})
        decisions = record.get("decision_count", "?") if isinstance(record, dict) else "?"
        print(f"  {i:>3}. {name}（決策次數：{decisions}）")

    source = input("\n請輸入「大腦來源國」的完整名稱：").strip()
    if source not in data:
        print(f"錯誤：找不到來源國「{source}」。請確認名稱與清單完全一致。")
        input("按 Enter 結束……")
        return

    target = input("請輸入「繼承者國家」的完整名稱：").strip()
    if not target:
        print("錯誤：目標國名稱不可空白。")
        input("按 Enter 結束……")
        return
    if source == target:
        print("已取消：來源國與目標國相同。")
        input("按 Enter 結束……")
        return

    exists = target in data
    print("\n即將執行：")
    print(f"  大腦來源：{source}")
    print(f"  繼承者：  {target}")
    print(f"  目標國目前{'存在，將被覆蓋' if exists else '不存在，將新建'}")
    print("\n繼承內容：Q-Table、visit_counts、action_stats、")
    print("pending_decisions、decision_count、policies 及其他欄位。")
    print("這是完整複製，不是數值合併。")

    confirm = input("\n輸入 YES 確認執行（其他輸入取消）：").strip()
    if confirm != "YES":
        print("已取消，沒有修改檔案。")
        input("按 Enter 結束……")
        return

    # 在寫入前先備份原始檔案。
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = json_path.with_name(
        f"{json_path.stem}.backup_{timestamp}{json_path.suffix}"
    )
    try:
        shutil.copy2(json_path, backup_path)

        # 深複製避免來源與目標在本次操作中共用同一個 Python 物件。
        data[target] = copy.deepcopy(data[source])

        # 使用 UTF-8、縮排 JSON，方便人工檢查。
        temp_path = json_path.with_name(json_path.name + ".tmp")
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                f.write("\n")
            temp_path.replace(json_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    except Exception as exc:
        print(f"操作失敗：{exc}")
        print(f"若需要還原，可檢查備份檔：{backup_path}")
        input("按 Enter 結束……")
        return

    print("\n繼承完成！")
    print(f"來源國：{source}")
    print(f"目標國：{target}")
    print(f"已備份：{backup_path}")
    print(f"已更新：{json_path}")
    print("\n注意：這會複製來源國的決策次數與統計，不只是 Q-Table。")
    print("若遊戲有其他獨立的 RL 儲存檔，這個工具不會自動修改那些檔案。")
    input("\n按 Enter 結束……")


if __name__ == "__main__":
    main()
