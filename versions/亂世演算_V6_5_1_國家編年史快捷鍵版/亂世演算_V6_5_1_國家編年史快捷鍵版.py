import json  # 匯入 JSON 模組，用於讀取與儲存 JSON 格式的檔案（例如國家資料、 Q-Table 檔案）
import math  # 匯入數學模組，用於無條件進位（math.ceil）等計算
import os  # 匯入作業系統模組，用於檢查檔案或路徑是否存在
import random  # 匯入隨機模組，用於隨機事件、隨機選擇與機率判斷
import re  # V6：解析國號中的復國羅馬世代與政權世系
import threading  # 匯入多線程模組，用於背景執行戰局監控任務
import time  # 匯入時間模組，用於計算執行時間與時間延遲（sleep）
import gc  # 匯入垃圾回收模組 (Garbage Collection)，用於定期清理記憶體
from collections import deque  # 從 collections 匯入雙端隊列 deque，用於維護固定長度的 Log 訊息緩衝區

# 全域變數
last_sync_time = time.time()  # 紀錄最後同步時間點（初始化為當前時間秒數）
world_stage_g = 0  # RL 世界力量階段：BALANCED / RISING / EMPIRE
world_mode_g = "平常局勢"
world_mode_code_g = "NORMAL"

# ================================================
# 📜 Log 自動寫入文字檔（最新訊息在第一行，限制 1000 行）
# ================================================
LOG_FILE = "game.log"
MAX_LOG_LINES = 1000
LOG_FLUSH_INTERVAL = 0.25
log_buffer = deque(maxlen=MAX_LOG_LINES)
_log_dirty = False
_last_log_flush = 0.0


def flush_game_log(force=False):
    """批次刷新 LOG，避免每印一行都重寫 1000 行。"""
    global _log_dirty, _last_log_flush
    if not _log_dirty:
        return
    now = time.time()
    if not force and (now - _last_log_flush) < LOG_FLUSH_INTERVAL:
        return

    temp_path = LOG_FILE + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.writelines(log_buffer)
        os.replace(temp_path, LOG_FILE)
        _log_dirty = False
        _last_log_flush = now
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


def custom_print(*args, **kwargs):
    """最新訊息維持在第一行，短時間合併落盤。"""
    global _log_dirty
    message = " ".join(map(str, args))
    log_buffer.appendleft(message + "\n")
    _log_dirty = True
    flush_game_log(force=False)


# 替換原生 print
print = custom_print


def _atomic_write_text(path, content):
    temp_path = str(path) + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(temp_path, path)


def _atomic_write_json(path, data, compact=True):
    temp_path = str(path) + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


# ====================================================
# 【遊戲經濟／戰爭平衡參數 V4】
# ====================================================
# 設計目標：
# 1. 和平、約 30% 軍事人口的國家可以緩慢累積資源。
# 2. 高軍事化（約 40~50%）會形成糧食與金屬壓力，不能無成本養大軍。
# 3. 人口採遊戲性節奏：約 1.5~3.0% 成長，單輪最多 10 人，讓文明崛起更明顯。
# 4. 全面戰爭比襲擾昂貴；打仗必須消耗糧草、兵器，戰利品不再憑空生成。
# 5. 資源庫存過高時採「邊際產能下降」，避免幾百輪後木材／金屬膨脹到數十萬。
#
# 想自行微調時，原則上只改這一區即可。
BALANCE_VERSION = 8
GLOBAL_EVENT_CHANCE = 0.05
COMPACT_FORMAT=True  #JSON檔是否要漂亮排版 {True: 不要, False: 要}

# ====================================================
# 【戰國模式 V3：動態事件 / 政權更替】
# ====================================================
# 這是「全世界每回合」抽一次，而不是每國都抽，因此事件不會洗版。
DYNAMIC_EVENT_CHANCE = 0.045
EVENT_HISTORY_MAX = 20

# 正統交接採「政權壽命制」：
# 政權至少存續 5000 Loop；達到門檻後，每輪有 10% 機率完成合法交接。
# 政治崩壞則仍可能在壽命到期前因政變提前更替。
REGIME_CHANGE_COOLDOWN_TURNS = 90
SUCCESSION_MIN_TENURE = 5000
SUCCESSION_CHANCE_PER_COUNTRY = 0.1

# 動態事件持續時間（Game Loop）。
EVENT_DURATION_SHORT = 5
EVENT_DURATION_NORMAL = 8
EVENT_DURATION_LONG = 10

BALANCE = {
    # 人口與住房
    "HOUSE_WOOD_COST": 100,
    # 房屋接近滿載才擴建，避免容量長期遠高於人口。
    "HOUSE_BUILD_THRESHOLD": 0.93,
    # 若房屋容量長期超過人口 30%，每輪會有少量閒置房屋自然荒廢。
    "HOUSE_EXCESS_CAPACITY_RATIO": 1.30,
    "HOUSE_ABANDON_MAX_PER_TURN": 6,
    "FOOD_COST_PER_BIRTH": 8,
    "BIRTH_MIN_RESERVE_TURNS": 5.0,
    "BIRTH_RATE_MIN": 0.015,
    "BIRTH_RATE_MAX": 0.030,
    "BIRTH_MAX_PER_TURN": 10,

    # 農民基礎產能（每名被分派到該工作的農民／每輪）
    "FOOD_PER_WORKER": 4.8,
    "WOOD_PER_WORKER": 2.0,
    "METAL_PER_WORKER": 1.7,

    # 每輪維持費
    "FARMER_FOOD_UPKEEP": 1.0,
    "SOLDIER_FOOD_UPKEEP": 2.0,
    "SOLDIER_METAL_UPKEEP": 0.20,
    "OVERCROWD_FOOD_PENALTY": 1.5,

    # 徵兵
    "RECRUIT_METAL_COST": 8,
    "RECRUIT_FOOD_COST": 3,
    # 一般自動徵兵會隨人口動態放大，不再永遠只有 4~12 人。
    "RECRUIT_BATCH_MIN": 8,
    "RECRUIT_BATCH_MAX": 36,
    "RECRUIT_DYNAMIC_POP_RATIO": 0.012,
    "RECRUIT_DYNAMIC_MAX": 60,

    # Action 6「戰時動員」可一次動員約人口 3%，但封頂避免瞬間抽乾農民。
    "MOBILIZE_POP_RATIO": 0.030,
    "MOBILIZE_MIN": 18,
    "MOBILIZE_MAX": 120,

    # 糧食安全與勞工配置
    "FAMINE_WARNING_TURNS": 3.0,
    "LOW_FOOD_TURNS": 6.0,
    "SURPLUS_FOOD_TURNS": 12.0,

    # 庫存過高時，採集效率下降（不是硬砍庫存）
    "SURPLUS_PRODUCTION_FACTOR": 0.20,
    "SURPLUS_FOOD_PRODUCTION_FACTOR": 0.35,
    "WOOD_RESERVE_PER_POP": 3.0,
    "METAL_RESERVE_PER_POP": 0.8,
    "METAL_RESERVE_PER_SOLDIER": 2.5,

    # 非戰鬥人口／軍力保護
    # 糧食或金屬不足時只允許「逐步退伍」，禁止一輪把數百士兵全部轉回農夫。
    "EMERGENCY_DEMOB_MAX_RATIO": 0.02,       # 每輪最多退伍總人口 2%
    "EMERGENCY_DEMOB_MAX_COUNT": 20,         # 且最多 20 人
    "METAL_SHORTAGE_DEMOB_MAX_RATIO": 0.03,  # 金屬不足每輪最多退伍總人口 3%
    "METAL_SHORTAGE_DEMOB_MAX_COUNT": 25,

    # 飢荒採漸進制：第一次欠糧先進入配給，不立即大量死亡。
    "FAMINE_GRACE_TURNS": 1,
    "FAMINE_DEFICIT_PER_DEATH": 6.0,
    "FAMINE_MAX_POP_LOSS_RATIO": 0.015,      # 每輪最多死亡總人口 1.5%
    "FAMINE_MAX_DEATHS_PER_TURN": 40,

    # 全面戰爭：每名「實際出征士兵」的一次性補給
    "WAR_DEPLOY_MIN": 0.45,
    "WAR_DEPLOY_MAX": 0.65,
    "WAR_FOOD_PER_SOLDIER": 0.80,
    "WAR_METAL_PER_SOLDIER": 0.90,

    # 正面交戰規模與傷亡
    "BATTLE_CLASH_MIN": 0.25,
    "BATTLE_CLASH_MAX": 0.45,
    "BATTLE_LOSS_MIN": 0.65,
    "BATTLE_LOSS_MAX": 0.95,

    # 戰爭掠奪負重（每名實際出征士兵）
    "PLUNDER_FOOD_PER_SOLDIER": 5,
    "PLUNDER_WOOD_PER_SOLDIER": 3,
    "PLUNDER_METAL_PER_SOLDIER": 2,

    # 滅國後可帶走的敵方現有庫存比例
    "CONQUEST_CAPTURE_RATE": 0.25,

    # 小規模襲擾
    "RAID_FORCE_RATIO": 0.15,
    "RAID_FOOD_PER_SOLDIER": 0.60,
    "RAID_METAL_PER_SOLDIER": 0.25,
    "RAID_LOSS_MIN": 0.03,
    "RAID_LOSS_MAX": 0.08,

    # 初始國家資源
    "START_FOOD_MIN": 700,
    "START_FOOD_MAX": 1200,
    "START_WOOD_MIN": 250,
    "START_WOOD_MAX": 450,
    "START_METAL_MIN": 150,
    "START_METAL_MAX": 300,
}

# ================================================
# 全球事件與性格定義
# ================================================
PERSONALITIES = {  # 定義國家 AI 的性格類別與其偏好參數
    "WARMONGER": {  # 好戰狂魔：高攻擊與背叛傾向
        "name": "好戰狂魔",  # 性格名稱
        "atk_pref": 0.4,  # 主動進攻偏好係數
        "betray_pref": 0.2,  # 背叛盟友偏好係數
    },
    "PACIFIST": {  # 和平主義：極低攻擊與背叛傾向
        "name": "和平主義",  # 性格名稱
        "atk_pref": 0.05,  # 主動進攻偏好係數
        "betray_pref": 0.0,  # 背叛盟友偏好係數
    },
    "OPPORTUNIST": {  # 投機政客：中等攻擊與高背叛傾向
        "name": "投機政客",  # 性格名稱
        "atk_pref": 0.2,  # 主動進攻偏好係數
        "betray_pref": 0.3,  # 背叛盟友偏好係數
    },
}

def calculate_rts_power(data):
    """根據士兵數統計國家戰力（以士兵為核心）"""
    if not data.get("is_alive", True):  # 檢查國家是否滅亡（若 is_alive 為 False）
        return 0  # 滅亡的國家戰力歸零
    
    soldiers = data.get("soldiers", 0)  # 取得該國目前的士兵數量，若無則預設 0
    # 戰力純粹由士兵決定（每名士兵提供 50 點戰力）
    pwr = soldiers * 50  # 計算總戰力 (士兵數 * 50)
    return pwr  # 回傳計算出來的戰力值


def enforce_farmer_majority(data):
    """硬性維持人口規則：任何存活國家都必須 farmers >= soldiers，且兩者總和等於 pop_total。"""
    if not data.get("is_alive", True):
        # 滅亡國家直接歸零，連舊存檔的不一致資料也一併清掉。
        data["pop_total"] = 0
        data["farmers"] = 0
        data["soldiers"] = 0
        return

    pop_total = max(1, int(data.get("pop_total", 1) or 1))
    soldiers = max(0, int(data.get("soldiers", 0) or 0))

    # 士兵最多只能占總人口的一半；奇數人口時，農夫必定多 1 人。
    max_soldiers = int(pop_total * 0.5)
    soldiers = min(soldiers, max_soldiers)
    farmers = pop_total - soldiers

    data["pop_total"] = pop_total
    data["soldiers"] = soldiers
    data["farmers"] = farmers

def trigger_global_event():
    """全球隨機事件；V2 降低頻率以抑制長局資源膨脹。"""
    if random.random() < GLOBAL_EVENT_CHANCE:
        # 戰國模式：暫停會直接大量削減人口的隕石事件。
        events = [
            ("金礦大發掘", "BOOM", "⛏️ [全球事件] 發現超級金礦！全體國家資源大幅提升！"),
            (
                "大航海時代",
                "EXPANSION",
                "⛵ [全球事件] 大航海時代開啟！休養生息與生產效率翻倍！",
            ),
        ]
        return random.choice(events)  # 隨機抽取一個事件回傳
    return None, None, None  # 未觸發時回傳三個 None


# ====================================================
# 【羅馬數字轉換與名稱生成】工具函式
# ====================================================
def to_roman(number):
    """將世代數轉換為羅馬數字"""
    num_map = [  # 阿拉伯數字與羅馬數字對照清單（從大到小排列）
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    roman = ""  # 初始化羅馬數字字串
    while number > 0:  # 當數字大於 0 時持續進行轉換
        for val, symbol in num_map:  # 依序尋找可扣抵的最大對照值
            while number >= val:  # 若數字大於等於對照值
                roman += symbol  # 拼接對應的羅馬符號
                number -= val  # 扣除相應的數值
    return roman  # 回傳轉換完成的羅馬數字字串



def from_roman(roman):
    """將羅馬數字轉為整數；無法辨識時回傳 0。"""
    roman = str(roman or "").strip().upper()
    if not roman:
        return 0
    values = {
        "I": 1, "V": 5, "X": 10, "L": 50,
        "C": 100, "D": 500, "M": 1000,
    }
    total = 0
    prev = 0
    try:
        for ch in reversed(roman):
            value = values[ch]
            if value < prev:
                total -= value
            else:
                total += value
                prev = value
    except KeyError:
        return 0
    return max(0, total)


def _to_chinese_number(number):
    """政權世系顯示用：2 -> 二、11 -> 十一、23 -> 二十三。"""
    n = max(0, int(number or 0))
    if n == 0:
        return "零"

    digits = "零一二三四五六七八九"

    if n < 10:
        return digits[n]
    if n < 20:
        return "十" + (digits[n % 10] if n % 10 else "")
    if n < 100:
        return (
            digits[n // 10]
            + "十"
            + (digits[n % 10] if n % 10 else "")
        )
    if n < 1000:
        hundreds, rem = divmod(n, 100)
        result = digits[hundreds] + "百"
        if rem == 0:
            return result
        if rem < 10:
            return result + "零" + digits[rem]
        return result + _to_chinese_number(rem)
    if n < 10000:
        thousands, rem = divmod(n, 1000)
        result = digits[thousands] + "千"
        if rem == 0:
            return result
        if rem < 100:
            result += "零"
        return result + _to_chinese_number(rem)

    # 理論上不會到這麼高；避免超長轉換邏輯。
    return str(n)


def _strip_regime_succession_suffix(name):
    """移除 V6 政權世系尾碼，例如：(二世)、(12世)。"""
    s = str(name or "").strip()
    return re.sub(
        r"\((?:[零〇一二三四五六七八九十百千兩0-9]+)世\)$",
        "",
        s,
    ).strip()


def _extract_old_roman_generation(name):
    """
    舊版復國格式是「國號 II」。
    V6 新格式是「國號II」且另有 regime_name_root，因此主要用於舊存檔 migration。
    """
    s = _strip_regime_succession_suffix(name)
    match = re.search(r"\s+([IVXLCDM]+)$", s, flags=re.IGNORECASE)
    if not match:
        return 0
    return from_roman(match.group(1))


def _strip_old_roman_generation(name):
    """移除舊版「 國號 II」尾碼，保留真正的政權國號根。"""
    s = _strip_regime_succession_suffix(name)
    return re.sub(
        r"\s+[IVXLCDM]+$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()


def _infer_legacy_name_generation_from_history(data):
    """
    推算「目前國號」已復國到第幾次：
    1 = 原始國號，不顯示 I
    2 = II
    3 = III

    只計算最近一次政變改國號之後發生的亡國重建。
    """
    generation = 1
    history = data.get("regime_history", []) or []

    coup_kinds = {
        "軍事政變",
        "宮廷政變",
        "民變革命",
    }

    for item in reversed(history):
        if not isinstance(item, dict):
            continue

        kind = str(item.get("kind", "") or "")

        if kind in coup_kinds:
            break

        if kind == "亡國重建":
            generation += 1

    return max(1, generation)


def _infer_regime_generation_from_history(data):
    """
    推算目前政權合法傳承到第幾世。
    最近一次政變或亡國重建後，每次合法／正統交接 +1。
    """
    generation = 1
    history = data.get("regime_history", []) or []

    for item in reversed(history):
        if not isinstance(item, dict):
            continue

        kind = str(item.get("kind", "") or "")

        if kind in {
            "正統繼承",
            "正統交接",
            "合法交接",
        }:
            generation += 1
            continue

        break

    return max(1, generation)


def _format_regime_display_name(
    regime_name_root,
    name_generation=1,
    regime_generation=1,
):
    """
    V6.3 三軌顯示規則：

    country_generation：
        國家歷史總世代，永遠累加，但不直接拿來組合國號。

    name_generation：
        目前這個國號的復國世代。
        1 -> 不顯示 I
        2 -> II
        3 -> III

    regime_generation：
        目前政權合法交接世系。
        1 -> 不顯示
        2 -> (二世)
        3 -> (三世)

    範例：
        挫蛋先鋒
        挫蛋先鋒II
        挫蛋先鋒II(二世)
        政變後 -> 挫蛋軍政府
        再復國 -> 挫蛋軍政府II
    """
    root = str(regime_name_root or "").strip()
    name_generation = max(1, int(name_generation or 1))
    regime_generation = max(1, int(regime_generation or 1))

    display = root

    if name_generation > 1:
        display += to_roman(name_generation)

    if regime_generation > 1:
        display += (
            f"({_to_chinese_number(regime_generation)}世)"
        )

    return display


def _advance_country_rebirth_identity(country_key, data):
    """
    亡國重建：
    - 國家總世代 +1。
    - 延續滅亡前最後國號。
    - 目前國號復國世代 +1，因此 II / III / IV...。
    - 政權合法交接世系重新由一世起算。
    """
    old_name = str(data.get("display_name", country_key))

    root = str(
        data.get("regime_name_root", "")
        or _strip_old_roman_generation(old_name)
        or country_key
    ).strip()

    country_generation = max(
        1,
        int(
            data.get(
                "country_generation",
                data.get("gen", 1),
            )
            or 1
        ),
    ) + 1

    name_generation = max(
        1,
        int(data.get("name_generation", 1) or 1),
    ) + 1

    data["country_generation"] = country_generation
    data["gen"] = country_generation
    data["name_generation"] = name_generation
    data["regime_name_root"] = root
    data["regime_generation"] = 1

    new_name = _format_regime_display_name(
        root,
        name_generation,
        1,
    )
    data["display_name"] = new_name

    return old_name, new_name




# ====================================================
# 【V6.5 國家編年史 / 1 Game Loop = 1 年】
# ====================================================
CHRONICLE_SCHEMA_VERSION = 1


def _world_year(turn_counter):
    """《亂世演算》世界曆：1 Game Loop 視為 1 年。"""
    return max(1, int(turn_counter or 0))


def _new_chronicle_entry(country_key, data, start_year):
    """建立一個新的國家世代編年史紀錄。"""
    start_year = max(1, int(start_year or 1))
    return {
        "generation": max(
            1,
            int(
                data.get(
                    "country_generation",
                    data.get("gen", 1),
                )
                or 1
            ),
        ),
        "name": str(data.get("display_name", country_key) or country_key),
        "regime_type": str(data.get("regime_type", "正統政權") or "正統政權"),
        "start_year": start_year,
        "end_year": None,
        "duration_years": None,
        "end_reason": "",
        "ended_by": "",
        "peak_power": max(0, int(data.get("power", 0) or 0)),
        "peak_power_year": start_year,
        "peak_population": max(0, int(data.get("pop_total", 0) or 0)),
        "best_rank": None,
    }


def _chronicle_active_entry(data):
    history = data.get("country_chronicle", []) or []
    for item in reversed(history):
        if isinstance(item, dict) and item.get("end_year") in (None, ""):
            return item
    return None


def _chronicle_update_live_stats(data, turn_counter, rank=None):
    """
    更新目前國家世代的巔峰紀錄。
    若國家目前正在亡國冷卻期，沒有 active entry 就不自行開新世代。
    """
    current = _chronicle_active_entry(data)
    if current is None:
        return

    year = _world_year(turn_counter)
    power = max(0, int(data.get("power", 0) or 0))
    population = max(0, int(data.get("pop_total", 0) or 0))

    if power > int(current.get("peak_power", 0) or 0):
        current["peak_power"] = power
        current["peak_power_year"] = year

    if population > int(current.get("peak_population", 0) or 0):
        current["peak_population"] = population

    if rank is not None:
        rank = int(rank)
        old_rank = current.get("best_rank")
        if old_rank in (None, "", 0) or rank < int(old_rank):
            current["best_rank"] = rank

    # 存活中的 active row 可同步目前名稱/政權類型。
    current["name"] = str(data.get("display_name", current.get("name", "")))
    current["regime_type"] = str(
        data.get("regime_type", current.get("regime_type", "正統政權"))
        or "正統政權"
    )


def _chronicle_close_current(
    country_key,
    data,
    turn_counter,
    end_reason,
    ended_by="",
):
    """結束目前國家世代；不會自動建立下一世代。"""
    _ensure_country_chronicle(country_key, data, turn_counter)

    current = _chronicle_active_entry(data)
    if current is None:
        return None

    year = _world_year(turn_counter)

    # 關閉前先吃到當年最後可見的戰力/人口。
    _chronicle_update_live_stats(data, turn_counter)

    current["end_year"] = year
    start_year = int(current.get("start_year", 0) or 0)
    if start_year > 0:
        current["duration_years"] = max(1, year - start_year + 1)
    else:
        current["duration_years"] = None

    current["end_reason"] = str(end_reason or "世代結束")
    current["ended_by"] = str(ended_by or "")
    return current


def _chronicle_start_current(country_key, data, turn_counter):
    """以目前 display_name / country_generation 建立新世代。"""
    history = data.setdefault("country_chronicle", [])
    generation = max(
        1,
        int(
            data.get(
                "country_generation",
                data.get("gen", 1),
            )
            or 1
        ),
    )

    current = _chronicle_active_entry(data)
    if current is not None:
        if int(current.get("generation", 0) or 0) == generation:
            return current
        # 保險：上一筆若異常未關閉，就先標示為資料修復。
        current["end_year"] = _world_year(turn_counter)
        current["duration_years"] = max(
            1,
            int(current["end_year"])
            - int(current.get("start_year", current["end_year"]) or current["end_year"])
            + 1,
        )
        current["end_reason"] = current.get("end_reason") or "世代資料修復"

    entry = _new_chronicle_entry(
        country_key,
        data,
        _world_year(turn_counter),
    )
    history.append(entry)
    return entry


def _rebuild_chronicle_from_regime_history(country_key, data, turn_counter):
    """
    舊 V6.4 以前沒有完整編年史。
    若 regime_history 還留有近期政權更替，就盡可能重建可辨識的最近歷史；
    無法確定的最早建立年份以 0 表示，UI 會顯示「舊檔未知」。
    """
    events = [
        item
        for item in (data.get("regime_history", []) or [])
        if isinstance(item, dict) and int(item.get("turn", 0) or 0) > 0
    ]
    events.sort(key=lambda item: int(item.get("turn", 0) or 0))

    history = []
    if not events:
        entry = _new_chronicle_entry(
            country_key,
            data,
            max(
                1,
                int(data.get("last_regime_change_turn", 0) or 0),
            ),
        )
        if int(data.get("last_regime_change_turn", 0) or 0) <= 0:
            entry["start_year"] = 1
        history.append(entry)
        return history

    first = events[0]
    first_new_gen = max(
        1,
        int(
            first.get(
                "country_generation",
                first.get("generation", 1),
            )
            or 1
        ),
    )
    first_old_gen = max(1, first_new_gen - 1)

    first_entry = {
        "generation": first_old_gen,
        "name": str(first.get("old_name", country_key) or country_key),
        "regime_type": "舊檔未記錄",
        "start_year": 0,
        "end_year": int(first.get("turn", 0) or 0),
        "duration_years": None,
        "end_reason": str(first.get("kind", "世代更替") or "世代更替"),
        "ended_by": "",
        "peak_power": 0,
        "peak_power_year": None,
        "peak_population": 0,
        "best_rank": None,
    }
    history.append(first_entry)

    for idx, event in enumerate(events):
        event_year = _world_year(event.get("turn", 1))
        generation = max(
            1,
            int(
                event.get(
                    "country_generation",
                    event.get("generation", 1),
                )
                or 1
            ),
        )
        name = str(event.get("new_name", country_key) or country_key)

        entry = {
            "generation": generation,
            "name": name,
            "regime_type": "舊檔未記錄",
            "start_year": event_year,
            "end_year": None,
            "duration_years": None,
            "end_reason": "",
            "ended_by": "",
            "peak_power": 0,
            "peak_power_year": None,
            "peak_population": 0,
            "best_rank": None,
        }

        if idx + 1 < len(events):
            nxt = events[idx + 1]
            end_year = _world_year(nxt.get("turn", event_year))
            entry["end_year"] = end_year
            entry["duration_years"] = max(1, end_year - event_year + 1)
            entry["end_reason"] = str(nxt.get("kind", "世代更替") or "世代更替")
        history.append(entry)

    # 最後一筆同步目前真實資料。
    if history:
        last = history[-1]
        last["generation"] = max(
            1,
            int(
                data.get(
                    "country_generation",
                    data.get("gen", last.get("generation", 1)),
                )
                or 1
            ),
        )
        last["name"] = str(data.get("display_name", last.get("name", country_key)))
        last["regime_type"] = str(data.get("regime_type", "正統政權") or "正統政權")

        if not data.get("is_alive", True):
            # 舊檔無法知道精確滅亡年/兇手，只標記為目前已滅亡。
            if last.get("end_year") in (None, ""):
                last["end_year"] = _world_year(turn_counter)
                sy = int(last.get("start_year", 0) or 0)
                last["duration_years"] = (
                    max(1, int(last["end_year"]) - sy + 1)
                    if sy > 0
                    else None
                )
                last["end_reason"] = "舊存檔：滅亡（原因未記錄）"

    return history


def _ensure_country_chronicle(country_key, data, turn_counter=0):
    """確保新舊存檔都有 V6.5 編年史資料。"""
    if int(data.get("chronicle_schema_version", 0) or 0) < CHRONICLE_SCHEMA_VERSION:
        if not isinstance(data.get("country_chronicle"), list) or not data.get("country_chronicle"):
            data["country_chronicle"] = _rebuild_chronicle_from_regime_history(
                country_key,
                data,
                turn_counter,
            )
        data["chronicle_schema_version"] = CHRONICLE_SCHEMA_VERSION

    data.setdefault("country_chronicle", [])

    # 新局或舊檔沒有任何可重建資料時，補一筆現行世代。
    if not data["country_chronicle"] and data.get("is_alive", True):
        data["country_chronicle"].append(
            _new_chronicle_entry(
                country_key,
                data,
                _world_year(turn_counter),
            )
        )

    # 存活國必須有 active entry；亡國冷卻期間則故意保持沒有 active entry。
    if data.get("is_alive", True) and _chronicle_active_entry(data) is None:
        _chronicle_start_current(country_key, data, turn_counter)

    return data["country_chronicle"]


def generate_country_names(n):
    """生成基本國家名稱列表"""
    custom_names = [  # 預設自訂特色名稱清單
        "挫蛋先鋒", "奶霜聯盟", "嗜血狂鯊", "霹靂暗雷", "地獄烈焰", "閃電戰狼", "虛擬幻影",
        "深淵巨妖", "夜城行者", "量子重力", "黑客帝國", "蒸汽朋克", "諸神黃昏", "冥府使者",
        "奧林帕斯", "北歐暴風", "絕對零度", "不死鳳凰", "黃金聖盾", "劇毒沼澤", "猩紅女巫",
        "合金重裝", "像素方塊", "末地使者", "戰地轟炸", "凋零風暴", "紅石科技", "摸魚大師",
        "肝帝連盟", "歐皇附體", "非酋救濟", "宵夜雷達",

        "終焉之刃", "極光幻滅", "暗夜孤狼", "雷霆萬鈞", "寒冰刺客", "烈焰風暴", "不滅戰魂",
        "幽冥狂瀾", "影疾風刃", "鋼鐵意志", "天譴黑翼", "星海游俠", "孤高遊俠", "狂暴巨獸",
        "瞬步暗殺", "虛空之眼", "星河戰隊", "破曉之光",

        "混沌領主", "聖殿騎士", "不朽傳奇", "迷霧幽靈", "惡魔獵手", "亞特蘭提", "煉金術士",
        "命運之輪", "深海歌姬", "精靈密語", "亡靈序曲", "星辰之子", "時空旅人", "永夜序曲",
        "符文刻印",

        "矩陣重組", "賽博浪人", "極限方塊", "潛影之貝", "凋零骷髏", "極限生存", "黑曜石牆",
        "指令方塊", "機械公敵", "光纖追蹤", "超頻驅動", "代碼漏洞", "量子糾纏", "引力坍塌",
        "核心熔毀",

        "薪水小偷", "熬夜冠軍", "外送達人", "起司漢堡", "肥宅快樂", "魔法防禦", "躺平精靈",
        "課金大佬", "戰力單位", "氣氛大師", "極限手殘", "路過鄉民", "珍珠奶茶", "爆米花隊",
        "火鍋戰隊", "咖啡因癮", "睡意襲來", "滿血復活", "絕地翻盤", "全村希望"
    ]

    prefixes = [  # 隨機生成名稱用的前綴字庫
        "阿斯", "貝洛", "塞勒", "多倫", "埃爾", "芬蘭", "格林", "海倫", "伊斯", "克倫",
        "拉斐", "馬爾", "諾斯", "奧林", "佩拉", "昆斯", "雷克", "索倫", "泰坦", "烏拉",
        "瓦爾", "溫斯", "薩克", "約克", "齊格", "阿爾", "博爾", "卡斯", "德拉", "福爾",
        "安地", "波斯", "迦太", "德魯", "伊特", "腓尼", "赫梯", "印加", "美索", "諾曼",
        "帕提", "斯巴", "特洛", "烏加", "梵蒂", "拜占", "瑪雅", "塞爾", "維京", "蘇美"
    ]
    suffixes = [  # 隨機生成名稱用的後綴字庫
        "蒂娜", "斯塔", "利亞", "尼西亞", "高地", "群島", "大路", "特區", "男爵領", "侯國",
        "公國", "聯邦", "帝國", "王國", "聖域", "自治領", "郡", "省", "堡", "關",
        "海峽", "半島", "平線", "谷地", "荒原",
        "之森", "之峰", "之海", "之嶺", "灣", "峽谷", "綠洲", "高原", "沼澤", "苔原",
        "丘陵", "雪原", "沃野", "裂谷", "凍土", "河口", "斷崖", "暗礁", "沙洲", "火山",
        "山脈", "盆地", "溪谷", "峭壁", "海灣"
    ]

    names = []  # 初始化最終名稱串列
    for name in custom_names:  # 優先從自訂名稱庫填入
        if len(names) < n:  # 若數量尚未達到指定需求 n
            names.append(name)  # 加入名稱
        else:
            break  # 已達數量則跳出迴圈

    while len(names) < n:  # 若自訂名稱不夠 n 個，則透過前後綴組合隨機生成
        p = random.choice(prefixes)  # 隨機選取前綴
        s = random.choice(suffixes)  # 隨機選取後綴
        generated_name = f"{p}{s}"  # 組合前後綴
        if generated_name not in names:  # 確保名稱不重複
            names.append(generated_name)  # 加入名稱串列

    return names  # 回傳產生的國家名稱串列


def generate_awesome_alliance_name(is_anti_hegemon=False, target_name=""):
    prefixes = [  # 聯盟名稱前綴庫
        "真理", "正義", "和平", "神聖", "狂熱", "英勇", "至高", "不朽", "榮耀", "天譴",
        "極光", "創世", "黎明", "終焉", "永恆", "烈焰", "寒冰", "雷霆", "風暴", "大地",
        "深海", "流沙", "微風", "怒濤", "烈日", "新月", "繁星", "熔線", "霜狼", "蒼穹",
        "黑鐵", "白銀", "黃金", "水晶", "秘銀", "鋼鐵", "赤紅", "漆黑", "青銅", "黑曜",
        "巨石", "戰歌", "破曉", "先鋒", "鐵衛", "征服", "庇護", "守護", "堅壁", "裁決"
    ]
    suffixes = [  # 聯盟名稱後綴庫
        "戰線", "憲章", "宣言", "條約", "體系", "陣營", "安保體系", "互助會", "同盟會", "連線",
        "共識", "密約", "協議", "議定書", "盟約", "陣營", "維和部隊", "聯合防衛線", "合作社", "防衛圈",
        "夥伴關係", "防衛協議", "公約國", "戰術聯盟", "聯合會"
    ]

    if is_anti_hegemon:  # 臨時反霸權聯軍
        target_tag = f"·反{target_name}" if target_name else "·反霸權"
        return f"【<<{random.choice(prefixes)}{random.choice(suffixes)}{target_tag}>>】"

    return f"【=={random.choice(prefixes)}{random.choice(suffixes)}==】"  # 一般同盟使用 == == 括號風格


def get_country_alliance(country_name, alliances):
    """查詢某國家目前所屬的普通聯盟名稱。反霸權聯軍不寫入 alliances。"""
    for ally_name, members in alliances.items():
        if country_name in members:
            return ally_name
    return ""


def get_country_coalition(country_name, anti_hegemon_coalitions):
    """查詢某國是否正在參與臨時反霸權聯軍；回傳聯軍名稱，否則空字串。"""
    for coalition_name, info in anti_hegemon_coalitions.items():
        if not isinstance(info, dict):
            continue
        if country_name in (info.get("members") or []):
            return coalition_name
    return ""


def get_coalition_entity(coalition_name, anti_hegemon_coalitions, countries):
    """建立臨時聯軍的戰鬥實體；只動員實際參與圍剿的國家。"""
    info = anti_hegemon_coalitions.get(coalition_name, {})
    members = [
        m for m in (info.get("members") or [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    return {
        "type": "COALITION",
        "name": coalition_name,
        "members": members,
        "power": sum(countries[m].get("power", 0) for m in members),
    }


def coalition_join_willingness(candidate, hegemon_key, countries, alliances, rl_agents, rank_map):
    """回傳 0~0.95 的參加反霸權聯軍意願。越曾受霸主威脅、越弱、越接近前段班，意願越高。"""
    if candidate == hegemon_key:
        return 0.0

    c = countries[candidate]
    h = countries[hegemon_key]
    if not c.get("is_alive", True):
        return 0.0

    # 與霸主處於同一普通聯盟者不參加討伐，避免同盟內戰。
    c_ally = get_country_alliance(candidate, alliances)
    h_ally = get_country_alliance(hegemon_key, alliances)
    if c_ally and h_ally and c_ally == h_ally:
        return 0.0

    willingness = 0.12
    if c.get("event_coalition_bonus_target") == hegemon_key:
        willingness += 0.18
    recent_attackers = set(c.get("recent_attackers", []) or [])
    if hegemon_key in recent_attackers:
        willingness += 0.48

    my_power = max(1, c.get("power", 0))
    hegemon_power = max(1, h.get("power", 0))
    if my_power < hegemon_power * 0.45:
        willingness += 0.16
    elif my_power < hegemon_power * 0.75:
        willingness += 0.08

    rank = rank_map.get(candidate, 999)
    if 2 <= rank <= 5:
        willingness += 0.16  # 有能力競逐霸權的前段班更願意牽制第一名
    elif rank <= 12:
        willingness += 0.07

    personality = getattr(rl_agents.get(candidate), "personality_type", "OPPORTUNIST")
    if personality == "WARMONGER":
        willingness += 0.12
    elif personality == "PACIFIST":
        willingness += 0.10 if hegemon_key in recent_attackers else -0.06
    else:
        willingness += 0.06

    # 已有普通聯盟者略偏保守，但不需要退盟。
    if c_ally:
        willingness -= 0.04

    willingness *= float(
        c.get("world_coalition_bias", 1.0) or 1.0
    )

    return float(_clamp(willingness, 0.02, 0.95))


def get_entity_info(country_key, countries, alliances):
    """取得戰鬥實體資訊（單一國家或同盟整體）"""
    ally_name = get_country_alliance(country_key, alliances)  # 檢查該國是否屬於某同盟
    if ally_name:  # 若屬於某同盟
        members = [m for m in alliances[ally_name] if countries[m]["is_alive"]]  # 篩選出同盟內存活的成員
        total_pwr = sum(countries[m]["power"] for m in members)  # 計算同盟總戰力
        return {"type": "ALLIANCE", "name": ally_name, "members": members, "power": total_pwr}  # 回傳同盟實體資料
    else:  # 若為單一國家
        c = countries[country_key]  # 取得國家資料
        return {  # 回傳單一國家實體資料
            "type": "SINGLE",
            "name": c["display_name"],
            "members": [country_key],
            "power": c["power"] if c["is_alive"] else 0,
        }



# ====================================================
# 【亂世演算 V5：普通聯盟議會 / 戰爭表決】
# ====================================================
ALLIANCE_WAR_VOTE_COOLDOWN_MIN = 4
ALLIANCE_WAR_VOTE_COOLDOWN_MAX = 6
ALLIANCE_JOIN_VOTE_COOLDOWN_MIN = 5
ALLIANCE_JOIN_VOTE_COOLDOWN_MAX = 8


def _alliance_vote_target_token(target_key, countries, alliances):
    """以目標聯盟作為冷卻單位，避免換一名盟員當 anchor 就重複洗票。"""
    target_alliance = get_country_alliance(target_key, alliances)
    if target_alliance:
        return f"ALLY::{target_alliance}"
    return f"COUNTRY::{target_key}"


def _alliance_vote_cooldown_key(alliance_name, target_key, countries, alliances):
    return (
        f"{alliance_name}||"
        f"{_alliance_vote_target_token(target_key, countries, alliances)}"
    )


def _alliance_vote_target_members(target_key, countries, alliances):
    entity = get_entity_info(target_key, countries, alliances)
    members = [
        m
        for m in entity.get("members", [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    return entity, members



def _alliance_join_vote_cooldown_key(alliance_name, candidate_key):
    """同一申請國對同一聯盟的入盟申請冷卻鍵。"""
    return f"{alliance_name}||{candidate_key}"


def _alliance_vote_power_weights(members, countries):
    """
    聯盟議會票權 = 當下戰力。

    例：
    1,000,000 戰力的國家，其票權就是 1,000,000；
    100,000 戰力的國家，其票權就是 100,000；
    前者在議會中的權重正好是後者 10 倍。

    若所有合格成員戰力恰好都為 0，才退回每國 1 票，
    避免議會因總票權為 0 而無法做任何決議。
    """
    unique_members = list(dict.fromkeys(members))
    weights = {
        m: max(
            0,
            int(countries.get(m, {}).get("power", 0) or 0),
        )
        for m in unique_members
    }

    if sum(weights.values()) <= 0:
        weights = {m: 1 for m in unique_members}

    return weights


def _alliance_weighted_vote_summary(members, votes, countries):
    """
    依當下戰力加總議會票權。
    通過門檻為「全體合格票權嚴格過半」。
    """
    weights = _alliance_vote_power_weights(members, countries)
    total_weight = sum(weights.values())

    yes_weight = sum(
        weights.get(m, 0)
        for m in members
        if votes.get(m) == "贊成"
    )
    no_weight = sum(
        weights.get(m, 0)
        for m in members
        if votes.get(m) == "反對"
    )
    abstain_weight = sum(
        weights.get(m, 0)
        for m in members
        if votes.get(m) == "棄權"
    )

    # 戰力為整數，嚴格過半可用 floor(total/2)+1 表示。
    threshold_weight = total_weight // 2 + 1
    passed = yes_weight >= threshold_weight

    return {
        "weights": weights,
        "total_weight": int(total_weight),
        "threshold_weight": int(threshold_weight),
        "yes_weight": int(yes_weight),
        "no_weight": int(no_weight),
        "abstain_weight": int(abstain_weight),
        "passed": bool(passed),
    }


def _war_countries_are_opponents(country_a, country_b, active_wars):
    """兩國目前若在同一場正式戰爭的敵對兩側，回傳 True。"""
    if not country_a or not country_b:
        return False

    for war in active_wars.values():
        if not isinstance(war, dict):
            continue
        attackers = set(war.get("attacker_members", []) or [])
        defenders = set(war.get("defender_members", []) or [])
        if (
            country_a in attackers and country_b in defenders
        ) or (
            country_b in attackers and country_a in defenders
        ):
            return True
    return False


def _alliance_member_admission_vote(
    voter_key,
    candidate_key,
    alliance_name,
    countries,
    alliances,
    rl_agents,
    active_wars,
    turn_counter,
):
    """現有盟員對新申請國投 贊成 / 反對 / 棄權。"""
    voter = countries[voter_key]
    candidate = countries[candidate_key]

    if not voter.get("is_alive", True):
        return "反對", "政權已滅亡"
    if not candidate.get("is_alive", True):
        return "反對", "申請國已滅亡"
    if _war_countries_are_opponents(voter_key, candidate_key, active_wars):
        return "反對", "雙方正在交戰"

    score = 0.64

    candidate_infamy = float(candidate.get("infamy", 0) or 0)
    score -= min(0.38, candidate_infamy / 220.0)

    voter_recent_attackers = set(voter.get("recent_attackers", []) or [])
    candidate_recent_attackers = set(candidate.get("recent_attackers", []) or [])

    if candidate_key in voter_recent_attackers:
        score -= 0.42
    if voter_key in candidate_recent_attackers:
        score -= 0.16

    hostility = voter.get("hostility", {}) or {}
    candidate_hostility = float(hostility.get(candidate_key, 0) or 0)
    score -= min(0.30, candidate_hostility / 190.0)

    common_enemies = voter_recent_attackers & candidate_recent_attackers
    if common_enemies:
        score += min(0.20, len(common_enemies) * 0.08)

    candidate_wars = _war_country_war_count(candidate_key, active_wars)
    if candidate_wars >= 2:
        score -= 0.18
    elif candidate_wars == 1:
        score -= 0.07

    candidate_stability = float(
        candidate.get("political_stability", 75) or 75
    )
    candidate_exhaustion = float(
        candidate.get("war_exhaustion", 0) or 0
    )
    if candidate_stability < 25:
        score -= 0.13
    elif candidate_stability < 45:
        score -= 0.06

    if candidate_exhaustion >= 80:
        score -= 0.10
    elif candidate_exhaustion >= 60:
        score -= 0.05

    living_members = [
        m
        for m in alliances.get(alliance_name, [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    if len(living_members) >= 4:
        score -= 0.06

    member_powers = [
        max(0, int(countries[m].get("power", 0) or 0))
        for m in living_members
    ]
    avg_member_power = (
        sum(member_powers) / len(member_powers)
        if member_powers
        else 1.0
    )
    candidate_power = max(0, int(candidate.get("power", 0) or 0))
    power_ratio = candidate_power / max(1.0, avg_member_power)

    if 0.55 <= power_ratio <= 1.70:
        score += 0.08
    elif power_ratio < 0.25:
        score -= 0.08
    elif power_ratio > 2.20:
        score -= 0.05

    personality = getattr(
        rl_agents.get(voter_key),
        "personality_type",
        "OPPORTUNIST",
    )
    if personality == "WARMONGER":
        if candidate_power >= max(
            1,
            int(voter.get("power", 0) or 0) * 0.60,
        ):
            score += 0.06
    elif personality == "PACIFIST":
        if candidate_wars:
            score -= 0.10
        if candidate_infamy >= 35:
            score -= 0.08
    else:
        if power_ratio >= 0.60:
            score += 0.03

    if _event_active(voter, "ALLIANCE_SUMMIT", turn_counter):
        score += 0.08
    if _event_active(voter, "MEMBER_DISPUTE", turn_counter):
        score -= 0.12

    mode = str(voter.get("world_mode_code", "NORMAL") or "NORMAL")
    if mode == "DIPLOMATIC":
        score += 0.15
    elif mode == "FRAGMENTED":
        score -= 0.18
    elif mode == "TOTAL_WAR":
        score += 0.05
    elif mode == "RECUPERATION":
        score += 0.04
    elif mode == "HEGEMONIC" and power_ratio >= 0.70:
        score += 0.07
    elif mode == "ARMS_RACE" and power_ratio >= 0.75:
        score += 0.06
    elif mode == "ECONOMIC_BOOM":
        score += 0.05
    elif mode == "SCARCITY":
        score -= 0.08

    score += random.uniform(-0.10, 0.10)

    if score >= 0.55:
        if common_enemies:
            return "贊成", "共同敵人"
        if candidate_infamy <= 20:
            return "贊成", "信任良好"
        return "贊成", "利大於弊"

    if score <= 0.38:
        if candidate_key in voter_recent_attackers:
            return "反對", "曾遭申請國攻擊"
        if candidate_infamy >= 70:
            return "反對", "惡名過高"
        return "反對", "風險過高"

    return "棄權", "仍需觀望"


def _alliance_admission_vote(
    alliance_name,
    candidate_key,
    countries,
    alliances,
    rl_agents,
    active_wars,
    turn_counter,
):
    """
    新國家申請加入普通聯盟：
    由現有存活盟員投票，申請國沒有投票權；
    每一盟員的票權等於其當下戰力，
    贊成戰力須取得全體合格票權嚴格過半。
    """
    members = [
        m
        for m in alliances.get(alliance_name, [])
        if (
            m in countries
            and countries[m].get("is_alive", True)
            and m != candidate_key
        )
    ]
    members = list(dict.fromkeys(members))

    if not members:
        return {
            "kind": "入盟表決",
            "turn": int(turn_counter),
            "alliance": alliance_name,
            "candidate": candidate_key,
            "candidate_name": countries[candidate_key].get(
                "display_name", candidate_key
            ),
            "eligible": 0,
            "threshold": 1,
            "threshold_weight": 1,
            "total_weight": 0,
            "yes": 0,
            "no": 0,
            "abstain": 0,
            "yes_weight": 0,
            "no_weight": 0,
            "abstain_weight": 0,
            "vote_weights": {},
            "passed": False,
            "result": "否決",
            "votes": {},
            "reasons": {},
        }

    votes = {}
    reasons = {}

    for member in members:
        vote, reason = _alliance_member_admission_vote(
            member,
            candidate_key,
            alliance_name,
            countries,
            alliances,
            rl_agents,
            active_wars,
            turn_counter,
        )
        votes[member] = vote
        reasons[member] = reason

    yes_members = [m for m in members if votes.get(m) == "贊成"]
    no_members = [m for m in members if votes.get(m) == "反對"]
    abstain_members = [m for m in members if votes.get(m) == "棄權"]

    weighted = _alliance_weighted_vote_summary(
        members,
        votes,
        countries,
    )
    vote_weights = weighted["weights"]
    total_weight = weighted["total_weight"]
    threshold_weight = weighted["threshold_weight"]
    yes_weight = weighted["yes_weight"]
    no_weight = weighted["no_weight"]
    abstain_weight = weighted["abstain_weight"]
    passed = weighted["passed"]

    candidate_name = countries[candidate_key].get(
        "display_name",
        candidate_key,
    )

    print(
        f"🗳️ [聯盟入盟表決] {alliance_name}｜"
        f"申請【{candidate_name}】加入："
        f"贊成 {len(yes_members)} 國／反對 {len(no_members)} 國／"
        f"棄權 {len(abstain_members)} 國｜"
        f"贊成戰力 {yes_weight:,}／總票權 {total_weight:,}｜"
        f"過半門檻 {threshold_weight:,} → "
        f"{'✅ 通過' if passed else '❌ 否決'}。"
    )
    print(
        f"🗳️ [入盟表決明細] {alliance_name}｜"
        + "、".join(
            f"{countries[m].get('display_name', m)}:"
            f"{votes[m]}[票權 {vote_weights.get(m, 0):,}]"
            f"({reasons[m]})"
            for m in members
        )
    )

    return {
        "kind": "入盟表決",
        "turn": int(turn_counter),
        "alliance": alliance_name,
        "candidate": candidate_key,
        "candidate_name": candidate_name,
        "eligible": len(members),
        # threshold 保留作為相容欄位；V6.4 起代表「戰力票權門檻」。
        "threshold": threshold_weight,
        "threshold_weight": threshold_weight,
        "total_weight": total_weight,
        "yes": len(yes_members),
        "no": len(no_members),
        "abstain": len(abstain_members),
        "yes_weight": yes_weight,
        "no_weight": no_weight,
        "abstain_weight": abstain_weight,
        "vote_weights": vote_weights,
        "passed": bool(passed),
        "result": "通過" if passed else "否決",
        "votes": votes,
        "reasons": reasons,
    }


def _alliance_vote_member_offense(
    voter_key,
    proposer_key,
    target_key,
    countries,
    alliances,
    rl_agents,
    active_wars,
    turn_counter,
):
    """普通聯盟主動開戰：每個盟國投 贊成 / 反對 / 棄權。"""
    if voter_key == proposer_key:
        return "贊成", "提案國"

    voter = countries[voter_key]

    if not voter.get("is_alive", True):
        return "反對", "政權已滅亡"

    if not _war_country_can_join_new_war(voter_key, active_wars):
        return "反對", "戰線已滿"

    target_entity, target_members = _alliance_vote_target_members(
        target_key,
        countries,
        alliances,
    )

    score = 0.50

    # 恩怨 / 復仇
    hostility = voter.get("hostility", {}) or {}
    target_hostility = max(
        [float(hostility.get(m, 0) or 0) for m in target_members]
        or [0.0]
    )
    score += min(0.30, target_hostility / 220.0)

    recent_attackers = set(voter.get("recent_attackers", []) or [])
    if recent_attackers & set(target_members):
        score += 0.22

    if str(voter.get("event_war_target", "") or "") in target_members:
        score += 0.15

    if voter.get("strategic_mode") == "報復模式":
        score += 0.10

    # 疲勞 / 政局 / 補給
    exhaustion = float(voter.get("war_exhaustion", 0) or 0)
    stability = float(voter.get("political_stability", 75) or 75)

    if exhaustion >= 80:
        score -= 0.34
    elif exhaustion >= 60:
        score -= 0.20
    elif exhaustion >= 40:
        score -= 0.08

    if stability < 25:
        score -= 0.18
    elif stability < 45:
        score -= 0.08

    if _war_country_war_count(voter_key, active_wars) == 1:
        score -= 0.14

    soldiers = max(1, int(voter.get("soldiers", 0) or 0))
    food = max(0.0, float(voter.get("food", 0) or 0))
    metal = max(0.0, float(voter.get("metal", 0) or 0))

    if food < max(100, soldiers * 1.5):
        score -= 0.12
    if metal < max(60, soldiers * 0.75):
        score -= 0.12

    # AI 性格
    personality = getattr(
        rl_agents.get(voter_key),
        "personality_type",
        "OPPORTUNIST",
    )
    if personality == "WARMONGER":
        score += 0.14
    elif personality == "PACIFIST":
        score -= 0.18
    else:
        score += 0.03

    # 敵我總戰力
    my_alliance = get_country_alliance(voter_key, alliances)
    my_members = [
        m
        for m in alliances.get(my_alliance, [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    my_power = sum(
        max(0, int(countries[m].get("power", 0) or 0))
        for m in my_members
    )
    target_power = max(1, int(target_entity.get("power", 1) or 1))

    if my_power > 0:
        ratio = target_power / max(1, my_power)
        if ratio >= 1.60:
            score -= 0.20
        elif ratio >= 1.25:
            score -= 0.10
        elif ratio <= 0.65:
            score += 0.10

    # 聯盟事件
    if _event_active(voter, "ALLIANCE_SUMMIT", turn_counter):
        score += 0.08
    if _event_active(voter, "MEMBER_DISPUTE", turn_counter):
        score -= 0.12

    # 世界局勢
    mode = str(voter.get("world_mode_code", "NORMAL") or "NORMAL")
    if mode == "FRAGMENTED":
        score -= 0.20
    elif mode == "TOTAL_WAR":
        score += 0.20
    elif mode == "RECUPERATION":
        score -= 0.25
    elif mode == "ARMS_RACE":
        score += 0.08
    elif mode == "ECONOMIC_BOOM":
        score -= 0.08
    elif mode == "SCARCITY":
        score -= 0.15
    elif mode == "DIPLOMATIC":
        score += 0.03
    elif mode == "HEGEMONIC":
        alive = [
            k
            for k, c in countries.items()
            if c.get("is_alive", True)
        ]
        if alive:
            top_key = max(
                alive,
                key=lambda k: countries[k].get("power", 0),
            )
            if top_key in target_members:
                score += 0.25

    score += random.uniform(-0.12, 0.12)

    if score >= 0.58:
        return "贊成", "支持開戰"
    if score <= 0.38:
        return "反對", "風險過高"
    return "棄權", "態度保留"


def _alliance_offensive_war_vote(
    alliance_name,
    proposer_key,
    target_key,
    countries,
    alliances,
    rl_agents,
    active_wars,
    turn_counter,
):
    """
    主動戰爭表決：
    每一存活盟員的票權 = 當下戰力；
    贊成戰力必須取得全體合格票權「嚴格過半」。
    通過後仍只有投贊成票的國家出兵。
    """
    members = [
        m
        for m in alliances.get(alliance_name, [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    members = list(dict.fromkeys(members))

    if proposer_key not in members:
        members.insert(0, proposer_key)

    votes = {}
    reasons = {}

    for member in members:
        vote, reason = _alliance_vote_member_offense(
            member,
            proposer_key,
            target_key,
            countries,
            alliances,
            rl_agents,
            active_wars,
            turn_counter,
        )
        votes[member] = vote
        reasons[member] = reason

    yes_members = [m for m in members if votes.get(m) == "贊成"]
    no_members = [m for m in members if votes.get(m) == "反對"]
    abstain_members = [m for m in members if votes.get(m) == "棄權"]

    weighted = _alliance_weighted_vote_summary(
        members,
        votes,
        countries,
    )
    vote_weights = weighted["weights"]
    total_weight = weighted["total_weight"]
    threshold_weight = weighted["threshold_weight"]
    yes_weight = weighted["yes_weight"]
    no_weight = weighted["no_weight"]
    abstain_weight = weighted["abstain_weight"]
    passed = weighted["passed"]

    target_entity, _ = _alliance_vote_target_members(
        target_key,
        countries,
        alliances,
    )
    proposer_name = countries[proposer_key].get(
        "display_name",
        proposer_key,
    )
    target_name = target_entity.get(
        "name",
        countries[target_key].get("display_name", target_key),
    )

    print(
        f"🗳️ [聯盟戰爭表決] {alliance_name}｜"
        f"提案【{proposer_name}】對【{target_name}】開戰："
        f"贊成 {len(yes_members)} 國／反對 {len(no_members)} 國／"
        f"棄權 {len(abstain_members)} 國｜"
        f"贊成戰力 {yes_weight:,}／總票權 {total_weight:,}｜"
        f"過半門檻 {threshold_weight:,} → "
        f"{'✅ 通過' if passed else '❌ 否決'}。"
    )
    print(
        f"🗳️ [表決明細] {alliance_name}｜"
        + "、".join(
            f"{countries[m].get('display_name', m)}:"
            f"{votes[m]}[票權 {vote_weights.get(m, 0):,}]"
            for m in members
        )
    )

    return {
        "kind": "進攻表決",
        "turn": int(turn_counter),
        "alliance": alliance_name,
        "proposer": proposer_key,
        "target": target_key,
        "target_name": target_name,
        "eligible": len(members),
        # threshold 保留作為相容欄位；V6.4 起代表「戰力票權門檻」。
        "threshold": threshold_weight,
        "threshold_weight": threshold_weight,
        "total_weight": total_weight,
        "yes": len(yes_members),
        "no": len(no_members),
        "abstain": len(abstain_members),
        "yes_weight": yes_weight,
        "no_weight": no_weight,
        "abstain_weight": abstain_weight,
        "vote_weights": vote_weights,
        "passed": bool(passed),
        "result": "通過" if passed else "否決",
        "participants": yes_members if passed else [],
        "votes": votes,
        "reasons": reasons,
    }


def _alliance_member_defense_support(
    member_key,
    defender_key,
    attacker_key,
    countries,
    alliances,
    rl_agents,
    active_wars,
    turn_counter,
):
    """被攻擊國一定自衛；其他盟國自行決定要不要履行共同防禦。"""
    if member_key == defender_key:
        return True, "本國遭攻擊"

    if not _war_country_can_join_new_war(member_key, active_wars):
        return False, "戰線已滿"

    c = countries[member_key]
    score = 0.66

    _, attacker_members = _alliance_vote_target_members(
        attacker_key,
        countries,
        alliances,
    )

    hostility = c.get("hostility", {}) or {}
    hostile_score = max(
        [float(hostility.get(m, 0) or 0) for m in attacker_members]
        or [0.0]
    )
    score += min(0.24, hostile_score / 240.0)

    if set(c.get("recent_attackers", []) or []) & set(attacker_members):
        score += 0.20

    if _event_active(c, "DEFENSE_PACT", turn_counter):
        score += 0.24
    if _event_active(c, "ALLIANCE_SUMMIT", turn_counter):
        score += 0.08
    if _event_active(c, "MEMBER_DISPUTE", turn_counter):
        score -= 0.12

    exhaustion = float(c.get("war_exhaustion", 0) or 0)
    if exhaustion >= 85:
        score -= 0.30
    elif exhaustion >= 65:
        score -= 0.16
    elif exhaustion >= 45:
        score -= 0.06

    if float(c.get("political_stability", 75) or 75) < 25:
        score -= 0.12

    soldiers = max(1, int(c.get("soldiers", 0) or 0))
    if float(c.get("food", 0) or 0) < max(80, soldiers * 1.2):
        score -= 0.10
    if float(c.get("metal", 0) or 0) < max(45, soldiers * 0.55):
        score -= 0.08

    personality = getattr(
        rl_agents.get(member_key),
        "personality_type",
        "OPPORTUNIST",
    )
    if personality == "WARMONGER":
        score += 0.10
    elif personality == "PACIFIST":
        score += 0.02
    else:
        score += 0.05

    mode = str(c.get("world_mode_code", "NORMAL") or "NORMAL")
    if mode == "FRAGMENTED":
        score -= 0.12
    elif mode == "DIPLOMATIC":
        score += 0.10
    elif mode == "TOTAL_WAR":
        score += 0.12
    elif mode == "RECUPERATION":
        score += 0.04
    elif mode == "SCARCITY":
        score -= 0.10

    score += random.uniform(-0.12, 0.12)

    support = score >= 0.50
    return support, ("履行共同防禦" if support else "拒絕增援")


def _alliance_defensive_support_vote(
    alliance_name,
    defender_key,
    attacker_key,
    countries,
    alliances,
    rl_agents,
    active_wars,
    turn_counter,
):
    members = [
        m
        for m in alliances.get(alliance_name, [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    members = list(dict.fromkeys(members))

    if defender_key not in members:
        members.insert(0, defender_key)

    votes = {}
    reasons = {}
    supporters = []

    for member in members:
        support, reason = _alliance_member_defense_support(
            member,
            defender_key,
            attacker_key,
            countries,
            alliances,
            rl_agents,
            active_wars,
            turn_counter,
        )
        votes[member] = "支援" if support else "拒絕"
        reasons[member] = reason
        if support:
            supporters.append(member)

    if defender_key not in supporters:
        supporters.insert(0, defender_key)

    attacker_name = countries[attacker_key].get(
        "display_name",
        attacker_key,
    )
    defender_name = countries[defender_key].get(
        "display_name",
        defender_key,
    )
    refused = max(0, len(members) - len(supporters))

    print(
        f"🛡️ [共同防禦表態] {alliance_name}｜"
        f"【{defender_name}】遭【{attacker_name}】攻擊："
        f"支援 {len(supporters)}／拒絕 {refused}。"
    )
    print(
        f"🛡️ [防禦明細] {alliance_name}｜"
        + "、".join(
            f"{countries[m].get('display_name', m)}:{votes[m]}"
            for m in members
        )
    )

    return {
        "kind": "共同防禦",
        "turn": int(turn_counter),
        "alliance": alliance_name,
        "proposer": defender_key,
        "target": attacker_key,
        "target_name": attacker_name,
        "eligible": len(members),
        "threshold": 1,
        "yes": len(supporters),
        "no": refused,
        "abstain": 0,
        "passed": True,
        "result": f"{len(supporters)} 國支援",
        "participants": supporters,
        "votes": votes,
        "reasons": reasons,
    }


def _finalize_rejected_war_action(
    agent,
    c_data,
    before_data,
    action,
    action_value,
    total_world_power,
    top_power,
    alive_count,
):
    """否決/冷卻仍回饋 RL，避免直接 continue 造成這次決策沒有學習。"""
    enforce_farmer_majority(c_data)
    c_data["power"] = calculate_rts_power(c_data)
    after_data = _rl_snapshot(c_data)

    reward = agent.calculate_reward(
        before_data,
        after_data,
        action,
        False,
        action_value,
        total_world_power,
        top_power,
        alive_count,
    )

    c_data["last_action"] = "聯盟戰爭提案未成"
    c_data["last_reward"] = round(reward, 2)
    c_data["ai_status"] = agent.describe_state(
        after_data,
        total_world_power,
        top_power,
        alive_count,
    )
    agent.learn(
        before_data,
        total_world_power,
        top_power,
        alive_count,
        action,
        reward,
        after_data,
    )


# ====================================================
# 【戰國模式 V4：世界局勢模式】
# ====================================================
WORLD_MODE_MIN_DURATION = 14
WORLD_MODE_MAX_DURATION = 24
WORLD_MODE_PEACE_GAP_MIN = 5
WORLD_MODE_PEACE_GAP_MAX = 9
WORLD_MODE_FIRST_START_MIN = 6
WORLD_MODE_FIRST_START_MAX = 10

WORLD_MODES = {
    "FRAGMENTED": {"name": "群雄割據", "description": "結盟意願降低，更多聯盟成員自行開戰，局部單國戰增加。", "weight": 1.00},
    "DIPLOMATIC": {"name": "合縱連橫", "description": "結盟、退盟、背刺與反霸權聯軍都更活躍。", "weight": 1.00},
    "TOTAL_WAR": {"name": "全面戰國", "description": "宣戰增加、第二戰線更常出現，戰後和平縮短。", "weight": 0.85},
    "RECUPERATION": {"name": "休養生息", "description": "徵兵略降，人口與經濟優先。", "weight": 1.00},
    "HEGEMONIC": {"name": "霸權時代", "description": "前三名互相警戒，其餘國家更願意牽制第一名。", "weight": 0.85},
    "ARMS_RACE": {"name": "軍備競賽", "description": "AI 對排名鄰近國家的兵力差距更敏感。", "weight": 1.00},
    "ECONOMIC_BOOM": {"name": "經濟繁榮", "description": "貿易與人口成長提高，但富裕弱國更像肥羊。", "weight": 1.00},
    "SCARCITY": {"name": "資源緊縮", "description": "糧食與金屬更重要，長期戰爭更難維持。", "weight": 0.90},
}

def _world_mode_normal_state(turn_counter=0):
    return {
        "code": "NORMAL",
        "name": "平常局勢",
        "description": "天下暫無主導性時代局勢。",
        "start_turn": int(turn_counter),
        "expires_turn": int(turn_counter),
        "remaining_turns": 0,
        "previous_code": "",
    }

def _world_mode_pick(previous_code=""):
    codes = [c for c in WORLD_MODES if c != previous_code]
    weights = [float(WORLD_MODES[c].get("weight", 1.0)) for c in codes]
    return random.choices(codes, weights=weights, k=1)[0]

def _world_mode_advance(current_mode, next_mode_turn, turn_counter):
    global world_mode_g, world_mode_code_g
    if not isinstance(current_mode, dict):
        current_mode = _world_mode_normal_state(turn_counter)

    code = str(current_mode.get("code", "NORMAL") or "NORMAL")
    expires = int(current_mode.get("expires_turn", 0) or 0)

    if code != "NORMAL" and turn_counter < expires:
        current_mode["remaining_turns"] = max(0, expires - turn_counter)
        world_mode_code_g = code
        world_mode_g = str(current_mode.get("name", code))
        return current_mode, next_mode_turn, False

    if code != "NORMAL" and turn_counter >= expires:
        previous = code
        old_name = str(current_mode.get("name", code))
        print(f"🌍 [世界局勢結束]「{old_name}」告一段落，天下暫時回歸常態。")
        current_mode = _world_mode_normal_state(turn_counter)
        current_mode["previous_code"] = previous
        next_mode_turn = turn_counter + random.randint(
            WORLD_MODE_PEACE_GAP_MIN,
            WORLD_MODE_PEACE_GAP_MAX,
        )
        world_mode_code_g = "NORMAL"
        world_mode_g = "平常局勢"
        return current_mode, next_mode_turn, True

    if turn_counter < int(next_mode_turn or 0):
        current_mode["remaining_turns"] = max(0, int(next_mode_turn or 0) - turn_counter)
        world_mode_code_g = "NORMAL"
        world_mode_g = "平常局勢"
        return current_mode, next_mode_turn, False

    previous = str(current_mode.get("previous_code", "") or "")
    code = _world_mode_pick(previous)
    info = WORLD_MODES[code]
    duration = random.randint(WORLD_MODE_MIN_DURATION, WORLD_MODE_MAX_DURATION)
    current_mode = {
        "code": code,
        "name": info["name"],
        "description": info["description"],
        "start_turn": int(turn_counter),
        "expires_turn": int(turn_counter + duration),
        "remaining_turns": duration,
        "previous_code": code,
    }
    next_mode_turn = int(turn_counter + duration)
    world_mode_code_g = code
    world_mode_g = info["name"]
    print(
        f"🌍 [世界局勢]「{info['name']}」時代來臨！"
        f"{info['description']} 預計持續 {duration} 回合。"
    )
    return current_mode, next_mode_turn, True

def _reset_world_mode_modifiers(data):
    data.update({
        "world_mode_code": "NORMAL",
        "world_mode_name": "平常局勢",
        "world_mode_remaining": 0,
        "world_war_bias": 1.0,
        "world_alliance_bias": 1.0,
        "world_betray_bias": 1.0,
        "world_coalition_bias": 1.0,
        "world_recruit_mult": 1.0,
        "world_trade_mult": 1.0,
        "world_birth_mult": 1.0,
        "world_food_prod_mult": 1.0,
        "world_wood_prod_mult": 1.0,
        "world_metal_prod_mult": 1.0,
        "world_recruit_cost_mult": 1.0,
        "world_war_upkeep_mult": 1.0,
        "world_fat_sheep_bias": 1.0,
        "world_single_war_chance": 0.0,
    })

def _apply_world_mode_modifiers(countries, current_mode, turn_counter):
    """
    沒有地理地圖，因此「軍備競賽」用排名前後各 2 國作為戰略鄰國。
    """
    if not isinstance(current_mode, dict):
        current_mode = _world_mode_normal_state(turn_counter)

    code = str(current_mode.get("code", "NORMAL") or "NORMAL")
    name = str(current_mode.get("name", "平常局勢") or "平常局勢")
    expires = int(current_mode.get("expires_turn", turn_counter) or turn_counter)
    remaining = max(0, expires - int(turn_counter))

    alive = sorted(
        [k for k, c in countries.items() if c.get("is_alive", True)],
        key=lambda k: countries[k].get("power", 0),
        reverse=True,
    )
    rank_map = {k: i + 1 for i, k in enumerate(alive)}

    for key, data in countries.items():
        _reset_world_mode_modifiers(data)
        data["world_mode_code"] = code
        data["world_mode_name"] = name
        data["world_mode_remaining"] = remaining

        if not data.get("is_alive", True):
            continue

        if code == "FRAGMENTED":
            data["world_war_bias"] = 1.40
            data["world_alliance_bias"] = 0.55
            data["world_betray_bias"] = 1.25
            data["world_coalition_bias"] = 0.82
            data["world_single_war_chance"] = 0.55

        elif code == "DIPLOMATIC":
            data["world_war_bias"] = 1.08
            data["world_alliance_bias"] = 1.65
            data["world_betray_bias"] = 1.60
            data["world_coalition_bias"] = 1.70

        elif code == "TOTAL_WAR":
            data["world_war_bias"] = 1.80
            data["world_alliance_bias"] = 0.90
            data["world_recruit_mult"] = 1.20
            data["world_war_upkeep_mult"] = 1.08

        elif code == "RECUPERATION":
            data["world_war_bias"] = 0.42
            data["world_alliance_bias"] = 1.12
            data["world_recruit_mult"] = 0.78
            data["world_trade_mult"] = 1.25
            data["world_birth_mult"] = 1.28
            data["world_food_prod_mult"] = 1.15
            data["world_wood_prod_mult"] = 1.10
            data["world_metal_prod_mult"] = 1.08

        elif code == "HEGEMONIC":
            rank = rank_map.get(key, 999)
            if rank == 1:
                data["world_war_bias"] = 1.05
                data["world_recruit_mult"] = 1.15
                data["world_alliance_bias"] = 1.15
            elif rank <= 3:
                data["world_war_bias"] = 1.28
                data["world_recruit_mult"] = 1.22
                data["world_coalition_bias"] = 1.55
            else:
                data["world_war_bias"] = 0.92
                data["world_alliance_bias"] = 1.18
                data["world_coalition_bias"] = 1.90

        elif code == "ARMS_RACE":
            data["world_recruit_mult"] = 1.35
            data["world_war_bias"] = 1.08
            idx = rank_map.get(key, 999) - 1
            neighbors = []
            if 0 <= idx < len(alive):
                for off in (-2, -1, 1, 2):
                    j = idx + off
                    if 0 <= j < len(alive):
                        neighbors.append(alive[j])
            if neighbors:
                avg = sum(
                    max(0, int(countries[n].get("soldiers", 0) or 0))
                    for n in neighbors
                ) / len(neighbors)
                mine = max(0, int(data.get("soldiers", 0) or 0))
                if mine < avg * 0.90:
                    data["world_recruit_mult"] *= 1.55
                    data["world_war_bias"] *= 1.08

        elif code == "ECONOMIC_BOOM":
            data["world_war_bias"] = 0.88
            data["world_trade_mult"] = 1.55
            data["world_birth_mult"] = 1.25
            data["world_food_prod_mult"] = 1.12
            data["world_wood_prod_mult"] = 1.15
            data["world_metal_prod_mult"] = 1.12
            data["world_fat_sheep_bias"] = 1.40

        elif code == "SCARCITY":
            data["world_war_bias"] = 0.72
            data["world_trade_mult"] = 1.25
            data["world_birth_mult"] = 0.82
            data["world_food_prod_mult"] = 0.82
            data["world_metal_prod_mult"] = 0.78
            data["world_recruit_cost_mult"] = 1.35
            data["world_war_upkeep_mult"] = 1.35

def _world_mode_current_truce_turns():
    if world_mode_code_g == "TOTAL_WAR":
        return 2
    if world_mode_code_g == "FRAGMENTED":
        return 3
    if world_mode_code_g == "RECUPERATION":
        return 6
    return 4

# ====================================================
# 【亂世演算 V6.3：國家世代、國號世代、政權世系分流】
# ====================================================

def _ensure_dynamic_country_state(country_key, data):
    """為新舊存檔補齊 V3 政治與事件欄位。country_key 永遠是國家本體 ID。"""
    if "political_stability" not in data:
        data["political_stability"] = random.randint(68, 86)
    data.setdefault("war_exhaustion", 0.0)
    data.setdefault("regime_type", "正統政權")
    data.setdefault("regime_history", [])
    data.setdefault("regime_tenure", 0)
    data.setdefault("last_regime_change_turn", -999999)
    data.setdefault("regime_change_count", 0)

    # V6.3 三軌世代：
    # country_generation = 國家歷史總世代（任何正統交接 / 政變 / 亡國重建都 +1）
    # name_generation    = 目前國號的復國世代（只有亡國重建 +1；政變改名歸 1）
    # regime_generation  = 目前政權合法交接世系（合法交接 +1；政變/亡國歸 1）

    generation_model = int(
        data.get("generation_model_version", 0) or 0
    )

    if generation_model < 3:
        had_v6_fields = (
            "country_generation" in data
            and "regime_name_root" in data
        )

        if had_v6_fields:
            # 舊 V6 的 country_generation 只計亡國重建；
            # regime_change_count 則計正統交接與政變。
            # 兩者相加即可還原目前可知的國家總世代。
            legacy_rebirth_generation = max(
                1,
                int(
                    data.get(
                        "country_generation",
                        data.get("gen", 1),
                    )
                    or 1
                ),
            )
            country_generation = (
                legacy_rebirth_generation
                + int(data.get("regime_change_count", 0) or 0)
            )

            # 目前國號的 Roman 必須從最近一次政變後重新計算。
            name_generation = (
                _infer_legacy_name_generation_from_history(data)
            )
        else:
            # V5.x 以前 gen 本身就隨各類政權更替累加，
            # 因此直接沿用為國家總世代。
            country_generation = max(
                1,
                int(data.get("gen", 1) or 1),
            )

            # 舊名稱若有「 國號 II」格式，先讀取；否則由歷史推算。
            parsed_name_generation = _extract_old_roman_generation(
                data.get("display_name", country_key)
            )
            name_generation = (
                parsed_name_generation
                if parsed_name_generation > 0
                else _infer_legacy_name_generation_from_history(data)
            )

        data["country_generation"] = max(
            1,
            int(country_generation or 1),
        )
        data["name_generation"] = max(
            1,
            int(name_generation or 1),
        )

        if "regime_generation" not in data:
            data["regime_generation"] = (
                _infer_regime_generation_from_history(data)
            )

        data["generation_model_version"] = 3

    data["country_generation"] = max(
        1,
        int(
            data.get(
                "country_generation",
                data.get("gen", 1),
            )
            or 1
        ),
    )
    data["gen"] = data["country_generation"]

    data["name_generation"] = max(
        1,
        int(data.get("name_generation", 1) or 1),
    )

    data["regime_generation"] = max(
        1,
        int(data.get("regime_generation", 1) or 1),
    )

    if "regime_name_root" not in data:
        data["regime_name_root"] = (
            _strip_old_roman_generation(
                data.get("display_name", country_key)
            )
            or str(country_key)
        )

    data["regime_name_root"] = str(
        data.get("regime_name_root", country_key)
        or country_key
    ).strip()

    data["display_name"] = _format_regime_display_name(
        data["regime_name_root"],
        data["name_generation"],
        data["regime_generation"],
    )

    data.setdefault("strategic_mode", "正常發展")
    data.setdefault("last_event", "無")
    data.setdefault("active_events", {})
    data.setdefault("event_summary", "無")

    # 每輪重算的修正值也給安全預設值。
    data.setdefault("event_food_prod_mult", 1.0)
    data.setdefault("event_metal_prod_mult", 1.0)
    data.setdefault("event_recruit_cost_mult", 1.0)
    data.setdefault("event_recruit_mult", 1.0)
    data.setdefault("event_trade_mult", 1.0)
    data.setdefault("event_war_bias", 1.0)
    data.setdefault("event_alliance_bias", 1.0)
    data.setdefault("event_reputation_bias", 1.0)
    data.setdefault("event_action_efficiency", 1.0)
    data.setdefault("event_war_target", "")
    data.setdefault("event_coalition_bonus_target", "")
    data.setdefault("world_mode_code", "NORMAL")
    data.setdefault("world_mode_name", "平常局勢")
    data.setdefault("world_mode_remaining", 0)
    data.setdefault("world_war_bias", 1.0)
    data.setdefault("world_alliance_bias", 1.0)
    data.setdefault("world_betray_bias", 1.0)
    data.setdefault("world_coalition_bias", 1.0)
    data.setdefault("world_recruit_mult", 1.0)
    data.setdefault("world_trade_mult", 1.0)
    data.setdefault("world_birth_mult", 1.0)
    data.setdefault("world_food_prod_mult", 1.0)
    data.setdefault("world_wood_prod_mult", 1.0)
    data.setdefault("world_metal_prod_mult", 1.0)
    data.setdefault("world_recruit_cost_mult", 1.0)
    data.setdefault("world_war_upkeep_mult", 1.0)
    data.setdefault("world_fat_sheep_bias", 1.0)
    data.setdefault("world_single_war_chance", 0.0)

    data["political_stability"] = float(
        _clamp(float(data.get("political_stability", 75) or 75), 0.0, 100.0)
    )
    data["war_exhaustion"] = float(
        _clamp(float(data.get("war_exhaustion", 0) or 0), 0.0, 100.0)
    )
    if not isinstance(data.get("active_events"), dict):
        data["active_events"] = {}
    if not isinstance(data.get("regime_history"), list):
        data["regime_history"] = []


def _set_last_event(data, text_value):
    data["last_event"] = str(text_value)[:160]


def _event_active(data, code, turn_counter=None):
    info = (data.get("active_events") or {}).get(code)
    if not isinstance(info, dict):
        return False
    if turn_counter is None:
        return True
    return int(info.get("expires_turn", 0) or 0) > int(turn_counter)


def _add_country_event(data, code, name, turn_counter, duration, target=""):
    active = data.setdefault("active_events", {})
    active[code] = {
        "name": name,
        "expires_turn": int(turn_counter) + max(1, int(duration)),
        "target": target or "",
    }
    _set_last_event(data, name)


def _refresh_country_event_modifiers(data, turn_counter):
    """清除逾期事件，並把仍生效的事件轉成真正會影響 AI / 經濟的倍率。"""
    _ensure_dynamic_country_state("", data)
    active = data.get("active_events", {}) or {}
    active = {
        code: info
        for code, info in active.items()
        if isinstance(info, dict)
        and int(info.get("expires_turn", 0) or 0) > int(turn_counter)
    }
    data["active_events"] = active

    data["event_food_prod_mult"] = 1.0
    data["event_metal_prod_mult"] = 1.0
    data["event_recruit_cost_mult"] = 1.0
    data["event_recruit_mult"] = 1.0
    data["event_trade_mult"] = 1.0
    data["event_war_bias"] = 1.0
    data["event_alliance_bias"] = 1.0
    data["event_reputation_bias"] = 1.0
    data["event_action_efficiency"] = 1.0
    data["event_war_target"] = ""
    data["event_coalition_bonus_target"] = ""

    event_names = []
    for code, info in active.items():
        name = str(info.get("name", code))
        event_names.append(name)
        target = str(info.get("target", "") or "")

        if code == "HARVEST":
            data["event_food_prod_mult"] *= 1.22
        elif code == "TRADE_BOOM":
            data["event_trade_mult"] *= 1.55
        elif code == "METAL_SHORTAGE":
            data["event_metal_prod_mult"] *= 0.72
            data["event_recruit_cost_mult"] *= 1.45
        elif code == "ARMS_RACE":
            data["event_recruit_mult"] *= 1.28
            data["event_war_bias"] *= 1.15
            if target:
                data["event_war_target"] = target
        elif code == "BORDER_DISPUTE":
            data["event_war_bias"] *= 1.18
            if target:
                data["event_war_target"] = target
        elif code == "BORDER_MOBILIZATION":
            data["event_recruit_mult"] *= 1.18
            data["event_war_bias"] *= 1.45
            if target:
                data["event_war_target"] = target
        elif code == "WAR_FATIGUE_WAVE":
            data["event_recruit_mult"] *= 0.82
            data["event_war_bias"] *= 0.45
            data["event_action_efficiency"] *= 0.90
        elif code == "NATIONAL_UNITY":
            data["event_recruit_mult"] *= 1.25
            data["event_war_bias"] *= 1.08
        elif code == "WAR_HERO":
            data["event_recruit_mult"] *= 1.12
            data["event_war_bias"] *= 1.10
        elif code == "ALLIANCE_SUMMIT":
            data["event_alliance_bias"] *= 1.35
        elif code == "DIPLOMATIC_SCANDAL":
            data["event_alliance_bias"] *= 0.68
            data["event_reputation_bias"] *= 1.35
        elif code == "SUCCESSION_CRISIS":
            data["event_action_efficiency"] *= 0.78
            data["event_alliance_bias"] *= 0.82
        elif code == "DEFENSE_PACT":
            data["event_recruit_mult"] *= 1.08
        elif code == "WORLD_SHOCK":
            if target:
                data["event_coalition_bonus_target"] = target

    data["event_summary"] = "、".join(event_names) if event_names else "無"


def _update_political_pressure(data):
    """和平會恢復疲勞與穩定；戰爭、飢荒與高度疲勞會侵蝕政局。"""
    if not data.get("is_alive", True):
        return

    stability = float(data.get("political_stability", 75) or 75)
    exhaustion = float(data.get("war_exhaustion", 0) or 0)
    at_war = bool(data.get("current_wars"))
    famine = int(data.get("famine_streak", 0) or 0)

    if at_war:
        stability -= 0.12
    else:
        exhaustion -= 1.55
        stability += 0.18

    if famine > 0:
        stability -= min(1.2, 0.35 + famine * 0.18)
    if exhaustion >= 70:
        stability -= 0.35
    elif exhaustion <= 20 and famine == 0 and not at_war:
        stability += 0.12

    data["war_exhaustion"] = float(_clamp(exhaustion, 0.0, 100.0))
    data["political_stability"] = float(_clamp(stability, 0.0, 100.0))
    data["regime_tenure"] = int(data.get("regime_tenure", 0) or 0) + 1


def _update_strategic_mode(country_key, data, countries, rank_map, total_world_power):
    """人格是長期傾向；戰略模式是國家依局勢暫時採取的國策。"""
    if not data.get("is_alive", True):
        data["strategic_mode"] = "政權崩潰"
        return

    pop = max(1, int(data.get("pop_total", 1) or 1))
    soldiers = max(0, int(data.get("soldiers", 0) or 0))
    military_ratio = soldiers / pop
    food = max(0, int(data.get("food", 0) or 0))
    food_turns = food / max(1.0, data.get("farmers", 0) + soldiers * 2.0)
    exhaustion = float(data.get("war_exhaustion", 0) or 0)
    hostility = data.get("hostility", {}) or {}
    top_hostility = max([int(v or 0) for v in hostility.values()] or [0])
    at_war = bool(data.get("current_wars"))
    rank = rank_map.get(country_key, 999)
    share = data.get("power", 0) / max(1, total_world_power)

    if food_turns < 2.2 or int(data.get("famine_streak", 0) or 0) > 0:
        mode = "糧荒求生"
    elif exhaustion >= 68:
        mode = "戰後復甦"
    elif at_war and military_ratio < 0.14:
        mode = "全面防禦"
    elif at_war:
        mode = "戰時動員"
    elif top_hostility >= 70 and military_ratio >= 0.18:
        mode = "報復模式"
    elif rank == 1 and share >= 0.10:
        mode = "霸權維持"
    elif rank <= 12 and military_ratio >= 0.26 and food_turns >= 6:
        mode = "擴張模式"
    else:
        mode = "正常發展"

    data["strategic_mode"] = mode


def _same_alliance(a, b, countries):
    aa = countries.get(a, {}).get("current_alliance", "")
    bb = countries.get(b, {}).get("current_alliance", "")
    return bool(aa and bb and aa == bb)


def _pick_rival_pair(alive_sorted, countries, active_wars=None):
    candidates = []
    for i, a in enumerate(alive_sorted):
        for b in alive_sorted[i + 1:]:
            if _same_alliance(a, b, countries):
                continue
            if active_wars and _war_countries_share_war(a, b, active_wars):
                continue
            candidates.append((a, b))
    return random.choice(candidates) if candidates else (None, None)


def _leave_alliance(country_key, countries, alliances, reason="政局變動"):
    ally_name = get_country_alliance(country_key, alliances)
    if not ally_name or ally_name not in alliances:
        return False
    members = [m for m in alliances[ally_name] if m != country_key]
    countries[country_key]["current_alliance"] = ""
    if len(members) >= 2:
        alliances[ally_name] = members
    else:
        alliances.pop(ally_name, None)
        for m in members:
            if m in countries:
                countries[m]["current_alliance"] = ""
    print(
        f"🤝 [退盟]【{countries[country_key].get('display_name', country_key)}】"
        f"因{reason}退出 {ally_name}。"
    )
    return True


def _unique_regime_name(country_key, countries, suffixes):
    """政變產生新的『政權國號根』；復國與合法世系尾碼由 V6 格式器統一附加。"""
    base = str(country_key).strip()
    prefix = base[:2] if len(base) >= 2 else base

    used_roots = {
        str(
            c.get("regime_name_root", "")
            or _strip_old_roman_generation(
                c.get("display_name", k)
            )
        ).strip()
        for k, c in countries.items()
        if k != country_key
    }

    choices = list(suffixes)
    random.shuffle(choices)

    for suffix in choices:
        candidate = f"{prefix}{suffix}"
        if candidate not in used_roots:
            return candidate

    # 極端重名時，用短亂數尾碼區隔，但仍保持原國名前兩字。
    return (
        f"{prefix}{random.choice(choices)}"
        f"{random.randint(2, 99)}"
    )


def _record_regime_history(data, turn_counter, kind, old_name, new_name):
    history = data.setdefault("regime_history", [])
    history.append(
        {
            "turn": int(turn_counter),
            "kind": str(kind),
            "old_name": str(old_name),
            "new_name": str(new_name),
            "generation": int(
                data.get(
                    "country_generation",
                    data.get("gen", 1),
                )
                or 1
            ),
            "country_generation": int(
                data.get(
                    "country_generation",
                    data.get("gen", 1),
                )
                or 1
            ),
            "name_generation": int(
                data.get("name_generation", 1) or 1
            ),
            "regime_generation": int(
                data.get("regime_generation", 1) or 1
            ),
        }
    )
    if len(history) > EVENT_HISTORY_MAX:
        del history[:-EVENT_HISTORY_MAX]


def _apply_regime_change(
    country_key,
    countries,
    alliances,
    rl_agents,
    turn_counter,
    kind,
    active_wars=None,
):
    data = countries[country_key]
    if not data.get("is_alive", True):
        return False

    _ensure_dynamic_country_state(country_key, data)

    old_name = str(data.get("display_name", country_key))
    country_generation = max(
        1,
        int(
            data.get(
                "country_generation",
                data.get("gen", 1),
            )
            or 1
        ),
    )

    # V6.3：國家總世代會隨正統交接、政變、亡國重建持續累加。
    data["country_generation"] = country_generation
    data["gen"] = country_generation
    data["regime_tenure"] = 0
    data["last_regime_change_turn"] = int(turn_counter)
    data["regime_change_count"] = int(
        data.get("regime_change_count", 0) or 0
    ) + 1

    agent = rl_agents.get(country_key)

    if kind == "SUCCESSION":
        # 正統 / 合法交接：
        # 國家總世代 +1；國號 Roman 維持；政權世系 +1。
        succession_kind = (
            "正統交接"
            if (data.get("regime_type", "正統政權") or "正統政權") == "正統政權"
            else "合法交接"
        )
        _chronicle_close_current(
            country_key,
            data,
            turn_counter,
            succession_kind,
        )

        country_generation += 1
        data["country_generation"] = country_generation
        data["gen"] = country_generation

        data["regime_generation"] = max(
            1,
            int(data.get("regime_generation", 1) or 1),
        ) + 1

        name_generation = max(
            1,
            int(data.get("name_generation", 1) or 1),
        )

        root = str(
            data.get("regime_name_root", country_key)
            or country_key
        ).strip()

        new_name = _format_regime_display_name(
            root,
            name_generation,
            data["regime_generation"],
        )
        data["display_name"] = new_name

        data["political_stability"] = _clamp(
            float(data.get("political_stability", 70) or 70) + 8,
            0,
            100,
        )
        data["war_exhaustion"] = _clamp(
            float(data.get("war_exhaustion", 0) or 0) - 4,
            0,
            100,
        )

        data["regime_type"] = (
            data.get("regime_type", "正統政權")
            or "正統政權"
        )

        lineage_text = (
            f"{_to_chinese_number(data['regime_generation'])}世"
        )
        event_text = (
            f"{succession_kind}：{old_name} → {new_name}；"
            f"目前政權進入{lineage_text}"
        )
        _set_last_event(data, event_text)
        _record_regime_history(
            data,
            turn_counter,
            succession_kind,
            old_name,
            new_name,
        )
        _chronicle_start_current(
            country_key,
            data,
            turn_counter,
        )
        print(
            f"👑 [{succession_kind}]【{old_name}】完成合法交接 → "
            f"【{new_name}】；國家總世代進入第 {country_generation} 代，"
            f"目前政權為{_to_chinese_number(data['regime_generation'])}世。"
        )
        return True

    if kind == "MILITARY":
        new_name = _unique_regime_name(
            country_key,
            countries,
            ["軍政府", "統制國", "武衛國", "護國府"],
        )
        data["regime_type"] = "軍事政權"
        data["political_stability"] = 36.0
        data["military_target_ratio"] = float(
            _clamp(float(data.get("military_target_ratio", 0.30)) + 0.08, 0.18, 0.50)
        )
        data["infamy"] = int(data.get("infamy", 0) or 0) + 10
        if agent:
            agent.personality_type = "WARMONGER"
            agent.personality = PERSONALITIES["WARMONGER"]
        leave_chance = 0.22
        kind_name = "軍事政變"

    elif kind == "REVOLUTION":
        new_name = _unique_regime_name(
            country_key,
            countries,
            ["共和國", "聯邦", "新政國", "公民國"],
        )
        data["regime_type"] = "革命政權"
        data["political_stability"] = 41.0
        data["infamy"] = max(0, int(data.get("infamy", 0) or 0) - 12)
        data["military_target_ratio"] = float(
            _clamp(float(data.get("military_target_ratio", 0.30)), 0.22, 0.38)
        )
        if agent:
            new_p = random.choice(["PACIFIST", "OPPORTUNIST"])
            agent.personality_type = new_p
            agent.personality = PERSONALITIES[new_p]
        leave_chance = 0.55
        kind_name = "民變革命"

    else:  # PALACE
        new_name = _unique_regime_name(
            country_key,
            countries,
            ["王朝", "新朝", "攝政府", "皇朝"],
        )
        data["regime_type"] = "宮廷政權"
        data["political_stability"] = 46.0
        data["infamy"] = int(data.get("infamy", 0) or 0) + 3
        if agent:
            new_p = random.choice(list(PERSONALITIES.keys()))
            agent.personality_type = new_p
            agent.personality = PERSONALITIES[new_p]
        leave_chance = 0.12
        kind_name = "宮廷政變"

    # 政變：
    # 國家總世代 +1，但改成全新國號，因此 Roman 從 I 重新計算；
    # 新政權合法世系也重新由一世起算。
    _chronicle_close_current(
        country_key,
        data,
        turn_counter,
        kind_name,
    )

    country_generation += 1
    data["country_generation"] = country_generation
    data["gen"] = country_generation

    data["regime_name_root"] = new_name
    data["name_generation"] = 1
    data["regime_generation"] = 1

    new_name = _format_regime_display_name(
        data["regime_name_root"],
        1,
        1,
    )
    data["display_name"] = new_name

    # 若政變發生在單國戰爭期間，戰報中的陣營名稱同步更新；
    # 聯盟名稱本身則維持聯盟名，不受單一成員政變影響。
    if active_wars:
        for war in active_wars.values():
            if not isinstance(war, dict):
                continue
            if (
                war.get("attacker_anchor") == country_key
                and war.get("attacker_name") == old_name
            ):
                war["attacker_name"] = new_name
            if (
                war.get("defender_anchor") == country_key
                and war.get("defender_name") == old_name
            ):
                war["defender_name"] = new_name

    data["war_exhaustion"] = float(
        _clamp(float(data.get("war_exhaustion", 0) or 0) - 5, 0, 100)
    )

    if random.random() < leave_chance:
        _leave_alliance(country_key, countries, alliances, reason=kind_name)

    event_text = f"{kind_name}：{old_name} → {new_name}"
    _set_last_event(data, event_text)
    _record_regime_history(data, turn_counter, kind_name, old_name, new_name)
    _chronicle_start_current(
        country_key,
        data,
        turn_counter,
    )
    print(
        f"⚠️ [{kind_name}]【{old_name}】政權更替 → 【{new_name}】；"
        f"國家總世代進入第 {country_generation} 代，"
        f"新國號 Roman 與新政權世系均由一世重新起算。"
    )
    return True


def _coup_probability(data, turn_counter):
    if int(turn_counter) - int(data.get("last_regime_change_turn", -999999) or -999999) < REGIME_CHANGE_COOLDOWN_TURNS:
        return 0.0

    stability = float(data.get("political_stability", 75) or 75)
    exhaustion = float(data.get("war_exhaustion", 0) or 0)

    if stability >= 65:
        chance = 0.000002
    elif stability >= 45:
        chance = 0.000015
    elif stability >= 30:
        chance = 0.000080
    elif stability >= 15:
        chance = 0.000350
    else:
        chance = 0.001300

    if exhaustion >= 80:
        chance += 0.00035
    if int(data.get("famine_streak", 0) or 0) >= 2:
        chance += 0.00045
    if _event_active(data, "SUCCESSION_CRISIS", turn_counter):
        chance *= 2.2

    return float(min(0.0045, chance))


def _maybe_trigger_regime_change(
    countries, alliances, rl_agents, turn_counter, alive_sorted, active_wars=None
):
    """每輪最多一國政權更替，避免 100 國同時洗版。"""
    shuffled = list(alive_sorted)
    random.shuffle(shuffled)

    # 先判政變：真正危機國家風險才高。
    for key in shuffled:
        data = countries[key]
        if random.random() >= _coup_probability(data, turn_counter):
            continue

        pop = max(1, int(data.get("pop_total", 1) or 1))
        military_ratio = int(data.get("soldiers", 0) or 0) / pop
        stability = float(data.get("political_stability", 75) or 75)
        famine = int(data.get("famine_streak", 0) or 0)

        if military_ratio >= 0.36 and random.random() < 0.62:
            kind = "MILITARY"
        elif (stability < 18 or famine >= 2) and random.random() < 0.62:
            kind = "REVOLUTION"
        else:
            kind = "PALACE"

        return _apply_regime_change(
            key, countries, alliances, rl_agents, turn_counter, kind, active_wars
        )

    # 沒政變才判正統繼承；要先累積足夠在位時間。
    for key in shuffled:
        data = countries[key]
        if int(data.get("regime_tenure", 0) or 0) < SUCCESSION_MIN_TENURE:
            continue
        if int(turn_counter) - int(data.get("last_regime_change_turn", -999999) or -999999) < REGIME_CHANGE_COOLDOWN_TURNS:
            continue
        if random.random() < SUCCESSION_CHANCE_PER_COUNTRY:
            return _apply_regime_change(
                key, countries, alliances, rl_agents, turn_counter, "SUCCESSION", active_wars
            )

    return False


def _dynamic_event_pair_name(a, b, countries):
    return (
        countries[a].get("display_name", a),
        countries[b].get("display_name", b),
    )


def _trigger_dynamic_event(
    countries,
    alliances,
    active_wars,
    rl_agents,
    turn_counter,
    alive_sorted,
    total_world_power,
):
    """全世界每輪至多觸發一個動態事件；事件會真的改變 AI / 經濟，而非只有 LOG。"""
    result = {"coalition_target": None, "triggered": False}
    if len(alive_sorted) < 2 or random.random() >= DYNAMIC_EVENT_CHANCE:
        return result

    # 某些事件需要特定條件；抽不到條件時最多重試 5 次。
    event_codes = [
        "BORDER_DISPUTE",
        "ALLIANCE_SUMMIT",
        "DIPLOMATIC_SCANDAL",
        "ARMS_RACE",
        "BORDER_MOBILIZATION",
        "WAR_FATIGUE_WAVE",
        "TRADE_BOOM",
        "METAL_SHORTAGE",
        "HARVEST",
        "SUCCESSION_CRISIS",
        "NATIONAL_UNITY",
        "MEMBER_DISPUTE",
        "DEFENSE_PACT",
        "WORLD_SHOCK",
    ]
    weights = [12, 7, 8, 9, 8, 7, 8, 7, 9, 5, 8, 6, 7, 7]

    for _attempt in range(5):
        code = random.choices(event_codes, weights=weights, k=1)[0]

        if code == "BORDER_DISPUTE":
            a, b = _pick_rival_pair(alive_sorted, countries, active_wars)
            if not a:
                continue
            an, bn = _dynamic_event_pair_name(a, b, countries)
            _war_add_hostility(countries, a, b, 12)
            _war_add_hostility(countries, b, a, 12)
            countries[a]["political_stability"] = _clamp(countries[a].get("political_stability", 75) - 2, 0, 100)
            countries[b]["political_stability"] = _clamp(countries[b].get("political_stability", 75) - 2, 0, 100)
            _add_country_event(countries[a], code, f"邊境爭議：{bn}", turn_counter, EVENT_DURATION_NORMAL, b)
            _add_country_event(countries[b], code, f"邊境爭議：{an}", turn_counter, EVENT_DURATION_NORMAL, a)
            print(f"🗺️ [邊境爭議]【{an}】與【{bn}】爆發領土爭議，雙方仇恨升高。")

        elif code == "ALLIANCE_SUMMIT":
            eligible = [(n, [m for m in ms if countries.get(m, {}).get("is_alive", True)]) for n, ms in alliances.items()]
            eligible = [(n, ms) for n, ms in eligible if len(ms) >= 2]
            if not eligible:
                continue
            ally_name, members = random.choice(eligible)
            for m in members:
                c = countries[m]
                c["political_stability"] = _clamp(c.get("political_stability", 75) + 4, 0, 100)
                c["infamy"] = max(0, int(c.get("infamy", 0) or 0) - 2)
                _add_country_event(c, code, f"聯盟峰會：{ally_name}", turn_counter, EVENT_DURATION_NORMAL)
            print(f"🤝 [聯盟峰會] {ally_name} 召開高峰會，成員凝聚力與政治穩定提升。")

        elif code == "DIPLOMATIC_SCANDAL":
            k = random.choice(alive_sorted)
            c = countries[k]
            infamy_gain = random.randint(10, 22)
            c["infamy"] = int(c.get("infamy", 0) or 0) + infamy_gain
            c["political_stability"] = _clamp(c.get("political_stability", 75) - random.randint(4, 8), 0, 100)
            _add_country_event(c, code, "外交醜聞", turn_counter, 7)
            print(f"📰 [外交醜聞]【{c['display_name']}】爆出外交醜聞，惡名 +{infamy_gain}、政局受損。")

        elif code == "ARMS_RACE":
            pool = alive_sorted[:min(24, len(alive_sorted))]
            a, b = _pick_rival_pair(pool, countries, active_wars)
            if not a:
                continue
            an, bn = _dynamic_event_pair_name(a, b, countries)
            for x, target in ((a, b), (b, a)):
                c = countries[x]
                c["military_target_ratio"] = float(_clamp(c.get("military_target_ratio", 0.30) + 0.04, 0.15, 0.50))
                _war_add_hostility(countries, x, target, 5)
                _add_country_event(c, code, f"軍備競賽：{countries[target]['display_name']}", turn_counter, EVENT_DURATION_LONG, target)
            print(f"🪖 [軍備競賽]【{an}】與【{bn}】互相擴軍，短期徵兵效率提高。")

        elif code == "BORDER_MOBILIZATION":
            pair = None
            for a in alive_sorted:
                info = (countries[a].get("active_events") or {}).get("BORDER_DISPUTE")
                if isinstance(info, dict):
                    b = info.get("target")
                    if b in countries and countries[b].get("is_alive", True):
                        pair = (a, b)
                        break
            if pair is None:
                pair = _pick_rival_pair(alive_sorted, countries, active_wars)
            a, b = pair
            if not a or not b:
                continue
            an, bn = _dynamic_event_pair_name(a, b, countries)
            for x, target in ((a, b), (b, a)):
                c = countries[x]
                c["military_target_ratio"] = float(_clamp(c.get("military_target_ratio", 0.30) + 0.03, 0.15, 0.50))
                _war_add_hostility(countries, x, target, 8)
                _add_country_event(c, code, f"邊境集結：{countries[target]['display_name']}", turn_counter, 6, target)
            print(f"⚔️ [邊境集結]【{an}】與【{bn}】在邊境集結重兵，短期宣戰風險大增。")

        elif code == "WAR_FATIGUE_WAVE":
            eligible = [k for k in alive_sorted if float(countries[k].get("war_exhaustion", 0) or 0) >= 55]
            if not eligible:
                continue
            k = max(eligible, key=lambda x: countries[x].get("war_exhaustion", 0))
            c = countries[k]
            c["political_stability"] = _clamp(c.get("political_stability", 75) - 5, 0, 100)
            c["military_target_ratio"] = float(_clamp(c.get("military_target_ratio", 0.30) - 0.03, 0.15, 0.50))
            _add_country_event(c, code, "戰爭疲勞浪潮", turn_counter, EVENT_DURATION_NORMAL)
            print(f"😮‍💨 [戰爭疲勞]【{c['display_name']}】厭戰情緒升高，主動開戰與徵兵意願暫時下降。")

        elif code == "TRADE_BOOM":
            k = random.choice(alive_sorted)
            c = countries[k]
            pop = max(1, int(c.get("pop_total", 1) or 1))
            c["food"] += min(300, max(20, int(pop * 0.20)))
            c["wood"] += min(180, max(10, int(pop * 0.10)))
            _add_country_event(c, code, "商路繁榮", turn_counter, EVENT_DURATION_NORMAL)
            print(f"🧭 [商路繁榮]【{c['display_name']}】商路暢通，市場交易收益暫時提高。")

        elif code == "METAL_SHORTAGE":
            k = random.choice(alive_sorted)
            c = countries[k]
            _add_country_event(c, code, "金屬短缺", turn_counter, EVENT_DURATION_NORMAL)
            print(f"⛏️ [金屬短缺]【{c['display_name']}】礦產供應緊縮，短期徵兵裝備成本提高。")

        elif code == "HARVEST":
            k = random.choice(alive_sorted)
            c = countries[k]
            pop = max(1, int(c.get("pop_total", 1) or 1))
            gain = min(800, max(40, int(pop * random.uniform(0.45, 0.75))))
            c["food"] += gain
            _add_country_event(c, code, "豐收", turn_counter, EVENT_DURATION_SHORT)
            print(f"🌾 [豐收]【{c['display_name']}】本季豐收，糧食 +{gain}，農業產出短期提高。")

        elif code == "SUCCESSION_CRISIS":
            eligible = [k for k in alive_sorted if int(countries[k].get("regime_tenure", 0) or 0) >= 60]
            if not eligible:
                continue
            k = random.choice(eligible)
            c = countries[k]
            c["political_stability"] = _clamp(c.get("political_stability", 75) - 15, 0, 100)
            _add_country_event(c, code, "王位危機", turn_counter, EVENT_DURATION_NORMAL)
            print(f"👑 [王位危機]【{c['display_name']}】繼承秩序出現爭議，政治穩定大幅下降。")

        elif code == "NATIONAL_UNITY":
            eligible = [k for k in alive_sorted if countries[k].get("current_wars") or countries[k].get("recent_attackers")]
            if not eligible:
                continue
            k = random.choice(eligible)
            c = countries[k]
            c["political_stability"] = _clamp(c.get("political_stability", 75) + 10, 0, 100)
            c["war_exhaustion"] = _clamp(c.get("war_exhaustion", 0) - 10, 0, 100)
            c["fortification"] = int(_clamp(c.get("fortification", 0) + 4, 0, 100))
            _add_country_event(c, code, "民族團結", turn_counter, EVENT_DURATION_NORMAL)
            print(f"🛡️ [民族團結]【{c['display_name']}】外敵壓力凝聚民心，防禦與動員能力暫時提高。")

        elif code == "MEMBER_DISPUTE":
            eligible = [(n, [m for m in ms if countries.get(m, {}).get("is_alive", True)]) for n, ms in alliances.items()]
            eligible = [(n, ms) for n, ms in eligible if len(ms) >= 2]
            if not eligible:
                continue
            ally_name, members = random.choice(eligible)
            member = min(members, key=lambda m: countries[m].get("political_stability", 75))
            for m in members:
                countries[m]["political_stability"] = _clamp(countries[m].get("political_stability", 75) - 3, 0, 100)
            leave = len(members) >= 3 and (
                countries[member].get("political_stability", 75) < 35 or random.random() < 0.28
            )
            if leave:
                _leave_alliance(member, countries, alliances, reason="聯盟成員爭執")
                print(f"💢 [聯盟爭執] {ally_name} 爆發內鬥，【{countries[member]['display_name']}】選擇退盟。")
            else:
                for m in members:
                    _add_country_event(countries[m], code, f"聯盟爭執：{ally_name}", turn_counter, EVENT_DURATION_SHORT)
                print(f"💢 [聯盟爭執] {ally_name} 成員公開爭執，暫時削弱聯盟凝聚力。")

        elif code == "DEFENSE_PACT":
            eligible = [(n, [m for m in ms if countries.get(m, {}).get("is_alive", True)]) for n, ms in alliances.items()]
            eligible = [(n, ms) for n, ms in eligible if len(ms) >= 2]
            if not eligible:
                continue
            ally_name, members = random.choice(eligible)
            for m in members:
                c = countries[m]
                c["political_stability"] = _clamp(c.get("political_stability", 75) + 3, 0, 100)
                c["fortification"] = int(_clamp(c.get("fortification", 0) + 5, 0, 100))
                _add_country_event(c, code, f"共同防禦協議：{ally_name}", turn_counter, EVENT_DURATION_LONG)
            print(f"🛡️ [共同防禦協議] {ally_name} 強化共同防禦，成員城防與凝聚力提升。")

        elif code == "WORLD_SHOCK":
            if len(alive_sorted) < 3 or total_world_power <= 0:
                continue
            top = alive_sorted[0]
            second = alive_sorted[1]
            top_power = max(0, countries[top].get("power", 0))
            second_power = max(1, countries[second].get("power", 0))
            share = top_power / max(1, total_world_power)
            lead = top_power / second_power
            if share < 0.08 and lead < 1.25:
                continue
            for k in alive_sorted[1:]:
                _add_country_event(
                    countries[k], code,
                    f"天下震動：警戒{countries[top]['display_name']}",
                    turn_counter, EVENT_DURATION_NORMAL, top,
                )
            result["coalition_target"] = top
            print(
                f"🌏 [天下震動] 第一名【{countries[top]['display_name']}】快速坐大，"
                f"各國對其警戒與圍剿意願暫時提高。"
            )

        else:
            continue

        result["triggered"] = True
        return result

    return result


def _maybe_trigger_war_hero(winner_members, countries, turn_counter):
    living = [m for m in winner_members if m in countries and countries[m].get("is_alive", True)]
    if not living or random.random() >= 0.14:
        return
    hero_country = max(living, key=lambda m: countries[m].get("power", 0))
    c = countries[hero_country]
    c["political_stability"] = _clamp(c.get("political_stability", 75) + 8, 0, 100)
    c["war_exhaustion"] = _clamp(c.get("war_exhaustion", 0) - 7, 0, 100)
    c["military_target_ratio"] = float(_clamp(c.get("military_target_ratio", 0.30) + 0.02, 0.15, 0.50))
    _add_country_event(c, "WAR_HERO", "戰爭英雄", turn_counter, EVENT_DURATION_NORMAL)
    print(f"🎖️ [戰爭英雄]【{c['display_name']}】戰場英雄受到崇敬，軍心與政治穩定提升。")


# ====================================================
# 【世紀帝國風 RTS 國家輔助系統】(含詳細 LOG 輸出)
# ====================================================
import math
import random


def update_rts_economy_and_jobs(data):
    """平衡版 RTS 經濟：人口、農民產出、住房、徵兵、維持費與飢荒。"""
    if not data.get("is_alive", True):
        return

    c_name = data.get("display_name", "未命名國家")
    enforce_farmer_majority(data)

    houses = max(1, int(data.get("houses", 15) or 15))
    pop_total = max(1, int(data.get("pop_total", 10) or 10))
    pop_at_turn_start = pop_total
    data.setdefault("famine_streak", 0)
    data.setdefault("last_population_change_reason", "")
    food = float(data.get("food", 300) or 0)
    wood = float(data.get("wood", 200) or 0)
    metal = float(data.get("metal", 100) or 0)
    soldiers = min(max(0, int(data.get("soldiers", 0) or 0)), pop_total // 2)
    farmers = pop_total - soldiers

    # ---------------------------------------------------------
    # 🏠 1. 住房：接近 88% 容量時才擴建
    # ---------------------------------------------------------
    house_wood_cost = BALANCE["HOUSE_WOOD_COST"]
    pop_max = houses * 10

    # 舊存檔或長期和平可能累積過量房屋。
    # 容量若超過人口 30%，每輪僅讓少量閒置房屋荒廢，
    # 讓攻城摧毀房屋重新具有戰略意義，但不會一口氣砍掉大量建築。
    excess_capacity_limit = int(
        math.ceil(
            pop_total
            * BALANCE["HOUSE_EXCESS_CAPACITY_RATIO"]
            / 10.0
        )
    )
    if houses > max(1, excess_capacity_limit):
        excess_houses = houses - max(1, excess_capacity_limit)
        abandon_count = min(
            excess_houses,
            BALANCE["HOUSE_ABANDON_MAX_PER_TURN"],
            max(1, int(houses * 0.015)),
        )
        houses = max(1, houses - abandon_count)
        pop_max = houses * 10

    if (
        wood >= house_wood_cost
        and pop_total >= int(pop_max * BALANCE["HOUSE_BUILD_THRESHOLD"])
    ):
        affordable_houses = int(wood // house_wood_cost)
        build_cap = 1 if pop_total < 500 else 2
        build_count = min(affordable_houses, build_cap)
        if build_count > 0:
            houses += build_count
            wood -= build_count * house_wood_cost
            pop_max = houses * 10

    # ---------------------------------------------------------
    # 🍼 2. 人口：只有至少 6 輪安全糧時才自然成長
    # ---------------------------------------------------------
    pre_growth_consumption = (
        farmers * BALANCE["FARMER_FOOD_UPKEEP"]
        + soldiers * BALANCE["SOLDIER_FOOD_UPKEEP"]
    )
    reserve_turns = food / max(1.0, pre_growth_consumption)

    food_cost_per_birth = BALANCE["FOOD_COST_PER_BIRTH"]
    if (
        pop_total < pop_max
        and food >= food_cost_per_birth
        and reserve_turns >= BALANCE["BIRTH_MIN_RESERVE_TURNS"]
    ):
        world_birth_mult = float(data.get("world_birth_mult", 1.0) or 1.0)
        growth_target = int(
            pop_total
            * random.uniform(BALANCE["BIRTH_RATE_MIN"], BALANCE["BIRTH_RATE_MAX"])
            * world_birth_mult
        )
        growth_target = max(
            1,
            min(
                max(1, int(BALANCE["BIRTH_MAX_PER_TURN"] * world_birth_mult)),
                growth_target,
            ),
        )
        growth = min(
            pop_max - pop_total,
            int(food // food_cost_per_birth),
            growth_target,
        )
        if growth > 0:
            pop_total += growth
            farmers += growth
            food -= growth * food_cost_per_birth

    # ---------------------------------------------------------
    # 🌾 3. 勞工配置：依糧食安全動態調整
    # ---------------------------------------------------------
    estimated_consumption = (
        farmers * BALANCE["FARMER_FOOD_UPKEEP"]
        + soldiers * BALANCE["SOLDIER_FOOD_UPKEEP"]
    )
    food_turns = food / max(1.0, estimated_consumption)
    is_famine_warning = food_turns < BALANCE["FAMINE_WARNING_TURNS"]

    if is_famine_warning:
        # 糧荒時「戰略目標」暫時限制到 15%，但不永久覆寫 military_target_ratio。
        # 退伍採漸進式，避免 45% 軍備一輪直接掉到 15% 而損失數百戰力人口。
        emergency_target = int(pop_total * 0.15)
        if soldiers > emergency_target:
            excess = soldiers - emergency_target
            demob_cap = min(
                BALANCE["EMERGENCY_DEMOB_MAX_COUNT"],
                max(1, int(math.ceil(pop_total * BALANCE["EMERGENCY_DEMOB_MAX_RATIO"]))),
            )
            demoted_soldiers = min(excess, demob_cap)
            soldiers -= demoted_soldiers
            farmers += demoted_soldiers
            print(
                f"🪖 [糧荒縮編]【{c_name}】糧食不足，本輪僅讓 {demoted_soldiers} 名士兵退伍轉農；"
                f"總人口維持 {pop_total}，現役士兵 {soldiers}。"
            )
        food_share, wood_share, metal_share = 0.80, 0.10, 0.10
    elif food_turns < BALANCE["LOW_FOOD_TURNS"]:
        food_share, wood_share, metal_share = 0.65, 0.20, 0.15
    elif food_turns > BALANCE["SURPLUS_FOOD_TURNS"]:
        food_share, wood_share, metal_share = 0.40, 0.35, 0.25
    else:
        food_share, wood_share, metal_share = 0.50, 0.30, 0.20

    f_food = int(farmers * food_share)
    f_wood = int(farmers * wood_share)
    f_metal = max(0, farmers - f_food - f_wood)

    # 庫存高於戰略需求時採集效率下降，避免長局資源無限膨脹。
    current_consumption = max(
        1.0,
        farmers * BALANCE["FARMER_FOOD_UPKEEP"]
        + soldiers * BALANCE["SOLDIER_FOOD_UPKEEP"],
    )
    food_factor = (
        BALANCE["SURPLUS_FOOD_PRODUCTION_FACTOR"]
        if food > current_consumption * BALANCE["SURPLUS_FOOD_TURNS"]
        else 1.0
    )
    wood_factor = (
        BALANCE["SURPLUS_PRODUCTION_FACTOR"]
        if wood > pop_total * BALANCE["WOOD_RESERVE_PER_POP"]
        else 1.0
    )
    metal_reserve_target = (
        pop_total * BALANCE["METAL_RESERVE_PER_POP"]
        + soldiers * BALANCE["METAL_RESERVE_PER_SOLDIER"]
    )
    metal_factor = (
        BALANCE["SURPLUS_PRODUCTION_FACTOR"]
        if metal > metal_reserve_target
        else 1.0
    )

    event_efficiency = float(data.get("event_action_efficiency", 1.0) or 1.0)
    food += (
        f_food
        * BALANCE["FOOD_PER_WORKER"]
        * food_factor
        * float(data.get("event_food_prod_mult", 1.0) or 1.0)
        * float(data.get("world_food_prod_mult", 1.0) or 1.0)
        * event_efficiency
    )
    wood += (
        f_wood
        * BALANCE["WOOD_PER_WORKER"]
        * wood_factor
        * float(data.get("world_wood_prod_mult", 1.0) or 1.0)
        * event_efficiency
    )
    metal += (
        f_metal
        * BALANCE["METAL_PER_WORKER"]
        * metal_factor
        * float(data.get("event_metal_prod_mult", 1.0) or 1.0)
        * float(data.get("world_metal_prod_mult", 1.0) or 1.0)
        * event_efficiency
    )

    # ---------------------------------------------------------
    # ⚔️ 4. 徵兵：同時需要糧草與金屬
    # ---------------------------------------------------------
    military_target_ratio = float(data.get("military_target_ratio", 0.30) or 0.30)
    military_target_ratio = _clamp(military_target_ratio, 0.10, 0.50)

    post_prod_consumption = max(
        1.0,
        farmers * BALANCE["FARMER_FOOD_UPKEEP"]
        + soldiers * BALANCE["SOLDIER_FOOD_UPKEEP"],
    )
    post_prod_food_turns = food / post_prod_consumption

    # effective_ratio 是「本輪」安全軍備上限；military_target_ratio 保留 AI 的長期政策。
    effective_ratio = military_target_ratio
    if is_famine_warning:
        effective_ratio = min(effective_ratio, 0.15)
        print(
            f"🛑 [徵兵暫停]【{c_name}】處於糧食危機，本輪停止新增徵兵；"
            f"長期軍備目標仍保留 {military_target_ratio:.0%}。"
        )
    elif post_prod_food_turns < 5.0:
        effective_ratio = min(effective_ratio, 0.20)

    desired_soldiers = min(int(pop_total * effective_ratio), pop_total // 2)

    # 糧荒時上面已做過一次「限額漸進縮編」，這裡不再重複退伍。
    if soldiers > desired_soldiers and not is_famine_warning:
        excess = soldiers - desired_soldiers
        demobilize_count = min(excess, random.randint(4, 10))
        if demobilize_count > 0:
            soldiers -= demobilize_count
            farmers += demobilize_count

    elif soldiers < desired_soldiers and not is_famine_warning:
        needed = desired_soldiers - soldiers
        metal_cost = max(
            1,
            int(
                math.ceil(
                    BALANCE["RECRUIT_METAL_COST"]
                    * float(data.get("event_recruit_cost_mult", 1.0) or 1.0)
                    * float(data.get("world_recruit_cost_mult", 1.0) or 1.0)
                )
            ),
        )
        food_cost = BALANCE["RECRUIT_FOOD_COST"]
        affordable = min(
            int(metal // metal_cost),
            int(food // food_cost),
        )
        max_train_without_breaking_rule = max(0, (farmers - soldiers) // 2)
        dynamic_recruit_cap = min(
            int(
                BALANCE["RECRUIT_DYNAMIC_MAX"]
                * float(data.get("event_recruit_mult", 1.0) or 1.0)
                * float(data.get("world_recruit_mult", 1.0) or 1.0)
            ),
            max(
                BALANCE["RECRUIT_BATCH_MAX"],
                int(
                    pop_total
                    * BALANCE["RECRUIT_DYNAMIC_POP_RATIO"]
                    * float(data.get("event_recruit_mult", 1.0) or 1.0)
                    * float(data.get("world_recruit_mult", 1.0) or 1.0)
                ),
            ),
        )
        recruit_roll = random.randint(
            BALANCE["RECRUIT_BATCH_MIN"],
            max(
                BALANCE["RECRUIT_BATCH_MIN"],
                dynamic_recruit_cap,
            ),
        )

        train_count = min(
            needed,
            affordable,
            max_train_without_breaking_rule,
            recruit_roll,
        )
        if train_count > 0:
            soldiers += train_count
            farmers -= train_count
            metal -= train_count * metal_cost
            food -= train_count * food_cost

    # ---------------------------------------------------------
    # 🍞 5. 每輪維持費
    # ---------------------------------------------------------
    base_food_consumed = (
        farmers * BALANCE["FARMER_FOOD_UPKEEP"]
        + soldiers * BALANCE["SOLDIER_FOOD_UPKEEP"]
    )
    overcrowded_pop = max(0, pop_total - pop_max)
    food -= (
        base_food_consumed
        + overcrowded_pop * BALANCE["OVERCROWD_FOOD_PENALTY"]
    )

    metal_maintenance = int(math.ceil(soldiers * BALANCE["SOLDIER_METAL_UPKEEP"]))
    if metal >= metal_maintenance:
        metal -= metal_maintenance
    else:
        # 金屬短缺只造成「漸進退伍」，不允許一輪把養不起的全部士兵瞬間解編。
        shortage = max(0, metal_maintenance - metal)
        metal = 0

        if soldiers > 0 and shortage > 0:
            demob_cap = min(
                BALANCE["METAL_SHORTAGE_DEMOB_MAX_COUNT"],
                max(1, int(math.ceil(pop_total * BALANCE["METAL_SHORTAGE_DEMOB_MAX_RATIO"]))),
            )
            # 缺口越大，越接近本輪上限，但永遠不超過 demob_cap。
            upkeep = max(0.01, BALANCE["SOLDIER_METAL_UPKEEP"])
            shortage_based = max(1, int(math.ceil(shortage / upkeep)))
            demoted = min(soldiers, demob_cap, shortage_based)
            soldiers -= demoted
            farmers += demoted
            print(
                f"🔧 [軍備短缺]【{c_name}】金屬不足，本輪 {demoted} 名士兵退伍轉農；"
                f"總人口維持 {pop_total}，避免軍力瞬間崩盤。"
            )

    # 飢荒採「配給 -> 漸進死亡」兩階段。
    # 第一次出現赤字只記錄配給危機，不立即一次死幾百人；
    # 持續欠糧才會死人，而且每輪死亡有 1.5% / 40 人雙重上限。
    if food < 0:
        deficit = abs(food)
        data["famine_streak"] = int(data.get("famine_streak", 0)) + 1
        food = 0

        if data["famine_streak"] <= BALANCE["FAMINE_GRACE_TURNS"]:
            print(
                f"🥣 [緊急配給]【{c_name}】本輪糧食出現 {int(math.ceil(deficit))} 缺口，"
                f"先啟動配給與救濟，暫無人口死亡。"
            )
        else:
            ratio_cap = max(
                1,
                int(math.ceil(pop_total * BALANCE["FAMINE_MAX_POP_LOSS_RATIO"])),
            )
            death_cap = min(
                BALANCE["FAMINE_MAX_DEATHS_PER_TURN"],
                ratio_cap,
            )
            deficit_deaths = max(
                1,
                int(math.ceil(deficit / BALANCE["FAMINE_DEFICIT_PER_DEATH"])),
            )
            starved = min(max(0, pop_total - 1), death_cap, deficit_deaths)

            if starved > 0:
                # 飢荒死亡依軍民占比自然分攤，但優先保留最少 1 人。
                old_pop = pop_total
                soldier_deaths = min(
                    soldiers,
                    int(round(starved * soldiers / max(1, old_pop))),
                )
                farmer_deaths = min(farmers, starved - soldier_deaths)

                # 若農夫不足以承擔剩餘死亡，再回頭扣士兵。
                remaining = starved - soldier_deaths - farmer_deaths
                if remaining > 0:
                    extra_soldier_deaths = min(
                        soldiers - soldier_deaths,
                        remaining,
                    )
                    soldier_deaths += extra_soldier_deaths
                    remaining -= extra_soldier_deaths

                soldiers -= soldier_deaths
                farmers -= farmer_deaths
                pop_total = max(1, soldiers + farmers)
                # 保證人口結構一致。
                soldiers = min(soldiers, pop_total // 2)
                farmers = pop_total - soldiers

                data["last_population_change_reason"] = (
                    f"持續飢荒第{data['famine_streak']}輪，死亡{starved}人"
                )
                print(
                    f"☠️ [持續飢荒]【{c_name}】已連續欠糧 {data['famine_streak']} 輪，"
                    f"本輪死亡 {starved} 人（上限保護生效），剩餘人口 {pop_total}。"
                )
    else:
        data["famine_streak"] = 0

    # 經濟階段除了「持續飢荒」之外，不應直接讓總人口下降。
    # 若未記錄飢荒原因卻出現人口減少，先修正回本輪起始人口，並留下警告。
    if pop_total < pop_at_turn_start and not data.get("last_population_change_reason", ""):
        print(
            f"⚠️ [人口保護]【{c_name}】偵測到非戰鬥、非飢荒人口異常下降 "
            f"{pop_at_turn_start - pop_total} 人，已自動校正。"
        )
        pop_total = pop_at_turn_start
        soldiers = min(soldiers, pop_total // 2)
        farmers = pop_total - soldiers

    data["houses"] = houses
    data["pop_total"] = pop_total
    data["soldiers"] = min(max(0, int(soldiers)), pop_total // 2)
    data["farmers"] = pop_total - data["soldiers"]
    data["food"] = max(0, int(round(food)))
    data["wood"] = max(0, int(round(wood)))
    data["metal"] = max(0, int(round(metal)))
    data["military_target_ratio"] = float(_clamp(military_target_ratio, 0.10, 0.50))
    if data["pop_total"] >= pop_at_turn_start:
        data["last_population_change_reason"] = ""

    if "calculate_rts_power" in globals():
        data["power"] = calculate_rts_power(data)


# ====================================================
# 【強化版 RL 大腦 V2】12 Actions + 多維 State + 情境式 Reward
# ====================================================

RL_VERSION = 2

# ====================================================
# 【記憶體 / OOM 防護】
# ====================================================
# 每國 Q-State 上限；100 國約最多 120,000 個 State，
# 避免長時間運行後 Q-table 無限制膨脹。
MAX_Q_STATES_PER_AGENT = 1200
Q_PRUNE_BATCH = 120

# 過大的舊 Q-table JSON 在載入時可能瞬間耗盡 RAM。
# 超過此大小會先自動備份，再從乾淨 Q-table 繼續學習。
MAX_QTABLE_FILE_MB = 80

# Q-table 不必每 2 秒寫一次；每 10 個 Game Loop 存一次即可。
QTABLE_SAVE_INTERVAL_TURNS = 10

# 探索率隨決策緩慢下降，但保留最低探索避免策略完全僵化。
RL_EPSILON_MIN = 0.07
RL_EPSILON_DECAY = 0.9997

# Full GC 不必每 2 秒跑一次；降低長時間卡頓。
GC_INTERVAL_TURNS = 30

RL_ACTIONS = {
    0: "發動戰爭",
    1: "締結同盟",
    2: "號召圍剿",
    3: "經濟發展",
    4: "背叛背刺",
    5: "加固防線",
    6: "戰時動員",
    7: "農業振興",
    8: "市場貿易",
    9: "修復聲望",
    10: "小規模襲擾",
    11: "裁軍休養",
}
RL_ACTION_SIZE = len(RL_ACTIONS)


def _clamp(value, low, high):
    return max(low, min(high, value))


RL_SNAPSHOT_FIELDS = (
    "is_alive", "power", "pop_total", "farmers", "soldiers",
    "food", "wood", "metal", "current_alliance", "recent_attackers",
    "infamy", "prev_power", "annexed_count",
)


def _rl_snapshot(data):
    """RL 只複製真正會用到的欄位，避免 deepcopy 整份國家歷史資料。"""
    snap = {}
    for key in RL_SNAPSHOT_FIELDS:
        value = data.get(key)
        if key == "recent_attackers":
            value = list(value or [])
        snap[key] = value
    return snap


def get_valid_rl_actions(attacker_key, countries, alliances, anti_hegemon_coalitions, alive_sorted):
    """依照客觀條件建立 Action Mask；圍剿使用獨立臨時聯軍，不改變普通聯盟。"""
    c = countries[attacker_key]
    valid = {3, 7}  # 發展與農業至少永遠可做，避免無合法動作

    if not c.get("is_alive", True):
        return [3]

    pop = max(1, int(c.get("pop_total", 1)))
    farmers = max(0, int(c.get("farmers", 0)))
    soldiers = max(0, int(c.get("soldiers", 0)))
    food = max(0, c.get("food", 0))
    wood = max(0, c.get("wood", 0))
    metal = max(0, c.get("metal", 0))
    current_alliance = c.get("current_alliance", "")

    # 非本國、非本國同盟成員的存活國家
    my_members = set(alliances.get(current_alliance, [])) if current_alliance else {attacker_key}
    hostile_targets = [
        k for k in alive_sorted
        if k != attacker_key and countries[k].get("is_alive", True) and k not in my_members
    ]

    # 0 全面戰爭：主動宣戰至少要有「人口 10% 或 12 人」的基本兵力。
    # 低軍備的肥羊仍然可以被別人攻擊，但不再自己用 5 個兵亂宣大戰。
    minimum_war_force = max(12, int(pop * 0.10))
    if (
        soldiers >= minimum_war_force
        and hostile_targets
        and food >= max(20, int(soldiers * 0.5))
        and metal >= max(20, int(soldiers * 1.25))
    ):
        valid.add(0)

    # 1 結盟：尚未加入任何同盟，且世界上仍有可結盟對象。
    if not current_alliance and any(
        k != attacker_key and countries[k].get("is_alive", True) for k in alive_sorted
    ):
        valid.add(1)

    # 2 圍剿：自己不能是第一名，且全球圍剿聯盟未達上限。
    if (
        alive_sorted
        and alive_sorted[0] != attacker_key
        and len(alive_sorted) >= 4
        and len(anti_hegemon_coalitions) < 2
    ):
        valid.add(2)

    # 4 背叛：必須真的有活著的盟友可背刺。
    if current_alliance in alliances:
        partners = [
            m for m in alliances[current_alliance]
            if m != attacker_key and countries[m].get("is_alive", True)
        ]
        if partners:
            valid.add(4)

    # 5 防線：需要真實支付材料，而非憑空增加資源。
    if wood >= 35 and metal >= 15 and c.get("fortification", 0) < 95:
        valid.add(5)

    # 6 動員：仍有可轉為士兵的安全農民，並有基本裝備與軍糧。
    if (
        soldiers < pop // 2
        and farmers > soldiers
        and metal >= 60
        and food >= 100
    ):
        valid.add(6)

    # 8 市場：至少有一種可交換的盈餘資源。
    if max(food, wood * 2, metal * 2) >= 150:
        valid.add(8)

    # 9 聲望修復：有惡名才需要做。
    if c.get("infamy", 0) > 0 and food >= 100:
        valid.add(9)

    # 10 襲擾：比全面戰爭成本低，但仍需基本兵力與敵對目標。
    if soldiers >= 5 and hostile_targets and food >= 30:
        valid.add(10)

    # 11 裁軍：有士兵才能裁。
    if soldiers > 0:
        valid.add(11)

    return sorted(valid)


class CountryRLAgent:
    """12 動作、10 維離散 State 的 Q-Learning 國家 AI。"""

    def __init__(
        self,
        country_name,
        personality="OPPORTUNIST",
        action_size=RL_ACTION_SIZE,
        learning_rate=0.10,
        discount_factor=0.92,
        epsilon=0.22,
        q_table=None,
        decision_count=0,
    ):
        self.country_name = country_name
        self.personality_type = personality
        self.personality = PERSONALITIES.get(personality, PERSONALITIES["OPPORTUNIST"])
        self.action_size = RL_ACTION_SIZE
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = float(epsilon)
        self.decision_count = max(0, int(decision_count or 0))
        self.q_table = q_table if isinstance(q_table, dict) else {}

        # 舊存檔若已經累積過多 State，載入後先保留較新的部分。
        if len(self.q_table) > MAX_Q_STATES_PER_AGENT:
            keep_keys = list(self.q_table.keys())[
                -MAX_Q_STATES_PER_AGENT:
            ]
            self.q_table = {
                k: self.q_table[k]
                for k in keep_keys
            }

        # 舊版只有 6 Actions；若同一個 State 剛好沿用，補齊至 12 格。
        for key, values in list(self.q_table.items()):
            if not isinstance(values, list):
                self.q_table[key] = [0.0] * self.action_size
                continue
            if len(values) < self.action_size:
                self.q_table[key] = values + [0.0] * (self.action_size - len(values))
            elif len(values) > self.action_size:
                self.q_table[key] = values[: self.action_size]

    def _ensure_q_vector(self, state_str):
        # 新 State 加入前先控制 Q-table 大小。
        # Python dict 保留插入順序，因此刪除最早的一小批 State，
        # 可避免長時間運行後記憶體持續成長。
        if (
            state_str not in self.q_table
            and len(self.q_table)
            >= MAX_Q_STATES_PER_AGENT
        ):
            prune_count = min(
                Q_PRUNE_BATCH,
                max(
                    1,
                    len(self.q_table)
                    - MAX_Q_STATES_PER_AGENT
                    + Q_PRUNE_BATCH,
                ),
            )
            # 優先淘汰幾乎沒有學到訊號的 State，保留較有資訊量的 Q 值。
            def information_score(item):
                _key, vec = item
                if not isinstance(vec, list) or not vec:
                    return 0.0
                try:
                    return max(abs(float(v)) for v in vec)
                except Exception:
                    return 0.0

            prune_candidates = sorted(
                self.q_table.items(), key=information_score
            )[:prune_count]
            for old_key, _vec in prune_candidates:
                self.q_table.pop(old_key, None)

        values = self.q_table.get(state_str)
        if not isinstance(values, list):
            values = []
        if len(values) < self.action_size:
            values = values + [0.0] * (self.action_size - len(values))
        elif len(values) > self.action_size:
            values = values[: self.action_size]
        self.q_table[state_str] = values
        return values

    def _get_state_key(self, country_data, total_world_power, max_power, alive_count):
        """
        State 維度：
        0戰力、1經濟、2糧食安全、3軍事化、4外交、5威脅、
        6惡名、7戰力趨勢、8世界局勢、9是否霸主。
        """
        global world_stage_g

        my_power = max(0, country_data.get("power", 0))
        avg_power = max(total_world_power / max(alive_count, 1), 1.0)
        pwr_ratio = my_power / avg_power

        if pwr_ratio < 0.45:
            pwr_level = "VERY_WEAK"
        elif pwr_ratio < 0.85:
            pwr_level = "WEAK"
        elif pwr_ratio < 1.35:
            pwr_level = "NORMAL"
        elif pwr_ratio < 2.30:
            pwr_level = "STRONG"
        else:
            pwr_level = "SUPREME"

        pop = max(1, int(country_data.get("pop_total", 1) or 1))
        farmers = max(0, int(country_data.get("farmers", 0) or 0))
        soldiers = max(0, int(country_data.get("soldiers", 0) or 0))
        food = max(0.0, float(country_data.get("food", 0) or 0))
        wood = max(0.0, float(country_data.get("wood", 0) or 0))
        metal = max(0.0, float(country_data.get("metal", 0) or 0))

        # 經濟用「加權資源 / 人口」衡量，避免大國只因絕對庫存高就被判定富裕。
        wealth_pc = (food + wood * 1.2 + metal * 2.0) / pop
        if wealth_pc < 5:
            economy_level = "CRISIS"
        elif wealth_pc < 12:
            economy_level = "POOR"
        elif wealth_pc < 28:
            economy_level = "STABLE"
        else:
            economy_level = "RICH"

        estimated_consumption = max(1.0, farmers + soldiers * 2.0)
        food_turns = food / estimated_consumption
        if food_turns < 1.0:
            food_status = "FAMINE"
        elif food_turns < 3.0:
            food_status = "LOW"
        elif food_turns < 8.0:
            food_status = "SAFE"
        else:
            food_status = "SURPLUS"

        military_ratio = soldiers / pop
        if military_ratio < 0.16:
            military_status = "LIGHT"
        elif military_ratio < 0.36:
            military_status = "BALANCED"
        else:
            military_status = "MOBILIZED"

        alliance_status = "ALLIED" if country_data.get("current_alliance") else "SOLO"

        attacker_count = len(country_data.get("recent_attackers", []) or [])
        if attacker_count == 0:
            threat_status = "CALM"
        elif attacker_count <= 2:
            threat_status = "ALERT"
        else:
            threat_status = "BESIEGED"

        infamy = max(0, int(country_data.get("infamy", 0) or 0))
        if infamy < 20:
            infamy_status = "CLEAN"
        elif infamy < 60:
            infamy_status = "TARNISHED"
        else:
            infamy_status = "NOTORIOUS"

        prev_pwr = max(0, country_data.get("prev_power", my_power))
        trend_ratio = (my_power - prev_pwr) / max(prev_pwr, 1.0)
        if trend_ratio > 0.05:
            trend = "RISING"
        elif trend_ratio < -0.05:
            trend = "FALLING"
        else:
            trend = "STABLE"

        top_dominance = max_power / avg_power
        if top_dominance < 1.8:
            world_stage = "BALANCED"
        elif top_dominance < 3.5:
            world_stage = "RISING"
        else:
            world_stage = "EMPIRE"

        world_stage_g = world_stage
        is_top = 1 if (my_power >= max_power and my_power > 0) else 0

        return (
            pwr_level,
            economy_level,
            food_status,
            military_status,
            alliance_status,
            threat_status,
            infamy_status,
            trend,
            world_stage,
            is_top,
        )

    def describe_state(self, country_data, total_world_power, max_power, alive_count):
        s = self._get_state_key(country_data, total_world_power, max_power, alive_count)
        return (
            f"{s[0]}/{s[1]}/{s[2]}/{s[3]}/"
            f"{s[4]}/{s[5]}/{s[6]}/{s[7]}/{s[8]}"
        )

    def _contextual_weights(self, state):
        # 12 Actions 的性格基礎探索權重
        if self.personality_type == "PACIFIST":
            weights = [0.03, 0.16, 0.07, 0.15, 0.005, 0.12, 0.04, 0.16, 0.10, 0.08, 0.015, 0.09]
        elif self.personality_type == "WARMONGER":
            weights = [0.22, 0.06, 0.11, 0.07, 0.09, 0.06, 0.13, 0.04, 0.05, 0.025, 0.105, 0.035]
        else:
            weights = [0.12, 0.11, 0.10, 0.12, 0.06, 0.08, 0.09, 0.08, 0.09, 0.05, 0.07, 0.03]

        pwr, econ, food, military, alliance, threat, infamy, trend, world, is_top = state

        # 糧荒時：農業、貿易、裁軍優先；戰爭與動員降權。
        if food == "FAMINE":
            for a in (7, 8, 11):
                weights[a] *= 4.0
            for a in (0, 6, 10):
                weights[a] *= 0.12
        elif food == "LOW":
            for a in (7, 8, 11):
                weights[a] *= 2.2
            weights[6] *= 0.5

        # 軍事人口過低時，優先補足常備軍。
        # LIGHT = 士兵低於總人口 16%。
        if military == "LIGHT":
            weights[6] *= 4.0
            weights[5] *= 1.25
            # 極低軍備時先補軍，不鼓勵自己主動開多條戰線。
            weights[0] *= 0.75
        elif military == "MOBILIZED":
            # 已高度軍事化，動員需求自然降低。
            weights[6] *= 0.55

        # 受威脅時：結盟、防禦、動員、圍剿更合理。
        if threat == "BESIEGED":
            for a in (1, 2, 5, 6):
                weights[a] *= 2.5
            weights[11] *= 0.25
        elif threat == "ALERT":
            for a in (1, 5, 6):
                weights[a] *= 1.6

        # 經濟差時少打仗，多發展。
        if econ in ("CRISIS", "POOR"):
            weights[3] *= 2.0
            weights[7] *= 1.5
            weights[8] *= 1.5
            weights[0] *= 0.55

        # 惡名高時，修復聲望優先；繼續背叛降權。
        if infamy == "NOTORIOUS":
            weights[9] *= 4.0
            weights[4] *= 0.15
        elif infamy == "TARNISHED":
            weights[9] *= 2.0
            weights[4] *= 0.5

        # 弱國更傾向結盟與休養；強國才更有本錢戰爭。
        if pwr in ("VERY_WEAK", "WEAK"):
            weights[1] *= 1.8
            weights[3] *= 1.5
            weights[5] *= 1.4
            weights[0] *= 0.45
        elif pwr in ("STRONG", "SUPREME"):
            weights[0] *= 1.35
            weights[10] *= 1.2

        # 帝國期的非霸主更重視圍剿；霸主自己不該偏好圍剿。
        if world == "EMPIRE" and not is_top:
            weights[2] *= 2.3
        if is_top:
            weights[2] *= 0.05
            weights[5] *= 1.4

        return weights

    def choose_action(
        self,
        country_data,
        total_world_power,
        max_power,
        alive_count,
        valid_actions=None,
    ):
        """Epsilon-Greedy + Action Mask + State-aware exploration。"""
        state = self._get_state_key(country_data, total_world_power, max_power, alive_count)
        state_str = str(state)
        q_values = self._ensure_q_vector(state_str)

        valid_actions = list(valid_actions or range(self.action_size))
        valid_actions = [a for a in valid_actions if 0 <= a < self.action_size]
        if not valid_actions:
            valid_actions = [3]

        weights = self._contextual_weights(state)

        # V3：人格是長期偏好；戰略模式與事件是短期國策。
        mode = str(country_data.get("strategic_mode", "正常發展"))
        if mode == "糧荒求生":
            for a in (3, 7, 8, 11):
                weights[a] *= 2.2
            for a in (0, 4, 10):
                weights[a] *= 0.25
        elif mode == "戰後復甦":
            for a in (3, 7, 8, 11):
                weights[a] *= 1.8
            weights[0] *= 0.35
            weights[10] *= 0.45
        elif mode == "全面防禦":
            weights[5] *= 2.3
            weights[6] *= 2.0
            weights[7] *= 1.3
            weights[0] *= 0.40
        elif mode == "戰時動員":
            weights[5] *= 1.35
            weights[6] *= 1.65
            weights[7] *= 1.20
        elif mode == "報復模式":
            weights[0] *= 2.1
            weights[6] *= 1.35
            weights[10] *= 1.35
        elif mode == "擴張模式":
            weights[0] *= 1.55
            weights[1] *= 1.20
            weights[6] *= 1.25
        elif mode == "霸權維持":
            weights[5] *= 1.45
            weights[9] *= 1.35
            weights[1] *= 1.15
            weights[4] *= 0.70

        war_bias = float(country_data.get("event_war_bias", 1.0) or 1.0)
        alliance_bias = float(country_data.get("event_alliance_bias", 1.0) or 1.0)
        recruit_bias = float(country_data.get("event_recruit_mult", 1.0) or 1.0)
        trade_bias = float(country_data.get("event_trade_mult", 1.0) or 1.0)
        reputation_bias = float(country_data.get("event_reputation_bias", 1.0) or 1.0)

        weights[0] *= war_bias
        weights[10] *= war_bias
        weights[1] *= alliance_bias
        weights[2] *= alliance_bias
        weights[6] *= recruit_bias
        weights[8] *= trade_bias
        weights[9] *= reputation_bias

        # V4 世界局勢與單國事件疊加。
        weights[0] *= float(country_data.get("world_war_bias", 1.0) or 1.0)
        weights[10] *= float(country_data.get("world_war_bias", 1.0) or 1.0)
        weights[1] *= float(country_data.get("world_alliance_bias", 1.0) or 1.0)
        weights[4] *= float(country_data.get("world_betray_bias", 1.0) or 1.0)
        weights[2] *= float(country_data.get("world_coalition_bias", 1.0) or 1.0)
        weights[6] *= float(country_data.get("world_recruit_mult", 1.0) or 1.0)
        weights[8] *= float(country_data.get("world_trade_mult", 1.0) or 1.0)

        if (
            country_data.get("world_mode_code") == "TOTAL_WAR"
            and len(country_data.get("current_wars", []) or []) == 1
        ):
            weights[0] *= 1.80

        # 高度厭戰會直接抑制再次主動開戰。
        exhaustion = float(country_data.get("war_exhaustion", 0) or 0)
        if exhaustion >= 85:
            weights[0] *= 0.12
            weights[10] *= 0.18
        elif exhaustion >= 65:
            weights[0] *= 0.42
            weights[10] *= 0.60

        # 新 State 尚未學到差異時，不要讓 argmax 永遠選 Action 0。
        valid_q = [q_values[a] for a in valid_actions]
        q_is_untrained = max(valid_q) - min(valid_q) < 1e-9

        self.decision_count += 1
        effective_epsilon = max(
            RL_EPSILON_MIN,
            self.epsilon * (RL_EPSILON_DECAY ** self.decision_count),
        )

        if random.random() < effective_epsilon or q_is_untrained:
            candidate_weights = [max(0.0001, weights[a]) for a in valid_actions]
            return random.choices(valid_actions, weights=candidate_weights, k=1)[0]

        max_q = max(q_values[a] for a in valid_actions)
        best_actions = [a for a in valid_actions if abs(q_values[a] - max_q) < 1e-12]
        return random.choice(best_actions)

    def calculate_reward(
        self,
        before_data,
        after_data,
        action,
        action_success,
        action_value,
        total_world_power,
        max_power,
        alive_count,
    ):
        """以『生存、相對成長、經濟、人口、行動情境、惡名成本』綜合計分。"""
        before_state = self._get_state_key(before_data, total_world_power, max_power, alive_count)
        after_state = self._get_state_key(after_data, total_world_power, max_power, alive_count)

        reward = 0.0

        # 1) 生存是底線，但不再像舊版第一名固定 +100 那樣壓過所有訊號。
        if after_data.get("is_alive", True):
            reward += 1.5
        else:
            reward -= 85.0

        # 2) 戰力變化採比例而非絕對值，避免大國因基數大而天然拿更多 Reward。
        before_power = max(1.0, float(before_data.get("power", 0) or 0))
        after_power = max(0.0, float(after_data.get("power", 0) or 0))
        pwr_change = (after_power - before_power) / before_power
        power_reward = _clamp(pwr_change * 22.0, -22.0, 22.0)
        # 裁軍是有意識用軍力換經濟韌性，不能把計畫性退伍當成一般戰敗同額處罰。
        if action == 11 and power_reward < 0:
            power_reward *= 0.20
        reward += power_reward

        # 3) 人口變化
        before_pop = max(1.0, float(before_data.get("pop_total", 1) or 1))
        after_pop = max(0.0, float(after_data.get("pop_total", 0) or 0))
        pop_change = (after_pop - before_pop) / before_pop
        reward += _clamp(pop_change * 16.0, -18.0, 12.0)

        # 4) 經濟資產變化（木材與金屬給不同權重）
        def resource_score(d):
            return (
                max(0.0, float(d.get("food", 0) or 0))
                + max(0.0, float(d.get("wood", 0) or 0)) * 1.2
                + max(0.0, float(d.get("metal", 0) or 0)) * 2.0
            )

        before_res = max(100.0, resource_score(before_data))
        after_res = resource_score(after_data)
        res_change = (after_res - before_res) / before_res
        reward += _clamp(res_change * 10.0, -12.0, 12.0)

        # 5) 成功吞併是真正長期成果
        annex_gain = max(
            0,
            int(after_data.get("annexed_count", 0) or 0)
            - int(before_data.get("annexed_count", 0) or 0),
        )
        reward += annex_gain * 40.0

        # 6) 有效執行 vs 空轉
        reward += 3.0 if action_success else -4.0

        pwr, econ, food, military, alliance, threat, infamy, trend, world, is_top = before_state

        # 7) Action-specific 情境合理化
        if action == 0:  # 全面戰爭
            if pwr == "VERY_WEAK":
                reward -= 14.0
            if food in ("FAMINE", "LOW"):
                reward -= 12.0
            if action_success:
                reward += 4.0

        elif action == 1:  # 結盟
            if action_success:
                reward += 9.0
                if threat in ("ALERT", "BESIEGED"):
                    reward += 5.0
            if alliance == "ALLIED":
                reward -= 4.0

        elif action == 2:  # 圍剿
            if action_success:
                reward += 8.0
                if world == "EMPIRE" and not is_top:
                    reward += 8.0
            elif world == "BALANCED":
                reward -= 3.0

        elif action == 3:  # 經濟
            reward += 7.0 if econ in ("CRISIS", "POOR") else 2.0
            if threat == "BESIEGED":
                reward -= 2.0

        elif action == 4:  # 背叛
            if action_success:
                reward += min(8.0, max(0.0, action_value) / 100.0)
            # 惡名是跨回合成本，不讓偷一次糧就永遠是神技。
            infamy_gain = max(
                0,
                int(after_data.get("infamy", 0) or 0) - int(before_data.get("infamy", 0) or 0),
            )
            reward -= infamy_gain * 0.22

        elif action == 5:  # 防禦
            reward += 7.0 if threat in ("ALERT", "BESIEGED") else 2.0
            if econ == "CRISIS":
                reward -= 3.0

        elif action == 6:  # 動員
            if threat in ("ALERT", "BESIEGED") or pwr in ("VERY_WEAK", "WEAK"):
                reward += 8.0
            if food in ("FAMINE", "LOW"):
                reward -= 10.0
            if military == "MOBILIZED":
                reward -= 5.0

        elif action == 7:  # 農業
            reward += 10.0 if food in ("FAMINE", "LOW") else 2.0

        elif action == 8:  # 市場
            reward += 7.0 if action_success and (food in ("FAMINE", "LOW") or econ in ("CRISIS", "POOR")) else 2.0

        elif action == 9:  # 修復聲望
            reward += 9.0 if infamy in ("TARNISHED", "NOTORIOUS") else 1.0

        elif action == 10:  # 襲擾
            if action_success:
                reward += min(7.0, max(0.0, action_value) / 120.0)
            if pwr == "VERY_WEAK":
                reward -= 7.0
            if food == "FAMINE":
                reward -= 6.0

        elif action == 11:  # 裁軍
            if food in ("FAMINE", "LOW") or econ in ("CRISIS", "POOR"):
                reward += 12.0
                reward += min(6.0, max(0.0, action_value) / 60.0)
            else:
                reward += 1.0
            if threat == "BESIEGED":
                reward -= 10.0

        # 8) 狀態真的改善才加分
        if before_state[2] in ("FAMINE", "LOW") and after_state[2] in ("SAFE", "SURPLUS"):
            reward += 8.0
        if before_state[1] in ("CRISIS", "POOR") and after_state[1] in ("STABLE", "RICH"):
            reward += 6.0
        if before_state[6] in ("TARNISHED", "NOTORIOUS") and after_state[6] == "CLEAN":
            reward += 6.0
        if before_state[7] == "FALLING" and after_state[7] != "FALLING":
            reward += 4.0

        # 9) 第一名只給小額「維持優勢」訊號，不再固定 +100。
        if after_state[9]:
            reward += 3.0

        # 10) 防止 Reward 爆炸讓 Q 值失控。
        return float(_clamp(reward, -100.0, 100.0))

    def learn(
        self,
        country_data,
        total_world_power,
        max_power,
        alive_count,
        action,
        reward,
        next_country_data,
    ):
        """標準 Q-Learning；country_data 與 next_country_data 必須是不同時間點的快照。"""
        state = self._get_state_key(country_data, total_world_power, max_power, alive_count)
        next_state = self._get_state_key(next_country_data, total_world_power, max_power, alive_count)

        s_str = str(state)
        ns_str = str(next_state)
        q_now = self._ensure_q_vector(s_str)
        q_next = self._ensure_q_vector(ns_str)

        predict = q_now[action]
        target = reward + self.gamma * max(q_next)
        q_now[action] += self.lr * (target - predict)


# ====================================================
# 【獨立大腦 存檔與載入管理】
# ====================================================
def save_all_agents(rl_agents, file_path="rl_agents_q_tables.json"):
    """將所有國家的 RL Q-Tables 保存至 JSON 檔案"""
    data = {}
    for name, agent in rl_agents.items():
        data[name] = {
            "rl_version": RL_VERSION,
            "action_size": RL_ACTION_SIZE,
            "personality": agent.personality_type,
            "decision_count": agent.decision_count,
            "q_table": agent.q_table,
        }
    try:
        _atomic_write_json(file_path, data, compact=True)
    except Exception as e:
        print(f"⚠️ [RL] 所有國家 Q-Tables 保存失敗: {e}")


def load_all_agents(country_list, file_path="rl_agents_q_tables.json"):
    """從 JSON 檔案載入所有國家的獨立 RL 大腦，若無則初始化新大腦"""
    all_agent_data = {}
    if os.path.exists(file_path):  # 若檔案存在
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            if file_size_mb > MAX_QTABLE_FILE_MB:
                backup_path = (
                    file_path
                    + f".oversize_backup_{int(time.time())}"
                )
                os.replace(file_path, backup_path)
                print(
                    f"🛡️ [OOM防護] Q-table 存檔已達 {file_size_mb:.1f} MB，"
                    f"為避免載入時記憶體爆滿，已備份為 {backup_path}，"
                    f"本次從精簡新大腦重新學習。"
                )
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    all_agent_data = json.load(f)

                print(
                    f"🧠 [RL 載入成功] 已讀取 {len(all_agent_data)} 個國家的獨立 Q-Table 大腦！"
                )

        except Exception as e:
            print(
                f"⚠️ [RL] 載入獨立大腦失敗，將建立全新大腦: {e}"
            )

    agents = {}
    for name in country_list:  # 遍歷國家名單
        a_info = all_agent_data.get(name, {})
        pers = a_info.get("personality", random.choice(list(PERSONALITIES.keys())))
        # V1 的 State 維度與 6 Actions 和 V2 不相容；保留性格，但從乾淨的 V2 Q-Table 重新學習。
        if a_info.get("rl_version") == RL_VERSION and a_info.get("action_size") == RL_ACTION_SIZE:
            q_tab = a_info.get("q_table", {})
        else:
            q_tab = {}
        agents[name] = CountryRLAgent(
            country_name=name,
            personality=pers,
            q_table=q_tab,
            decision_count=int(a_info.get("decision_count", 0) or 0),
        )
    return agents  # 回傳包含所有國家大腦的字典


# ====================================================
# 【主要邏輯與多線程監控】thread_stat_monitor
# ====================================================

# ============================================================
# 【戰國模式 V1】持續戰爭 / 攻城 / 仇恨 / 國都陷落
# ============================================================
WARSTATE = {
    "ACTIVE_COUNTRIES_MIN": 10,
    "ACTIVE_COUNTRIES_MAX": 18,
    "WAR_DURATION_MIN": 3,
    "WAR_DURATION_MAX": 8,
    "SIEGE_WEIGHT": 0.20,
    "BATTLE_WEIGHT": 0.55,
    "RAID_WEIGHT": 0.25,
    "CLASH_MIN": 0.25,
    "CLASH_MAX": 0.45,
    "FORT_SIEGE_MIN": 10,
    "FORT_SIEGE_MAX": 20,
    "FORT_BATTLE_MIN": 3,
    "FORT_BATTLE_MAX": 8,
    "CAPITAL_LOSS_STREAK": 2,
    "CAPITAL_SOLDIER_RATIO": 0.25,
    "CAPITAL_FORT": 20,
    "CAPITAL_CHANCE_MIN": 0.45,
    "CAPITAL_CHANCE_MAX": 0.65,
    "CAPITAL_DEATH_MIN": 0.10,
    "CAPITAL_DEATH_MAX": 0.18,
    "HOSTILITY_ATTACK": 20,
    "HOSTILITY_ALLY_ATTACK": 10,
    "HOSTILITY_RAID": 15,
    "HOSTILITY_BETRAY": 40,
    "HOSTILITY_DECAY": 1,

    # ========================================================
    # 雙線作戰
    # ========================================================
    # 每個國家最多同時參加 2 場正式戰爭。
    "MAX_ACTIVE_WARS_PER_COUNTRY": 2,

    # 第二戰線不能再把同一批士兵完整算一次：
    # 只有約 55% 現役兵力可視為第二戰線有效戰力。
    "SECOND_FRONT_FORCE_MULTIPLIER": 0.55,

    # 新開第二戰線時，第一波遠征補給更昂貴。
    "SECOND_FRONT_INITIAL_FOOD_MULTIPLIER": 1.35,
    "SECOND_FRONT_INITIAL_METAL_MULTIPLIER": 1.25,

    # 每個持續戰爭回合，第二戰線還會額外支付維持費。
    "SECOND_FRONT_UPKEEP_FOOD_PER_SOLDIER": 0.18,
    "SECOND_FRONT_UPKEEP_METAL_PER_SOLDIER": 0.04,

    # 所有正式戰爭每回合都要維持前線補給；第二戰線另外再加上上面的額外成本。
    "WAR_ROUND_FOOD_PER_SOLDIER": 0.10,
    "WAR_ROUND_METAL_PER_SOLDIER": 0.02,

    # 戰後短暫休戰，避免同一批國家隔一輪立刻重打。
    "TRUCE_TURNS": 4,
    # 到期時戰況差距超過此值才判定勝負，接近才是真和局。
    "DEADLINE_DECISION_MARGIN": 0.10,
    # 戰敗求和賠款（只搬動現有庫存，不創造資源）。
    "SURRENDER_FOOD_RATE": 0.06,
    "SURRENDER_WOOD_RATE": 0.03,
    "SURRENDER_METAL_RATE": 0.04,
}


def _war_add_hostility(countries, source_key, target_key, amount):
    if source_key not in countries or target_key not in countries or source_key == target_key:
        return
    h = countries[source_key].setdefault("hostility", {})
    h[target_key] = int(_clamp(int(h.get(target_key, 0) or 0) + int(amount), 0, 100))


def _war_decay_hostility(country_data):
    h = country_data.setdefault("hostility", {})
    country_data["hostility"] = {
        k: max(0, int(v or 0) - WARSTATE["HOSTILITY_DECAY"])
        for k, v in h.items()
        if max(0, int(v or 0) - WARSTATE["HOSTILITY_DECAY"]) > 0
    }


def _war_country_active_war_ids(country_key, active_wars):
    """取得某國目前參與中的所有正式戰爭 ID，依宣戰先後排序。"""
    result = []
    for war_id, war in active_wars.items():
        if not isinstance(war, dict):
            continue
        if (
            country_key in (war.get("attacker_members") or [])
            or country_key in (war.get("defender_members") or [])
        ):
            result.append(
                (
                    int(war.get("started_turn", 0) or 0),
                    str(war_id),
                )
            )

    result.sort(key=lambda x: (x[0], x[1]))
    return [war_id for _started_turn, war_id in result]


def _war_country_war_count(country_key, active_wars):
    return len(_war_country_active_war_ids(country_key, active_wars))


def _war_country_in_active_war(country_key, active_wars):
    return _war_country_war_count(country_key, active_wars) > 0


def _war_country_can_join_new_war(country_key, active_wars):
    return (
        _war_country_war_count(country_key, active_wars)
        < WARSTATE["MAX_ACTIVE_WARS_PER_COUNTRY"]
    )


def _war_countries_share_war(country_a, country_b, active_wars):
    """避免同一對交戰國重複建立第二個完全相同的戰爭。"""
    if not country_a or not country_b:
        return False

    for war in active_wars.values():
        if not isinstance(war, dict):
            continue

        participants = set(war.get("attacker_members", []) or []) | set(
            war.get("defender_members", []) or []
        )
        if country_a in participants and country_b in participants:
            return True

    return False


def _war_front_number(country_key, war_id, active_wars):
    """
    回傳此戰爭對該國是第幾戰線。
    1 = 第一戰線；2 = 第二戰線。
    """
    war_ids = _war_country_active_war_ids(country_key, active_wars)
    try:
        return war_ids.index(str(war_id)) + 1
    except ValueError:
        return 1


def _war_front_multiplier(country_key, war_id, active_wars):
    return (
        WARSTATE["SECOND_FRONT_FORCE_MULTIPLIER"]
        if _war_front_number(country_key, war_id, active_wars) >= 2
        else 1.0
    )


def _war_effective_soldiers(members, countries, war_id, active_wars):
    """
    計算某一條戰線真正可投入的有效兵力。
    第一戰線=100%；第二戰線=55%。
    """
    total = 0
    for m in _war_live_members(members, countries):
        soldiers = max(0, int(countries[m].get("soldiers", 0) or 0))
        multiplier = _war_front_multiplier(m, war_id, active_wars)
        total += int(soldiers * multiplier)
    return max(0, total)


def _war_round_upkeep(members, countries, war_id, active_wars):
    """所有戰線每回合都支付基本軍糧與武器耗損；回傳實付與缺口。"""
    paid_food = paid_metal = shortage_food = shortage_metal = 0
    for m in _war_live_members(members, countries):
        soldiers = max(0, int(countries[m].get("soldiers", 0) or 0))
        effective = int(soldiers * _war_front_multiplier(m, war_id, active_wars))
        world_upkeep_mult = float(
            countries[m].get("world_war_upkeep_mult", 1.0) or 1.0
        )
        need_food = int(
            math.ceil(
                effective
                * WARSTATE["WAR_ROUND_FOOD_PER_SOLDIER"]
                * world_upkeep_mult
            )
        )
        need_metal = int(
            math.ceil(
                effective
                * WARSTATE["WAR_ROUND_METAL_PER_SOLDIER"]
                * world_upkeep_mult
            )
        )

        stock_food = max(0, int(countries[m].get("food", 0) or 0))
        stock_metal = max(0, int(countries[m].get("metal", 0) or 0))
        use_food = min(stock_food, need_food)
        use_metal = min(stock_metal, need_metal)
        countries[m]["food"] = stock_food - use_food
        countries[m]["metal"] = stock_metal - use_metal
        paid_food += use_food
        paid_metal += use_metal
        shortage_food += max(0, need_food - use_food)
        shortage_metal += max(0, need_metal - use_metal)

    return paid_food, paid_metal, shortage_food, shortage_metal


def _war_second_front_upkeep(members, countries, war_id, active_wars):
    """
    第二戰線每回合額外支付補給。
    回傳 (第二戰線國家數, 糧食消耗, 金屬消耗)。
    """
    second_front_members = 0
    food_cost_total = 0
    metal_cost_total = 0

    for m in _war_live_members(members, countries):
        if _war_front_number(m, war_id, active_wars) < 2:
            continue

        second_front_members += 1
        soldiers = max(0, int(countries[m].get("soldiers", 0) or 0))
        effective = int(
            soldiers * WARSTATE["SECOND_FRONT_FORCE_MULTIPLIER"]
        )

        world_upkeep_mult = float(
            countries[m].get("world_war_upkeep_mult", 1.0) or 1.0
        )
        food_cost = int(
            math.ceil(
                effective
                * WARSTATE["SECOND_FRONT_UPKEEP_FOOD_PER_SOLDIER"]
                * world_upkeep_mult
            )
        )
        metal_cost = int(
            math.ceil(
                effective
                * WARSTATE["SECOND_FRONT_UPKEEP_METAL_PER_SOLDIER"]
                * world_upkeep_mult
            )
        )

        paid_food = min(
            max(0, int(countries[m].get("food", 0) or 0)),
            food_cost,
        )
        paid_metal = min(
            max(0, int(countries[m].get("metal", 0) or 0)),
            metal_cost,
        )

        countries[m]["food"] = max(
            0, countries[m].get("food", 0) - paid_food
        )
        countries[m]["metal"] = max(
            0, countries[m].get("metal", 0) - paid_metal
        )

        food_cost_total += paid_food
        metal_cost_total += paid_metal

    return second_front_members, food_cost_total, metal_cost_total


def _war_filter_members_for_new_front(members, active_wars):
    """聯盟參戰時，已達兩線上限的盟友不再被強制拖入新戰爭。"""
    return [
        m
        for m in (members or [])
        if _war_country_can_join_new_war(m, active_wars)
    ]


def _war_pair_key(country_a, country_b):
    a, b = sorted((str(country_a), str(country_b)))
    return f"{a}||{b}"


def _war_is_truce(country_a, country_b, war_truces, turn_counter):
    expiry = int(war_truces.get(_war_pair_key(country_a, country_b), 0) or 0)
    return expiry > turn_counter


def _war_set_truce_between_sides(attacker_members, defender_members, war_truces, turn_counter):
    expiry = turn_counter + _world_mode_current_truce_turns()
    for a in attacker_members or []:
        for d in defender_members or []:
            if a != d:
                war_truces[_war_pair_key(a, d)] = expiry


def _war_collect_reparations(winner_members, loser_members, countries):
    """求和時收取小額賠款，按勝方兵力分配。"""
    winners = _war_live_members(winner_members, countries)
    losers = _war_live_members(loser_members, countries)
    if not winners or not losers:
        return 0, 0, 0

    paid = {"food": 0, "wood": 0, "metal": 0}
    rates = {
        "food": WARSTATE["SURRENDER_FOOD_RATE"],
        "wood": WARSTATE["SURRENDER_WOOD_RATE"],
        "metal": WARSTATE["SURRENDER_METAL_RATE"],
    }
    for res, rate in rates.items():
        for m in losers:
            stock = max(0, int(countries[m].get(res, 0) or 0))
            take = min(stock, int(stock * rate))
            countries[m][res] = stock - take
            paid[res] += take

        weights = [max(1, int(countries[m].get("soldiers", 0) or 0)) for m in winners]
        total_weight = max(1, sum(weights))
        remaining = paid[res]
        for idx, (m, weight) in enumerate(zip(winners, weights)):
            if idx == len(winners) - 1:
                gain = remaining
            else:
                gain = min(remaining, int(paid[res] * weight / total_weight))
            countries[m][res] = max(0, int(countries[m].get(res, 0) or 0)) + gain
            remaining -= gain

    return paid["food"], paid["wood"], paid["metal"]


def _war_live_members(members, countries):
    return [
        m for m in (members or [])
        if m in countries and countries[m].get("is_alive", True)
    ]


def _war_total_soldiers(members, countries):
    return sum(
        max(0, int(countries[m].get("soldiers", 0) or 0))
        for m in _war_live_members(members, countries)
    )


def _war_avg_fort(members, countries):
    live = _war_live_members(members, countries)
    if not live:
        return 0.0
    return sum(float(countries[m].get("fortification", 0) or 0) for m in live) / len(live)


def _war_apply_soldier_losses(members, countries, total_loss, note_population_loss, reason):
    live = [
        m for m in _war_live_members(members, countries)
        if countries[m].get("soldiers", 0) > 0
    ]
    total_available = sum(countries[m].get("soldiers", 0) for m in live)
    total_loss = min(max(0, int(total_loss)), total_available)
    if total_loss <= 0 or not live:
        return 0

    remaining = total_loss
    basis = max(1, total_available)
    for idx, m in enumerate(live):
        if remaining <= 0:
            break
        if idx == len(live) - 1:
            share = remaining
        else:
            share = int(round(total_loss * countries[m].get("soldiers", 0) / basis))
            share = min(share, remaining)
        actual = min(share, countries[m].get("soldiers", 0))
        if actual <= 0:
            continue
        countries[m]["soldiers"] -= actual
        countries[m]["pop_total"] = countries[m].get("farmers", 0) + countries[m]["soldiers"]
        note_population_loss(m, actual, reason)
        enforce_farmer_majority(countries[m])
        countries[m]["power"] = calculate_rts_power(countries[m])
        remaining -= actual

    return total_loss - remaining


def _war_damage_fort(members, countries, low, high, damage_houses=False):
    total_fort = 0
    total_houses = 0
    for m in _war_live_members(members, countries):
        c = countries[m]
        old = int(_clamp(c.get("fortification", 0), 0, 100))
        dmg = min(old, random.randint(low, high))
        c["fortification"] = max(0, old - dmg)
        total_fort += dmg
        if damage_houses and c.get("houses", 1) > 1:
            houses_now = max(1, int(c.get("houses", 1) or 1))

            # 攻城會破壞約 2.5%~5.5% 房屋，但每國單回合最多 18 間，
            # 避免以前永遠只拆 1~2 間、對數百間房屋幾乎無感。
            pct_damage = max(
                1,
                int(
                    houses_now
                    * random.uniform(0.025, 0.055)
                ),
            )
            structural_damage = max(
                1,
                random.randint(1, max(1, dmg // 4)),
            )
            hd = min(
                houses_now - 1,
                18,
                max(pct_damage, structural_damage),
            )

            c["houses"] = max(1, houses_now - hd)
            total_houses += hd
    return total_fort, total_houses


def _war_steal(attacker_members, defender_members, countries, force):
    defs = _war_live_members(defender_members, countries)
    atts = _war_live_members(attacker_members, countries)
    if not defs or not atts:
        return 0, 0, 0

    caps = {
        "food": max(0, int(force * 1.5)),
        "wood": max(0, int(force * 0.8)),
        "metal": max(0, int(force * 0.5)),
    }
    stolen = {"food": 0, "wood": 0, "metal": 0}
    pct = {"food": 0.025, "wood": 0.020, "metal": 0.018}

    for res in ("food", "wood", "metal"):
        total_stock = sum(max(0, countries[m].get(res, 0)) for m in defs)
        remaining = min(caps[res], int(total_stock * pct[res]))
        for m in defs:
            if remaining <= 0:
                break
            take = min(max(0, countries[m].get(res, 0)), remaining)
            countries[m][res] -= take
            stolen[res] += take
            remaining -= take

        # 依現役兵力分給進攻成員
        weights = [max(1, countries[m].get("soldiers", 0)) for m in atts]
        total_weight = max(1, sum(weights))
        remain_gain = stolen[res]
        for idx, (m, w) in enumerate(zip(atts, weights)):
            if idx == len(atts) - 1:
                gain = remain_gain
            else:
                gain = min(remain_gain, int(stolen[res] * w / total_weight))
            countries[m][res] = max(0, countries[m].get(res, 0)) + gain
            remain_gain -= gain

    return stolen["food"], stolen["wood"], stolen["metal"]


def _war_execute_capital_fall(
    loser_key,
    attacker_members,
    countries,
    note_population_loss,
    turn_counter,
):
    if loser_key not in countries or not countries[loser_key].get("is_alive", True):
        return None

    winners = _war_live_members(attacker_members, countries)
    if not winners:
        return None

    winner_key = max(
        winners,
        key=lambda m: (countries[m].get("soldiers", 0), countries[m].get("power", 0)),
    )
    winner = countries[winner_key]
    loser = countries[loser_key]

    old_pop = max(1, int(loser.get("pop_total", 1) or 1))
    deaths = max(
        1,
        min(
            old_pop - 1,
            int(round(old_pop * random.uniform(
                WARSTATE["CAPITAL_DEATH_MIN"],
                WARSTATE["CAPITAL_DEATH_MAX"],
            ))),
        ),
    )
    survivors = max(0, old_pop - deaths)
    note_population_loss(loser_key, deaths, "國都陷落：戰亂死亡")

    # 存活居民轉由勝國統治，而不是憑空消失。
    winner["pop_total"] = max(1, int(winner.get("pop_total", 1) or 1)) + survivors
    winner["farmers"] = max(0, int(winner.get("farmers", 0) or 0)) + survivors
    winner["houses"] = max(1, int(winner.get("houses", 1) or 1)) + int(max(0, loser.get("houses", 0)) * 0.55)

    captured = {}
    for res in ("food", "wood", "metal"):
        gain = int(max(0, loser.get(res, 0)) * 0.35)
        winner[res] = max(0, winner.get(res, 0)) + gain
        captured[res] = gain

    winner["annexed_count"] = int(winner.get("annexed_count", 0) or 0) + 1
    winner["capital_captures"] = int(winner.get("capital_captures", 0) or 0) + 1
    enforce_farmer_majority(winner)
    winner["power"] = calculate_rts_power(winner)

    loser_name = loser.get("display_name", loser_key)
    winner_name = winner.get("display_name", winner_key)

    _chronicle_close_current(
        loser_key,
        loser,
        turn_counter,
        "滅國",
        ended_by=winner_name,
    )

    loser["last_population_audit"] = f"國都陷落：{deaths} 人死亡，{survivors} 人改隸【{winner_name}】"
    loser["is_alive"] = False
    loser["power"] = 0
    loser["pop_total"] = 0
    loser["farmers"] = 0
    loser["soldiers"] = 0
    loser["food"] = 0
    loser["wood"] = 0
    loser["metal"] = 0
    loser["houses"] = 0
    loser["fortification"] = 0
    loser["death_respawn_cooldown"] = 6
    loser["current_wars"] = []
    loser["war_status"] = "國都陷落，等待新世代重建"

    print(
        f"🏯 [國都陷落]【{loser_name}】政權崩潰！戰亂死亡 {deaths} 人，"
        f"{survivors} 人改由【{winner_name}】統治；"
        f"勝方接收糧:{captured['food']}/木:{captured['wood']}/金:{captured['metal']}。"
    )
    return winner_key


def resolve_persistent_war_round(
    war_id,
    war,
    countries,
    active_wars,
    turn_counter,
    note_population_loss,
):
    att_members = _war_live_members(war.get("attacker_members"), countries)
    def_members = _war_live_members(war.get("defender_members"), countries)
    if not att_members:
        return {"ended": True, "winner": "DEFENDER", "reason": "進攻陣營已無有效成員"}
    if not def_members:
        return {"ended": True, "winner": "ATTACKER", "reason": "防守陣營已無有效成員"}

    war["attacker_members"] = att_members
    war["defender_members"] = def_members
    war["rounds"] = int(war.get("rounds", 0) or 0) + 1
    war["last_turn"] = turn_counter
    round_no = war["rounds"]

    att_name = war.get("attacker_name", "進攻方")
    def_name = war.get("defender_name", "防守方")

    # V3 戰爭疲勞：每個持續戰爭回合都累積，第二戰線額外更累。
    for m in att_members + def_members:
        front_no = _war_front_number(m, war_id, active_wars)
        fatigue_gain = 3.0 + (2.0 if front_no >= 2 else 0.0)
        countries[m]["war_exhaustion"] = float(
            _clamp(float(countries[m].get("war_exhaustion", 0) or 0) + fatigue_gain, 0, 100)
        )
        countries[m]["political_stability"] = float(
            _clamp(float(countries[m].get("political_stability", 75) or 75) - 0.20, 0, 100)
        )

    # 第二戰線不是把同一批軍隊再完整算一次。
    # 第一戰線 100%；第二戰線僅以 55% 現役兵力計入此戰線。
    att_s = _war_effective_soldiers(
        att_members, countries, war_id, active_wars
    )
    def_s = _war_effective_soldiers(
        def_members, countries, war_id, active_wars
    )

    # 所有正式戰線每回合都要付基本軍費，讓長期戰爭真正拖累國庫。
    att_base_food, att_base_metal, att_short_food, att_short_metal = _war_round_upkeep(
        att_members, countries, war_id, active_wars
    )
    def_base_food, def_base_metal, def_short_food, def_short_metal = _war_round_upkeep(
        def_members, countries, war_id, active_wars
    )
    if att_short_food or att_short_metal or def_short_food or def_short_metal:
        print(
            f"⚠️ [前線補給危機] {war_id}：【{att_name}】缺糧 {att_short_food}/缺金 {att_short_metal}；"
            f"【{def_name}】缺糧 {def_short_food}/缺金 {def_short_metal}。"
        )

    # 第二戰線每回合還要額外支付維持費。
    att_second_count, att_food_upkeep, att_metal_upkeep = (
        _war_second_front_upkeep(
            att_members, countries, war_id, active_wars
        )
    )
    def_second_count, def_food_upkeep, def_metal_upkeep = (
        _war_second_front_upkeep(
            def_members, countries, war_id, active_wars
        )
    )

    if att_second_count or def_second_count:
        print(
            f"⚠️ [雙線作戰] {war_id}：【{att_name}】第二戰線成員 {att_second_count} 國"
            f"（額外糧 -{att_food_upkeep}/金 -{att_metal_upkeep}）；"
            f"【{def_name}】第二戰線成員 {def_second_count} 國"
            f"（額外糧 -{def_food_upkeep}/金 -{def_metal_upkeep}）。"
        )

    # 沒有守軍時，持續進入攻城而不是把所有農夫當場屠光。
    if def_s <= 0:
        tactic = "SIEGE"
    else:
        tactic = random.choices(
            ["SIEGE", "BATTLE", "RAID"],
            weights=[
                WARSTATE["SIEGE_WEIGHT"],
                WARSTATE["BATTLE_WEIGHT"],
                WARSTATE["RAID_WEIGHT"],
            ],
            k=1,
        )[0]

    att_loss = def_loss = fort_damage = 0

    if tactic == "BATTLE":
        clash = max(1, int(min(att_s, def_s) * random.uniform(WARSTATE["CLASH_MIN"], WARSTATE["CLASH_MAX"])))
        ratio = _clamp(att_s / max(1, def_s), 0.6, 1.7)
        defense = 1.0 + (_war_avg_fort(def_members, countries) / 100.0) * 0.35
        att_loss = int(clash * random.uniform(0.65, 0.98) * defense / math.sqrt(ratio))
        def_loss = int(clash * random.uniform(0.65, 0.98) * math.sqrt(ratio) / defense)
        att_loss = _war_apply_soldier_losses(att_members, countries, att_loss, note_population_loss, "持續戰爭：攻方會戰傷亡")
        def_loss = _war_apply_soldier_losses(def_members, countries, def_loss, note_population_loss, "持續戰爭：守方會戰傷亡")
        fort_damage, _ = _war_damage_fort(
            def_members, countries,
            WARSTATE["FORT_BATTLE_MIN"], WARSTATE["FORT_BATTLE_MAX"],
            False,
        )
        print(
            f"⚔️ [持續會戰] {war_id} 第{round_no}回合：【{att_name}】損失 {att_loss} 兵，"
            f"【{def_name}】損失 {def_loss} 兵，城防 -{fort_damage}。"
        )

    elif tactic == "SIEGE":
        fort_damage, house_damage = _war_damage_fort(
            def_members, countries,
            WARSTATE["FORT_SIEGE_MIN"], WARSTATE["FORT_SIEGE_MAX"],
            True,
        )
        att_loss = _war_apply_soldier_losses(
            att_members, countries, int(att_s * random.uniform(0.01, 0.04)),
            note_population_loss, "持續戰爭：攻城方傷亡"
        )
        def_loss = _war_apply_soldier_losses(
            def_members, countries, int(def_s * random.uniform(0.03, 0.08)),
            note_population_loss, "持續戰爭：守城方傷亡"
        )
        print(
            f"🏯 [攻城戰] {war_id} 第{round_no}回合：【{att_name}】猛攻【{def_name}】，"
            f"城防 -{fort_damage}、房屋 -{house_damage}，攻方損失 {att_loss}、守方損失 {def_loss}。"
        )

    else:
        stolen_f, stolen_w, stolen_m = _war_steal(att_members, def_members, countries, max(1, att_s))
        att_loss = _war_apply_soldier_losses(
            att_members, countries, int(att_s * random.uniform(0.003, 0.015)),
            note_population_loss, "持續戰爭：掠奪戰損"
        )
        def_loss = _war_apply_soldier_losses(
            def_members, countries, int(def_s * random.uniform(0.005, 0.02)),
            note_population_loss, "持續戰爭：反掠奪戰損"
        )
        print(
            f"🔥 [戰時掠奪] {war_id} 第{round_no}回合：【{att_name}】自【{def_name}】"
            f"奪取糧:{stolen_f}/木:{stolen_w}/金:{stolen_m}。"
        )

    war["attacker_losses"] = int(war.get("attacker_losses", 0) or 0) + att_loss
    war["defender_losses"] = int(war.get("defender_losses", 0) or 0) + def_loss
    war["last_tactic"] = tactic

    # 每輪持續增加恩怨
    att_anchor = war.get("attacker_anchor")
    def_anchor = war.get("defender_anchor")
    for m in def_members:
        _war_add_hostility(countries, m, att_anchor, 4)
    for m in att_members:
        _war_add_hostility(countries, m, def_anchor, 2)

    decisive_att = def_loss > max(2, int(att_loss * 1.15)) or (tactic == "SIEGE" and fort_damage >= max(8, len(def_members) * 8))
    decisive_def = att_loss > max(2, int(def_loss * 1.15))
    if decisive_att:
        war["defender_loss_streak"] = int(war.get("defender_loss_streak", 0) or 0) + 1
        war["attacker_loss_streak"] = 0
    elif decisive_def:
        war["attacker_loss_streak"] = int(war.get("attacker_loss_streak", 0) or 0) + 1
        war["defender_loss_streak"] = 0

    cur_att = _war_effective_soldiers(
        att_members, countries, war_id, active_wars
    )
    cur_def = _war_effective_soldiers(
        def_members, countries, war_id, active_wars
    )
    att_initial = max(1, int(war.get("attacker_initial_soldiers", 1) or 1))
    def_initial = max(1, int(war.get("defender_initial_soldiers", 1) or 1))
    att_ratio = cur_att / att_initial
    def_ratio = cur_def / def_initial
    avg_fort = _war_avg_fort(def_members, countries)

    # 國都陷落：不是人口死光，而是軍事與政權崩潰。
    if (
        int(war.get("defender_loss_streak", 0) or 0) >= WARSTATE["CAPITAL_LOSS_STREAK"]
        and def_ratio <= WARSTATE["CAPITAL_SOLDIER_RATIO"]
        and avg_fort < WARSTATE["CAPITAL_FORT"]
    ):
        advantage = cur_att / max(1, cur_def)
        chance = WARSTATE["CAPITAL_CHANCE_MIN"] + min(0.20, max(0.0, advantage - 1.0) * 0.08)
        chance = _clamp(chance, WARSTATE["CAPITAL_CHANCE_MIN"], WARSTATE["CAPITAL_CHANCE_MAX"])
        if random.random() < chance:
            loser_key = war.get("defender_anchor")
            if loser_key not in def_members:
                loser_key = min(def_members, key=lambda m: countries[m].get("soldiers", 0))
            if _war_execute_capital_fall(
                loser_key,
                att_members,
                countries,
                note_population_loss,
                turn_counter,
            ):
                return {"ended": True, "winner": "ATTACKER", "reason": "國都陷落"}

    # 至少 3 回合後才允許撤軍或求和
    if round_no >= 3:
        if att_ratio <= 0.30 or int(war.get("attacker_loss_streak", 0) or 0) >= 3:
            if random.random() < 0.70:
                return {"ended": True, "winner": "DEFENDER", "reason": "進攻方攻勢耗盡撤軍"}

        if def_ratio <= 0.40 and avg_fort < 30:
            surrender_chance = 0.35 + (0.15 if def_ratio <= 0.25 else 0.0) + (0.10 if avg_fort < 15 else 0.0)
            if random.random() < min(0.65, surrender_chance):
                paid_f, paid_w, paid_m = _war_collect_reparations(
                    att_members, def_members, countries
                )
                print(
                    f"🏳️ [戰敗求和] {war_id}：【{def_name}】向【{att_name}】求和，"
                    f"支付賠款 糧:{paid_f}/木:{paid_w}/金:{paid_m}。"
                )
                return {"ended": True, "winner": "ATTACKER", "reason": "防守方戰敗求和"}

    if round_no >= int(war.get("planned_duration", WARSTATE["WAR_DURATION_MAX"]) or WARSTATE["WAR_DURATION_MAX"]):
        # 到期不再一律算和局。剩餘軍力、對手損耗、城防共同決定戰況。
        att_remaining = _clamp(att_ratio, 0.0, 1.0)
        def_remaining = _clamp(def_ratio, 0.0, 1.0)
        fort_ratio = _clamp(avg_fort / 100.0, 0.0, 1.0)

        attacker_score = (
            att_remaining * 0.50
            + (1.0 - def_remaining) * 0.25
            + (1.0 - fort_ratio) * 0.25
        )
        defender_score = (
            def_remaining * 0.50
            + (1.0 - att_remaining) * 0.25
            + fort_ratio * 0.25
        )
        gap = attacker_score - defender_score
        margin = WARSTATE["DEADLINE_DECISION_MARGIN"]

        if gap >= margin:
            return {
                "ended": True,
                "winner": "ATTACKER",
                "reason": f"期限屆滿，進攻方戰況判定勝利（{attacker_score:.2f}:{defender_score:.2f}）",
            }
        if gap <= -margin:
            return {
                "ended": True,
                "winner": "DEFENDER",
                "reason": f"期限屆滿，防守方戰況判定勝利（{defender_score:.2f}:{attacker_score:.2f}）",
            }
        return {
            "ended": True,
            "winner": None,
            "reason": f"期限屆滿，雙方戰況接近而停戰（{attacker_score:.2f}:{defender_score:.2f}）",
        }

    return {"ended": False, "winner": None, "reason": ""}


def _war_refresh_country_status(countries, active_wars):
    for c in countries.values():
        c["current_wars"] = []
        c["war_status"] = "和平"
        c["war_log_terms"] = []

    for war_id, war in active_wars.items():
        rounds = int(war.get("rounds", 0) or 0)
        duration = int(war.get("planned_duration", 0) or 0)
        for m in _war_live_members(war.get("attacker_members"), countries):
            countries[m]["current_wars"].append(war_id)
            countries[m]["war_status"] = f"進攻【{war.get('defender_name', '敵國')}】（第 {rounds}/{duration} 回合）"
            countries[m]["war_log_terms"] = list(dict.fromkeys(
                countries[m].get("war_log_terms", [])
                + [war.get("attacker_name", ""), war.get("defender_name", ""), war_id]
            ))
        for m in _war_live_members(war.get("defender_members"), countries):
            countries[m]["current_wars"].append(war_id)
            countries[m]["war_status"] = f"防禦【{war.get('attacker_name', '敵國')}】（第 {rounds}/{duration} 回合）"
            countries[m]["war_log_terms"] = list(dict.fromkeys(
                countries[m].get("war_log_terms", [])
                + [war.get("attacker_name", ""), war.get("defender_name", ""), war_id]
            ))



def thread_stat_monitor():
    """主要模擬循環線程：處理經濟、外交、戰爭、RL學習與紀錄存檔"""
    global last_sync_time, world_stage_g

    print("⚔️ 全球多維度戰局與高級 RL 模擬系統 啟動！")

    

    start_time = time.time()  # 紀錄本屆賽事開始時間
    time_total = 1000  # 每屆賽事持續時間 (秒)
    num = 100  # 初始生成國家數量
    # 反霸權聯軍：只有真正形成霸權後才允許成立。
    COALITION_MIN_MEMBERS = 3
    COALITION_MAX_MEMBERS = 7
    COALITION_MAX_ACTIVE = 2
    HEGEMON_SHARE_TRIGGER = 0.15       # 戰力佔全球 >= 15% 可視為霸權
    HEGEMON_LEAD_TRIGGER = 1.80        # 或戰力 >= 第二名 1.8 倍
    HEGEMON_REQUIRED_STREAK = 3        # 需連續維持 3 個 Game Loop
    COALITION_TARGET_POWER_RATIO = 0.95  # 聯軍達目標約 95% 戰力後停止招募
    COALITION_MAX_DURATION = 15        # 最長 15 個 Game Loop（約 30 秒）
    COALITION_COOLDOWN = 12            # 同目標/成員解散後 12 Loop 冷卻
    dead_mode = 0  # 復活模式設定 (0 代表冷卻後會以第二代/第三代復活)

    # 檔案儲存路徑定義
    countries_file = "war_live_countries.json"
    alliances_file = "war_live_alliances.json"
    q_tables_file = "rl_agents_q_tables.json"

    # V5.2 斷點續跑：
    # JSON 供程式恢復；TXT 供人工直接查看目前跑到第幾屆、幾秒。
    runtime_checkpoint_file = "亂世演算_執行進度.json"
    runtime_progress_text_file = "亂世演算_執行進度.txt"

    # 資料結構初始化
    countries = {}
    alliances = {}
    # 臨時反霸權聯軍獨立於普通 alliances。
    # coalition_name -> {target, members, created_turn, expires_turn}
    anti_hegemon_coalitions = {}
    coalition_target_cooldowns = {}
    coalition_member_cooldowns = {}
    hegemon_streaks = {}
    active_wars = {}
    war_sequence = 0
    war_truces = {}

    # 普通聯盟議會
    alliance_war_vote_cooldowns = {}
    alliance_last_war_votes = {}
    alliance_join_vote_cooldowns = {}
    alliance_last_join_votes = {}

    turn_counter = 0
    count_round = 1

    loaded_max_power = 0
    loaded_max_person = ""
    loaded_max_round = 0
    loaded_season_elapsed = 0.0
    loaded_completed_runtime_seconds = 0.0
    loaded_world_event_counter = 0
    loaded_world_mode = _world_mode_normal_state(0)
    loaded_next_world_mode_turn = random.randint(
        WORLD_MODE_FIRST_START_MIN,
        WORLD_MODE_FIRST_START_MAX,
    )
    loaded_world_mode_counter = 0

    
    TEST = 0
    # =============== TEST =============== #

    if TEST == 1:
        num = 10

    # =============== TEST =============== #


    # 讀檔邏輯：檢查是否存在先前紀錄
    is_loaded = False
    if os.path.exists(countries_file) and os.path.exists(alliances_file):
        try:
            with open(countries_file, "r", encoding="utf-8") as f_c:
                saved_countries_data = json.load(f_c)
            with open(alliances_file, "r", encoding="utf-8") as f_a:
                saved_alliances_data = json.load(f_a)

            saved_countries = saved_countries_data.get("countries", {})

            if saved_countries:
                countries = saved_countries
                # 為舊版存檔補齊可能缺失的鍵值
                for base_name, c_data in countries.items():
                    c_data.setdefault("championship_records", [])
                    c_data.setdefault("championship_count", 0)
                    c_data.setdefault("death_respawn_cooldown", 0)
                    c_data.setdefault("annexed_count", 0)
                    c_data.setdefault("infamy", 0)
                    c_data.setdefault("recent_attackers", [])
                    c_data.setdefault("fortification", 0)
                    c_data.setdefault("military_target_ratio", 0.30)
                    c_data.setdefault("last_action", "")
                    c_data.setdefault("last_reward", 0.0)
                    c_data.setdefault("ai_status", "")
                    c_data.setdefault("current_coalition", "")
                    c_data.setdefault("last_population_audit", "尚無異常人口變動")
                    c_data.setdefault("hostility", {})
                    c_data.setdefault("wars_fought", 0)
                    c_data.setdefault("wars_won", 0)
                    c_data.setdefault("wars_lost", 0)
                    c_data.setdefault("wars_drawn", 0)
                    c_data.setdefault("capital_captures", 0)

                    loaded_balance_version = int(c_data.get("balance_version", 0) or 0)
                    if loaded_balance_version < BALANCE_VERSION:
                        old_target = float(c_data.get("military_target_ratio", 0.30) or 0.30)
                        if old_target <= 0.16:
                            c_data["military_target_ratio"] = 0.30
                        c_data["balance_version"] = BALANCE_VERSION
                    c_data.setdefault("current_wars", [])
                    c_data.setdefault("war_status", "和平")
                    c_data.setdefault("war_log_terms", [])
                    c_data.setdefault("top_hostility_target", "無")
                    c_data.setdefault("famine_streak", 0)
                    c_data.setdefault("last_population_change_reason", "")
                    _ensure_dynamic_country_state(base_name, c_data)

                    # 若戰力呈現為字典格式，轉換並相容 RTS 資源欄位
                    if isinstance(c_data.get("power"), dict):
                        p_dict = c_data["power"]
                        c_data["houses"] = p_dict.get("houses", 15)
                        c_data["pop_total"] = p_dict.get("pop_total", 100)
                        c_data["farmers"] = p_dict.get("farmers", 60)
                        c_data["soldiers"] = p_dict.get("soldiers", 40)
                        c_data["food"] = p_dict.get("food", 900)
                        c_data["wood"] = p_dict.get("wood", 350)
                        c_data["metal"] = p_dict.get("metal", 220)
                        c_data["power"] = calculate_rts_power(c_data)
                    elif "houses" not in c_data:  # 預設建構 RTS 欄位
                        c_data["houses"] = 20
                        c_data["pop_total"] = 100
                        c_data["farmers"] = 60
                        c_data["soldiers"] = 40
                        c_data["food"] = 900
                        c_data["wood"] = 350
                        c_data["metal"] = 220
                        c_data["power"] = calculate_rts_power(c_data)

                    # 不論新舊存檔格式，載入後立刻校正為農夫 >= 士兵。
                    enforce_farmer_majority(c_data)
                    c_data["power"] = calculate_rts_power(c_data)

                # 讀取同盟資訊
                saved_alliance_details = saved_alliances_data.get("alliance_details", {})
                # alliance_details 也包含反霸權聯軍；讀檔時只把 ordinary alliance 放進 alliances。
                alliances = {
                    ally_name: list(details.get("members", []))
                    for ally_name, details in saved_alliance_details.items()
                    if not bool(details.get("is_coalition", False))
                }
                count_round = saved_alliances_data.get("count_round", 1)
                turn_counter = int(saved_alliances_data.get("turn_counter", 0) or 0)

                for base_name, c_data in countries.items():
                    _ensure_country_chronicle(
                        base_name,
                        c_data,
                        turn_counter,
                    )

                coalition_target_cooldowns = saved_alliances_data.get("coalition_target_cooldowns", {}) or {}
                coalition_member_cooldowns = saved_alliances_data.get("coalition_member_cooldowns", {}) or {}
                hegemon_streaks = saved_alliances_data.get("hegemon_streaks", {}) or {}
                active_wars = saved_alliances_data.get("active_wars", {}) or {}
                war_sequence = int(saved_alliances_data.get("war_sequence", 0) or 0)
                war_truces = saved_alliances_data.get("war_truces", {}) or {}
                alliance_war_vote_cooldowns = saved_alliances_data.get(
                    "alliance_war_vote_cooldowns",
                    {},
                ) or {}
                alliance_last_war_votes = saved_alliances_data.get(
                    "alliance_last_war_votes",
                    {},
                ) or {}
                alliance_join_vote_cooldowns = saved_alliances_data.get(
                    "alliance_join_vote_cooldowns",
                    {},
                ) or {}
                alliance_last_join_votes = saved_alliances_data.get(
                    "alliance_last_join_votes",
                    {},
                ) or {}
                loaded_max_power = int(saved_alliances_data.get("historical_max_power", 0) or 0)
                loaded_max_person = str(saved_alliances_data.get("historical_max_person", "") or "")
                loaded_max_round = int(saved_alliances_data.get("historical_max_round", 0) or 0)
                loaded_season_elapsed = float(
                    saved_alliances_data.get("season_elapsed_seconds", 0.0)
                    or 0.0
                )
                loaded_completed_runtime_seconds = float(
                    saved_alliances_data.get(
                        "completed_runtime_seconds",
                        max(0, int(count_round) - 1) * float(time_total),
                    )
                    or 0.0
                )
                loaded_world_event_counter = int(
                    saved_alliances_data.get("dynamic_event_counter", 0) or 0
                )
                loaded_world_mode = saved_alliances_data.get(
                    "world_mode",
                    _world_mode_normal_state(turn_counter),
                ) or _world_mode_normal_state(turn_counter)
                loaded_next_world_mode_turn = int(
                    saved_alliances_data.get(
                        "next_world_mode_turn",
                        turn_counter
                        + random.randint(
                            WORLD_MODE_FIRST_START_MIN,
                            WORLD_MODE_FIRST_START_MAX,
                        ),
                    )
                    or 0
                )
                loaded_world_mode_counter = int(
                    saved_alliances_data.get("world_mode_counter", 0) or 0
                )

                saved_coalitions = saved_alliances_data.get("anti_hegemon_coalitions", {}) or {}
                if saved_coalitions:
                    anti_hegemon_coalitions = saved_coalitions
                else:
                    # 舊存檔相容：舊版把圍剿聯盟塞進 ordinary alliances。
                    legacy_targets = saved_alliances_data.get("anti_hegemon_targets", {}) or {}
                    for legacy_name, target_id in legacy_targets.items():
                        legacy_members = list(alliances.get(legacy_name, []))
                        if legacy_members:
                            anti_hegemon_coalitions[legacy_name] = {
                                "target": target_id,
                                "members": legacy_members,
                                "created_turn": turn_counter,
                                "expires_turn": turn_counter + COALITION_MAX_DURATION,
                            }
                        # 從普通聯盟系統移除；之後 current_alliance 只代表真正外交聯盟。
                        alliances.pop(legacy_name, None)

                # 若有獨立斷點檔，而且與世界存檔屬於「同一屆、同一 turn」，
                # 就採用其中較新的秒數；否則保守忽略，避免時間與世界狀態錯位。
                if os.path.exists(runtime_checkpoint_file):
                    try:
                        with open(
                            runtime_checkpoint_file,
                            "r",
                            encoding="utf-8",
                        ) as f_cp:
                            checkpoint = json.load(f_cp)

                        cp_round = int(
                            checkpoint.get("count_round", 0) or 0
                        )
                        cp_turn = int(
                            checkpoint.get("turn_counter", -1) or -1
                        )

                        if (
                            cp_round == int(count_round)
                            and cp_turn == int(turn_counter)
                        ):
                            cp_elapsed = float(
                                checkpoint.get(
                                    "season_elapsed_seconds",
                                    0.0,
                                )
                                or 0.0
                            )
                            loaded_season_elapsed = max(
                                loaded_season_elapsed,
                                min(cp_elapsed, float(time_total)),
                            )
                            loaded_completed_runtime_seconds = max(
                                loaded_completed_runtime_seconds,
                                float(
                                    checkpoint.get(
                                        "completed_runtime_seconds",
                                        0.0,
                                    )
                                    or 0.0
                                ),
                            )
                    except Exception as cp_error:
                        print(
                            f"⚠️ [斷點讀取警告] {cp_error}；"
                            "改用主存檔中的屆次與秒數。"
                        )

                is_loaded = True
                print(
                    f"📁 [讀檔成功] 已成功載入第 {count_round} 屆資料，"
                    f"本屆已完成 {loaded_season_elapsed:.1f}/{time_total} 秒，"
                    f"共 {len(countries)} 個國家。"
                )
        except Exception as e:
            print(f"⚠️ [讀檔失敗] ({e})，準備建立新局...")

    # 若無法讀檔，則建立全新初始開局
    if not is_loaded:
            base_country_names = generate_country_names(num)  # 生成 100 個國家名稱
            for name in base_country_names:
                # pop = random.randint(80, 150)  # 隨機初始人口
                # soldiers = int(pop * 0.30)  # 平衡版：初始約 30% 軍人
    
    
                pop = 100 # 初始人口
                soldiers = 30 # 初始約 30% 軍人
                farmers = pop - soldiers # 初始農夫
    
    
                t1 = random.randint(BALANCE["START_FOOD_MIN"], BALANCE["START_FOOD_MAX"])
                t2 = random.randint(BALANCE["START_WOOD_MIN"], BALANCE["START_WOOD_MAX"])
                t3 = random.randint(BALANCE["START_METAL_MIN"], BALANCE["START_METAL_MAX"])
    
                countries[name] = {  # 設定國家初始屬性
                    "gen": 1,
                    "country_generation": 1,
                    "name_generation": 1,
                    "regime_generation": 1,
                    "generation_model_version": 3,
                    "regime_name_root": name,
                    "display_name": name,
                    # "houses": random.randint(15, 30),
                    "houses": 15,
                    "pop_total": pop,
                    "farmers": farmers,
                    "soldiers": soldiers,
                    "food": t1,
                    "wood": t2,
                    "metal": t3,
                    "power": 0,
                    "is_alive": True,
                    "annexed_count": 0,
                    "death_respawn_cooldown": 3,
                    "championship_records": [],
                    "championship_count": 0,
                    "infamy": 0,
                    "fortification": 0,
                    "military_target_ratio": 0.30,
                    "famine_streak": 0,
                    "last_population_change_reason": "",
                    "last_action": "",
                    "last_reward": 0.0,
                    "ai_status": "",
                    "current_alliance": "",
                    "current_coalition": "",
                    "last_population_audit": "尚無異常人口變動",
                    "hostility": {},
                    "wars_fought": 0,
                    "wars_won": 0,
                    "wars_lost": 0,
                    "wars_drawn": 0,
                    "capital_captures": 0,
                    "balance_version": BALANCE_VERSION,
                    "current_wars": [],
                    "war_status": "和平",
                    "war_log_terms": [],
                    "top_hostility_target": "無",
                    "recent_attackers": [],
                    # "political_stability": random.randint(72, 88),
                    "political_stability": 75,
                    "war_exhaustion": 0.0,
                    "regime_type": "正統政權",
                    "regime_history": [],
                    "regime_tenure": 0,
                    "last_regime_change_turn": -999999,
                    "regime_change_count": 0,
                    "strategic_mode": "正常發展",
                    "last_event": "無",
                    "active_events": {},
                    "event_summary": "無",
                    "chronicle_schema_version": CHRONICLE_SCHEMA_VERSION,
                    "country_chronicle": []
                }
                countries[name]["power"] = calculate_rts_power(countries[name])  # 計算戰力
                _ensure_country_chronicle(name, countries[name], 1)

    # 載入所有國家的 RL Agent
    rl_agents = load_all_agents(list(countries.keys()), file_path=q_tables_file)

    base_country_names = list(countries.keys())
    medals = [f"{i+1}." for i in range(len(base_country_names))]  # 生成排行榜名次標籤

    # 最高紀錄追蹤變數：重啟程式後延續，不再歸零。
    max_power = loaded_max_power
    max_person = loaded_max_person
    max_round = loaded_max_round

    # 已完成各屆的累積模擬秒數，不包含本屆目前已跑秒數。
    completed_runtime_seconds = loaded_completed_runtime_seconds

    if is_loaded and loaded_season_elapsed > 0:
        start_time = (
            time.time()
            - min(loaded_season_elapsed, float(time_total))
        )
        print(
            f"⏱️ [斷點續跑] 從第 {count_round} 屆 "
            f"{loaded_season_elapsed:.1f} 秒處繼續，"
            f"剩餘約 "
            f"{max(0.0, float(time_total) - loaded_season_elapsed):.1f} 秒。"
        )

    dynamic_event_counter = loaded_world_event_counter
    current_world_mode = (
        loaded_world_mode
        if isinstance(loaded_world_mode, dict)
        else _world_mode_normal_state(turn_counter)
    )
    next_world_mode_turn = int(
        loaded_next_world_mode_turn
        or (
            turn_counter
            + random.randint(
                WORLD_MODE_FIRST_START_MIN,
                WORLD_MODE_FIRST_START_MAX,
            )
        )
    )
    world_mode_counter = loaded_world_mode_counter

    # 主遊戲運行迴圈 (Game Loop)
    while True:
        # ------------------------------------------------------------
        # 人口稽核總帳：任何合法人口損失都必須登記原因。
        # ------------------------------------------------------------
        population_loop_start = {
            k: int(v.get("pop_total", 0) or 0)
            for k, v in countries.items()
            if v.get("is_alive", True)
        }
        population_loss_ledger = {}

        def note_population_loss(country_key, amount, reason):
            amount = max(0, int(amount or 0))
            if amount <= 0 or country_key not in countries:
                return
            population_loss_ledger.setdefault(country_key, []).append(
                (amount, str(reason))
            )

        # V4：先更新世界局勢，讓本輪經濟與 AI 都吃到新時代規則。
        current_world_mode, next_world_mode_turn, world_mode_changed = (
            _world_mode_advance(
                current_world_mode,
                next_world_mode_turn,
                turn_counter,
            )
        )
        if (
            world_mode_changed
            and current_world_mode.get("code") != "NORMAL"
        ):
            world_mode_counter += 1

        _apply_world_mode_modifiers(
            countries,
            current_world_mode,
            turn_counter,
        )

        # V3：再刷新單國事件倍率與政治壓力。
        for name, c_data in countries.items():
            _ensure_dynamic_country_state(name, c_data)
            _refresh_country_event_modifiers(c_data, turn_counter)
            _update_political_pressure(c_data)

        # 1. 經濟與人口產出更新（僅限存活國家）
        for name, c_data in countries.items():
            if c_data["is_alive"]:
                # 保存上一輪戰力，讓 State 的 RISING/STABLE/FALLING 真正有時間差。
                c_data["prev_power"] = c_data.get("power", 0)

                econ_pop_before = int(c_data.get("pop_total", 0) or 0)
                update_rts_economy_and_jobs(c_data)
                econ_pop_after = int(c_data.get("pop_total", 0) or 0)

                if econ_pop_after < econ_pop_before:
                    econ_loss = econ_pop_before - econ_pop_after
                    econ_reason = (
                        c_data.get("last_population_change_reason", "")
                        or "經濟階段人口減少"
                    )
                    note_population_loss(name, econ_loss, econ_reason)

                c_data["power"] = calculate_rts_power(c_data)
                _war_decay_hostility(c_data)

        # 2. 統計總戰力與存活國家排序
        total_world_power = sum(
            v["power"] for v in countries.values() if v["is_alive"]
        )
        alive_sorted = sorted(
            [k for k, v in countries.items() if v["is_alive"]],
            key=lambda k: countries[k]["power"],
            reverse=True,
        )

        top_power = countries[alive_sorted[0]]["power"] if alive_sorted else 0
        turn_counter += 1

        # V3 動態事件：每輪全世界最多一件，避免事件洗版。
        event_result = _trigger_dynamic_event(
            countries,
            alliances,
            active_wars,
            rl_agents,
            turn_counter,
            alive_sorted,
            total_world_power,
        )
        if event_result.get("triggered"):
            dynamic_event_counter += 1

        # 事件可能剛加入，立即刷新倍率，讓本輪 AI 決策就能感受到。
        for k in alive_sorted:
            _refresh_country_event_modifiers(countries[k], turn_counter)

        # 編年史：政權更替發生前，先記錄本年度舊世代的巔峰資料。
        rank_map_before_regime = {
            k: idx + 1 for idx, k in enumerate(alive_sorted)
        }
        for k in alive_sorted:
            _ensure_country_chronicle(
                k,
                countries[k],
                turn_counter,
            )
            _chronicle_update_live_stats(
                countries[k],
                turn_counter,
                rank_map_before_regime.get(k),
            )

        # 極低機率政變 / 正統繼承；國家內部 key 不變。
        _maybe_trigger_regime_change(
            countries, alliances, rl_agents, turn_counter, alive_sorted, active_wars
        )

        rank_map_v3 = {k: idx + 1 for idx, k in enumerate(alive_sorted)}
        for k in alive_sorted:
            _update_strategic_mode(
                k, countries[k], countries, rank_map_v3, total_world_power
            )
            _chronicle_update_live_stats(
                countries[k],
                turn_counter,
                rank_map_v3.get(k),
            )

        # 清除已到期的聯盟戰爭議案冷卻。
        alliance_war_vote_cooldowns = {
            key: expiry
            for key, expiry in alliance_war_vote_cooldowns.items()
            if int(expiry or 0) > turn_counter
        }

        # 清除已到期的入盟申請冷卻。
        alliance_join_vote_cooldowns = {
            key: expiry
            for key, expiry in alliance_join_vote_cooldowns.items()
            if int(expiry or 0) > turn_counter
        }

        # 清除已到期休戰條約。
        war_truces = {
            key: expiry
            for key, expiry in war_truces.items()
            if int(expiry or 0) > turn_counter
        }

        # 霸權資格需連續成立 3 Loop，避免前期排名剛好第一就立刻被圍剿。
        current_hegemon_candidate = None
        if len(alive_sorted) >= 2 and total_world_power > 0:
            first_key = alive_sorted[0]
            second_key = alive_sorted[1]
            first_power = max(0, countries[first_key]["power"])
            second_power = max(1, countries[second_key]["power"])
            first_share = first_power / total_world_power
            first_lead = first_power / second_power
            if first_share >= HEGEMON_SHARE_TRIGGER or first_lead >= HEGEMON_LEAD_TRIGGER:
                current_hegemon_candidate = first_key

        for k in list(hegemon_streaks.keys()):
            if k != current_hegemon_candidate:
                hegemon_streaks[k] = 0
        if current_hegemon_candidate:
            hegemon_streaks[current_hegemon_candidate] = hegemon_streaks.get(current_hegemon_candidate, 0) + 1

        # --------------------------------------------------------
        # 稀有「自發圍剿」窗口
        # --------------------------------------------------------
        # 即使第一名尚未達到正式霸權門檻，也有極小機率因各國恐懼其坐大，
        # 出現一次臨時牽制窗口。這只是讓「圍剿」不至於整晚完全看不到，
        # 並不保證聯軍一定能成立。
        rare_coalition_target = event_result.get("coalition_target")
        if rare_coalition_target is None:
            for _k in alive_sorted:
                _target = countries[_k].get("event_coalition_bonus_target")
                if _target in countries and countries[_target].get("is_alive", True):
                    rare_coalition_target = _target
                    break

        if (
            len(alive_sorted) >= 4
            and total_world_power > 0
            and not anti_hegemon_coalitions
        ):
            first_key = alive_sorted[0]
            second_key = alive_sorted[1]
            first_power = max(
                0,
                countries[first_key].get("power", 0),
            )
            second_power = max(
                1,
                countries[second_key].get("power", 0),
            )
            first_share = first_power / total_world_power
            first_lead = first_power / second_power

            modest_threat = (
                first_share >= 0.06
                or first_lead >= 1.20
            )

            if (
                rare_coalition_target is None
                and modest_threat
                and random.random() < 0.02
            ):
                rare_coalition_target = first_key

        # 3. 普通聯盟瓦解與分裂檢測機制（反霸權聯軍不在 alliances，因此不受此規則影響）
        alliances_to_remove = []
        for ally_name, members in list(alliances.items()):
            alive_m = [m for m in members if countries[m]["is_alive"]]
            ally_power = sum(countries[m]["power"] for m in alive_m)
            HEGEMON_DISBAND_THRESHOLD = 0.12  # 單國戰力佔比 >= 12% 才觸發普通聯盟霸權瓦解，避免聯盟過早解散

            for m in alive_m:
                pwr = countries[m]["power"]
                is_overpowered = (
                    total_world_power > 0
                    and (pwr / total_world_power) >= HEGEMON_DISBAND_THRESHOLD
                )

                if is_overpowered:
                    print(
                        f"[霸權瓦解] 【{countries[m]['display_name']}】戰力佔比達 {pwr/total_world_power:.1%}！【{ally_name}】過於龐大自動瓦解！"
                    )
                    alliances_to_remove.append(ally_name)
                    break

            # 普通同盟整體過強時仍可能內鬥；臨時反霸權聯軍不走這個資料結構。
            if ally_name not in alliances_to_remove:
                if ally_power > total_world_power * 0.28 or (
                    total_world_power > 0
                    and (ally_power / total_world_power) >= 0.5
                ):
                    print(f"[聯盟分裂] 【{ally_name}】 勢力過大引發內鬥解散！")
                    alliances_to_remove.append(ally_name)

        # 執行刪除過大同盟
        for ally_n in set(alliances_to_remove):
            if ally_n in alliances:
                del alliances[ally_n]

        # 政權滅亡即視為舊盟約失效：死亡國家先移出名單。
        # 新世代重生後必須重新外交，不會自動回到前朝聯盟。
        cleaned_alliances = {}
        for ally_name, members in alliances.items():
            live_members = [
                m for m in members
                if m in countries and countries[m].get("is_alive", True)
            ]
            live_members = list(dict.fromkeys(live_members))
            if len(live_members) >= 2:
                cleaned_alliances[ally_name] = live_members
        alliances = cleaned_alliances

        # 更新各國普通聯盟與臨時聯軍狀態。兩者可以同時存在。
        for k in countries:
            countries[k]["current_alliance"] = get_country_alliance(k, alliances)
            countries[k]["current_coalition"] = get_country_coalition(k, anti_hegemon_coalitions)

        # 4. 觸發全球隨機事件
        event_name, event_type, event_msg = trigger_global_event()
        if event_msg:
            print(event_msg)
            if event_type == "BOOM":  # 大發掘：全體獲取物資
                for k in alive_sorted:
                    pop_ref = max(1, countries[k]["pop_total"])
                    countries[k]["metal"] += random.randint(
                        max(20, int(pop_ref * 0.25)),
                        max(30, int(pop_ref * 0.55)),
                    )
                    countries[k]["food"] += random.randint(
                        max(50, int(pop_ref * 0.70)),
                        max(80, int(pop_ref * 1.20)),
                    )
            elif event_type == "DISASTER":  # 隕石浩劫：全體損失人口與資源
                for k in alive_sorted:
                    old_pop = max(1, countries[k]["pop_total"])
                    new_pop = max(1, int(old_pop * 0.85))
                    survival_ratio = new_pop / old_pop
                    disaster_loss = max(0, old_pop - new_pop)

                    note_population_loss(k, disaster_loss, "全球事件：隕石浩劫")
                    print(
                        f"☄️ [人口變動]【{countries[k].get('display_name', k)}】"
                        f"受隕石浩劫影響，人口 {old_pop} → {new_pop}（-{disaster_loss}）。"
                    )

                    # 人口災害同步縮減職業人口，不能只改 pop_total 留下非法軍民數字。
                    countries[k]["pop_total"] = new_pop
                    countries[k]["soldiers"] = int(countries[k]["soldiers"] * survival_ratio)
                    countries[k]["farmers"] = int(countries[k]["farmers"] * survival_ratio)
                    enforce_farmer_majority(countries[k])
                    countries[k]["fortification"] = int(countries[k].get("fortification", 0) * 0.85)
                    countries[k]["power"] = calculate_rts_power(countries[k])
                    countries[k]["food"] = int(countries[k]["food"] * 0.85)
                    countries[k]["wood"] = int(countries[k]["wood"] * 0.90)
                    countries[k]["metal"] = int(countries[k]["metal"] * 0.90)

        # ============================================================
        # 5. 戰國模式：持續戰爭階段
        # ============================================================
        for war_id in list(active_wars.keys()):
            war = active_wars.get(war_id)
            if not isinstance(war, dict):
                active_wars.pop(war_id, None)
                continue

            result = resolve_persistent_war_round(
                war_id,
                war,
                countries,
                active_wars,
                turn_counter,
                note_population_loss,
            )

            if result.get("ended"):
                winner_side = result.get("winner")
                att_members = list(war.get("attacker_members") or [])
                def_members = list(war.get("defender_members") or [])

                if winner_side == "ATTACKER":
                    for m in att_members:
                        if m in countries:
                            countries[m]["wars_won"] = int(countries[m].get("wars_won", 0) or 0) + 1
                            countries[m]["political_stability"] = _clamp(countries[m].get("political_stability", 75) + 3, 0, 100)
                            countries[m]["war_exhaustion"] = _clamp(countries[m].get("war_exhaustion", 0) - 4, 0, 100)
                    for m in def_members:
                        if m in countries:
                            countries[m]["wars_lost"] = int(countries[m].get("wars_lost", 0) or 0) + 1
                            countries[m]["political_stability"] = _clamp(countries[m].get("political_stability", 75) - 4, 0, 100)
                    _maybe_trigger_war_hero(att_members, countries, turn_counter)
                elif winner_side == "DEFENDER":
                    for m in def_members:
                        if m in countries:
                            countries[m]["wars_won"] = int(countries[m].get("wars_won", 0) or 0) + 1
                            countries[m]["political_stability"] = _clamp(countries[m].get("political_stability", 75) + 3, 0, 100)
                            countries[m]["war_exhaustion"] = _clamp(countries[m].get("war_exhaustion", 0) - 4, 0, 100)
                    for m in att_members:
                        if m in countries:
                            countries[m]["wars_lost"] = int(countries[m].get("wars_lost", 0) or 0) + 1
                            countries[m]["political_stability"] = _clamp(countries[m].get("political_stability", 75) - 4, 0, 100)
                    _maybe_trigger_war_hero(def_members, countries, turn_counter)
                else:
                    for m in set(att_members + def_members):
                        if m in countries:
                            countries[m]["wars_drawn"] = int(countries[m].get("wars_drawn", 0) or 0) + 1
                            countries[m]["war_exhaustion"] = _clamp(countries[m].get("war_exhaustion", 0) - 2, 0, 100)

                _war_set_truce_between_sides(
                    att_members, def_members, war_truces, turn_counter
                )
                print(
                    f"📜 [戰爭結算] {war_id}：【{war.get('attacker_name', '進攻方')}】"
                    f" vs 【{war.get('defender_name', '防守方')}】結束；原因：{result.get('reason', '停戰')}；"
                    f"休戰 {_world_mode_current_truce_turns()} 回合。"
                )
                active_wars.pop(war_id, None)

        _war_refresh_country_status(countries, active_wars)

        # 持續戰爭可能改變軍力與存亡，主動決策前重算排名。
        total_world_power = sum(
            v["power"] for v in countries.values() if v.get("is_alive", True)
        )
        alive_sorted = sorted(
            [k for k, v in countries.items() if v.get("is_alive", True)],
            key=lambda k: countries[k]["power"],
            reverse=True,
        )
        top_power = countries[alive_sorted[0]]["power"] if alive_sorted else 0

        # 6. 主行動階段：RL Agent 決策與執行行動
        if len(alive_sorted) >= 2:
            # 戰國模式：100 國世界每輪約 10~18 國採取主動決策。
            active_countries = random.sample(
                alive_sorted,
                min(
                    random.randint(
                        WARSTATE["ACTIVE_COUNTRIES_MIN"],
                        WARSTATE["ACTIVE_COUNTRIES_MAX"],
                    ),
                    len(alive_sorted),
                ),
            )

            attacked_this_round = set()  # 本輪已承受新宣戰的國家
            acted_this_round = set()  # 本輪已採取過行動的國家

            for attacker_key in active_countries:
                c_data = countries[attacker_key]
                if not c_data["is_alive"]:  # 防護檢查
                    continue

                # RL 必須保留「行動前」快照；不能把同一份已修改 dict 同時當 state 與 next_state。
                before_data = _rl_snapshot(c_data)
                prev_power = c_data["power"]
                prev_annexed = c_data["annexed_count"]
                action_success = False
                action_value = 0.0

                agent = rl_agents[attacker_key]

                # 限制 1：如果該國本輪已經動過，或是本輪已經被打了，就不能再當攻擊方
                if (
                    attacker_key in acted_this_round
                    or attacker_key in attacked_this_round
                ):
                    continue

                # 標記此國家本輪已行動
                acted_this_round.add(attacker_key)

                valid_actions = get_valid_rl_actions(
                    attacker_key, countries, alliances, anti_hegemon_coalitions, alive_sorted
                )

                # 雙線作戰：
                # - 已有 1 場正式戰爭：仍可選 Action 0 再開第二戰線，
                #   但不在戰時另結盟、另組反霸權聯軍、背叛或邊境襲擾。
                # - 已有 2 場：禁止第三戰線。
                current_war_count = _war_country_war_count(
                    attacker_key, active_wars
                )

                if current_war_count >= WARSTATE["MAX_ACTIVE_WARS_PER_COUNTRY"]:
                    valid_actions = [
                        a for a in valid_actions
                        if a not in (0, 1, 2, 4, 10)
                    ]
                elif current_war_count == 1:
                    valid_actions = [
                        a for a in valid_actions
                        if a not in (1, 2, 4, 10)
                    ]

                exhaustion_now = float(c_data.get("war_exhaustion", 0) or 0)
                if exhaustion_now >= 88:
                    valid_actions = [a for a in valid_actions if a not in (0, 4, 10)]
                elif exhaustion_now >= 72 and 0 in valid_actions and random.random() < 0.60:
                    valid_actions.remove(0)

                if not valid_actions:
                    valid_actions = [3, 5, 6, 7, 8, 11]

                # Action 2 只有在「真正霸權 + 連續 3 Loop + 無冷卻 + 本國未參加其他聯軍」時才開放。
                if 2 in valid_actions:
                    hegemon_key_for_mask = alive_sorted[0] if alive_sorted else None
                    coalition_action_ready = bool(
                        hegemon_key_for_mask
                        and hegemon_key_for_mask != attacker_key
                        and (
                            hegemon_streaks.get(
                                hegemon_key_for_mask, 0
                            )
                            >= HEGEMON_REQUIRED_STREAK
                            or hegemon_key_for_mask
                            == rare_coalition_target
                        )
                        and int(coalition_target_cooldowns.get(hegemon_key_for_mask, 0) or 0) <= turn_counter
                        and int(coalition_member_cooldowns.get(attacker_key, 0) or 0) <= turn_counter
                        and not get_country_coalition(attacker_key, anti_hegemon_coalitions)
                        and not any(
                            isinstance(info, dict) and info.get("target") == hegemon_key_for_mask
                            for info in anti_hegemon_coalitions.values()
                        )
                    )
                    if not coalition_action_ready:
                        valid_actions.remove(2)

                action = agent.choose_action(
                    c_data,
                    total_world_power,
                    top_power,
                    len(alive_sorted),
                    valid_actions=valid_actions,
                )

                # ----------------------------------------------------
                # Action 0: 發動戰爭
                # ----------------------------------------------------
                

                if action == 0:
                    # 平常戰爭仍使用普通聯盟；若本國正在參加反霸權聯軍，
                    # 且本次決定執行共同討伐，則只動員聯軍成員，不拖普通盟友下水。
                    coalition_name = get_country_coalition(attacker_key, anti_hegemon_coalitions)
                    coalition_info = anti_hegemon_coalitions.get(coalition_name, {}) if coalition_name else {}
                    coalition_target = coalition_info.get("target") if isinstance(coalition_info, dict) else None
                    use_coalition_force = False

                    normal_att_entity = get_entity_info(attacker_key, countries, alliances)

                    if (
                        normal_att_entity.get("type") == "ALLIANCE"
                        and random.random()
                        < float(c_data.get("world_single_war_chance", 0.0) or 0.0)
                    ):
                        normal_att_entity = {
                            "type": "SINGLE",
                            "name": c_data.get("display_name", attacker_key),
                            "members": [attacker_key],
                            "power": c_data.get("power", 0),
                        }

                    attacker_ordinary_alliance = get_country_alliance(
                        attacker_key,
                        alliances,
                    )
                    protected_allied_members = set(
                        alliances.get(
                            attacker_ordinary_alliance,
                            [],
                        )
                    )

                    possible_defenders = [
                        k for k in alive_sorted
                        if k != attacker_key
                        and k not in protected_allied_members
                        and countries[k]["is_alive"]
                        and k not in attacked_this_round
                        and _war_country_can_join_new_war(k, active_wars)
                        and not _war_countries_share_war(
                            attacker_key, k, active_wars
                        )
                        and not _war_is_truce(
                            attacker_key, k, war_truces, turn_counter
                        )
                    ]

                    if possible_defenders:
                        action_success = True
                        defender_key = None

                        # 聯軍成員約 70% 的全面戰爭會優先履行共同討伐任務。
                        if (
                            coalition_target
                            and coalition_target in possible_defenders
                            and countries.get(coalition_target, {}).get("is_alive", False)
                            and random.random() < 0.70
                        ):
                            defender_key = coalition_target
                            use_coalition_force = True

                        if not defender_key:
                            # 15% 保留不可預測性；其餘依恩怨、復仇、弱點與資源價值選敵。
                            if random.random() < 0.15:
                                defender_key = random.choice(possible_defenders)
                            else:
                                my_power = max(1, c_data.get("power", 0))
                                hostility_map = c_data.get("hostility", {}) or {}
                                recent_attackers = set(c_data.get("recent_attackers", []) or [])

                                def war_target_score(k):
                                    d = countries[k]
                                    target_power = max(1, d.get("power", 0))
                                    hostility = float(hostility_map.get(k, 0) or 0)
                                    revenge = 28.0 if k in recent_attackers else 0.0
                                    weakness = max(0.0, 1.0 - target_power / my_power)
                                    resources = (
                                        d.get("food", 0)
                                        + d.get("wood", 0) * 1.2
                                        + d.get("metal", 0) * 2.0
                                    )
                                    resource_bonus = min(
                                        18.0,
                                        resources
                                        / max(target_power, 300)
                                        * 0.8,
                                    )

                                    # 「肥羊」判定：
                                    # 軍事人口很低、資源多、又沒有普通聯盟保護時，
                                    # 對投機型/好戰型國家更有吸引力。
                                    target_pop = max(
                                        1,
                                        int(d.get("pop_total", 1) or 1),
                                    )
                                    target_soldiers = max(
                                        0,
                                        int(d.get("soldiers", 0) or 0),
                                    )
                                    target_military_ratio = (
                                        target_soldiers / target_pop
                                    )
                                    target_wealth_pc = (
                                        resources / target_pop
                                    )

                                    fat_sheep_bonus = 0.0
                                    if target_military_ratio < 0.08:
                                        fat_sheep_bonus += 42.0
                                    elif target_military_ratio < 0.12:
                                        fat_sheep_bonus += 30.0
                                    elif target_military_ratio < 0.16:
                                        fat_sheep_bonus += 16.0

                                    fat_sheep_bonus += min(
                                        18.0,
                                        max(
                                            0.0,
                                            (target_wealth_pc - 10.0)
                                            * 0.65,
                                        ),
                                    )

                                    if not d.get("current_alliance"):
                                        fat_sheep_bonus += 8.0

                                    fat_sheep_bonus *= float(
                                        c_data.get("world_fat_sheep_bias", 1.0) or 1.0
                                    )

                                    event_target_bonus = 0.0
                                    if c_data.get("event_war_target") == k:
                                        event_target_bonus = 30.0

                                    score = hostility * 2.0 + revenge + event_target_bonus
                                    if agent.personality_type == "OPPORTUNIST":
                                        score += (
                                            weakness * 35.0
                                            + resource_bonus
                                            + fat_sheep_bonus
                                        )
                                    elif agent.personality_type == "WARMONGER":
                                        score += (
                                            12.0
                                            + weakness * 18.0
                                            + fat_sheep_bonus * 0.60
                                        )
                                    else:
                                        # 和平主義仍不太主動獵殺肥羊。
                                        score += (
                                            hostility * 0.8
                                            + weakness * 8.0
                                            + fat_sheep_bonus * 0.10
                                        )

                                    return score + random.uniform(0.0, 6.0)

                                defender_key = max(possible_defenders, key=war_target_score)

                        att_entity = (
                            get_coalition_entity(
                                coalition_name,
                                anti_hegemon_coalitions,
                                countries,
                            )
                            if use_coalition_force
                            else normal_att_entity
                        )
                        def_entity = get_entity_info(
                            defender_key, countries, alliances
                        )

                        # 防守聯盟改採逐國「共同防禦表態」，
                        # 不再用隨機方式把整個聯盟直接拖入或排除。

                        # ------------------------------------------------
                        # V5 普通聯盟議會
                        # ------------------------------------------------
                        offensive_vote = None
                        defensive_vote = None

                        # 普通聯盟主動發戰：先提案、再表決。
                        # 反霸權聯軍本身為自願軍事組織，不重複投票。
                        if (
                            att_entity.get("type") == "ALLIANCE"
                            and not use_coalition_force
                        ):
                            attacking_alliance = att_entity.get("name", "")
                            vote_cd_key = _alliance_vote_cooldown_key(
                                attacking_alliance,
                                defender_key,
                                countries,
                                alliances,
                            )
                            vote_cd_expiry = int(
                                alliance_war_vote_cooldowns.get(
                                    vote_cd_key,
                                    0,
                                )
                                or 0
                            )

                            if vote_cd_expiry > turn_counter:
                                wait_turns = vote_cd_expiry - turn_counter
                                print(
                                    f"⏳ [聯盟戰爭議案冷卻] {attacking_alliance} "
                                    f"近期已否決對【{def_entity.get('name', defender_key)}】的戰爭提案，"
                                    f"約 {wait_turns} 回合後才能再次表決。"
                                )
                                _finalize_rejected_war_action(
                                    agent,
                                    c_data,
                                    before_data,
                                    action,
                                    -4.0,
                                    total_world_power,
                                    top_power,
                                    len(alive_sorted),
                                )
                                continue

                            offensive_vote = _alliance_offensive_war_vote(
                                attacking_alliance,
                                attacker_key,
                                defender_key,
                                countries,
                                alliances,
                                rl_agents,
                                active_wars,
                                turn_counter,
                            )
                            alliance_last_war_votes[
                                attacking_alliance
                            ] = offensive_vote

                            if not offensive_vote.get("passed", False):
                                cooldown_turns = random.randint(
                                    ALLIANCE_WAR_VOTE_COOLDOWN_MIN,
                                    ALLIANCE_WAR_VOTE_COOLDOWN_MAX,
                                )
                                alliance_war_vote_cooldowns[
                                    vote_cd_key
                                ] = turn_counter + cooldown_turns

                                print(
                                    f"⏳ [戰爭提案否決] {attacking_alliance} "
                                    f"對同一目標 {cooldown_turns} 回合內不得重新提案。"
                                )
                                _finalize_rejected_war_action(
                                    agent,
                                    c_data,
                                    before_data,
                                    action,
                                    -2.0,
                                    total_world_power,
                                    top_power,
                                    len(alive_sorted),
                                )
                                continue

                            # 只有投贊成票的盟員成為本次進攻方。
                            att_entity = dict(att_entity)
                            att_entity["members"] = list(
                                offensive_vote.get(
                                    "participants",
                                    [],
                                )
                            )

                        # 被打的普通聯盟：被攻擊國必定自衛；
                        # 其餘盟員逐國決定是否支援。
                        if def_entity.get("type") == "ALLIANCE":
                            defending_alliance = def_entity.get("name", "")
                            defensive_vote = _alliance_defensive_support_vote(
                                defending_alliance,
                                defender_key,
                                attacker_key,
                                countries,
                                alliances,
                                rl_agents,
                                active_wars,
                                turn_counter,
                            )
                            alliance_last_war_votes[
                                defending_alliance
                            ] = defensive_vote

                            def_entity = dict(def_entity)
                            def_entity["members"] = list(
                                defensive_vote.get(
                                    "participants",
                                    [defender_key],
                                )
                            )

                        # 已經同時打滿 2 場的成員仍不加入新戰線。
                        att_entity = dict(att_entity)
                        def_entity = dict(def_entity)

                        att_entity["members"] = _war_filter_members_for_new_front(
                            att_entity.get("members", []),
                            active_wars,
                        )
                        def_entity["members"] = _war_filter_members_for_new_front(
                            def_entity.get("members", []),
                            active_wars,
                        )

                        # 主動宣戰國與被宣戰國本身必須仍有戰線名額。
                        if (
                            attacker_key not in att_entity["members"]
                            or defender_key not in def_entity["members"]
                        ):
                            action_success = False
                            print(
                                f"⛔ [宣戰取消]【{countries[attacker_key].get('display_name', attacker_key)}】"
                                f"或【{countries[defender_key].get('display_name', defender_key)}】"
                                f"已達 {WARSTATE['MAX_ACTIVE_WARS_PER_COUNTRY']} 條戰線上限。"
                            )
                            continue

                        att_entity["power"] = sum(
                            countries[m].get("power", 0)
                            for m in att_entity["members"]
                            if m in countries
                        )
                        def_entity["power"] = sum(
                            countries[m].get("power", 0)
                            for m in def_entity["members"]
                            if m in countries
                        )

                        # 一個戰鬥實體（單國或整個聯盟）本輪只承受一次主戰攻擊。
                        attacked_this_round.update(def_entity["members"])

                        # 紀錄仇恨清單 (最近攻擊者)
                        for dm in def_entity["members"]:
                            if attacker_key not in countries[dm].get("recent_attackers", []):
                                countries[dm].setdefault("recent_attackers", []).append(attacker_key)
                                countries[dm]["recent_attackers"] = countries[dm]["recent_attackers"][-5:]

                        def_pwr = def_entity["power"]
                        att_pwr = att_entity["power"]

                        # 被打者與盟友累積恩怨。
                        for dm in def_entity["members"]:
                            _war_add_hostility(
                                countries, dm, attacker_key, WARSTATE["HOSTILITY_ATTACK"]
                            )
                            ally_name = get_country_alliance(dm, alliances)
                            if ally_name:
                                for ally_m in alliances.get(ally_name, []):
                                    if (
                                        ally_m != dm
                                        and countries.get(ally_m, {}).get("is_alive", False)
                                    ):
                                        _war_add_hostility(
                                            countries,
                                            ally_m,
                                            attacker_key,
                                            WARSTATE["HOSTILITY_ALLY_ATTACK"],
                                        )
                        for am in att_entity["members"]:
                            _war_add_hostility(countries, am, defender_key, 8)

                        # 正式宣戰後建立 3~8 回合的持續戰爭。
                        # 只禁止「同一對交戰國」重複建立戰爭；
                        # 若雙方各自在別處已有一場戰爭，仍可形成第二戰線。
                        existing_conflict = (
                            "已有相同交戰"
                            if _war_countries_share_war(
                                attacker_key,
                                defender_key,
                                active_wars,
                            )
                            else None
                        )

                        if existing_conflict is None:
                            war_sequence += 1
                            war_id = f"W{war_sequence:05d}"
                            active_wars[war_id] = {
                                "attacker_anchor": attacker_key,
                                "defender_anchor": defender_key,
                                "attacker_members": list(dict.fromkeys(att_entity["members"])),
                                "defender_members": list(dict.fromkeys(def_entity["members"])),
                                "attacker_name": att_entity["name"],
                                "defender_name": def_entity["name"],
                                "started_turn": turn_counter,
                                "last_turn": turn_counter,
                                "planned_duration": random.randint(
                                    WARSTATE["WAR_DURATION_MIN"],
                                    WARSTATE["WAR_DURATION_MAX"],
                                ),
                                "rounds": 0,
                                "attacker_initial_soldiers": sum(
                                    countries[x].get("soldiers", 0)
                                    for x in att_entity["members"]
                                    if x in countries and countries[x].get("is_alive", True)
                                ),
                                "defender_initial_soldiers": sum(
                                    countries[x].get("soldiers", 0)
                                    for x in def_entity["members"]
                                    if x in countries and countries[x].get("is_alive", True)
                                ),
                                "attacker_losses": 0,
                                "defender_losses": 0,
                                "attacker_loss_streak": 0,
                                "defender_loss_streak": 0,
                                "last_tactic": "宣戰",
                                "attacker_vote": (
                                    {
                                        "alliance": offensive_vote.get("alliance"),
                                        "yes": offensive_vote.get("yes", 0),
                                        "no": offensive_vote.get("no", 0),
                                        "abstain": offensive_vote.get("abstain", 0),
                                        "yes_weight": offensive_vote.get("yes_weight", 0),
                                        "no_weight": offensive_vote.get("no_weight", 0),
                                        "abstain_weight": offensive_vote.get("abstain_weight", 0),
                                        "total_weight": offensive_vote.get("total_weight", 0),
                                        "threshold": offensive_vote.get("threshold", 0),
                                        "threshold_weight": offensive_vote.get("threshold_weight", offensive_vote.get("threshold", 0)),
                                        "result": offensive_vote.get("result", ""),
                                    }
                                    if isinstance(offensive_vote, dict)
                                    else None
                                ),
                                "defender_support": (
                                    {
                                        "alliance": defensive_vote.get("alliance"),
                                        "yes": defensive_vote.get("yes", 0),
                                        "no": defensive_vote.get("no", 0),
                                        "result": defensive_vote.get("result", ""),
                                    }
                                    if isinstance(defensive_vote, dict)
                                    else None
                                ),
                            }
                            for x in set(att_entity["members"] + def_entity["members"]):
                                if x in countries:
                                    countries[x]["wars_fought"] = int(
                                        countries[x].get("wars_fought", 0) or 0
                                    ) + 1
                                    countries[x]["war_exhaustion"] = float(
                                        _clamp(float(countries[x].get("war_exhaustion", 0) or 0) + 4.0, 0, 100)
                                    )
                            attacker_front_no = _war_front_number(
                                attacker_key, war_id, active_wars
                            )
                            defender_front_no = _war_front_number(
                                defender_key, war_id, active_wars
                            )

                            front_note = ""
                            if attacker_front_no >= 2 or defender_front_no >= 2:
                                front_note = (
                                    f"（雙線作戰：攻方第 {attacker_front_no} 戰線／"
                                    f"守方第 {defender_front_no} 戰線）"
                                )

                            print(
                                f"📯 [正式宣戰] {war_id}：【{att_entity['name']}】向【{def_entity['name']}】宣戰！"
                                f"預定持續 {active_wars[war_id]['planned_duration']} 回合。"
                                f"{front_note}"
                            )

                        # 戰國模式：新宣戰至少先打一場；第 3 回合後才可能撤軍、求和或投降。

                        # 進行真實開戰交鋒計算
                        # att_luck = 1.3 if random.random() < 0.15 else random.uniform(0.15, 0.25)  # 隨機戰術運氣係數
                        # def_luck = 1.3 if random.random() < 0.15 else random.uniform(0.15, 0.25)

                        # att_total_dmg = int(def_entity["power"] * att_luck)  # 防守方造成的傷害
                        # def_total_dmg = int(att_entity["power"] * def_luck)  # 攻擊方造成的傷害

                        war_tactics = random.choices(
                            [0, 1, 2],
                            weights=[
                                WARSTATE["SIEGE_WEIGHT"],
                                WARSTATE["BATTLE_WEIGHT"],
                                WARSTATE["RAID_WEIGHT"],
                            ],
                            k=1,
                        )[0]  # 0:攻城, 1:會戰, 2:掠奪

                        # 各參戰國只動員約 45~65% 現役軍，補給也各自支付。
                        att_deployments = {}
                        total_war_food_cost = 0
                        total_war_metal_cost = 0

                        for m in att_entity["members"]:
                            if not countries[m].get("is_alive", True):
                                continue

                            available = max(0, int(countries[m].get("soldiers", 0)))
                            if available <= 0:
                                continue

                            front_no = _war_front_number(
                                m, war_id, active_wars
                            )
                            front_force_multiplier = (
                                WARSTATE["SECOND_FRONT_FORCE_MULTIPLIER"]
                                if front_no >= 2
                                else 1.0
                            )

                            intended = max(
                                1,
                                int(
                                    available
                                    * random.uniform(
                                        BALANCE["WAR_DEPLOY_MIN"],
                                        BALANCE["WAR_DEPLOY_MAX"],
                                    )
                                    * front_force_multiplier
                                ),
                            )

                            food_rate = BALANCE["WAR_FOOD_PER_SOLDIER"]
                            metal_rate = BALANCE["WAR_METAL_PER_SOLDIER"]

                            if front_no >= 2:
                                food_rate *= WARSTATE[
                                    "SECOND_FRONT_INITIAL_FOOD_MULTIPLIER"
                                ]
                                metal_rate *= WARSTATE[
                                    "SECOND_FRONT_INITIAL_METAL_MULTIPLIER"
                                ]

                            max_by_food = int(
                                countries[m].get("food", 0)
                                // max(0.01, food_rate)
                            )
                            max_by_metal = int(
                                countries[m].get("metal", 0)
                                // max(0.01, metal_rate)
                            )
                            deployed = min(
                                intended,
                                max_by_food,
                                max_by_metal,
                            )

                            if deployed <= 0:
                                continue

                            food_cost_m = int(
                                math.ceil(deployed * food_rate)
                            )
                            metal_cost_m = int(
                                math.ceil(deployed * metal_rate)
                            )
                            countries[m]["food"] = max(0, countries[m]["food"] - food_cost_m)
                            countries[m]["metal"] = max(0, countries[m]["metal"] - metal_cost_m)

                            att_deployments[m] = deployed
                            total_war_food_cost += food_cost_m
                            total_war_metal_cost += metal_cost_m

                        att_soldiers = sum(att_deployments.values())
                        if att_soldiers <= 0:
                            action_success = False
                            # 若宣戰後才發現連第一波遠征軍都湊不出來，取消剛建立的戰爭。
                            for wid, w in list(active_wars.items()):
                                if (
                                    w.get("attacker_anchor") == attacker_key
                                    and w.get("defender_anchor") == defender_key
                                    and int(w.get("started_turn", -1)) == turn_counter
                                    and int(w.get("rounds", 0) or 0) == 0
                                ):
                                    active_wars.pop(wid, None)
                            print(f"[出兵取消]【{att_entity['name']}】補給不足，無法組織有效遠征軍，宣戰取消。")
                            continue

                        def apply_attacker_losses(loss_count):
                            """把攻方傷亡按各國尚在前線的兵力比例分攤。"""
                            nonlocal att_soldiers
                            loss_count = min(max(0, int(loss_count)), att_soldiers)
                            if loss_count <= 0 or not att_deployments:
                                return 0

                            original_front = max(1, sum(att_deployments.values()))
                            remaining = loss_count
                            members = list(att_deployments.keys())

                            for idx, m in enumerate(members):
                                if remaining <= 0:
                                    break
                                if idx == len(members) - 1:
                                    share = remaining
                                else:
                                    share = int(
                                        round(
                                            loss_count
                                            * att_deployments[m]
                                            / original_front
                                        )
                                    )
                                    share = min(share, remaining)

                                actual = min(
                                    share,
                                    att_deployments[m],
                                    countries[m].get("soldiers", 0),
                                )
                                countries[m]["soldiers"] -= actual
                                countries[m]["pop_total"] = (
                                    countries[m].get("farmers", 0)
                                    + countries[m]["soldiers"]
                                )
                                note_population_loss(m, actual, "戰鬥：攻方士兵傷亡")
                                att_deployments[m] -= actual
                                enforce_farmer_majority(countries[m])
                                countries[m]["power"] = calculate_rts_power(countries[m])
                                remaining -= actual

                            if remaining > 0:
                                for m in members:
                                    if remaining <= 0:
                                        break
                                    actual = min(
                                        remaining,
                                        att_deployments[m],
                                        countries[m].get("soldiers", 0),
                                    )
                                    countries[m]["soldiers"] -= actual
                                    countries[m]["pop_total"] = (
                                        countries[m].get("farmers", 0)
                                        + countries[m]["soldiers"]
                                    )
                                    note_population_loss(m, actual, "戰鬥：攻方士兵傷亡")
                                    att_deployments[m] -= actual
                                    enforce_farmer_majority(countries[m])
                                    countries[m]["power"] = calculate_rts_power(countries[m])
                                    remaining -= actual

                            applied = loss_count - remaining
                            att_soldiers = max(0, sum(att_deployments.values()))
                            return applied

                        print(
                            f"[出兵征戰]【{att_entity['name']}】實際出征 {att_soldiers} 人，"
                            f"消耗 {total_war_food_cost} 糧草與 {total_war_metal_cost} 兵器。"
                        )

                        # war_tactics = 2

                        if war_tactics == 0:  # 戰術 0：攻城
                            max_destroy_limit = max(1, att_soldiers // 25)
                            total_destroyed = 0
                            total_fort_damage = 0

                            for def_m in def_entity["members"]:
                                houses_now = max(
                                    1,
                                    int(
                                        countries[def_m].get(
                                            "houses", 1
                                        )
                                        or 1
                                    ),
                                )
                                pct_destroy = max(
                                    1,
                                    int(
                                        houses_now
                                        * random.uniform(0.020, 0.050)
                                    ),
                                )
                                random_destroy = random.randint(
                                    1,
                                    max(
                                        1,
                                        min(20, max_destroy_limit),
                                    ),
                                )
                                destroyed = min(
                                    max(0, houses_now - 1),
                                    20,
                                    max(
                                        pct_destroy,
                                        random_destroy,
                                    ),
                                )
                                countries[def_m]["houses"] = max(
                                    1, countries[def_m]["houses"] - destroyed
                                )
                                total_destroyed += destroyed

                                old_fort = int(_clamp(countries[def_m].get("fortification", 0), 0, 100))
                                fort_damage = min(
                                    old_fort,
                                    random.randint(
                                        WARSTATE["FORT_SIEGE_MIN"],
                                        WARSTATE["FORT_SIEGE_MAX"],
                                    ),
                                )
                                countries[def_m]["fortification"] = max(0, old_fort - fort_damage)
                                total_fort_damage += fort_damage

                            action_value += total_destroyed * 12 + total_fort_damage * 2
                            print(
                                f"🏯 [攻城戰] 【{att_entity['name']}】投入 {att_soldiers} 兵力猛攻"
                                f"【{def_entity['name']}】，摧毀 {total_destroyed} 棟房屋、城防 -{total_fort_damage}！"
                            )

                        elif war_tactics == 1:  # 戰術 1：雙方兵力交鋒 (優先消耗士兵)
                            total_kills = 0
                            total_att_losses = 0
                            total_soldier_kills = 0
                            total_farmer_kills = 0

                            for def_m in def_entity["members"]:
                                raw_def_soldiers = countries[def_m]["soldiers"]
                                def_front_multiplier = _war_front_multiplier(
                                    def_m, war_id, active_wars
                                )
                                def_soldiers = int(
                                    raw_def_soldiers
                                    * def_front_multiplier
                                )
                                def_farmers = countries[def_m]["farmers"]

                                if def_soldiers > 0:
                                    # 1. 交戰規模以兵力為主
                                    clash_size = int(
                                        min(att_soldiers, def_soldiers) * random.uniform(BALANCE["BATTLE_CLASH_MIN"], BALANCE["BATTLE_CLASH_MAX"])
                                    )
                                    clash_size = max(1, clash_size)

                                    att_ratio = att_soldiers / max(1, def_soldiers)

                                    # 計算雙方傷亡數
                                    fortification = _clamp(countries[def_m].get("fortification", 0), 0, 100)
                                    defense_factor = 1.0 + (fortification / 100.0) * 0.35
                                    att_loss = int(
                                        clash_size
                                        * random.uniform(BALANCE["BATTLE_LOSS_MIN"], BALANCE["BATTLE_LOSS_MAX"])
                                        * defense_factor
                                        / max(0.8, min(1.3, att_ratio))
                                    )
                                    raw_kills = int(
                                        clash_size * random.uniform(BALANCE["BATTLE_LOSS_MIN"], BALANCE["BATTLE_LOSS_MAX"]) / defense_factor
                                    )

                                    att_loss = min(att_soldiers, att_loss)

                                    # =========================================================
                                    # 🛡️ 優先扣除士兵，士兵死光才扣農夫
                                    # =========================================================
                                    soldier_kills = min(
                                        raw_def_soldiers,
                                        raw_kills,
                                    )  # 真正死亡仍由實際現役兵承受
                                    overkill = raw_kills - soldier_kills          # 溢出的傷害波及農夫
                                    farmer_kills = min(def_farmers, overkill)     # 扣除農夫

                                    kills = soldier_kills + farmer_kills  # 總死亡人數

                                    # 更新防守方人口
                                    countries[def_m]["soldiers"] -= soldier_kills
                                    countries[def_m]["farmers"] -= farmer_kills
                                    countries[def_m]["pop_total"] = (
                                        countries[def_m]["soldiers"] + countries[def_m]["farmers"]
                                    )

                                else:
                                    # 防守方完全無兵，攻擊方直接清剿農夫
                                    soldier_kills = 0
                                    farmer_kills = min(
                                        def_farmers, int(att_soldiers * random.uniform(0.05, 0.12))
                                    )
                                    farmer_kills = (
                                        max(1, farmer_kills) if countries[def_m]["pop_total"] > 0 else 0
                                    )

                                    kills = farmer_kills
                                    att_loss = int(kills * 0.05)  # 極低反抗戰損

                                    # 更新防守方人口
                                    countries[def_m]["farmers"] -= farmer_kills
                                    countries[def_m]["pop_total"] = (
                                        countries[def_m]["soldiers"] + countries[def_m]["farmers"]
                                    )

                                # 正面會戰也會磨損防禦工事。
                                old_fort = int(_clamp(countries[def_m].get("fortification", 0), 0, 100))
                                fort_damage = min(
                                    old_fort,
                                    random.randint(
                                        WARSTATE["FORT_BATTLE_MIN"],
                                        WARSTATE["FORT_BATTLE_MAX"],
                                    ),
                                )
                                countries[def_m]["fortification"] = max(0, old_fort - fort_damage)

                                # 防守方損失登記到人口總帳。
                                note_population_loss(
                                    def_m,
                                    soldier_kills + farmer_kills,
                                    "戰鬥：防守方人口傷亡",
                                )

                                # 累積全體成員戰損統計
                                total_soldier_kills += soldier_kills
                                total_farmer_kills += farmer_kills

                                # 破壞房屋 (每殺 10 人拆 1 房)
                                houses_destroyed = min(
                                    countries[def_m]["houses"] - 1, kills // 10
                                )
                                countries[def_m]["houses"] = max(
                                    1, countries[def_m]["houses"] - houses_destroyed
                                )
                                enforce_farmer_majority(countries[def_m])
                                countries[def_m]["power"] = calculate_rts_power(countries[def_m])
                                total_kills += kills

                                # 攻方傷亡按實際參戰兵力分攤至各同盟成員
                                applied_loss = apply_attacker_losses(att_loss)
                                total_att_losses += applied_loss

                            action_value += (total_kills * 4) - (total_att_losses * 3)
                            print(
                                f"[戰爭交鋒] 【{att_entity['name']}】自身損失 {total_att_losses} 兵力，"
                                f"消滅【{def_entity['name']}】{total_kills} 人口（含 {total_soldier_kills} 士兵、{total_farmer_kills} 農夫）！"
                            )
                        
                        elif war_tactics == 2:  # 戰術 2：隨機分配兵力負重掠奪
                            total_stolen_f, total_stolen_w, total_stolen_m = 0, 0, 0
                            
                            # 1. 隨機生成三種物資的分配比例 (總和為 100%)
                            p_food = random.randint(20, 50)
                            p_metal = random.randint(10, 40)
                            p_wood = 100 - p_food - p_metal
                            
                            # 2. 算各物資分配到的士兵數
                            soldiers_for_f = int(att_soldiers * (p_food / 100))
                            soldiers_for_m = int(att_soldiers * (p_metal / 100))
                            soldiers_for_w = att_soldiers - soldiers_for_f - soldiers_for_m  # 剩下的給木材
                            
                            # 3. 計算各物資可搬運上限 (1兵 = 4糧 或 2金 或 2木)
                            max_f = soldiers_for_f * BALANCE["PLUNDER_FOOD_PER_SOLDIER"]
                            max_m = soldiers_for_m * BALANCE["PLUNDER_METAL_PER_SOLDIER"]
                            max_w = soldiers_for_w * BALANCE["PLUNDER_WOOD_PER_SOLDIER"]

                            remaining_f, remaining_m, remaining_w = max_f, max_m, max_w
                            for def_m in def_entity["members"]:
                                if remaining_f <= 0 and remaining_m <= 0 and remaining_w <= 0:
                                    break

                                stolen_f = min(countries[def_m]["food"], remaining_f)
                                stolen_m = min(countries[def_m]["metal"], remaining_m)
                                stolen_w = min(countries[def_m]["wood"], remaining_w)

                                countries[def_m]["food"] -= stolen_f
                                countries[def_m]["metal"] -= stolen_m
                                countries[def_m]["wood"] -= stolen_w

                                remaining_f -= stolen_f
                                remaining_m -= stolen_m
                                remaining_w -= stolen_w

                                total_stolen_f += stolen_f
                                total_stolen_m += stolen_m
                                total_stolen_w += stolen_w
                                countries[def_m]["power"] = calculate_rts_power(countries[def_m])

                            # 戰利品依前線兵力比例分給實際參戰國。
                            if att_deployments:
                                deploy_total = max(1, sum(att_deployments.values()))
                                for resource_name, amount in (
                                    ("food", total_stolen_f),
                                    ("metal", total_stolen_m),
                                    ("wood", total_stolen_w),
                                ):
                                    remaining_amount = amount
                                    members = list(att_deployments.keys())
                                    for idx, m in enumerate(members):
                                        if idx == len(members) - 1:
                                            share = remaining_amount
                                        else:
                                            share = int(
                                                amount * att_deployments[m] / deploy_total
                                            )
                                            share = min(share, remaining_amount)
                                        countries[m][resource_name] += share
                                        remaining_amount -= share

                            action_value += (total_stolen_f + total_stolen_w * 1.2 + total_stolen_m * 2.0) / 10.0
                            print(f"[戰爭掠奪] 【{att_entity['name']}】投入 {att_soldiers} 兵力，"
          f"搶奪了【{def_entity['name']}】糧草:{total_stolen_f} / 金屬:{total_stolen_m} / 木材:{total_stolen_w}！"
          f"（分工比例 糧:{p_food}% / 金:{p_metal}% / 木:{p_wood}%）")
                        # 檢查防守方是否有人滅亡
                        # 沒有士兵只代表暫時失去軍隊，不代表幾百名農夫一起消失。
                        def_destroyed = [
                            m for m in def_entity["members"]
                            if countries[m]["pop_total"] <= 0
                        ]
                        if def_destroyed:
                            captured_food = 0
                            captured_wood = 0
                            captured_metal = 0
                            destroyed_count = 0

                            for dm in def_destroyed:
                                if countries[dm]["is_alive"]:
                                    attacker_candidates = [
                                        m
                                        for m in att_entity.get("members", [])
                                        if m in countries
                                    ]
                                    killer_key = (
                                        max(
                                            attacker_candidates,
                                            key=lambda m: countries[m].get("power", 0),
                                        )
                                        if attacker_candidates
                                        else None
                                    )
                                    killer_name = (
                                        countries[killer_key].get("display_name", killer_key)
                                        if killer_key
                                        else att_entity.get("name", "未知勢力")
                                    )
                                    _chronicle_close_current(
                                        dm,
                                        countries[dm],
                                        turn_counter,
                                        "滅國",
                                        ended_by=killer_name,
                                    )

                                    captured_food += int(
                                        countries[dm].get("food", 0)
                                        * BALANCE["CONQUEST_CAPTURE_RATE"]
                                    )
                                    captured_wood += int(
                                        countries[dm].get("wood", 0)
                                        * BALANCE["CONQUEST_CAPTURE_RATE"]
                                    )
                                    captured_metal += int(
                                        countries[dm].get("metal", 0)
                                        * BALANCE["CONQUEST_CAPTURE_RATE"]
                                    )
                                    destroyed_count += 1

                                    countries[dm]["is_alive"] = False
                                    countries[dm]["power"] = 0
                                    countries[dm]["pop_total"] = 0
                                    countries[dm]["farmers"] = 0
                                    countries[dm]["soldiers"] = 0
                                    countries[dm]["food"] = 0
                                    countries[dm]["wood"] = 0
                                    countries[dm]["metal"] = 0
                                    countries[dm]["houses"] = 0
                                    countries[dm]["death_respawn_cooldown"] = 3

                            if att_deployments:
                                deploy_total = max(1, sum(att_deployments.values()))
                                members = list(att_deployments.keys())
                                for resource_name, amount in (
                                    ("food", captured_food),
                                    ("wood", captured_wood),
                                    ("metal", captured_metal),
                                ):
                                    remaining_amount = amount
                                    for idx, m in enumerate(members):
                                        if idx == len(members) - 1:
                                            share = remaining_amount
                                        else:
                                            share = int(
                                                amount * att_deployments[m] / deploy_total
                                            )
                                            share = min(share, remaining_amount)
                                        countries[m][resource_name] += share
                                        remaining_amount -= share

                            c_data["annexed_count"] += destroyed_count
                            action_value += destroyed_count * 120.0
                            print(
                                f"[擊破滅亡] 【{att_entity['name']}】擊潰【{def_entity['name']}】，"
                                f"接收其剩餘庫存 25%：糧:{captured_food} / 木:{captured_wood} / 金:{captured_metal}。"
                            )

                        # 檢查進攻方是否戰死滅亡
                        # 攻方同理：軍隊全滅 ≠ 全國人口全滅。
                        att_destroyed = [
                            m for m in att_entity["members"]
                            if countries[m]["pop_total"] <= 0
                        ]
                        if att_destroyed:
                            for am in att_destroyed:
                                if countries[am]["is_alive"]:
                                    defender_candidates = [
                                        m
                                        for m in def_entity.get("members", [])
                                        if m in countries
                                    ]
                                    killer_key = (
                                        max(
                                            defender_candidates,
                                            key=lambda m: countries[m].get("power", 0),
                                        )
                                        if defender_candidates
                                        else None
                                    )
                                    killer_name = (
                                        countries[killer_key].get("display_name", killer_key)
                                        if killer_key
                                        else def_entity.get("name", "未知勢力")
                                    )
                                    _chronicle_close_current(
                                        am,
                                        countries[am],
                                        turn_counter,
                                        "滅國",
                                        ended_by=killer_name,
                                    )

                                    countries[am]["is_alive"] = False
                                    countries[am]["power"] = 0
                                    countries[am]["pop_total"] = 0
                                    countries[am]["farmers"] = 0
                                    countries[am]["soldiers"] = 0
                                    countries[am]["food"] = 0
                                    countries[am]["wood"] = 0
                                    countries[am]["metal"] = 0
                                    countries[am]["houses"] = 0
                                    countries[am]["death_respawn_cooldown"] = 3

                

                # ----------------------------------------------------
                # Action 1: 締結同盟
                # ---------------------------------------------------- 
                 
                elif action == 1:
                    if not c_data["current_alliance"]:  # 僅在尚未加入同盟時執行
                        existing_alliances = [
                            a_name
                            for a_name, members in alliances.items()
                            if len(
                                [
                                    m
                                    for m in members
                                    if countries[m]["is_alive"]
                                ]
                            ) < 5
                            and not a_name.startswith("【極限討伐】")
                            and int(
                                alliance_join_vote_cooldowns.get(
                                    _alliance_join_vote_cooldown_key(
                                        a_name,
                                        attacker_key,
                                    ),
                                    0,
                                )
                                or 0
                            ) <= turn_counter
                        ]

                        # 50% 嘗試申請加入現有同盟，50% 嘗試創建新同盟。
                        # 加入現有聯盟改由現有存活盟員正式投票。
                        if existing_alliances and random.random() < 0.5:
                            target_ally = random.choice(existing_alliances)

                            join_vote = _alliance_admission_vote(
                                target_ally,
                                attacker_key,
                                countries,
                                alliances,
                                rl_agents,
                                active_wars,
                                turn_counter,
                            )
                            alliance_last_join_votes[
                                target_ally
                            ] = join_vote

                            if join_vote.get("passed", False):
                                alliances[target_ally].append(attacker_key)
                                alliances[target_ally] = list(
                                    dict.fromkeys(alliances[target_ally])
                                )
                                c_data["current_alliance"] = target_ally
                                action_success = True
                                print(
                                    f"🤝 [入盟通過] 【{c_data['display_name']}】"
                                    f"經盟內表決獲准加入 {target_ally}！"
                                    f"（成員數：{len(alliances[target_ally])}）"
                                )
                            else:
                                cooldown_turns = random.randint(
                                    ALLIANCE_JOIN_VOTE_COOLDOWN_MIN,
                                    ALLIANCE_JOIN_VOTE_COOLDOWN_MAX,
                                )
                                cooldown_key = _alliance_join_vote_cooldown_key(
                                    target_ally,
                                    attacker_key,
                                )
                                alliance_join_vote_cooldowns[
                                    cooldown_key
                                ] = turn_counter + cooldown_turns
                                print(
                                    f"⏳ [入盟否決] 【{c_data['display_name']}】"
                                    f"申請加入 {target_ally} 未獲過半支持；"
                                    f"{cooldown_turns} 回合內不得向同一聯盟重新申請。"
                                )
                        else:  # 尋找未結盟國家創立新同盟
                            unallied = [
                                k for k in alive_sorted
                                if not countries[k]["current_alliance"] and k != attacker_key and countries[k]["is_alive"]
                            ]
                            if len(unallied) >= 1:
                                partner = random.choice(unallied)
                                attackers_a = set(c_data.get("recent_attackers", []))
                                attackers_b = set(countries[partner].get("recent_attackers", []))
                                common_enemies = attackers_a.intersection(attackers_b)  # 尋找共同敵人

                                alliance_success_rate = 0.30  # 基礎成功率 30%
                                # 惡名會讓別國不信任；修復聲望因此具有長期價值。
                                alliance_success_rate -= min(0.25, c_data.get("infamy", 0) / 250.0)
                                alliance_success_rate = max(0.05, alliance_success_rate)
                                alliance_success_rate *= float(
                                    c_data.get("world_alliance_bias", 1.0) or 1.0
                                )
                                alliance_success_rate = float(
                                    _clamp(alliance_success_rate, 0.03, 0.95)
                                )
                                if common_enemies:  # 若有共同強敵，結盟成功率大幅提高
                                    alliance_success_rate += len(common_enemies) * 0.35
                                    print(
                                        f"[同仇敵儾] 【{c_data['display_name']}】與 【{countries[partner]['display_name']}】"
                                        f"擁有共同強敵 {list(common_enemies)}！結盟意願暴增至 {min(alliance_success_rate*100, 100):.0f}%"
                                    )

                                if random.random() < alliance_success_rate:  # 判定是否成功結盟
                                    ally_name = generate_awesome_alliance_name()
                                    alliances[ally_name] = [attacker_key, partner]
                                    c_data["current_alliance"] = ally_name
                                    countries[partner]["current_alliance"] = ally_name
                                    action_success = True
                                    print(f"[外交策略] 【{c_data['display_name']}】與 【{countries[partner]['display_name']}】締結盟約，創立 {ally_name}！")               

                # ----------------------------------------------------
                # Action 2: 號召反霸權聯軍（臨時軍事聯軍，不改變普通聯盟）
                # ----------------------------------------------------
                elif action == 2:
                    if len(anti_hegemon_coalitions) < COALITION_MAX_ACTIVE and len(alive_sorted) >= 4:
                        hegemon_key = alive_sorted[0]
                        hegemon = countries[hegemon_key]

                        # 必須是連續 3 Loop 符合霸權門檻的第一名。
                        target_ready = (
                            hegemon_streaks.get(
                                hegemon_key, 0
                            )
                            >= HEGEMON_REQUIRED_STREAK
                            or hegemon_key
                            == rare_coalition_target
                        )
                        target_cooldown_ok = int(coalition_target_cooldowns.get(hegemon_key, 0) or 0) <= turn_counter
                        already_targeted = any(
                            info.get("target") == hegemon_key
                            for info in anti_hegemon_coalitions.values()
                            if isinstance(info, dict)
                        )

                        initiator_cooldown_ok = int(coalition_member_cooldowns.get(attacker_key, 0) or 0) <= turn_counter
                        initiator_not_in_coalition = not get_country_coalition(attacker_key, anti_hegemon_coalitions)

                        if (
                            hegemon_key != attacker_key
                            and hegemon.get("is_alive", True)
                            and target_ready
                            and target_cooldown_ok
                            and not already_targeted
                            and initiator_cooldown_ok
                            and initiator_not_in_coalition
                        ):
                            hegemon_alliance = get_country_alliance(hegemon_key, alliances)
                            hegemon_allies = set(alliances.get(hegemon_alliance, [])) if hegemon_alliance else {hegemon_key}
                            rank_map = {k: idx + 1 for idx, k in enumerate(alive_sorted)}

                            eligible = []
                            for k in alive_sorted:
                                if k == hegemon_key or k in hegemon_allies:
                                    continue
                                if get_country_coalition(k, anti_hegemon_coalitions):
                                    continue
                                if int(coalition_member_cooldowns.get(k, 0) or 0) > turn_counter:
                                    continue
                                willingness = coalition_join_willingness(
                                    k, hegemon_key, countries, alliances, rl_agents, rank_map
                                )
                                eligible.append((k, willingness))

                            # 發起國自己至少要有合理的參戰意願；避免 AI 無腦開聯軍。
                            initiator_willingness = coalition_join_willingness(
                                attacker_key, hegemon_key, countries, alliances, rl_agents, rank_map
                            )

                            if initiator_willingness >= 0.18:
                                accepted = [attacker_key]
                                target_power = max(1, hegemon.get("power", 0))
                                coalition_power = max(0, countries[attacker_key].get("power", 0))

                                # 意願高者優先，但仍需通過自己的機率判定；不是被隨機強迫抓進來。
                                for candidate, willingness in sorted(eligible, key=lambda x: x[1], reverse=True):
                                    if candidate == attacker_key or len(accepted) >= COALITION_MAX_MEMBERS:
                                        continue
                                    if random.random() > willingness:
                                        continue
                                    accepted.append(candidate)
                                    coalition_power += max(0, countries[candidate].get("power", 0))
                                    if (
                                        len(accepted) >= COALITION_MIN_MEMBERS
                                        and coalition_power >= target_power * COALITION_TARGET_POWER_RATIO
                                    ):
                                        break

                                if len(accepted) >= COALITION_MIN_MEMBERS:
                                    coalition_name = generate_awesome_alliance_name(
                                        is_anti_hegemon=True,
                                        target_name=hegemon.get("display_name", hegemon_key),
                                    )
                                    anti_hegemon_coalitions[coalition_name] = {
                                        "target": hegemon_key,
                                        "members": accepted,
                                        "created_turn": turn_counter,
                                        "expires_turn": turn_counter + COALITION_MAX_DURATION,
                                    }
                                    for m in accepted:
                                        countries[m]["current_coalition"] = coalition_name

                                    action_success = True
                                    action_value += len(accepted) * 12
                                    coalition_reason = (
                                        "稀有自發牽制"
                                        if hegemon_key
                                        == rare_coalition_target
                                        and hegemon_streaks.get(
                                            hegemon_key, 0
                                        )
                                        < HEGEMON_REQUIRED_STREAK
                                        else "反霸權"
                                    )
                                    print(
                                        f"[反霸權聯軍] 【{c_data['display_name']}】號召 {len(accepted)} 國成立 {coalition_name}，"
                                        f"共同牽制【{hegemon['display_name']}】！"
                                        f"起因：{coalition_reason}；成員保留原有普通聯盟。"
                                    )
                                else:
                                    print(
                                        f"[圍剿未成] 【{c_data['display_name']}】試圖號召各國牽制【{hegemon['display_name']}】，"
                                        f"但響應國不足 {COALITION_MIN_MEMBERS} 國。"
                                    )

                # Action 3: 養精蓄銳 (發展經濟)
                elif action == 3:
                    multiplier = (1.60 if event_type == "EXPANSION" else 1.0)
                    multiplier *= float(c_data.get("event_action_efficiency", 1.0) or 1.0)
                    econ_farmers = max(1, c_data.get("farmers", 1))
                    growth_food = int(
                        econ_farmers * random.uniform(0.35, 0.55) * multiplier
                    )
                    growth_wood = int(
                        econ_farmers * random.uniform(0.18, 0.30) * multiplier
                    )
                    growth_metal = int(
                        econ_farmers * random.uniform(0.08, 0.16) * multiplier
                    )
                    c_data["food"] += growth_food
                    c_data["wood"] += growth_wood
                    c_data["metal"] += growth_metal
                    action_success = True
                    action_value += (
                        growth_food + growth_wood * 1.2 + growth_metal * 2.0
                    )
                    print(
                        f"[養精蓄銳] 【{c_data['display_name']}】集中發展經濟，"
                        f"增產 糧:{growth_food} / 木:{growth_wood} / 金:{growth_metal}。"
                    )

                # ----------------------------------------------------
                # Action 4: 背叛背刺同盟
                # ----------------------------------------------------                
                elif action == 4:
                    curr_a = c_data["current_alliance"]
                    if curr_a and curr_a in alliances:
                        partners = [m for m in alliances[curr_a] if m != attacker_key and countries[m]["is_alive"]]
                        if partners:
                            victim = random.choice(partners)  # 隨機選擇一名盟友背刺
                            steal_food = min(250, int(countries[victim]["food"] * 0.12))  # 偷取 12%，且封頂 250
                            countries[victim]["food"] -= steal_food
                            c_data["food"] += steal_food
                            _war_add_hostility(
                                countries,
                                victim,
                                attacker_key,
                                WARSTATE["HOSTILITY_BETRAY"],
                            )

                            if attacker_key in alliances[curr_a]:
                                alliances[curr_a].remove(attacker_key)  # 退群
                                
                            c_data["current_alliance"] = ""  # 清空個人同盟紀錄
                            c_data["infamy"] = c_data.get("infamy", 0) + 50
                            action_success = True
                            action_value += steal_food
                            print(f"[背叛背刺] 【{c_data['display_name']}】撕毀條約！偷襲盟友【{countries[victim]['display_name']}】掠奪糧草！")

                # ----------------------------------------------------
                # Action 5: 加固防線 (防禦與建造)
                # ----------------------------------------------------
                
                elif action == 5:
                    # 防線不再「憑空增加木材/金屬」，而是實際支付材料換取持久防禦。
                    wood_cost = min(c_data["wood"], random.randint(35, 70))
                    metal_cost = min(c_data["metal"], random.randint(15, 35))
                    if wood_cost >= 35 and metal_cost >= 15:
                        c_data["wood"] -= wood_cost
                        c_data["metal"] -= metal_cost
                        fort_gain = random.randint(8, 16)
                        c_data["fortification"] = int(
                            _clamp(c_data.get("fortification", 0) + fort_gain, 0, 100)
                        )
                        # 加固防線只提升軍事防禦，不再順便增加住宅，
                        # 避免長局下住房容量永遠遠高於人口。
                        action_success = True
                        action_value += fort_gain * 5
                        print(
                            f"[加固防線] 【{c_data['display_name']}】投入木材 {wood_cost}、金屬 {metal_cost}，"
                            f"防禦工事提升至 {c_data['fortification']}。"
                        )

                # ----------------------------------------------------
                # Action 6: 戰時動員
                # ----------------------------------------------------
                elif action == 6:
                    c_data["military_target_ratio"] = float(
                        _clamp(max(c_data.get("military_target_ratio", 0.30), 0.45), 0.10, 0.50)
                    )
                    pop = max(1, c_data["pop_total"])
                    soldiers = c_data["soldiers"]
                    farmers = c_data["farmers"]
                    safe_train = max(0, (farmers - soldiers) // 2)
                    desired = min(pop // 2, max(soldiers + 1, int(pop * 0.45)))
                    need = max(0, desired - soldiers)
                    mobilize_metal_cost = max(
                        1,
                        int(
                            math.ceil(
                                BALANCE["RECRUIT_METAL_COST"]
                                * float(c_data.get("event_recruit_cost_mult", 1.0) or 1.0)
                                * float(
                                    c_data.get("world_recruit_cost_mult", 1.0)
                                    or 1.0
                                )
                            )
                        ),
                    )
                    mobilize_food_cost = BALANCE["RECRUIT_FOOD_COST"]
                    affordable = min(
                        int(c_data["metal"] // mobilize_metal_cost),
                        int(c_data["food"] // mobilize_food_cost),
                    )
                    recruit_event_mult = (
                        float(c_data.get("event_recruit_mult", 1.0) or 1.0)
                        * float(c_data.get("world_recruit_mult", 1.0) or 1.0)
                    )
                    mobilize_cap = min(
                        int(BALANCE["MOBILIZE_MAX"] * recruit_event_mult),
                        max(
                            BALANCE["MOBILIZE_MIN"],
                            int(
                                pop
                                * BALANCE["MOBILIZE_POP_RATIO"]
                                * recruit_event_mult
                            ),
                        ),
                    )
                    mobilize_roll = random.randint(
                        max(1, BALANCE["MOBILIZE_MIN"] // 2),
                        max(
                            BALANCE["MOBILIZE_MIN"],
                            mobilize_cap,
                        ),
                    )

                    train_count = min(
                        need,
                        safe_train,
                        affordable,
                        mobilize_roll,
                    )
                    if train_count > 0:
                        c_data["soldiers"] += train_count
                        c_data["farmers"] -= train_count
                        c_data["metal"] -= train_count * mobilize_metal_cost
                        c_data["food"] -= train_count * mobilize_food_cost
                        action_success = True
                        action_value += train_count * 10
                        print(
                            f"[戰時動員] 【{c_data['display_name']}】徵召 {train_count} 名新兵，"
                            f"軍力提升但經濟勞動力下降。"
                        )

                # ----------------------------------------------------
                # Action 7: 農業振興
                # ----------------------------------------------------
                elif action == 7:
                    farmers = max(1, c_data.get("farmers", 1))
                    investment = min(c_data["wood"], random.randint(10, 30))
                    c_data["wood"] -= investment
                    food_gain = int(farmers * random.uniform(0.60, 1.00) + investment * 1.20)
                    c_data["food"] += food_gain
                    action_success = True
                    action_value += food_gain
                    print(
                        f"[農業振興] 【{c_data['display_name']}】投入 {investment} 木材改善農業，"
                        f"新增 {food_gain} 糧食。"
                    )

                # ----------------------------------------------------
                # Action 8: 市場貿易（以折價交換補足短缺）
                # ----------------------------------------------------
                elif action == 8:
                    trade_event_mult = (
                        float(c_data.get("event_trade_mult", 1.0) or 1.0)
                        * float(c_data.get("world_trade_mult", 1.0) or 1.0)
                    )
                    farmers = max(0, c_data.get("farmers", 0))
                    soldiers = max(0, c_data.get("soldiers", 0))
                    consumption = max(1, farmers + soldiers * 2)
                    food_turns = c_data["food"] / consumption

                    if food_turns < 3 and (c_data["wood"] >= 30 or c_data["metal"] >= 20):
                        sell_wood = min(c_data["wood"], 80)
                        sell_metal = min(c_data["metal"], 40)
                        c_data["wood"] -= sell_wood
                        c_data["metal"] -= sell_metal
                        gain = int((sell_wood * 0.90 + sell_metal * 1.60) * trade_event_mult)
                        c_data["food"] += gain
                        action_success = True
                        action_value += gain
                        print(f"[市場貿易] 【{c_data['display_name']}】出售物資換得 {gain} 糧食以補充糧倉。")
                    elif c_data["metal"] < max(100, soldiers * 2) and c_data["food"] >= 120:
                        spend = min(c_data["food"] - 50, 180)
                        spend = max(0, spend)
                        if spend > 0:
                            c_data["food"] -= spend
                            gain = int(spend * 0.35 * trade_event_mult)
                            c_data["metal"] += gain
                            action_success = True
                            action_value += gain * 2
                            print(f"[市場貿易] 【{c_data['display_name']}】以 {spend} 糧食換得 {gain} 金屬。")
                    elif c_data["wood"] < 120 and c_data["food"] >= 100:
                        spend = min(c_data["food"] - 50, 150)
                        spend = max(0, spend)
                        if spend > 0:
                            c_data["food"] -= spend
                            gain = int(spend * 0.60 * trade_event_mult)
                            c_data["wood"] += gain
                            action_success = True
                            action_value += gain
                            print(f"[市場貿易] 【{c_data['display_name']}】以 {spend} 糧食換得 {gain} 木材。")
                    else:
                        # 沒有明顯短缺時，將少量糧食換成較稀缺的金屬。
                        spend = min(max(0, c_data["food"] - consumption * 5), 100)
                        if spend >= 30:
                            c_data["food"] -= spend
                            gain = int(spend * 0.30 * trade_event_mult)
                            c_data["metal"] += gain
                            action_success = True
                            action_value += gain * 2
                            print(f"[市場貿易] 【{c_data['display_name']}】調整庫存，以 {spend} 糧食換得 {gain} 金屬。")

                # ----------------------------------------------------
                # Action 9: 修復聲望
                # ----------------------------------------------------
                elif action == 9:
                    old_infamy = c_data.get("infamy", 0)
                    if old_infamy > 0:
                        food_stock = max(
                            0,
                            int(c_data.get("food", 0) or 0),
                        )
                        pop_now = max(
                            1,
                            int(c_data.get("pop_total", 1) or 1),
                        )

                        # 外交斡旋必須付出有感代價：
                        # 約糧庫 3%~7%，且最低會隨人口規模增加。
                        min_cost = max(
                            100,
                            int(pop_now * 0.15),
                            int(food_stock * 0.03),
                        )
                        max_cost = max(
                            min_cost,
                            int(food_stock * 0.07),
                        )

                        diplomacy_cost = min(
                            food_stock,
                            random.randint(
                                min_cost,
                                max_cost,
                            ),
                        )

                        if diplomacy_cost <= 0:
                            continue

                        c_data["food"] -= diplomacy_cost

                        # 花費越高，斡旋效果略好，但仍有上限。
                        cost_ratio = (
                            diplomacy_cost
                            / max(1, food_stock)
                        )
                        reduction = random.randint(14, 28) + int(
                            min(10, cost_ratio * 100)
                        )
                        c_data["infamy"] = max(0, old_infamy - reduction)
                        action_success = True
                        action_value += old_infamy - c_data["infamy"]
                        print(
                            f"[外交修復] 【{c_data['display_name']}】付出 {diplomacy_cost} 糧食進行外交斡旋，"
                            f"惡名由 {old_infamy} 降至 {c_data['infamy']}。"
                        )

                # ----------------------------------------------------
                # Action 10: 小規模襲擾（比全面戰爭低成本、低收益）
                # ----------------------------------------------------
                elif action == 10:
                    curr_a = c_data.get("current_alliance")
                    my_members = set(alliances.get(curr_a, [])) if curr_a else {attacker_key}
                    raid_targets = [
                        k for k in alive_sorted
                        if k != attacker_key
                        and k not in my_members
                        and countries[k]["is_alive"]
                        and countries[k]["pop_total"] > 0
                        and k not in attacked_this_round
                        and not _war_country_in_active_war(k, active_wars)
                        and not _war_is_truce(
                            attacker_key, k, war_truces, turn_counter
                        )
                    ]
                    if raid_targets and c_data["soldiers"] >= 5:
                        # 投機型偏好資源豐富但戰力較弱的目標
                        def raid_score(k):
                            d = countries[k]
                            resources = d["food"] + d["wood"] * 1.2 + d["metal"] * 2.0
                            return resources / max(d["power"], 100)

                        target = max(raid_targets, key=raid_score)
                        t = countries[target]
                        raid_force = min(
                            c_data["soldiers"],
                            max(
                                5,
                                int(
                                    c_data["soldiers"]
                                    * BALANCE["RAID_FORCE_RATIO"]
                                ),
                            ),
                        )
                        food_cost = int(
                            math.ceil(
                                raid_force * BALANCE["RAID_FOOD_PER_SOLDIER"]
                            )
                        )
                        metal_cost = int(
                            math.ceil(
                                raid_force * BALANCE["RAID_METAL_PER_SOLDIER"]
                            )
                        )

                        if (
                            c_data["food"] < food_cost
                            or c_data["metal"] < metal_cost
                        ):
                            raid_force = 0
                        else:
                            c_data["food"] -= food_cost
                            c_data["metal"] -= metal_cost

                        if raid_force <= 0:
                            action_success = False
                            print(
                                f"[邊境襲擾取消] 【{c_data['display_name']}】補給不足，取消襲擾。"
                            )
                            continue

                        steal_f = min(
                            t["food"],
                            max(3, min(int(t["food"] * 0.03), raid_force * 3)),
                        )
                        steal_w = min(
                            t["wood"],
                            max(2, min(int(t["wood"] * 0.025), raid_force * 2)),
                        )
                        steal_m = min(
                            t["metal"],
                            max(1, min(int(t["metal"] * 0.02), raid_force)),
                        )
                        t["food"] -= steal_f
                        t["wood"] -= steal_w
                        t["metal"] -= steal_m
                        c_data["food"] += steal_f
                        c_data["wood"] += steal_w
                        c_data["metal"] += steal_m

                        loss = min(
                            c_data["soldiers"],
                            int(
                                raid_force
                                * random.uniform(
                                    BALANCE["RAID_LOSS_MIN"],
                                    BALANCE["RAID_LOSS_MAX"],
                                )
                            ),
                        )
                        c_data["soldiers"] -= loss
                        c_data["pop_total"] = c_data["farmers"] + c_data["soldiers"]
                        note_population_loss(attacker_key, loss, "邊境襲擾：出擊戰損")
                        c_data["infamy"] = c_data.get("infamy", 0) + 8
                        t.setdefault("recent_attackers", []).append(attacker_key)
                        t["recent_attackers"] = t["recent_attackers"][-5:]
                        _war_add_hostility(
                            countries,
                            target,
                            attacker_key,
                            WARSTATE["HOSTILITY_RAID"],
                        )
                        attacked_this_round.add(target)

                        action_success = True
                        action_value += steal_f + steal_w * 1.2 + steal_m * 2.0 - loss * 20
                        print(
                            f"[邊境襲擾] 【{c_data['display_name']}】以 {raid_force} 兵襲擊"
                            f"【{t['display_name']}】，掠得糧:{steal_f}/木:{steal_w}/金:{steal_m}，"
                            f"損失 {loss} 兵。"
                        )

                # ----------------------------------------------------
                # Action 11: 裁軍休養
                # ----------------------------------------------------
                elif action == 11:
                    c_data["military_target_ratio"] = float(
                        _clamp(c_data.get("military_target_ratio", 0.30) - 0.10, 0.12, 0.50)
                    )
                    soldiers = c_data.get("soldiers", 0)
                    if soldiers > 0:
                        # 裁軍改為漸進式：每次僅退伍約 5~10%，且最多 20 人。
                        # 退伍只是士兵轉農夫，不是人口死亡，避免大國一次掉數百戰力人口。
                        demobilize = min(
                            soldiers,
                            20,
                            max(1, int(soldiers * random.uniform(0.05, 0.10))),
                        )
                        c_data["soldiers"] -= demobilize
                        c_data["farmers"] += demobilize
                        # 退役不退還全部軍費，只回收少量可用裝備。
                        c_data["metal"] += int(demobilize * 0.5)
                        action_success = True
                        action_value += demobilize * 5
                        print(
                            f"[裁軍休養] 【{c_data['display_name']}】讓 {demobilize} 名士兵退伍轉回農業生產。"
                        )

                # 重新計算最終戰力
                c_data["power"] = calculate_rts_power(c_data)

                # ----------------------------------------------------
                # RL V2 Reward：使用真正的 before -> after 快照
                # ----------------------------------------------------
                enforce_farmer_majority(c_data)
                c_data["power"] = calculate_rts_power(c_data)
                c_data["fortification"] = int(_clamp(c_data.get("fortification", 0), 0, 100))

                after_data = _rl_snapshot(c_data)
                reward = agent.calculate_reward(
                    before_data,
                    after_data,
                    action,
                    action_success,
                    action_value,
                    total_world_power,
                    top_power,
                    len(alive_sorted),
                )

                c_data["last_action"] = RL_ACTIONS.get(action, str(action))
                c_data["last_reward"] = round(reward, 2)
                c_data["ai_status"] = agent.describe_state(
                    after_data,
                    total_world_power,
                    top_power,
                    len(alive_sorted),
                )

                agent.learn(
                    before_data,
                    total_world_power,
                    top_power,
                    len(alive_sorted),
                    action,
                    reward,
                    after_data,
                )

        # 6. 死亡與世代重生機制 (Respawn Logic)
        for name, data in countries.items():
            if not data["is_alive"]:
                if dead_mode == 0:  # 冷卻模式
                    if data["death_respawn_cooldown"] > 0:
                        data["death_respawn_cooldown"] -= 1  # 扣除冷卻回合
                    else:
                        # V6 亡國重建：
                        # 延續滅亡前最後的政權國號根，只有復國才增加 Roman 世代。
                        old_regime_type = data.get(
                            "regime_type",
                            "正統政權",
                        )
                        old_regime_name, rebuilt_name = (
                            _advance_country_rebirth_identity(
                                name,
                                data,
                            )
                        )
                        data["is_alive"] = True  # 復活
                        _record_regime_history(
                            data,
                            turn_counter,
                            "亡國重建",
                            old_regime_name,
                            rebuilt_name,
                        )
                        
                        # 重置基礎資源與人口
                        data["houses"] = 5
                        data["pop_total"] = 10
                        data["farmers"] = 7
                        data["soldiers"] = 3
                        data["food"] = random.randint(180, 300)
                        data["wood"] = random.randint(100, 180)
                        data["metal"] = random.randint(60, 120)
                        enforce_farmer_majority(data)
                        data["power"] = calculate_rts_power(data)

                        data["annexed_count"] = 0
                        data["infamy"] = 0
                        data["fortification"] = 0
                        data["military_target_ratio"] = 0.30
                        data["balance_version"] = BALANCE_VERSION
                        data["famine_streak"] = 0
                        data["last_population_change_reason"] = ""
                        data["last_action"] = ""
                        data["last_reward"] = 0.0
                        data["ai_status"] = ""
                        data["current_alliance"] = ""
                        data["current_coalition"] = ""
                        data["last_population_audit"] = "新世代重生，人口重新起算"
                        data["hostility"] = {}
                        data["current_wars"] = []
                        data["war_status"] = "和平"
                        data["war_log_terms"] = []
                        data["top_hostility_target"] = "無"
                        data["recent_attackers"] = []
                        data["political_stability"] = 62.0
                        data["war_exhaustion"] = 0.0
                        # 國號與政權性質延續滅亡前最後狀態；
                        # 例如「挫蛋軍政府(三世)」復國成「挫蛋軍政府II」。
                        data["regime_type"] = old_regime_type
                        data["regime_generation"] = 1
                        data["regime_tenure"] = 0
                        _chronicle_start_current(
                            name,
                            data,
                            turn_counter,
                        )
                        data["last_regime_change_turn"] = turn_counter
                        data["strategic_mode"] = "正常發展"
                        data["last_event"] = (
                            f"亡國重建：{old_regime_name} → "
                            f"{data['display_name']}；政權世系重新由一世起算"
                        )
                        data["active_events"] = {}
                        data["event_summary"] = "無"

                        # 新世代隨機重新抽選性格
                        new_personality = random.choice(list(PERSONALITIES.keys()))
                        rl_agents[name].personality_type = new_personality
                        rl_agents[name].personality = PERSONALITIES[new_personality]

        # 7. 臨時反霸權聯軍：使命完成、威脅解除、逾期與冷卻
        rank_map = {k: idx + 1 for idx, k in enumerate(alive_sorted)}
        for coalition_name in list(anti_hegemon_coalitions.keys()):
            info = anti_hegemon_coalitions.get(coalition_name, {})
            if not isinstance(info, dict):
                del anti_hegemon_coalitions[coalition_name]
                continue

            target_id = info.get("target")
            target_c = countries.get(target_id)
            members = [
                m for m in (info.get("members") or [])
                if m in countries and countries[m].get("is_alive", True)
            ]
            info["members"] = members

            end_reason = None
            if not target_c or not target_c.get("is_alive", True):
                end_reason = "討伐目標已覆滅"
            elif len(members) < 2:
                end_reason = "聯軍有效成員不足"
            elif turn_counter >= int(info.get("expires_turn", turn_counter + 1)):
                end_reason = "聯軍任務期限已滿"
            else:
                target_rank = rank_map.get(target_id, 999)
                target_power = max(0, target_c.get("power", 0))
                target_share = target_power / max(1, total_world_power)
                other_powers = [
                    countries[k].get("power", 0)
                    for k in alive_sorted if k != target_id
                ]
                strongest_other = max(other_powers) if other_powers else 1
                lead_ratio = target_power / max(1, strongest_other)
                age = turn_counter - int(info.get("created_turn", turn_counter))

                # 至少存在 3 Loop 後才因「威脅解除」提前解散，避免成立隔輪就消失。
                if age >= 3:
                    if target_rank > 3:
                        end_reason = "霸權已跌出前三名"
                    elif target_share < 0.10 and lead_ratio < 1.30:
                        end_reason = "霸權優勢已被削弱"

            if end_reason:
                target_name = target_c.get("display_name", target_id) if target_c else "霸權"
                print(
                    f"[聯軍解散] {coalition_name} 對【{target_name}】的任務結束：{end_reason}。"
                    f"各國保留原有普通聯盟。"
                )
                coalition_target_cooldowns[target_id] = turn_counter + COALITION_COOLDOWN
                for m in members:
                    coalition_member_cooldowns[m] = turn_counter + COALITION_COOLDOWN
                    if countries.get(m, {}).get("current_coalition") == coalition_name:
                        countries[m]["current_coalition"] = ""
                del anti_hegemon_coalitions[coalition_name]

        # 清理已過期冷卻，避免 dict 永久膨脹。
        coalition_target_cooldowns = {
            k: v for k, v in coalition_target_cooldowns.items() if int(v or 0) > turn_counter
        }
        coalition_member_cooldowns = {
            k: v for k, v in coalition_member_cooldowns.items() if int(v or 0) > turn_counter
        }

        # ------------------------------------------------------------
        # 8. 人口總帳結算
        # ------------------------------------------------------------
        for country_key, start_pop in population_loop_start.items():
            c = countries.get(country_key)
            if not c or not c.get("is_alive", True):
                continue

            end_pop = max(0, int(c.get("pop_total", 0) or 0))
            net_loss = max(0, start_pop - end_pop)
            ledger_items = population_loss_ledger.get(country_key, [])
            known_loss = sum(
                max(0, int(amount))
                for amount, _reason in ledger_items
            )

            # 出生會抵消部分死亡，所以「合法損失總額」可以大於人口淨減少。
            if net_loss > known_loss:
                unexplained = net_loss - known_loss

                # 找不到任何已知機制的缺口，直接補回為農夫。
                c["pop_total"] += unexplained
                c["farmers"] = (
                    max(0, int(c.get("farmers", 0) or 0))
                    + unexplained
                )
                enforce_farmer_majority(c)
                c["power"] = calculate_rts_power(c)

                c["last_population_audit"] = (
                    f"未授權減少 {unexplained} 人，已自動補回"
                )
                print(
                    f"🛡️ [人口異常修復]【{c.get('display_name', country_key)}】"
                    f"本輪人口 {start_pop} → {end_pop}，"
                    f"其中 {unexplained} 人沒有任何合法減少原因，已補回為農夫。"
                )

            elif net_loss > 0:
                total_loss = sum(
                    max(0, int(amount))
                    for amount, _reason in ledger_items
                )
                population_gain = max(0, total_loss - net_loss)
                reasons = [
                    f"{reason} -{amount}"
                    for amount, reason in ledger_items
                    if amount > 0
                ]
                reason_text = "；".join(reasons) if reasons else "已登記人口損失"
                event_tag = (
                    "持續戰爭"
                    if any(
                        "持續戰爭" in str(reason)
                        for amount, reason in ledger_items
                        if amount > 0
                    )
                    else "人口變動"
                )
                display_reason = reason_text.replace("持續戰爭：", "")
                c["last_population_audit"] = (
                    f"{display_reason}；出生 +{population_gain}；淨增 -{net_loss}"
                )
                print(
                    f"[{event_tag}]【{c.get('display_name', country_key)}】"
                    f"人口 {start_pop} → {int(c.get('pop_total', 0))} "
                    f"（{display_reason}；出生 +{population_gain}；淨增 -{net_loss}）。"
                )
            else:
                c.setdefault("last_population_audit", "人口正常")

        # 9. 生成並輸出即時排行榜文件 (Live_Ranking.txt)
        sorted_countries = sorted(countries.items(), key=lambda x: x[1]["power"], reverse=True)
        total_q_states = sum(len(ag.q_table) for ag in rl_agents.values())  # 統計全系統累積的 Q-State 經驗數

        rank_text = f"===== 全陸霸權 RL 強化學習戰局 第 {count_round} 屆 =====  {int(time_total - (time.time() - start_time))} s\n"
        rank_text += (
            f"全陸總戰力 = {total_world_power} ({world_stage_g})"
            f"| Q-State {total_q_states:,}"
            f" / 安全上限約 {len(rl_agents) * MAX_Q_STATES_PER_AGENT:,}\n"
        )
        if current_world_mode.get("code") == "NORMAL":
            rank_text += (
                f"🌍 世界局勢 = 平常局勢｜下一次時代轉折約 "
                f"{max(0, next_world_mode_turn - turn_counter)} 回合後\n"
            )
        else:
            rank_text += (
                f"🌍 世界局勢 = {current_world_mode.get('name', '平常局勢')}"
                f"｜剩餘約 {max(0, int(current_world_mode.get('remaining_turns', 0) or 0))} 回合\n"
            )

        for i, (base_name, data) in enumerate(sorted_countries[:len(countries)]):
            pwr = data["power"]
            annex = data["annexed_count"]
            curr_alliance = get_country_alliance(base_name, alliances)
            championship_count = len(data.get("championship_records", []))
            entity_info = get_entity_info(base_name, countries, alliances)

            disp_label = (
                f"{entity_info['name']} {data['display_name']}"
                if entity_info["type"] == "ALLIANCE"
                else data["display_name"]
            )
            coalition_name = get_country_coalition(base_name, anti_hegemon_coalitions)
            if coalition_name:
                disp_label += f" [聯軍:{coalition_name}]"
            champions_str = f" (冠:{championship_count})" if championship_count > 0 else ""
            annex_str = f" [吞併:{annex}國]" if annex > 0 else ""
            status_str = "" if data["is_alive"] else " (滅亡)"
            personality_str = f" [{rl_agents[base_name].personality['name']}]"
            ai_action = data.get("last_action", "")
            ai_reward = data.get("last_reward", 0.0)
            ai_str = f" [{ai_action} R:{ai_reward:+.1f}]" if ai_action else ""
            war_str = " [⚔戰中]" if data.get("current_wars") else ""

            if i == 0:  # 第一名霸主處理
                if pwr > max_power:  # 更新歷史最高戰力紀錄
                    max_power = pwr
                    max_person = disp_label
                    max_round = count_round
                rank_text += f"歷史最高霸主紀錄 = {max_power} ({max_person} 第{max_round}屆)\n"
                rank_text += f"{medals[i]} {pwr} - {disp_label}{personality_str}{ai_str}{war_str}{champions_str}{status_str}\n"
            else:  # 其他名次顯示與前一名的戰力差距 (-diff)
                diff = sorted_countries[i - 1][1]["power"] - pwr
                rank_text += f"{medals[i]} {pwr} - {disp_label}{personality_str}{ai_str}{war_str}{champions_str}{status_str} (-{diff})\n"

        # 寫入文字檔排行榜：原子替換，避免 UI 讀到半份內容。
        try:
            _atomic_write_text("Live_Ranking.txt", rank_text.strip())
        except Exception as e:
            print(f"⚠️ [排行榜存檔警告] {e}")

        # 10. 整理與序列化寫入 JSON 存檔
        alliance_details = {}
        for ally_name, members in alliances.items():
            alive_m = [m for m in members if countries[m]["is_alive"]]
            tot_pwr = sum(countries[m]["power"] for m in alive_m)
            alliance_details[ally_name] = {
                "total_power": tot_pwr,
                "member_count": len(members),
                "alive_member_count": len(alive_m),
                "members": members,
                "target_hegemon": None,
                "is_coalition": False,
                "last_war_vote": alliance_last_war_votes.get(
                    ally_name,
                    {},
                ),
                "last_join_vote": alliance_last_join_votes.get(
                    ally_name,
                    {},
                ),
            }

        # 反霸權聯軍也輸出給 UI 顯示，但不加入 ordinary alliances。
        for coalition_name, info in anti_hegemon_coalitions.items():
            members = list(info.get("members", []))
            alive_m = [m for m in members if m in countries and countries[m].get("is_alive", True)]
            tot_pwr = sum(countries[m].get("power", 0) for m in alive_m)
            target_id = info.get("target")
            alliance_details[coalition_name] = {
                "total_power": tot_pwr,
                "member_count": len(members),
                "alive_member_count": len(alive_m),
                "members": members,
                "target_hegemon": target_id,
                "is_coalition": True,
                "created_turn": info.get("created_turn"),
                "expires_turn": info.get("expires_turn"),
            }

        try:
            _war_refresh_country_status(countries, active_wars)

            for base_name, c_data in countries.items():
                _ensure_dynamic_country_state(base_name, c_data)
                _refresh_country_event_modifiers(c_data, turn_counter)
                c_data["political_stability"] = round(float(c_data.get("political_stability", 75) or 75), 1)
                c_data["war_exhaustion"] = round(float(c_data.get("war_exhaustion", 0) or 0), 1)
                c_data["current_alliance"] = get_country_alliance(base_name, alliances)
                c_data["current_coalition"] = get_country_coalition(base_name, anti_hegemon_coalitions)
                c_data["championship_count"] = len(c_data.get("championship_records", []))

                agent = rl_agents.get(base_name)
                if agent:
                    c_data["ai_personality"] = agent.personality.get(
                        "name", agent.personality_type
                    )
                    c_data["ai_decision_count"] = agent.decision_count
                    c_data["ai_epsilon"] = round(
                        max(
                            RL_EPSILON_MIN,
                            agent.epsilon * (RL_EPSILON_DECAY ** agent.decision_count),
                        ),
                        4,
                    )
                    c_data["q_state_count"] = len(agent.q_table)

                hostility = c_data.get("hostility", {}) or {}
                live_hostility = {
                    k: int(v or 0)
                    for k, v in hostility.items()
                    if k in countries and countries[k].get("is_alive", True) and int(v or 0) > 0
                }
                if live_hostility:
                    target_key = max(live_hostility, key=live_hostility.get)
                    c_data["top_hostility_target"] = (
                        f"{countries[target_key].get('display_name', target_key)}"
                        f"（{live_hostility[target_key]}）"
                    )
                else:
                    c_data["top_hostility_target"] = "無"
                # 存檔前最後一道硬校正：JSON 中也絕不允許農夫少於士兵。
                enforce_farmer_majority(c_data)
                c_data["power"] = calculate_rts_power(c_data)

            # 編年史：存檔前再用本輪最終戰力更新一次巔峰數據。
            chronicle_alive_sorted = sorted(
                [
                    k
                    for k, v in countries.items()
                    if v.get("is_alive", True)
                ],
                key=lambda k: countries[k].get("power", 0),
                reverse=True,
            )
            chronicle_rank_map = {
                k: idx + 1
                for idx, k in enumerate(chronicle_alive_sorted)
            }
            for k in chronicle_alive_sorted:
                _ensure_country_chronicle(
                    k,
                    countries[k],
                    turn_counter,
                )
                _chronicle_update_live_stats(
                    countries[k],
                    turn_counter,
                    chronicle_rank_map.get(k),
                )

            # 斷點續跑時間資料。
            checkpoint_now = time.time()
            current_season_elapsed = min(
                float(time_total),
                max(0.0, checkpoint_now - start_time),
            )
            current_season_remaining = max(
                0.0,
                float(time_total) - current_season_elapsed,
            )
            cumulative_runtime_seconds = (
                float(completed_runtime_seconds)
                + current_season_elapsed
            )

            # 國家 / 外交 / 戰爭檔使用 atomic + compact JSON，降低 I/O 並防止半寫入。
            _atomic_write_json(
                "war_live_countries.json",
                {
                    "countries": countries,
                    "world_mode": current_world_mode,
                    "turn_counter": turn_counter,
                    "run_progress": {
                        "count_round": int(count_round),
                        "season_elapsed_seconds": round(
                            current_season_elapsed,
                            3,
                        ),
                        "season_remaining_seconds": round(
                            current_season_remaining,
                            3,
                        ),
                        "completed_runtime_seconds": round(
                            float(completed_runtime_seconds),
                            3,
                        ),
                        "cumulative_runtime_seconds": round(
                            cumulative_runtime_seconds,
                            3,
                        ),
                    },
                    "engine_version": "亂世演算V6.5.1_國家編年史快捷鍵版",
                },
                compact=COMPACT_FORMAT,
            )

            _atomic_write_json(
                "war_live_alliances.json",
                {
                    "count_round": count_round,
                    "total_world_power": total_world_power,
                    "alliance_details": alliance_details,
                    "anti_hegemon_coalitions": anti_hegemon_coalitions,
                    "anti_hegemon_targets": {
                        name: info.get("target")
                        for name, info in anti_hegemon_coalitions.items()
                    },
                    "coalition_target_cooldowns": coalition_target_cooldowns,
                    "coalition_member_cooldowns": coalition_member_cooldowns,
                    "hegemon_streaks": hegemon_streaks,
                    "active_wars": active_wars,
                    "war_truces": war_truces,
                    "war_sequence": war_sequence,
                    "alliance_war_vote_cooldowns": alliance_war_vote_cooldowns,
                    "alliance_last_war_votes": alliance_last_war_votes,
                    "alliance_join_vote_cooldowns": alliance_join_vote_cooldowns,
                    "alliance_last_join_votes": alliance_last_join_votes,
                    "turn_counter": turn_counter,
                    "historical_max_power": max_power,
                    "historical_max_person": max_person,
                    "historical_max_round": max_round,
                    "dynamic_event_counter": dynamic_event_counter,
                    "world_mode": current_world_mode,
                    "next_world_mode_turn": next_world_mode_turn,
                    "world_mode_counter": world_mode_counter,
                    "season_elapsed_seconds": round(
                        current_season_elapsed,
                        3,
                    ),
                    "season_remaining_seconds": round(
                        current_season_remaining,
                        3,
                    ),
                    "completed_runtime_seconds": round(
                        float(completed_runtime_seconds),
                        3,
                    ),
                    "cumulative_runtime_seconds": round(
                        cumulative_runtime_seconds,
                        3,
                    ),
                    "engine_version": "亂世演算V6.5.1_國家編年史快捷鍵版",
                },
                compact=COMPACT_FORMAT,
            )

            # 世界狀態完成落盤後，最後才更新獨立斷點檔。
            # 這樣即使寫檔途中中斷，也不會拿「超前的時間」去配「較舊的世界狀態」。
            checkpoint_payload = {
                "count_round": int(count_round),
                "season_elapsed_seconds": round(
                    current_season_elapsed,
                    3,
                ),
                "season_remaining_seconds": round(
                    current_season_remaining,
                    3,
                ),
                "season_total_seconds": float(time_total),
                "completed_runtime_seconds": round(
                    float(completed_runtime_seconds),
                    3,
                ),
                "cumulative_runtime_seconds": round(
                    cumulative_runtime_seconds,
                    3,
                ),
                "turn_counter": int(turn_counter),
                "saved_at_unix": round(checkpoint_now, 3),
                "engine_version": "亂世演算V6.5.1_國家編年史快捷鍵版",
            }
            _atomic_write_json(
                runtime_checkpoint_file,
                checkpoint_payload,
                compact=COMPACT_FORMAT,
            )

            _atomic_write_text(
                runtime_progress_text_file,
                (
                    f"亂世演算｜執行進度\n"
                    f"第 {count_round} 屆\n"
                    f"本屆已執行：{current_season_elapsed:.1f} / "
                    f"{float(time_total):.0f} 秒\n"
                    f"本屆剩餘：約 {current_season_remaining:.1f} 秒\n"
                    f"已完成歷屆秒數："
                    f"{float(completed_runtime_seconds):.1f} 秒\n"
                    f"累積模擬時間：{cumulative_runtime_seconds:.1f} 秒\n"
                    f"Turn：{turn_counter}\n"
                ),
            )

            # 保存所有 RL Agent 的 Q-Tables。
            # 不再每 2 秒序列化一次，降低長時間運行的 RAM / I/O 壓力。
            if (
                turn_counter % QTABLE_SAVE_INTERVAL_TURNS
                == 0
            ):
                save_all_agents(
                    rl_agents,
                    file_path=q_tables_file,
                )

        except Exception as e:
            print(f"⚠️ [世界存檔警告] {e}")

        # 11. 屆期結算檢查 (達到 time_total 時間即進行本屆冠軍結算與新一屆重置)
        if (time.time() - start_time) > time_total:
            if sorted_countries:
                champion_key, champion_data = sorted_countries[0]
                champion_power = champion_data["power"]

                if not isinstance(champion_data.get("championship_records"), list):
                    champion_data["championship_records"] = []

                # 紀錄冠軍歷史
                champion_data["championship_records"].append(
                    f"R{count_round}__{champion_power}__{champion_data['display_name']}"
                )
                print(f"🏆 [第 {count_round} 屆結算] 恭喜【{champion_data['display_name']}】以 {champion_power} 戰力獲勝！")

            # 本屆正式完成；累積時間只計本屆規定秒數，
            # 避免 Game Loop 排程延遲造成額外秒數灌入下一屆。
            completed_runtime_seconds += float(time_total)
            count_round += 1  # 進入下一屆

            # 重置戰術狀態
            for name, c_data in countries.items():
                c_data["recent_attackers"] = []
                c_data["infamy"] = 0
            start_time = time.time()  # 新一屆從 0 秒開始

            # 結算後立即留下人類可讀的進度提示。
            # 完整世界狀態仍會在下一個 Game Loop 正常寫入。
            try:
                _atomic_write_text(
                    runtime_progress_text_file,
                    (
                        f"亂世演算｜執行進度\n"
                        f"第 {count_round} 屆\n"
                        f"本屆已執行：0.0 / "
                        f"{float(time_total):.0f} 秒\n"
                        f"本屆剩餘：約 {float(time_total):.1f} 秒\n"
                        f"已完成歷屆秒數："
                        f"{float(completed_runtime_seconds):.1f} 秒\n"
                        f"累積模擬時間："
                        f"{float(completed_runtime_seconds):.1f} 秒\n"
                        f"Turn：{turn_counter}\n"
                    ),
                )
            except Exception as progress_error:
                print(
                    f"⚠️ [進度紀錄警告] {progress_error}"
                )

        # 本輪所有 LOG 統一落盤；Full GC 改為每 30 輪一次。
        flush_game_log(force=True)
        time.sleep(2)
        if turn_counter % GC_INTERVAL_TURNS == 0:
            gc.collect()


# 程式進入點 (Main Entry)
if __name__ == "__main__":
    # 建立多線程背景執行 thread_stat_monitor 函式 (Daemon 模式隨主線程結束)
    t2 = threading.Thread(target=thread_stat_monitor, daemon=True)
    t2.start()  # 啟動線程

    try:
        while True:  # 主線程持續保持運行狀態
            time.sleep(1)
    except KeyboardInterrupt:  # 監聽 Ctrl+C 終止訊號，實現平滑離開
        pass