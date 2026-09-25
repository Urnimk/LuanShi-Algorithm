import json  # 匯入 JSON 模組，用於讀取與儲存 JSON 格式的檔案（例如國家資料、 Q-Table 檔案）
import math  # 匯入數學模組，用於無條件進位（math.ceil）等計算
import os  # 匯入作業系統模組，用於檢查檔案或路徑是否存在
import random  # 匯入隨機模組，用於隨機事件、隨機選擇與機率判斷
import re  # V6：解析國號中的復國羅馬世代與政權世系
import threading  # 匯入多線程模組，用於背景執行戰局監控任務
import time  # 匯入時間模組，用於計算執行時間與時間延遲（sleep）
import gc  # 匯入垃圾回收模組 (Garbage Collection)，用於定期清理記憶體
import uuid
import shutil
import csv
from collections import deque  # 從 collections 匯入雙端隊列 deque，用於維護固定長度的 Log 訊息緩衝區
from decision_analysis import NationalDecisionHub
from strategy_states import strategic_state_256, readable_q_text
from policy_index import policy_cost, initialize as policy_index_initialize, settle_season as policy_index_settle_season, settle_currency_name
from fiscal_policy import (FISCAL_ACTIONS, treasury_circulation, fiscal_state,
                           fiscal_valid_actions, delayed_fiscal_reward, fiscal_q_report)

# 全域變數
last_sync_time = time.time()  # 紀錄最後同步時間點（初始化為當前時間秒數）
world_stage_g = 0  # RL 世界力量階段：BALANCED / RISING / EMPIRE
world_mode_g = "平常局勢"
world_mode_code_g = "NORMAL"
ENGINE_VERSION = "亂世演算V8_6_2_附庸生存實驗版"

# True：保留世界貨幣、市場與交易 AI；False：完整停用並改採混合資源政策成本。
MARKET_ECONOMY_ENABLED = False
RESOURCE_POLICY_COST_RATE = 0.10

# ============================================================================
# 【世界時間與屆期參數】所有時間顯示與結算只以這裡為準
# ============================================================================
WORLD_START_YEAR = 1             # 第一個 Game Loop 顯示為世界曆第 1 年
YEARS_PER_TURN = 1               # 固定：1 回合 = 1 年
SECONDS_PER_YEAR = 2.0           # 預設現實 2 秒推進 1 回合／1 年
YEARS_PER_SEASON = 500           # 一屆固定 500 年（500 回合）
SEASON_DURATION_SECONDS = YEARS_PER_SEASON * SECONDS_PER_YEAR
SEASON_SECONDS = SEASON_DURATION_SECONDS  # 舊介面相容名稱，禁止再除以秒／年

# 【新生與重建保護參數】單位都是世界年；1 年就是 1 回合
NEW_COUNTRY_PROTECTION_YEARS = 10
REBUILD_PROTECTION_YEARS = 200
REBUILD_PROTECTION_BLOCK_ATTACK = True
REBUILD_PROTECTION_BLOCK_ALLIANCE = False

# 【新國家安全準備】不增加 Q 維度；以連續分數輔助原本四維狀態
SURVIVAL_PREPARATION_WINDOW_YEARS = 50 # 脫保前多少年開始強化備戰學習
SECURITY_SAFE_THRESHOLD = 35           # 低於此分視為安全
SECURITY_CRITICAL_THRESHOLD = 70       # 達此分視為危急
SECURITY_TARGET_SOLDIER_RATIO = 0.25   # 脫保時希望至少 25% 人口為士兵
SECURITY_TARGET_FORTIFICATION = 40     # 脫保時希望至少 40 城防
SECURITY_TARGET_SUPPLY_YEARS = 5.0     # 糧食與金屬至少支撐 5 年戰爭
SECURITY_POST_PROTECTION_MILESTONES = (25, 50, 100)

# 【普通聯盟成長】未滿 5 國時逐步降低入盟門檻，滿 5 國後停止收人
ALLIANCE_MAX_MEMBERS = 5
ALLIANCE_EXISTING_JOIN_CHANCE = 0.80 # 有空缺聯盟時，優先申請加入而非另創新盟
ALLIANCE_UNDERFILLED_JOIN_BONUS = {
    1: 0.20,
    2: 0.16,
    3: 0.10,
    4: 0.05,
}

# 【弱國主權韌性】不延長無敵期，改用準備、外交代價、本土防禦與分層戰敗
PRE_RELEASE_GUARANTEED_ACTION_YEARS = 50 # 脫保前最後 50 年每年保證一次自主決策
POST_PROTECTION_TRANSITION_YEARS = 50   # 脫保後國際仍特別關注的過渡期
POST_PROTECTION_TARGET_SCORE_PENALTY = 45.0
POST_PROTECTION_ATTACK_INFAMY = 18
POST_PROTECTION_ATTACK_DREAD = 6000
POST_PROTECTION_ATTACK_STABILITY_LOSS = 6.0
HOMELAND_DEFENSE_BONUS_MAX = 0.35       # 極端兵力差下最高 35% 本土防禦加成
SUBJUGATION_BEFORE_ANNEXATION = 1       # 第一次國都陷落先附庸，再次才可能滅國
VASSAL_DURATION_YEARS = 150
CAPITULATION_PROTECTION_YEARS = 40
VASSAL_REPARATION_RATE = 0.12

# ============================================================================
# 【反霸權圍剿參數】全部以世界年／國家數為單位，集中於頂部方便調整
# ============================================================================
COALITION_MAX_ACTIVE = 4             # 同時最多存在 4 個圍剿聯盟
COALITION_MIN_MEMBERS = 3            # 成立所需最低成員數
COALITION_MAX_MEMBERS = 5            # 每個圍剿聯盟最多 5 國
COALITION_ONE_PER_TARGET = True       # 同一目標同時只能被一個圍剿聯盟鎖定
COALITION_ATTACK_INTERVAL_YEARS = 100 # 至少每 100 年主動討伐目標一次
COALITION_INITIAL_ATTACK_DELAY_YEARS = 10 # 成立後最晚 10 年內發動第一次討伐
COALITION_TARGET_POWER_RATIO = 0.95   # 招募至聯軍戰力約為目標 95% 即停止
COALITION_MAX_DURATION = 500          # 圍剿聯盟最長存在年數
COALITION_COOLDOWN_YEARS = 12         # 解散後目標與成員的冷卻年數
HEGEMON_SHARE_TRIGGER = 0.15          # 戰力占全球 15% 視為霸權候選
HEGEMON_LEAD_TRIGGER = 1.80           # 或戰力達第二名 1.8 倍
HEGEMON_REQUIRED_STREAK = 3           # 連續維持幾年才成為一般霸權目標
INTERNATIONAL_DREAD_CANDIDATE_THRESHOLD = 100000 # 達此忌憚值即可成為圍剿目標
COALITION_FORMATION_BOUNTY_BASE = 10  # 成立懸賞（再乘 MONEY_RATIO）
COALITION_VICTORY_BOUNTY_BASE = 60    # 勝利懸賞（再乘 MONEY_RATIO）

# 無守軍攻城仍可能因城防、陷阱與事故受傷，但不再按攻方大軍總數固定扣 1%~4%。
UNDEFENDED_SIEGE_ATTACKER_LOSS_PER_FORT = 0.35
UNDEFENDED_SIEGE_ATTACKER_LOSS_RATE_CAP = 0.005
UNDEFENDED_CAPITAL_FORT_THRESHOLD = 0 # 無守軍且城防降至此值，當回合國都陷落
UNDEFENDED_MAX_SIEGE_YEARS = 3        # 無守軍但仍有城防，最多再抵抗 3 年


# 所有執行期讀寫檔集中放在程式旁的 saves 資料夾。
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES_DIR = os.path.join(PROJECT_DIR, "saves")
os.makedirs(SAVES_DIR, exist_ok=True)

def save_path(filename):
    """回傳 saves 內的絕對路徑，並防止檔名跳脫存檔資料夾。"""
    safe_name = os.path.basename(str(filename))
    return os.path.join(SAVES_DIR, safe_name)

# UI 可安全控制背景模擬；預設維持原本每輪 2 秒。
_simulation_paused = threading.Event()
_simulation_step = threading.Event()
_simulation_speed_lock = threading.Lock()
_simulation_delay_seconds = SECONDS_PER_YEAR


def set_simulation_paused(paused=True):
    if paused:
        _simulation_paused.set()
    else:
        _simulation_paused.clear()


def toggle_simulation_paused():
    set_simulation_paused(not _simulation_paused.is_set())
    return _simulation_paused.is_set()


def request_simulation_step():
    _simulation_step.set()


def set_simulation_speed(delay_seconds):
    global _simulation_delay_seconds
    with _simulation_speed_lock:
        _simulation_delay_seconds = max(0.05, float(delay_seconds))


def get_simulation_control_state():
    with _simulation_speed_lock:
        return {"paused": _simulation_paused.is_set(), "delay": _simulation_delay_seconds}


def _wait_for_simulation_permission():
    while _simulation_paused.is_set() and not _simulation_step.is_set():
        time.sleep(0.10)
    _simulation_step.clear()

# ================================================
# 📜 Log 自動寫入文字檔（最新訊息在第一行，限制 1000 行）
# ================================================
LOG_FILE = save_path("game.log")
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
    if os.path.exists(path):
        try:
            shutil.copy2(path, str(path) + ".bak")
        except OSError:
            pass
    os.replace(temp_path, path)


def _tuple_tree(value):
    if isinstance(value, list):
        return tuple(_tuple_tree(v) for v in value)
    return value


def _load_consistent_snapshot_pair(countries_file, alliances_file):
    """從主檔或 .bak 選出 snapshot_id 一致且 turn 最新的一組。"""
    candidates = []
    for c_path in (countries_file, countries_file + ".bak"):
        for a_path in (alliances_file, alliances_file + ".bak"):
            if not os.path.exists(c_path) or not os.path.exists(a_path):
                continue
            try:
                with open(c_path, "r", encoding="utf-8") as f_c:
                    c_data = json.load(f_c)
                with open(a_path, "r", encoding="utf-8") as f_a:
                    a_data = json.load(f_a)
                c_sid = c_data.get("snapshot_id")
                a_sid = a_data.get("snapshot_id")
                if c_sid or a_sid:
                    if not c_sid or c_sid != a_sid:
                        continue
                elif int(c_data.get("turn_counter", 0) or 0) != int(a_data.get("turn_counter", 0) or 0):
                    continue
                score = min(int(c_data.get("turn_counter", 0) or 0), int(a_data.get("turn_counter", 0) or 0))
                candidates.append((score, c_path == countries_file and a_path == alliances_file, c_data, a_data, c_path, a_path))
            except (OSError, ValueError, TypeError):
                continue
    if not candidates:
        raise RuntimeError("找不到一致的國家／聯盟存檔組合")
    _score, primary, c_data, a_data, c_path, a_path = max(candidates, key=lambda item: (item[0], item[1]))
    return c_data, a_data, c_path, a_path


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
BALANCE_VERSION = 10
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
SUCCESSION_MIN_TENURE = 2500
SUCCESSION_CHANCE_PER_COUNTRY = 0.1

# 舊程式引用名稱保留相容；新建國與重建國已分成頂部兩組參數。
NEWBIE_PROTECTION_TURNS = NEW_COUNTRY_PROTECTION_YEARS

# 戰前軍事風險評估：不是開戰後才補兵，而是在和平期先觀察潛在攻擊者。
# 沒有地理地圖時，以戰力排名前後各 3 名作為「潛在攻擊者」。
PREWAR_THREAT_CANDIDATE_COUNT = 5
PREWAR_RISK_ALERT = 45
PREWAR_RISK_HIGH = 65
PREWAR_RISK_CRITICAL = 85
PREWAR_MOBILIZE_SOFT_CHANCE_MIN = 0.10
PREWAR_MOBILIZE_SOFT_CHANCE_MAX = 0.45
PREWAR_CRITICAL_SOLDIER_RATIO = 0.22
PREWAR_RESOURCE_FOOD_RUNWAY = 4.0
PREWAR_RESOURCE_METAL_PER_POP = 0.20
# 自身軍民失衡預警：農民相對士兵過多時，即使沒有明確敵人，也要提高戰備危機。
PREWAR_FARMER_SOLDIER_ALERT_RATIO = 3.0
PREWAR_FARMER_SOLDIER_HIGH_RATIO = 4.0
PREWAR_FARMER_SOLDIER_CRITICAL_RATIO = 4.5
PREWAR_FORCE_BALANCE_ALERT_SCORE = 45.0
PREWAR_FORCE_BALANCE_HIGH_SCORE = 65.0
PREWAR_FORCE_BALANCE_CRITICAL_SCORE = 82.0

# 動態事件持續時間（Game Loop）。
EVENT_DURATION_SHORT = 5
EVENT_DURATION_NORMAL = 8
EVENT_DURATION_LONG = 10


#貨幣倍率
MONEY_RATIO = 1
INIT_GOLD = 0

# 基礎建設是永久投資：實際支付三種資產，換取正式生產與市場效率。
INFRASTRUCTURE_MAX = 100
INFRASTRUCTURE_GOLD_BASE = 60 * MONEY_RATIO
INFRASTRUCTURE_WOOD_BASE = 50
INFRASTRUCTURE_METAL_BASE = 20
INDUSTRY_FOCUS_DURATION = 8

BALANCE = {
    # 人口與住房
    "HOUSE_WOOD_COST": 100,
    # 房屋接近滿載才擴建，避免容量長期遠高於人口。
    "HOUSE_BUILD_THRESHOLD": 0.93,
    # 若房屋容量長期超過人口 30%，每輪會有少量閒置房屋自然荒廢。
    "HOUSE_EXCESS_CAPACITY_RATIO": 2.0,
    "HOUSE_ABANDON_MAX_PER_TURN": 6,
    "FOOD_COST_PER_BIRTH": 8,
    "BIRTH_MIN_RESERVE_TURNS": 5.0,
    "BIRTH_RATE_MIN": 0.015,
    "BIRTH_RATE_MAX": 0.030,
    "BIRTH_MAX_PER_TURN": 10,

    # 農民基礎產能（每名被分派到該工作的農民／每輪）
    "FOOD_PER_WORKER": 6.0,  # 4.2
    "WOOD_PER_WORKER": 3.0,
    "METAL_PER_WORKER": 2.0, # 1.7 

    # 每輪消耗
    "FARMER_FOOD_UPKEEP": 1.0,
    # 每名農民每輪另需 0.5 木材，用於住宅裝修；金屬、糧食消耗不變。
    "FARMER_WOOD_UPKEEP": 0,
    "SOLDIER_FOOD_UPKEEP": 2.0,
    "SOLDIER_METAL_UPKEEP": 0.20,
    # 房屋每年維修消耗木材，按小數累積至整數再扣。
    "HOUSE_WOOD_UPKEEP_PER_HOUSE": 0.05,
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
    "SURPLUS_FOOD_TURNS": 8.5,

    # 庫存過高時，採集效率下降（不是硬砍庫存）
    "SURPLUS_PRODUCTION_FACTOR": 0.12,
    "SURPLUS_FOOD_PRODUCTION_FACTOR": 0.28,
    "WOOD_SURPLUS_MIN_FACTOR": 0.005,
    "WOOD_SURPLUS_DAMPING_EXPONENT": 8,
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
    "WAR_WOOD_PER_SOLDIER": 0.50,

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
    # V8 世界共同貨幣：由世界銀行發行，不可由各國自行印鈔。
    "START_GOLD_MIN": 400*MONEY_RATIO,
    "START_GOLD_MAX": 400*MONEY_RATIO,
}

# ====================================================
# 【V8 世界銀行 / 世界市場】
# ====================================================
CURRENCY_VERSION = 1
WORLD_BANK_NAME = "世界銀行"
WORLD_CURRENCY_NAME = "大洋"
# 只作名稱備選；所有名稱使用同一套 gold 帳本，不會自動兌換。
WORLD_CURRENCY_NAME_OPTIONS = (
    "大洋", "銀幣", "白銀", "銀元", "銀圓", "通寶", "世界幣", "聯邦幣", "商幣", "國際幣",
    "銀兩", "銀票", "銀盾", "月銀", "星幣", "海元", "商銀", "環球幣", "銀冠", "新大洋", "曜銀",
)
WORLD_BANK_RESPAWN_GRANT = 120*MONEY_RATIO
WORLD_BANK_TRANSACTION_FEE_RATE = 0.01
WORLD_BANK_LIQUIDITY_INTERVAL = 10
WORLD_BANK_MIN_RESERVE = WORLD_BANK_RESPAWN_GRANT * 3
WORLD_BANK_LIQUIDITY_SHARE = 0.20
WORLD_BANK_LIQUIDITY_GRANT_CAP = 60*MONEY_RATIO
CURRENCY_AUDIT_TOLERANCE = 0

MARKET_RESOURCES = ("food", "wood", "metal")
MARKET_RESOURCE_META = {
    "food": {"name": "糧食", "seed_price": 1.00*MONEY_RATIO},
    "wood": {"name": "木材", "seed_price": 1.80*MONEY_RATIO},
    "metal": {"name": "金屬", "seed_price": 3.20*MONEY_RATIO},
}
MARKET_ORDER_TTL = 4
MARKET_MAX_ORDERS = 300
MARKET_TRADE_HISTORY_MAX = 60
MARKET_PRICE_HISTORY_MAX = 40
MARKET_PRICE_LIMIT_RATE = 0.20
MARKET_VWAP_WINDOW = 10
# 市場允許低價掛單；僅在屆末以國家間實際成交判斷是否重定面額。
MARKET_PRICE_FLOOR_RATE = 0.00001
MARKET_PRICE_CEILING_RATE = 2.50
WORLD_BANK_ISSUE_TRIGGER_RATE = 0.10
# V8_5_5：以真實成交監測價格，而非用最後報價或固定價撐市。
MARKET_MONITOR_INTERVAL = 10             # 每 10 年彙整一次；不在每輪讀寫大量成交紀錄
MARKET_MONITOR_HISTORY = 24
MARKET_MONITOR_MIN_RESOURCE_QTY = 3     # 單資源過小成交，不列為有效價格樣本
MARKET_MONITOR_MIN_TOTAL_QTY = 20
MARKET_BASKET_WEIGHTS = {"food": 0.50, "wood": 0.30, "metal": 0.20}
MARKET_DEFLATION_3WINDOW = 0.03       # 連續 3 個觀測窗，累積跌幅至少 3%
MARKET_VOLUME_CONTRACTION = 0.80     # 最近成交量 < 前兩窗平均 80%
MARKET_CASH_STRESS_FRACTION = 0.50   # 至少半數存活國家缺乏流動性
MARKET_ISSUE_PER_OPERATION = 0.001  # 單次最多當前貨幣存量 0.1%
MARKET_ISSUE_PER_SEASON = 0.01      # 一屆累計最多屆初貨幣存量 1%

# 世界銀行不再以買入商品的方式發行貨幣。

BIRTH_POLICY_GOLD_COST = 120*MONEY_RATIO
BIRTH_POLICY_DURATION = 12
BIRTH_POLICY_MULT = 1.80
PRODUCTION_POLICY_GOLD_COST = 150*MONEY_RATIO
PRODUCTION_POLICY_DURATION = 10
PRODUCTION_POLICY_MULT = 1.50
DIPLOMACY_GOLD_MIN = 60*MONEY_RATIO
DIPLOMACY_GOLD_MAX = 150*MONEY_RATIO


def _default_price_monitor():
    """價格與流動性觀察狀態；不從單筆交易或無成交時的舊價推斷物價。"""
    return {
        "schema": 1,
        "last_observed_turn": -1,
        "last_cumulative": {r: {"qty": 0, "value": 0} for r in MARKET_RESOURCES},
        "history": [],
        "latest": {},
    }


def _default_world_bank():
    return {
        "name": WORLD_BANK_NAME,
        "currency": WORLD_CURRENCY_NAME,
        "issued_total": 0,
        "treasury": 0,
        "policy_collected": 0,
        "transaction_fees_collected": 0,
        "respawn_grants": 0,
        "liquidity_redistributed": 0,
        "liquidity_operations": 0,
        "currency_audit_gap": 0,
        "currency_audit_ok": True,
        "circulating_total": 0,
        "last_action": "建立世界共同貨幣制度",
        "market_issued_total": 0,
        "market_issue_operations": 0,
        "market_issue_last_turn": {res: -1 for res in MARKET_RESOURCES},
        "currency_name_index": 0,
        "deflation_episode_active": False,
        "currency_rename_last_turn": -1,
        "policy_price_index": 1.0,
        "policy_base_circulation": 0,
        "policy_base_real_basket": 0.0,
        "policy_index_target": 1.0,
        "policy_last_round": 0,
        "policy_index_schema": 0,
        "initial_issued_total": 0,
        "policy_base_population": 0,
        "policy_last_observed_turn": -1,
        "policy_deflation_streak": 0,
        "currency_last_checked_round": 0,
        "currency_last_observed_turn": -1,
        "currency_deflation_streak": 0,
        "currency_recovery_streak": 0,
        "currency_episode_active": False,
        "currency_rename_last_round": -999,
        "currency_rename_trigger_rate": WORLD_BANK_ISSUE_TRIGGER_RATE,
        "currency_denomination": 1,
        "market_issue_season": 0,
        "market_issue_season_budget": 0,
        "market_issued_this_season": 0,
        # 舊存檔銀行留存的實物庫存；新版本不再買賣。
        "market_reserves": {res: 0 for res in MARKET_RESOURCES},
        "stabilization_issued_total": 0,
        "stabilization_issue_operations": 0,
        "stabilization_issue_season": 0,
        "stabilization_issued_this_season": 0,
        "stabilization_season_base": 0,
        "stabilization_last_turn": -1,
    }


def _default_world_market():
    stats = {}
    for res in MARKET_RESOURCES:
        seed = float(MARKET_RESOURCE_META[res]["seed_price"])
        stats[res] = {
            "name": MARKET_RESOURCE_META[res]["name"],
            "last_price": seed,
            "best_bid": None,
            "best_ask": None,
            "buy_qty": 0,
            "sell_qty": 0,
            "traded_volume": 0,
            "traded_value": 0,
            "last_trade_volume": 0,
            "last_trade_turn": 0,
            "price_history": [seed],
            "vwap_10": seed,
            "trade_count": 0,
        }
    return {
        "schema_version": 1,
        "currency_denomination": 1,
        "orders": [],
        "stats": stats,
        "recent_trades": [],
        "order_sequence": 0,
        "orders_placed": 0,
        "orders_expired": 0,
        "orders_filled": 0,
        "price_monitor": _default_price_monitor(),
    }


def _disable_market_runtime(market):
    """清除未成交委託；保留歷史統計供切回 True 後繼續觀察。"""
    market["orders"] = []
    for stat in (market.get("stats", {}) or {}).values():
        stat["best_bid"] = None
        stat["best_ask"] = None
        stat["buy_qty"] = 0
        stat["sell_qty"] = 0
    market.setdefault("price_monitor", {})["latest"] = {
        "turn": -1, "reliable": False, "diagnosis": "市場與貨幣功能已關閉",
        "volume": 0, "cash_stressed": 0, "floor_cash_stress": False,
        "floor_pressure_resources": [],
    }


def _normalize_world_bank(bank):
    base = _default_world_bank()
    if isinstance(bank, dict):
        base.update(bank)
    base["market_reserves"] = dict(base.get("market_reserves", {}) or {})
    for res in MARKET_RESOURCES:
        base["market_reserves"][res] = max(0, int(base["market_reserves"].get(res, 0) or 0))
    issue_turns = base.get("market_issue_last_turn")
    if not isinstance(issue_turns, dict):
        issue_turns = {}
    base["market_issue_last_turn"] = {
        res: int(issue_turns.get(res, -1) or -1) for res in MARKET_RESOURCES
    }
    # 舊存檔沒有索引時沿用現有合法名稱，否則從大洋開始。
    current = base.get("currency", WORLD_CURRENCY_NAME)
    if "currency_name_index" not in (bank or {}):
        base["currency_name_index"] = (WORLD_CURRENCY_NAME_OPTIONS.index(current)
                                       if current in WORLD_CURRENCY_NAME_OPTIONS else 0)
    base["currency_name_index"] = max(0, int(base["currency_name_index"] or 0)) % len(WORLD_CURRENCY_NAME_OPTIONS)
    base["currency"] = WORLD_CURRENCY_NAME_OPTIONS[base["currency_name_index"]]
    base["deflation_episode_active"] = bool(base.get("deflation_episode_active", False))
    base["currency_rename_last_turn"] = int(base.get("currency_rename_last_turn", -1))
    base["policy_price_index"] = max(0.0, float(base.get("policy_price_index", 1.0) or 1.0))
    base["initial_issued_total"] = max(0, int(base.get("initial_issued_total", 0) or 0))
    base["policy_base_circulation"] = max(0, int(base.get("policy_base_circulation", 0) or 0))
    base["policy_base_real_basket"] = max(0.0, float(base.get("policy_base_real_basket", 0) or 0))
    base["policy_index_target"] = max(0.0, float(base.get("policy_index_target", 1.0) or 1.0))
    base["policy_last_round"] = max(0, int(base.get("policy_last_round", 0) or 0))
    for key in ("policy_index_schema", "policy_base_population", "policy_deflation_streak",
                "currency_last_checked_round", "currency_deflation_streak", "currency_recovery_streak",
                "market_issue_season", "market_issue_season_budget", "market_issued_this_season"):
        base[key] = max(0, int(base.get(key, 0) or 0))
    for key in ("policy_last_observed_turn", "currency_last_observed_turn", "currency_rename_last_round"):
        base[key] = int(base.get(key, -1) if base.get(key) is not None else -1)
    base["stabilization_last_turn"] = int(base.get("stabilization_last_turn", -1) if base.get("stabilization_last_turn") is not None else -1)
    base["currency_episode_active"] = bool(base.get("currency_episode_active", False))
    base["currency_rename_trigger_rate"] = WORLD_BANK_ISSUE_TRIGGER_RATE
    base["currency_denomination"] = max(1, int(base.get("currency_denomination", 1) or 1))
    for key in (
        "market_issued_total", "market_issue_operations",
        "issued_total", "treasury", "policy_collected",
        "transaction_fees_collected", "respawn_grants",
        "liquidity_redistributed", "liquidity_operations",
        "stabilization_issued_total", "stabilization_issue_operations",
        "stabilization_issue_season", "stabilization_issued_this_season",
        "stabilization_season_base",
    ):
        base[key] = max(0, int(base.get(key, 0) or 0))
    return base


def _normalize_world_market(market):
    base = _default_world_market()
    if not isinstance(market, dict):
        return base
    base["schema_version"] = 1
    base["currency_denomination"] = max(1, int(market.get("currency_denomination", 1) or 1))
    base["order_sequence"] = max(0, int(market.get("order_sequence", 0) or 0))
    for key in ("orders_placed", "orders_expired", "orders_filled"):
        base[key] = max(0, int(market.get(key, 0) or 0))
    base["orders"] = list(market.get("orders", []) or [])[-MARKET_MAX_ORDERS:]
    base["recent_trades"] = list(market.get("recent_trades", []) or [])[-MARKET_TRADE_HISTORY_MAX:]
    old_stats = market.get("stats", {}) or {}
    old_monitor = market.get("price_monitor")
    if isinstance(old_monitor, dict) and old_monitor.get("schema") == 1:
        base["price_monitor"].update(old_monitor)
        base["price_monitor"]["history"] = list(old_monitor.get("history", []) or [])[-MARKET_MONITOR_HISTORY:]
        base["price_monitor"]["last_cumulative"] = dict(old_monitor.get("last_cumulative", {}) or {})
    else:
        # 舊存檔的歷史累計成交不能當成新版本第一個觀測窗的成交量。
        base["price_monitor"]["last_cumulative"] = {
            r: {"qty": max(0, int((market.get("stats", {}).get(r, {}) or {}).get("traded_volume", 0) or 0)),
                "value": max(0, int((market.get("stats", {}).get(r, {}) or {}).get("traded_value", 0) or 0))}
            for r in MARKET_RESOURCES
        }
    for res in MARKET_RESOURCES:
        if isinstance(old_stats.get(res), dict):
            base["stats"][res].update(old_stats[res])
        stat = base["stats"][res]
        stat["last_price"] = max(0.01, float(stat.get("last_price", MARKET_RESOURCE_META[res]["seed_price"]) or MARKET_RESOURCE_META[res]["seed_price"]))
        stat["price_history"] = list(stat.get("price_history", []) or [])[-MARKET_PRICE_HISTORY_MAX:]
        if not stat["price_history"]:
            stat["price_history"] = [stat["last_price"]]
    return base


def _world_bank_collect(bank, amount, category="policy"):
    if not MARKET_ECONOMY_ENABLED:
        return 0
    amount = max(0, int(amount or 0))
    if amount <= 0:
        return 0
    bank["treasury"] = max(0, int(bank.get("treasury", 0) or 0)) + amount
    if category == "fee":
        bank["transaction_fees_collected"] = max(0, int(bank.get("transaction_fees_collected", 0) or 0)) + amount
    else:
        bank["policy_collected"] = max(0, int(bank.get("policy_collected", 0) or 0)) + amount
    return amount


def _mixed_resource_cost(data, rate=RESOURCE_POLICY_COST_RATE):
    """無貨幣模式的共通政策成本：三種資源各取現有庫存 10%。"""
    return {
        resource: min(
            max(0, int(data.get(resource, 0) or 0)),
            max(0, int(math.ceil(max(0, int(data.get(resource, 0) or 0)) * rate))),
        )
        for resource in MARKET_RESOURCES
    }


def _pay_mixed_resource_cost(data, rate=RESOURCE_POLICY_COST_RATE):
    costs = _mixed_resource_cost(data, rate)
    for resource, amount in costs.items():
        data[resource] = max(0, int(data.get(resource, 0) or 0) - amount)
    return costs


def _mixed_cost_value(costs):
    """僅供 Reward 比較，不是貨幣換算或交易價格。"""
    return sum(max(0, int(costs.get(resource, 0) or 0)) for resource in MARKET_RESOURCES)


def _format_mixed_cost(costs):
    return f"糧:{costs.get('food', 0)}／木:{costs.get('wood', 0)}／金屬:{costs.get('metal', 0)}"


def _market_transaction_fee(gross):
    """小額交易免最低 1 枚手續費；收費時也保留賣方至少 1 枚。"""
    gross = max(0, int(gross))
    if gross < 100:
        return 0
    return min(gross - 1, max(1, int(math.ceil(gross * WORLD_BANK_TRANSACTION_FEE_RATE))))


def _world_bank_grant(bank, country_data, amount, reason="援助"):
    if not MARKET_ECONOMY_ENABLED:
        return 0
    amount = max(0, int(amount or 0))
    if amount <= 0:
        return 0
    treasury = max(0, int(bank.get("treasury", 0) or 0))
    from_treasury = min(treasury, amount)
    newly_issued = amount - from_treasury
    bank["treasury"] = treasury - from_treasury
    if newly_issued > 0:
        bank["issued_total"] = max(0, int(bank.get("issued_total", 0) or 0)) + newly_issued
    country_data["gold"] = max(0, int(country_data.get("gold", 0) or 0)) + amount
    if reason == "重建援助":
        bank["respawn_grants"] = max(0, int(bank.get("respawn_grants", 0) or 0)) + amount
    bank["last_action"] = f"{reason}：{amount} {bank.get('currency', WORLD_CURRENCY_NAME)}"
    return amount


def _world_bank_pay_bounty(bank, country_data, amount, reason="國際懸賞"):
    if not MARKET_ECONOMY_ENABLED:
        return 0
    """懸賞只能從銀行現有庫存支付，不因圍剿憑空發行新幣。"""
    treasury = max(0, int(bank.get("treasury", 0) or 0))
    paid = min(treasury, max(0, int(amount or 0)))
    if paid <= 0:
        return 0
    bank["treasury"] = treasury - paid
    country_data["gold"] = max(0, int(country_data.get("gold", 0) or 0)) + paid
    bank["last_action"] = f"{reason}：{paid} {bank.get('currency', WORLD_CURRENCY_NAME)}"
    return paid


def _currency_audit(countries, bank, raise_on_error=False):
    """核對發行總額 = 各國持有 + 世界銀行庫存。"""
    country_total = sum(
        max(0, int(data.get("gold", 0) or 0))
        for data in countries.values()
    )
    treasury = max(0, int(bank.get("treasury", 0) or 0))
    issued = max(0, int(bank.get("issued_total", 0) or 0))
    accounted = country_total + treasury
    gap = issued - accounted
    bank["circulating_total"] = country_total
    bank["currency_audit_gap"] = gap
    bank["currency_audit_ok"] = abs(gap) <= CURRENCY_AUDIT_TOLERANCE
    if raise_on_error and not bank["currency_audit_ok"]:
        raise RuntimeError(
            f"貨幣守恆失敗：已發行 {issued}，可核對 {accounted}，差額 {gap}"
        )
    return {
        "issued": issued,
        "countries": country_total,
        "treasury": treasury,
        "accounted": accounted,
        "gap": gap,
        "ok": bank["currency_audit_ok"],
    }


def _market_floor_cash_pressure(market, cash_stressed, reliable=True):
    """已貼價格下限的資源，檢查賣盤與買方現金。"""
    resources = [r for r in MARKET_RESOURCES
                 if float(market['stats'][r].get('last_price', 0) or 0)
                 <= _market_price_floor(r, market) * 1.02
                 and int(market['stats'][r].get('sell_qty', 0) or 0)
                 >= max(3, int(market['stats'][r].get('buy_qty', 0) or 0) * 3)]
    return bool(reliable and resources and cash_stressed >= MARKET_CASH_STRESS_FRACTION), resources


def _market_health_update(market, bank, countries, turn_counter):
    if not MARKET_ECONOMY_ENABLED:
        _disable_market_runtime(market)
        return market["price_monitor"]["latest"]
    """每觀測窗使用累計成交金額/成交量計算 VWAP；無成交不沿用舊價格。

    指數以各資源「實際成交 VWAP / 初始參考價 / 貨幣面額倍率」計算，
    固定權重 50/30/20；缺乏完整樣本時僅顯示診斷，不觸發貨幣發行。
    """
    monitor = market.setdefault("price_monitor", _default_price_monitor())
    last_turn = int(monitor.get("last_observed_turn", -1))
    if (int(turn_counter) <= 0 or int(turn_counter) % MARKET_MONITOR_INTERVAL
            or int(turn_counter) == last_turn):
        return monitor.get("latest", {}) or {}
    previous_totals = monitor.setdefault("last_cumulative", {})
    denom = max(1, int(bank.get("currency_denomination", 1) or 1))
    interval_prices, observed, volumes, spreads = {}, [], {}, []
    for resource in MARKET_RESOURCES:
        stat = market.get("stats", {}).get(resource, {}) or {}
        current_qty = max(0, int(stat.get("traded_volume", 0) or 0))
        current_value = max(0, int(stat.get("traded_value", 0) or 0))
        previous = previous_totals.get(resource, {}) or {}
        old_qty = max(0, int(previous.get("qty", 0) or 0))
        old_value = max(0, int(previous.get("value", 0) or 0))
        # 當計數器因讀檔或新世界歸零時，絕不把跨世代累計量當成本輪成交。
        qty = max(0, current_qty - old_qty) if current_qty >= old_qty else 0
        value = max(0, current_value - old_value) if current_value >= old_value else 0
        previous_totals[resource] = {"qty": current_qty, "value": current_value}
        volumes[resource] = qty
        if qty >= MARKET_MONITOR_MIN_RESOURCE_QTY and value > 0:
            normalized_vwap = (value / qty) / denom
            # 面額可以高達 10**23；固定六位小數會把可信成交價抹成 0。
            interval_prices[resource] = normalized_vwap
            observed.append(resource)
        bid, ask = stat.get("best_bid"), stat.get("best_ask")
        if bid not in (None, 0) and ask not in (None, 0):
            midpoint = (float(bid) + float(ask)) * 0.5
            if midpoint > 0:
                spreads.append(max(0.0, (float(ask) - float(bid)) / midpoint))
    total_volume = sum(volumes.values())
    coverage = len(observed)
    reliable = coverage == len(MARKET_RESOURCES) and total_volume >= MARKET_MONITOR_MIN_TOTAL_QTY
    if reliable:
        index = sum(
            MARKET_BASKET_WEIGHTS[r] * interval_prices[r] / float(MARKET_RESOURCE_META[r]["seed_price"])
            for r in MARKET_RESOURCES
        )
    else:
        index = None
    alive = [data for data in countries.values() if data.get("is_alive", True)]
    cash_threshold = policy_cost(3 * MONEY_RATIO, bank)
    cash_stressed = sum(
        max(0, int(data.get("gold", 0) or 0)) / max(1, int(data.get("pop_total", 1) or 1))
        < cash_threshold for data in alive
    ) / max(1, len(alive))
    stock_ratios = {
        r: round(sum(max(0, float(c.get(r, 0) or 0)) for c in alive)
                 / max(1.0, sum(_market_target_stock(c, r) for c in alive)), 4)
        for r in MARKET_RESOURCES
    }
    observation = {
        "turn": int(turn_counter), "index": index,
        "denomination": denom,
        "coverage": coverage, "volume": total_volume, "volume_by_resource": volumes,
        "prices": interval_prices, "spread": round(sum(spreads) / len(spreads), 4) if spreads else None,
        "cash_stressed": round(cash_stressed, 4), "stock_ratios": stock_ratios,
    }
    history = monitor.setdefault("history", [])
    history.append(observation)
    del history[:-MARKET_MONITOR_HISTORY]
    monitor["last_observed_turn"] = int(turn_counter)

    deflation = False
    volume_down = False
    if reliable and len(history) >= 3:
        recent = history[-3:]
        consecutive = all(
            o.get("index") is not None and int(o.get("coverage", 0)) == 3
            for o in recent
        ) and all(
            int(recent[i]["turn"]) - int(recent[i-1]["turn"]) == MARKET_MONITOR_INTERVAL
            for i in (1, 2)
        ) and all(int(o.get("denomination", 0)) == denom for o in recent)
        if consecutive:
            indices = [float(o["index"]) for o in recent]
            deflation = (
                indices[0] > 0
                and indices[1] <= indices[0] * 0.99
                and indices[2] <= indices[1] * 0.99
                and indices[2] <= indices[0] * (1.0 - MARKET_DEFLATION_3WINDOW)
            )
            prior_volume = (int(recent[0]["volume"]) + int(recent[1]["volume"])) / 2.0
            volume_down = (
                prior_volume >= MARKET_MONITOR_MIN_TOTAL_QTY * 2
                and total_volume <= prior_volume * MARKET_VOLUME_CONTRACTION
            )
    physical_shortage = sum(stock_ratios[r] < 0.70 for r in MARKET_RESOURCES) >= 2
    physical_glut = sum(stock_ratios[r] > 1.40 for r in MARKET_RESOURCES) >= 2
    wide_spread = len(spreads) >= 2 and sum(spreads) / len(spreads) > 0.35
    liquidity_stress = (
        reliable and deflation and volume_down
        and cash_stressed >= MARKET_CASH_STRESS_FRACTION
        and not physical_shortage and not physical_glut and not wide_spread
    )
    # 價格已在下限時，連續跌價條件失去辨識力；單獨觀察缺現金與賣盤壓力。
    floor_cash_stress, floor_pressure = _market_floor_cash_pressure(market, cash_stressed, reliable)
    if not reliable:
        diagnosis = "成交樣本不足（不以過期價格觸發政策）"
    elif physical_shortage:
        diagnosis = "實物短缺：優先增加供應"
    elif physical_glut:
        diagnosis = "商品過剩：優先調整產能"
    elif wide_spread:
        diagnosis = "價差過大：先改善掛單與撮合"
    elif liquidity_stress:
        diagnosis = "連續跌價、縮量及廣泛現金不足"
    elif floor_cash_stress:
        diagnosis = "價格貼底、賣盤偏重及廣泛現金不足"
    else:
        diagnosis = "尚未確認流動性型通縮"
    latest = dict(observation, reliable=reliable, deflation=deflation,
                  volume_down=volume_down, liquidity_stress=liquidity_stress,
                  floor_cash_stress=floor_cash_stress,
                  floor_pressure_resources=floor_pressure,
                  diagnosis=diagnosis)
    monitor["latest"] = latest
    bank["market_price_index"] = latest["index"]
    bank["market_price_index_valid"] = reliable
    bank["market_liquidity_diagnosis"] = diagnosis
    return latest


def _world_bank_recirculate_liquidity(bank, countries, turn_counter, market=None):
    if not MARKET_ECONOMY_ENABLED:
        return []
    """有三窗可信成交證據才逆週期回流；優先使用舊庫存，再審慎增發。"""
    if int(turn_counter) <= 0 or int(turn_counter) % WORLD_BANK_LIQUIDITY_INTERVAL:
        return []
    health = (market or {}).get("price_monitor", {}).get("latest", {})
    if (not health or int(health.get("turn", -1)) != int(turn_counter)
            or not health.get("liquidity_stress")
            or int(bank.get("stabilization_last_turn", -1)) == int(turn_counter)):
        return []
    alive = [(key, c) for key, c in countries.items() if c.get("is_alive", True)]
    if not alive:
        return []
    threshold = policy_cost(3 * MONEY_RATIO, bank)
    candidates = []
    for key, country in alive:
        pop = max(1, int(country.get("pop_total", 1) or 1))
        gold_pc = max(0, int(country.get("gold", 0) or 0)) / pop
        if gold_pc < threshold:
            candidates.append((key, max(0.1, threshold - gold_pc) * math.sqrt(pop), gold_pc))
    if not candidates:
        return []
    season = max(1, int(bank.get("current_season_round", 1) or 1))
    if int(bank.get("stabilization_issue_season", 0) or 0) != season:
        bank["stabilization_issue_season"] = season
        bank["stabilization_issued_this_season"] = 0
        bank["stabilization_season_base"] = max(1, int(bank.get("issued_total", 0) or 0))
    treasury = max(0, int(bank.get("treasury", 0) or 0))
    # 真正的流動性危機時優先動用既有金庫；不因帳上保留準備金而先印新幣。
    available_from_treasury = min(
        treasury, max(1, int(treasury * WORLD_BANK_LIQUIDITY_SHARE)) if treasury else 0
    )
    # 只有實際存在缺口時才計算印鈔預算；世界銀行永不掛單或收購實物。
    issued = max(0, int(bank.get("issued_total", 0) or 0))
    period_cap = int(issued * MARKET_ISSUE_PER_OPERATION)
    seasonal_cap = max(0, int(bank.get("stabilization_season_base", 0) * MARKET_ISSUE_PER_SEASON)
                       - int(bank.get("stabilization_issued_this_season", 0) or 0))
    issue_budget = min(period_cap, seasonal_cap) if treasury <= 0 else 0
    # 每次扶助最多為低現金國家每人 1 單位，避免無限轉帳抬高資產價格。
    max_needed = sum(max(0, int(threshold - pc)) for _k, _w, pc in candidates)
    budget = min(available_from_treasury + issue_budget,
                 policy_cost(WORLD_BANK_LIQUIDITY_GRANT_CAP, bank) * len(candidates),
                 max_needed)
    if budget <= 0:
        return []
    total_weight = sum(w for _k, w, _pc in candidates) or 1.0
    sorted_candidates = sorted(candidates, key=lambda x: (x[2], -x[1]))
    grants, allocated = [], 0
    for i, (key, weight, gold_pc) in enumerate(sorted_candidates):
        if allocated >= budget:
            break
        remaining = budget - allocated
        share = remaining if i == len(sorted_candidates) - 1 else int(budget * weight / total_weight)
        amount = min(remaining, max(0, share), policy_cost(WORLD_BANK_LIQUIDITY_GRANT_CAP, bank))
        if amount <= 0:
            continue
        countries[key]["gold"] = max(0, int(countries[key].get("gold", 0) or 0)) + amount
        allocated += amount
        grants.append({"country": key, "country_name": countries[key].get("display_name", key), "amount": amount})
    treasury_paid = min(allocated, available_from_treasury)
    newly_issued = allocated - treasury_paid
    bank["treasury"] = treasury - treasury_paid
    if treasury_paid:
        bank["liquidity_redistributed"] = max(0, int(bank.get("liquidity_redistributed", 0) or 0)) + treasury_paid
        bank["liquidity_operations"] = max(0, int(bank.get("liquidity_operations", 0) or 0)) + 1
    if newly_issued:
        bank["issued_total"] = issued + newly_issued
        bank["stabilization_issued_total"] = int(bank.get("stabilization_issued_total", 0) or 0) + newly_issued
        bank["stabilization_issued_this_season"] = int(bank.get("stabilization_issued_this_season", 0) or 0) + newly_issued
        bank["stabilization_issue_operations"] = int(bank.get("stabilization_issue_operations", 0) or 0) + 1
    bank["stabilization_last_turn"] = int(turn_counter)
    bank["last_action"] = f"穩定流動性：既有庫存 {treasury_paid}／限額新發 {newly_issued} {bank.get('currency', WORLD_CURRENCY_NAME)}"
    print(f"🏦 [流動性穩定] 現有金庫回流 {treasury_paid}，限額新發 {newly_issued}，支援 {len(grants)} 國；診斷：{health['diagnosis']}。")
    _currency_audit(countries, bank, raise_on_error=True)
    return grants


def _market_order_reservations(market, country_key, exclude_order_id=None):
    reserved_gold = 0
    reserved_resources = {res: 0 for res in MARKET_RESOURCES}
    for order in market.get("orders", []) or []:
        if order.get("country") != country_key or order.get("id") == exclude_order_id:
            continue
        qty = max(0, int(order.get("qty", 0) or 0))
        if order.get("side") == "BUY":
            reserved_gold += max(0, int(math.ceil(qty * max(0.01, float(order.get("price", 0) or 0)))))
        elif order.get("side") == "SELL" and order.get("resource") in reserved_resources:
            reserved_resources[order["resource"]] += qty
    return reserved_gold, reserved_resources


def _market_target_stock(data, resource):
    pop = max(1, int(data.get("pop_total", 1) or 1))
    farmers = max(0, int(data.get("farmers", 0) or 0))
    soldiers = max(0, int(data.get("soldiers", 0) or 0))
    if resource == "food":
        consumption = max(1.0, farmers + soldiers * 2.0)
        return max(80.0, consumption * 7.0)
    if resource == "wood":
        return max(80.0, pop * 2.5)
    return max(60.0, pop * 0.8 + soldiers * 2.2)


def _market_refresh_stats(market):
    orders = [o for o in (market.get("orders", []) or []) if isinstance(o, dict) and int(o.get("qty", 0) or 0) > 0]
    market["orders"] = orders[-MARKET_MAX_ORDERS:]
    for res in MARKET_RESOURCES:
        stat = market["stats"][res]
        buys = [o for o in orders if o.get("resource") == res and o.get("side") == "BUY"]
        sells = [o for o in orders if o.get("resource") == res and o.get("side") == "SELL"]
        stat["best_bid"] = round(max((float(o.get("price", 0) or 0) for o in buys), default=0.0), 2) if buys else None
        stat["best_ask"] = round(min((float(o.get("price", 0) or 0) for o in sells), default=0.0), 2) if sells else None
        stat["buy_qty"] = sum(max(0, int(o.get("qty", 0) or 0)) for o in buys)
        stat["sell_qty"] = sum(max(0, int(o.get("qty", 0) or 0)) for o in sells)


def _market_prune_orders(market, countries, turn_counter):
    kept = []
    expired = 0
    for order in market.get("orders", []) or []:
        if not isinstance(order, dict):
            continue
        country = order.get("country")
        if country not in countries or not countries[country].get("is_alive", True):
            continue
        age = int(turn_counter) - int(order.get("turn", turn_counter) or turn_counter)
        if age > MARKET_ORDER_TTL:
            expired += 1
            continue
        if int(order.get("qty", 0) or 0) <= 0:
            continue
        if order.get("resource") not in MARKET_RESOURCES:
            continue
        kept.append(order)
    market["orders"] = kept[-MARKET_MAX_ORDERS:]
    market["orders_expired"] = max(0, int(market.get("orders_expired", 0) or 0)) + expired
    _market_refresh_stats(market)


def _market_quote_pressure(market, resource):
    stat = market["stats"][resource]
    buy_qty = max(0, int(stat.get("buy_qty", 0) or 0))
    sell_qty = max(0, int(stat.get("sell_qty", 0) or 0))
    total = buy_qty + sell_qty
    if total <= 0:
        return 0.0
    return _clamp((buy_qty - sell_qty) / total, -1.0, 1.0)


def _market_place_ai_order(country_key, countries, market, turn_counter):
    if not MARKET_ECONOMY_ENABLED:
        return None
    if country_key not in countries:
        return None
    data = countries[country_key]
    if not data.get("is_alive", True):
        return None

    _market_prune_orders(market, countries, turn_counter)
    gold = max(0, int(data.get("gold", 0) or 0))
    reserved_gold, reserved_resources = _market_order_reservations(market, country_key)
    available_gold = max(0, gold - reserved_gold)
    ratios = {}
    for res in MARKET_RESOURCES:
        stock = max(0.0, float(data.get(res, 0) or 0))
        target = _market_target_stock(data, res)
        ratios[res] = stock / max(1.0, target)

    shortage_res = min(MARKET_RESOURCES, key=lambda r: ratios[r])
    surplus_res = max(MARKET_RESOURCES, key=lambda r: ratios[r])
    shortage_ratio = ratios[shortage_res]
    surplus_ratio = ratios[surplus_res]

    if shortage_ratio < 0.95 and available_gold >= policy_cost(25 * MONEY_RATIO, data):
        side = "BUY"
        resource = shortage_res
    elif surplus_ratio > 1.30:
        side = "SELL"
        resource = surplus_res
    elif available_gold < 90 and surplus_ratio > 1.05:
        side = "SELL"
        resource = surplus_res
    elif available_gold >= policy_cost(180 * MONEY_RATIO, data):
        side = "BUY"
        resource = shortage_res
    else:
        return None

    # 即將被新委託取代的舊單先釋放保留額度。
    market["orders"] = [
        o for o in market.get("orders", [])
        if not (
            o.get("country") == country_key
            and o.get("resource") == resource
            and o.get("side") == side
        )
    ]
    reserved_gold, reserved_resources = _market_order_reservations(market, country_key)
    available_gold = max(0, gold - reserved_gold)

    stat = market["stats"][resource]
    base_price = _clamp(
        max(0.01, float(stat.get("last_price", MARKET_RESOURCE_META[resource]["seed_price"]) or MARKET_RESOURCE_META[resource]["seed_price"])),
        _market_price_floor(resource, market),
        _market_price_ceiling(resource, market),
    )
    pressure = _market_quote_pressure(market, resource)
    stock = max(0.0, float(data.get(resource, 0) or 0))
    target = _market_target_stock(data, resource)
    trade_mult = max(0.50, float(data.get("event_trade_mult", 1.0) or 1.0) * float(data.get("world_trade_mult", 1.0) or 1.0))

    if side == "BUY":
        urgency = _clamp((target - stock) / max(target, 1.0), 0.0, 1.0)
        price = base_price * (1.0 + 0.28 * urgency + 0.06 * pressure) * random.uniform(0.97, 1.05)
        wanted = max(10, int(max(0.0, target - stock) * 0.35))
        qty = max(10, int(wanted * min(1.35, trade_mult)))
        affordable = int(available_gold / max(0.01, price))
        qty = min(qty, affordable)
    else:
        surplus = max(0.0, stock - target)
        surplus_strength = _clamp(surplus / max(target, 1.0), 0.0, 2.0)
        price = base_price * (1.0 - min(0.20, 0.10 * surplus_strength) + 0.06 * pressure) * random.uniform(0.96, 1.05)
        qty = max(10, int(surplus * 0.25 * min(1.35, trade_mult)))
        qty = min(qty, max(0, int(stock) - reserved_resources.get(resource, 0)))

    # 單次報價相對最近成交價限制在 ±20%，抑制偶發極端價格。
    price = _clamp(
        price,
        base_price * (1.0 - MARKET_PRICE_LIMIT_RATE),
        base_price * (1.0 + MARKET_PRICE_LIMIT_RATE),
    )
    price = round(_clamp(price, _market_price_floor(resource, market), _market_price_ceiling(resource, market)), 2)
    qty = max(0, int(qty))
    if qty <= 0:
        return None

    # 同一國同一資源同方向只保留最新一張；買單與賣單可並存。
    market["order_sequence"] = max(0, int(market.get("order_sequence", 0) or 0)) + 1
    order = {
        "id": f"M{market['order_sequence']}",
        "turn": int(turn_counter),
        "country": country_key,
        "country_name": data.get("display_name", country_key),
        "side": side,
        "resource": resource,
        "resource_name": MARKET_RESOURCE_META[resource]["name"],
        "qty": qty,
        "price": price,
    }
    market.setdefault("orders", []).append(order)
    market["orders_placed"] = max(0, int(market.get("orders_placed", 0) or 0)) + 1
    market["orders"] = market["orders"][-MARKET_MAX_ORDERS:]
    _market_refresh_stats(market)
    return order


def _market_layer_state(data, market):
    stock_levels = []
    for resource in MARKET_RESOURCES:
        ratio = max(0.0, float(data.get(resource, 0) or 0)) / max(1.0, _market_target_stock(data, resource))
        stock_levels.append("LOW" if ratio < 0.75 else "OK" if ratio < 1.40 else "HIGH")
    pop = max(1, int(data.get("pop_total", 1) or 1))
    gold_pc = max(0.0, float(data.get("gold", 0) or 0)) / pop
    liquidity = "LOW" if gold_pc < policy_cost(MONEY_RATIO, data) else "OK" if gold_pc < policy_cost(4 * MONEY_RATIO, data) else "HIGH"
    trends = []
    spreads = []
    for resource in MARKET_RESOURCES:
        stat = market.get("stats", {}).get(resource, {}) or {}
        history = list(stat.get("price_history", []) or [])[-6:]
        if len(history) >= 2:
            change = (float(history[-1]) - float(history[0])) / max(0.01, float(history[0]))
            trends.append(change)
        bid, ask = stat.get("best_bid"), stat.get("best_ask")
        if bid not in (None, 0) and ask not in (None, 0):
            spreads.append((float(ask) - float(bid)) / max(0.01, (float(ask) + float(bid)) / 2.0))
    avg_trend = sum(trends) / len(trends) if trends else 0.0
    trend = "DOWN" if avg_trend < -0.05 else "UP" if avg_trend > 0.05 else "FLAT"
    avg_spread = sum(spreads) / len(spreads) if spreads else 1.0
    market_depth = "LIQUID" if avg_spread < 0.10 else "NORMAL" if avg_spread < 0.30 else "THIN"
    return tuple(stock_levels + [liquidity, trend, market_depth])


def _market_layer_valid_actions(country_key, countries, market):
    if not MARKET_ECONOMY_ENABLED:
        return [0]
    data = countries[country_key]
    reserved_gold, reserved_resources = _market_order_reservations(market, country_key)
    valid = [0]
    minimum_market_cash = int(min(meta["seed_price"] for meta in MARKET_RESOURCE_META.values()))
    if max(0, int(data.get("gold", 0) or 0) - reserved_gold) >= minimum_market_cash:
        valid.extend((1, 2, 3))
    for index, resource in enumerate(MARKET_RESOURCES, start=4):
        available = max(0, int(data.get(resource, 0) or 0) - reserved_resources.get(resource, 0))
        if available > 0:
            valid.append(index)
    return valid


def _market_reservation_price(side, resource, stock_ratio, reference, price_action, market):
    """依本國庫存調整願買／願售價；Q 動作仍決定三種積極程度。"""
    ratio = max(0.0, float(stock_ratio))
    aggression = (-0.06, 0.0, 0.06)[int(price_action)]
    if side == "BUY":
        # 快耗盡的物資提高願付價；充裕時降低出價，避免一路追隨舊成交價。
        need = 0.27 * min(1.0, max(0.0, 1.0 - ratio))
        if resource == "food" and ratio < 0.25:
            need += 0.03
        reserve_bias = need - 0.08 * min(1.0, max(0.0, ratio - 1.0))
        adjustment = reserve_bias + aggression
    else:
        # 庫存不足仍想賣時提高底價；真正過剩才願意折讓。
        reserve_bias = (0.18 * min(1.0, max(0.0, 1.05 - ratio))
                        - 0.13 * min(1.0, max(0.0, ratio - 1.10)))
        adjustment = reserve_bias - aggression
    low = max(_market_price_floor(resource, market), reference * 0.70)
    high = min(_market_price_ceiling(resource, market), reference * 1.30)
    return round(_clamp(reference * (1.0 + adjustment), low, high), 2)


def _market_quote_quality(order, trades):
    """價格 Q 值只評本次實際成交的議價品質，未成交不臆測獲利。"""
    if not order or not trades:
        return 0.0
    base = max(0.01, float(order.get("reference_price", order.get("price", 0)) or 0))
    buying = order.get("side") == "BUY"
    total = sum(max(0, int(trade.get("qty", 0) or 0)) for trade in trades)
    if not total:
        return 0.0
    edge = sum(max(0, int(t.get("qty", 0) or 0))
               * ((base - float(t.get("price", 0) or 0)) / base if buying
                  else (float(t.get("price", 0) or 0) - base) / base)
               for t in trades) / total
    worthless_sale = any(not buying and int(t.get("gross_gold", 0) or 0)
                         <= int(t.get("fee_gold", 0) or 0) for t in trades)
    return _clamp(edge * 0.60 - (0.15 if worthless_sale else 0.0), -0.30, 0.30)


def _market_place_layered_order(country_key, countries, market, turn_counter, market_action, price_action, size_action):
    if not MARKET_ECONOMY_ENABLED:
        return None
    if market_action == 0:
        return None
    side = "BUY" if market_action <= 3 else "SELL"
    resource = MARKET_RESOURCES[(market_action - 1) % 3]
    data = countries[country_key]
    market["orders"] = [
        order for order in market.get("orders", [])
        if not (order.get("country") == country_key and order.get("resource") == resource and order.get("side") == side)
    ]
    reserved_gold, reserved_resources = _market_order_reservations(market, country_key)
    stat = market.get("stats", {}).get(resource, {}) or {}
    reference = _clamp(
        max(0.05, float(stat.get("vwap_10", stat.get("last_price", MARKET_RESOURCE_META[resource]["seed_price"])) or MARKET_RESOURCE_META[resource]["seed_price"])),
        _market_price_floor(resource, market),
        _market_price_ceiling(resource, market),
    )
    stock = max(0.0, float(data.get(resource, 0) or 0))
    target = _market_target_stock(data, resource)
    price = _market_reservation_price(side, resource, stock / max(1.0, target),
                                      reference, price_action, market)
    pop = max(1, int(data.get("pop_total", 1) or 1))
    total_assets = sum(max(0.0, float(data.get(res, 0) or 0)) * float(MARKET_RESOURCE_META[res]["seed_price"]) for res in MARKET_RESOURCES) + max(0.0, float(data.get("gold", 0) or 0))
    economy_factor = _clamp(math.log1p(total_assets) / 8.0, 0.55, 1.8)
    liquidity_factor = _clamp(max(0.0, float(data.get("gold", 0) or 0)) / max(policy_cost(50 * MONEY_RATIO, data), pop * policy_cost(2 * MONEY_RATIO, data)), 0.35, 1.5)
    infrastructure_factor = 1.0 + min(0.75, float(data.get("infrastructure", 0) or 0) / 100.0)
    # 人口、財富與基建決定基礎容量；資源盈缺決定額外需求。
    # 交易大小仍由 market_size_policy 的小／中／大三個 Q 動作控制。
    scale_factor = economy_factor * liquidity_factor * infrastructure_factor
    retail_capacity = math.sqrt(pop) * 4.0 * scale_factor
    bulk_capacity = pop * 0.06 * _clamp(scale_factor, 0.60, 2.0)
    gap_capacity = max(0.0, (target - stock) if side == "BUY" else (stock - target)) * 0.25
    capacity = max(5, int(retail_capacity + bulk_capacity + gap_capacity))
    size_multiplier = (0.30, 0.60, 1.0)[int(size_action)]
    qty = max(1, int(capacity * size_multiplier))
    if side == "BUY":
        available_gold = max(0, int(data.get("gold", 0) or 0) - reserved_gold)
        qty = min(qty, int(available_gold / max(0.01, price)))
    else:
        available_stock = max(0, int(data.get(resource, 0) or 0) - reserved_resources.get(resource, 0))
        qty = min(qty, available_stock)
    if qty <= 0:
        return None
    market["order_sequence"] = max(0, int(market.get("order_sequence", 0) or 0)) + 1
    order = {
        "id": f"M{market['order_sequence']}", "turn": int(turn_counter),
        "country": country_key, "country_name": data.get("display_name", country_key),
        "side": side, "resource": resource, "resource_name": MARKET_RESOURCE_META[resource]["name"],
        "qty": int(qty), "price": price, "reference_price": reference,
        "policy": "V8_4_MARKET_SUBPOLICY",
        "price_style": MARKET_PRICE_ACTIONS[int(price_action)], "size_style": MARKET_SIZE_ACTIONS[int(size_action)],
    }
    market.setdefault("orders", []).append(order)
    market["orders_placed"] = max(0, int(market.get("orders_placed", 0) or 0)) + 1
    _market_refresh_stats(market)
    return order


def _market_price_floor(resource, market=None):
    """回傳該資源的市場價格下限；避免長期單邊賣壓把價格打到接近 0。"""
    denomination = max(1, int((market or {}).get("currency_denomination", 1) or 1))
    seed = float(MARKET_RESOURCE_META[resource]["seed_price"]) * denomination
    return max(0.05 * denomination, seed * MARKET_PRICE_FLOOR_RATE)


def _market_price_ceiling(resource, market=None):
    """回傳該資源的市場價格上限，避免短期搶購無限拉高。"""
    denomination = max(1, int((market or {}).get("currency_denomination", 1) or 1))
    seed = float(MARKET_RESOURCE_META[resource]["seed_price"]) * denomination
    return max(_market_price_floor(resource, market), seed * MARKET_PRICE_CEILING_RATE)


def _redenominate_currency(bank, countries, market, factor=10):
    """舊幣 1 換新幣 factor；全部存量及名目報價同步變動，實質資產不變。"""
    if factor <= 1:
        raise ValueError("重定面額倍率必須大於 1")
    for country in countries.values():
        country["gold"] = int(country.get("gold", 0) or 0) * factor
    monetary_bank_fields = (
        "issued_total", "initial_issued_total", "treasury", "policy_collected",
        "transaction_fees_collected", "respawn_grants", "liquidity_redistributed",
        "circulating_total", "market_issued_total", "market_issue_season_budget",
        "market_issued_this_season", "policy_base_circulation", "currency_issue_baseline",
        "stabilization_issued_total", "stabilization_issued_this_season", "stabilization_season_base",
        "fiscal_recycle_total",
    )
    for key in monetary_bank_fields:
        if key in bank:
            bank[key] = int(bank[key] or 0) * factor
    bank["currency_denomination"] = max(1, int(bank.get("currency_denomination", 1) or 1)) * factor
    market["currency_denomination"] = bank["currency_denomination"]
    bank["birth_policy_cost"] = policy_cost(BIRTH_POLICY_GOLD_COST, bank)
    for country in countries.values():
        country["currency_denomination"] = bank["currency_denomination"]
    for order in market.get("orders", []):
        order["price"] = round(float(order.get("price", 0) or 0) * factor, 2)
        if "reference_price" in order:
            order["reference_price"] = round(float(order["reference_price"]) * factor, 2)
    for trade in market.get("recent_trades", []):
        for key in ("price",):
            if key in trade:
                trade[key] = round(float(trade[key]) * factor, 2)
        for key in ("gross_gold", "fee_gold", "currency_issued", "bank_treasury_used"):
            if key in trade:
                trade[key] = int(trade[key] or 0) * factor
    for stat in market.get("stats", {}).values():
        for key in ("last_price", "vwap_10", "best_bid", "best_ask"):
            if stat.get(key) is not None:
                stat[key] = round(float(stat[key]) * factor, 4)
        stat["price_history"] = [round(float(p) * factor, 4) for p in stat.get("price_history", [])]
        stat["traded_value"] = int(stat.get("traded_value", 0) or 0) * factor
    monitor = market.get("price_monitor", {})
    for saved in (monitor.get("last_cumulative", {}) or {}).values():
        if isinstance(saved, dict):
            saved["value"] = int(saved.get("value", 0) or 0) * factor
    # 歷史價格已除以面額倍率，因此跨幣名仍可比較實質物價。
    _currency_audit(countries, bank, raise_on_error=True)


def _market_match_orders(countries, market, bank, turn_counter):
    if not MARKET_ECONOMY_ENABLED:
        _disable_market_runtime(market)
        return []
    _market_prune_orders(market, countries, turn_counter)
    trades = []

    for resource in MARKET_RESOURCES:
        while True:
            buys = sorted(
                [o for o in market.get("orders", []) if o.get("resource") == resource and o.get("side") == "BUY" and int(o.get("qty", 0) or 0) > 0],
                key=lambda o: (-float(o.get("price", 0) or 0), int(o.get("turn", 0) or 0), int(str(o.get("id", "M0")).lstrip("M") or 0)),
            )
            sells = sorted(
                [o for o in market.get("orders", []) if o.get("resource") == resource and o.get("side") == "SELL" and int(o.get("qty", 0) or 0) > 0],
                key=lambda o: (float(o.get("price", 0) or 0), int(o.get("turn", 0) or 0), int(str(o.get("id", "M0")).lstrip("M") or 0)),
            )
            pair = None
            for buy in buys:
                for sell in sells:
                    if buy.get("country") == sell.get("country"):
                        continue
                    if float(buy.get("price", 0) or 0) >= float(sell.get("price", 0) or 0):
                        pair = (buy, sell)
                        break
                if pair:
                    break
            if not pair:
                break

            buy, sell = pair
            buyer = countries.get(buy.get("country"))
            seller = countries.get(sell.get("country"))
            if not buyer or not seller or not buyer.get("is_alive", True) or not seller.get("is_alive", True):
                buy["qty"] = 0
                sell["qty"] = 0
                continue

            # 價格優先、時間優先；成交價採較早委託（maker）的價格。
            buy_priority = (int(buy.get("turn", 0) or 0), int(str(buy.get("id", "M0")).lstrip("M") or 0))
            sell_priority = (int(sell.get("turn", 0) or 0), int(str(sell.get("id", "M0")).lstrip("M") or 0))
            unit_price = round(float(buy["price"] if buy_priority <= sell_priority else sell["price"]), 2)
            buyer_gold = max(0, int(buyer.get("gold", 0) or 0))
            seller_stock = max(0, int(seller.get(resource, 0) or 0))
            other_reserved_gold, _ = _market_order_reservations(market, buy.get("country"), buy.get("id"))
            _, other_reserved_resources = _market_order_reservations(market, sell.get("country"), sell.get("id"))
            buyer_available = max(0, buyer_gold - other_reserved_gold)
            seller_available = max(0, seller_stock - other_reserved_resources.get(resource, 0))
            affordable_qty = int(buyer_available / max(0.01, unit_price))
            qty = min(int(buy.get("qty", 0) or 0), int(sell.get("qty", 0) or 0), seller_available, affordable_qty)
            if qty <= 0:
                if seller_stock <= 0:
                    sell["qty"] = 0
                if affordable_qty <= 0:
                    buy["qty"] = 0
                continue

            gross = max(1, int(round(qty * unit_price)))
            if gross > buyer_gold:
                qty = max(0, int(buyer_gold / max(0.01, unit_price)))
                gross = max(0, int(round(qty * unit_price)))
            if qty <= 0 or gross <= 0:
                buy["qty"] = 0
                continue

            fee = _market_transaction_fee(gross)
            net = gross - fee

            buyer["gold"] = buyer_gold - gross
            seller["gold"] = max(0, int(seller.get("gold", 0) or 0)) + net
            seller[resource] = seller_stock - qty
            buyer[resource] = max(0, int(buyer.get(resource, 0) or 0)) + qty
            _world_bank_collect(bank, fee, category="fee")

            buy["qty"] = int(buy.get("qty", 0) or 0) - qty
            sell["qty"] = int(sell.get("qty", 0) or 0) - qty
            if buy["qty"] <= 0:
                market["orders_filled"] = max(0, int(market.get("orders_filled", 0) or 0)) + 1
            if sell["qty"] <= 0:
                market["orders_filled"] = max(0, int(market.get("orders_filled", 0) or 0)) + 1

            trade = {
                "turn": int(turn_counter),
                "resource": resource,
                "resource_name": MARKET_RESOURCE_META[resource]["name"],
                "qty": qty,
                "price": unit_price,
                "gross_gold": gross,
                "fee_gold": fee,
                "buyer": buy.get("country"),
                "buyer_name": buyer.get("display_name", buy.get("country")),
                "seller": sell.get("country"),
                "seller_name": seller.get("display_name", sell.get("country")),
                "buy_order_id": buy.get("id"),
                "sell_order_id": sell.get("id"),
            }
            trades.append(trade)
            market.setdefault("recent_trades", []).append(trade)
            market["recent_trades"] = market["recent_trades"][-MARKET_TRADE_HISTORY_MAX:]

            stat = market["stats"][resource]
            stat["last_price"] = unit_price
            stat["traded_volume"] = max(0, int(stat.get("traded_volume", 0) or 0)) + qty
            stat["traded_value"] = max(0, int(stat.get("traded_value", 0) or 0)) + gross
            stat["last_trade_volume"] = qty
            stat["last_trade_turn"] = int(turn_counter)
            stat["trade_count"] = max(0, int(stat.get("trade_count", 0) or 0)) + 1
            hist = list(stat.get("price_history", []) or [])
            hist.append(unit_price)
            stat["price_history"] = hist[-MARKET_PRICE_HISTORY_MAX:]
            recent_for_vwap = [
                t for t in market.get("recent_trades", [])
                if t.get("resource") == resource
            ][-MARKET_VWAP_WINDOW:]
            vwap_qty = sum(max(0, int(t.get("qty", 0) or 0)) for t in recent_for_vwap)
            if vwap_qty:
                stat["vwap_10"] = round(
                    sum(float(t.get("price", 0) or 0) * int(t.get("qty", 0) or 0) for t in recent_for_vwap) / vwap_qty,
                    4,
                )

            print(
                f"💱 [世界市場成交] 【{trade['buyer_name']}】以 {gross} {bank.get('currency', WORLD_CURRENCY_NAME)}向"
                f"【{trade['seller_name']}】買入 {qty} {trade['resource_name']}，"
                f"成交單價 {unit_price:.2f}，世界銀行手續費 {fee}。"
            )

    # V8_5：世界銀行不參與市場買賣，低價交易不造成新增發行。
    _market_prune_orders(market, countries, turn_counter)
    return trades


def _apply_birth_policy(data, bank):
    if MARKET_ECONOMY_ENABLED:
        cost = policy_cost(BIRTH_POLICY_GOLD_COST, bank)
        gold = max(0, int(data.get("gold", 0) or 0))
        if gold < cost:
            return False, 0
        data["gold"] = gold - cost
        _world_bank_collect(bank, cost, category="policy")
        paid = cost
    else:
        paid = _pay_mixed_resource_cost(data)
    data["birth_policy_turns"] = max(int(data.get("birth_policy_turns", 0) or 0), BIRTH_POLICY_DURATION)
    # 政策當下即產生可觀測效果；仍受住房、糧食與人口規則限制。
    pop = max(1, int(data.get("pop_total", 1) or 1))
    capacity = max(0, max(1, int(data.get("houses", 1) or 1)) * 10 - pop)
    food = max(0, int(data.get("food", 0) or 0))
    immediate_births = min(
        capacity,
        food // max(1, BALANCE["FOOD_COST_PER_BIRTH"]),
        max(2, min(30, int(math.ceil(pop * 0.02)))),
    )
    if immediate_births > 0:
        data["pop_total"] = pop + immediate_births
        data["farmers"] = max(0, int(data.get("farmers", 0) or 0)) + immediate_births
        data["food"] = food - immediate_births * BALANCE["FOOD_COST_PER_BIRTH"]
    data["last_birth_policy_gain"] = immediate_births
    data["birth_policy_total_gain"] = max(0, int(data.get("birth_policy_total_gain", 0) or 0)) + immediate_births
    data["policy_summary"] = f"鼓勵生育（剩{data['birth_policy_turns']}年）"
    
    return True, paid


def _apply_production_policy(data, bank):
    if MARKET_ECONOMY_ENABLED:
        cost = policy_cost(PRODUCTION_POLICY_GOLD_COST, bank)
        gold = max(0, int(data.get("gold", 0) or 0))
        if gold < cost:
            return False, 0
        data["gold"] = gold - cost
        _world_bank_collect(bank, cost, category="policy")
        paid = cost
    else:
        paid = _pay_mixed_resource_cost(data)
    data["production_policy_turns"] = max(int(data.get("production_policy_turns", 0) or 0), PRODUCTION_POLICY_DURATION)
    farmers = max(1, int(data.get("farmers", 1) or 1))
    immediate = {
        "food": max(5, int(farmers * 0.80)),
        "wood": max(3, int(farmers * 0.35)),
        "metal": max(2, int(farmers * 0.20)),
    }
    for resource, amount in immediate.items():
        data[resource] = max(0, int(data.get(resource, 0) or 0)) + amount
    data["last_production_policy_gain"] = immediate
    data["production_policy_total_gain"] = max(0, int(data.get("production_policy_total_gain", 0) or 0)) + sum(immediate.values())
    data["policy_summary"] = f"增產補貼（剩{data['production_policy_turns']}年）"

    return True, paid


def _diplomatic_gold_aid(donor_key, countries, alliances):
    donor = countries.get(donor_key)
    if not donor or not donor.get("is_alive", True):
        return None
    donor_gold = max(0, int(donor.get("gold", 0) or 0))
    if MARKET_ECONOMY_ENABLED and donor_gold < policy_cost(DIPLOMACY_GOLD_MIN, donor):
        return None
    my_alliance = donor.get("current_alliance", "")
    allies = set(alliances.get(my_alliance, [])) if my_alliance else set()
    candidates = [
        k for k, d in countries.items()
        if k != donor_key and d.get("is_alive", True) and k not in allies
    ]
    if not candidates:
        return None
    hostility = donor.get("hostility", {}) or {}
    target_key = max(
        candidates,
        key=lambda k: (
            int(countries[k].get("hostility", {}).get(donor_key, 0) or 0),
            int(hostility.get(k, 0) or 0),
            -int(countries[k].get("power", 0) or 0),
        ),
    )
    if MARKET_ECONOMY_ENABLED:
        amount = min(donor_gold, random.randint(policy_cost(DIPLOMACY_GOLD_MIN, donor), policy_cost(DIPLOMACY_GOLD_MAX, donor)), max(policy_cost(DIPLOMACY_GOLD_MIN, donor), int(donor_gold * 0.18)))
        amount = max(0, int(amount))
        if amount <= 0:
            return None
        donor["gold"] -= amount
        countries[target_key]["gold"] = max(0, int(countries[target_key].get("gold", 0) or 0)) + amount
        transfers = {"gold": amount}
    else:
        transfers = _pay_mixed_resource_cost(donor)
        for resource, amount in transfers.items():
            countries[target_key][resource] = max(0, int(countries[target_key].get(resource, 0) or 0)) + amount
        amount = _mixed_cost_value(transfers)
    donor.setdefault("hostility", {})[target_key] = max(0, int(donor.get("hostility", {}).get(target_key, 0) or 0) - random.randint(8, 18))
    countries[target_key].setdefault("hostility", {})[donor_key] = max(0, int(countries[target_key].get("hostility", {}).get(donor_key, 0) or 0) - random.randint(12, 26))
    donor["infamy"] = max(0, int(donor.get("infamy", 0) or 0) - 2)
    return {"target": target_key, "amount": amount, "transfers": transfers}


def _alliance_resource_aid(donor_key, countries, alliances):
    donor = countries.get(donor_key)
    if not donor or not donor.get("is_alive", True):
        return None
    alliance = donor.get("current_alliance", "")
    members = [m for m in alliances.get(alliance, []) if m != donor_key and countries.get(m, {}).get("is_alive", True)]
    if not members:
        return None

    def need_score(k):
        d = countries[k]
        food_target = _market_target_stock(d, "food")
        food_ratio = max(0.0, float(d.get("food", 0) or 0)) / max(1.0, food_target)
        return (1.0 / max(0.1, food_ratio)) + (2.0 if d.get("current_wars") else 0.0) + (1.0 if float(d.get("political_stability", 75) or 75) < 30 else 0.0)

    target_key = max(members, key=need_score)
    target = countries[target_key]
    transfers = {}

    for res in MARKET_RESOURCES:
        target_stock = _market_target_stock(donor, res)
        surplus = max(0, int(float(donor.get(res, 0) or 0) - target_stock * 1.10))
        cap = {"food": 220, "wood": 90, "metal": 50}[res]
        amount = min(cap, int(surplus * 0.18))
        if amount > 0:
            donor[res] = max(0, int(donor.get(res, 0) or 0) - amount)
            target[res] = max(0, int(target.get(res, 0) or 0)) + amount
            transfers[res] = amount

    if MARKET_ECONOMY_ENABLED:
        gold_surplus = max(0, int(donor.get("gold", 0) or 0) - policy_cost(180 * MONEY_RATIO, donor))
        gold_amount = min(policy_cost(80 * MONEY_RATIO, donor), int(gold_surplus * 0.15))
        if gold_amount > 0:
            donor["gold"] -= gold_amount
            target["gold"] = max(0, int(target.get("gold", 0) or 0)) + gold_amount
            transfers["gold"] = gold_amount

    if not transfers:
        return None
    return {"target": target_key, "transfers": transfers}


def _alliance_layer_state(country_key, countries, alliances):
    data = countries[country_key]
    alliance = data.get("current_alliance", "")
    members = [m for m in alliances.get(alliance, []) if m != country_key and countries.get(m, {}).get("is_alive", True)]
    pop = max(1, int(data.get("pop_total", 1) or 1))
    ratios = [max(0.0, float(data.get(res, 0) or 0)) / max(1.0, _market_target_stock(data, res)) for res in MARKET_RESOURCES]
    surplus = "LOW" if max(ratios) < 1.1 else "MEDIUM" if max(ratios) < 1.8 else "HIGH"
    if not members:
        crisis = importance = reciprocity = cohesion = "NONE"
    else:
        need_scores = []
        for member in members:
            target = countries[member]
            need_scores.append(min(max(0.0, float(target.get(res, 0) or 0)) / max(1.0, _market_target_stock(target, res)) for res in MARKET_RESOURCES))
        minimum = min(need_scores)
        crisis = "SEVERE" if minimum < 0.35 else "NEED" if minimum < 0.8 else "OK" if minimum < 1.4 else "SURPLUS"
        ally_power = sum(max(0, int(countries[m].get("power", 0) or 0)) for m in members)
        importance = "LOW" if ally_power < data.get("power", 0) * 0.5 else "MEDIUM" if ally_power < data.get("power", 0) * 1.5 else "HIGH"
        credit = data.get("alliance_reciprocity", {}) or {}
        balance = sum(float(credit.get(m, 0) or 0) for m in members)
        reciprocity = "OWED" if balance < -50 else "BALANCED" if balance < 80 else "CREDITOR"
        cohesion = "FRAGILE" if len(members) < 2 else "NORMAL" if len(members) < 4 else "STRONG"
    war_pressure = "HIGH" if len(data.get("current_wars", []) or []) >= 2 else "WAR" if data.get("current_wars") else "PEACE"
    return (surplus, crisis, importance, reciprocity, war_pressure, cohesion)


def _alliance_layer_valid_actions(country_key, countries, alliances):
    data = countries[country_key]
    alliance = data.get("current_alliance", "")
    members = [m for m in alliances.get(alliance, []) if m != country_key and countries.get(m, {}).get("is_alive", True)]
    if not members:
        return [0]
    valid = [0, 1]
    if any(data.get(res, 0) > _market_target_stock(data, res) * 1.10 for res in MARKET_RESOURCES) or (MARKET_ECONOMY_ENABLED and data.get("gold", 0) > policy_cost(180 * MONEY_RATIO, data)):
        valid.append(2)
        if MARKET_ECONOMY_ENABLED:
            valid.extend((3, 4))
    if any(countries[m].get("current_wars") or countries[m].get("food", 0) < _market_target_stock(countries[m], "food") * 0.5 for m in members):
        valid.append(5)
    return sorted(set(valid))


def _alliance_execute_layer_action(country_key, action, countries, alliances, market, bank, turn_counter):
    data = countries[country_key]
    alliance = data.get("current_alliance", "")
    members = [m for m in alliances.get(alliance, []) if m != country_key and countries.get(m, {}).get("is_alive", True)]
    if not members or action == 0 or (not MARKET_ECONOMY_ENABLED and action in (3, 4)):
        return False, 0.0, None
    if action == 1:
        ratios = {res: max(0.0, float(data.get(res, 0) or 0)) / max(1.0, _market_target_stock(data, res)) for res in MARKET_RESOURCES}
        resource = min(ratios, key=ratios.get)
        data["alliance_aid_request"] = {"resource": resource, "turn": int(turn_counter), "urgency": round(1.0 - min(1.0, ratios[resource]), 3)}
        return True, max(0.0, 1.0 - ratios[resource]), {"kind": "request", "resource": resource}
    requesters = [m for m in members if isinstance(countries[m].get("alliance_aid_request"), dict)]
    target_key = max(requesters or members, key=lambda m: float((countries[m].get("alliance_aid_request") or {}).get("urgency", 0) or 0))
    target = countries[target_key]
    if action in (2, 5):
        result = _alliance_resource_aid(country_key, countries, alliances)
        if not result:
            return False, 0.0, None
        multiplier = 1.0
        if action == 5:
            # 緊急救援追加有限糧食，不使援助國低於自身安全庫存。
            reserve = _market_target_stock(data, "food")
            extra = min(250, max(0, int(data.get("food", 0) - reserve * 1.15)))
            if extra > 0:
                data["food"] -= extra
                countries[result["target"]]["food"] += extra
                result["transfers"]["food"] = result["transfers"].get("food", 0) + extra
                multiplier = 1.35
        amount = sum(float(v or 0) for v in result["transfers"].values())
        target = countries[result["target"]]
        target.setdefault("alliance_reciprocity", {})[country_key] = float(target.get("alliance_reciprocity", {}).get(country_key, 0) or 0) + amount
        data.setdefault("alliance_reciprocity", {})[result["target"]] = float(data.get("alliance_reciprocity", {}).get(result["target"], 0) or 0) - amount
        target.pop("alliance_aid_request", None)
        return True, amount * multiplier, {"kind": "emergency" if action == 5 else "aid", **result}
    if action == 3:
        # 盟內優惠交易：以市場VWAP的95%成交，仍支付1%世界銀行手續費。
        requested = (target.get("alliance_aid_request") or {}).get("resource")
        resource = requested if requested in MARKET_RESOURCES else min(MARKET_RESOURCES, key=lambda r: target.get(r, 0) / max(1.0, _market_target_stock(target, r)))
        surplus = max(0, int(data.get(resource, 0) - _market_target_stock(data, resource) * 1.10))
        stat = market.get("stats", {}).get(resource, {}) or {}
        price = max(0.05, float(stat.get("vwap_10", stat.get("last_price", MARKET_RESOURCE_META[resource]["seed_price"])) or MARKET_RESOURCE_META[resource]["seed_price"]) * 0.95)
        qty = min(120, surplus, int(max(0, target.get("gold", 0)) / price))
        if qty <= 0:
            return False, 0.0, None
        gross = max(1, int(round(qty * price))); fee = _market_transaction_fee(gross); net = gross - fee
        target["gold"] -= gross; data["gold"] += net; _world_bank_collect(bank, fee, category="fee")
        data[resource] -= qty; target[resource] += qty
        return True, float(qty), {"kind": "preferential_trade", "target": target_key, "resource": resource, "qty": qty, "gross": gross, "fee": fee}
    # 等值資源交換：不動用大洋，以種子價換算並保持實體資源守恆。
    give = max(MARKET_RESOURCES, key=lambda r: data.get(r, 0) / max(1.0, _market_target_stock(data, r)))
    receive = min(MARKET_RESOURCES, key=lambda r: data.get(r, 0) / max(1.0, _market_target_stock(data, r)))
    if give == receive:
        return False, 0.0, None
    partner = max(members, key=lambda m: countries[m].get(receive, 0) / max(1.0, _market_target_stock(countries[m], receive)))
    other = countries[partner]
    give_qty = min(80, max(0, int(data.get(give, 0) - _market_target_stock(data, give) * 1.10)))
    receive_qty = min(max(0, int(other.get(receive, 0) - _market_target_stock(other, receive) * 1.10)), int(give_qty * MARKET_RESOURCE_META[give]["seed_price"] / MARKET_RESOURCE_META[receive]["seed_price"]))
    if give_qty <= 0 or receive_qty <= 0:
        return False, 0.0, None
    actual_give = min(give_qty, int(receive_qty * MARKET_RESOURCE_META[receive]["seed_price"] / MARKET_RESOURCE_META[give]["seed_price"]) + 1)
    data[give] -= actual_give; other[give] += actual_give; other[receive] -= receive_qty; data[receive] += receive_qty
    return True, float(actual_give + receive_qty), {"kind": "barter", "target": partner, "give": (give, actual_give), "receive": (receive, receive_qty)}


# ================================================
# 全球事件 / 自主學習 AI
# ================================================
# V7 起取消固定人格。
# 每個國家不再被預先指定為好戰、和平、投機等類型；
# 行動策略由各自 Q-Table 在實際環境中學習形成。
# ================================================

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
    """依指定權重抽取全球隨機事件。"""
    if random.random() < GLOBAL_EVENT_CHANCE:
        events = [
            ("金礦大發掘", "BOOM",
             "⛏️ [全球事件] 發現超級金礦！全體國家資源大幅提升！"),

            ("隕石浩劫", "DISASTER",
             "☄️ [全球事件] 隕石砸落地球！所有國家損失部分人口與資源！"),

            ("大航海時代", "EXPANSION",
             "⛵ [全球事件] 大航海時代開啟！休養生息與生產效率翻倍！"),

            ("大洪水", "BIGWATER",
             "🌊 [全球事件] 大洪水降臨地表！所有國家損失巨量資源！"),
        ]

        weights = [
            25,  # 金礦大發掘
            25,  # 隕石浩劫
            25,  # 大航海時代
            25,  # 大洪水
        ]

        return random.choices(events, weights=weights, k=1)[0]

    return None, None, None


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
CHRONICLE_SCHEMA_VERSION = 2


def _world_year(turn_counter):
    """《亂世演算》世界曆：1 Game Loop 視為 1 年。"""
    return max(WORLD_START_YEAR, WORLD_START_YEAR + max(0, int(turn_counter or 0)) - 1)


def _is_rebuild_protected(data, turn_counter):
    """重建政權在指定保護年限內不得被攻擊或參加普通聯盟。"""
    explicit_until = int(data.get("rebuild_protection_until_turn", 0) or 0)
    legacy_until = (
        int(data.get("newbie_protection_until_turn", 0) or 0)
        if str(data.get("regime_type", "") or "") == "重建政權"
        else 0
    )


def _protection_transition_year(data, turn_counter):
    """回傳脫保後經過年數；從未具有保護期的舊國家回傳 None。"""
    protection_until = max(
        int(data.get("newbie_protection_until_turn", 0) or 0),
        int(data.get("rebuild_protection_until_turn", 0) or 0),
    )
    if protection_until <= 0:
        return None
    return int(turn_counter) - protection_until


def _is_capitulation_protected(data, turn_counter):
    return bool(
        data.get("is_alive", True)
        and int(data.get("capitulation_protection_until_turn", 0) or 0) > int(turn_counter)
    )


def _homeland_defense_bonus(attacker_force, defender_force):
    """兵力差越懸殊，守方越依賴地形、短補給線與游擊；不適用於零守軍。"""
    attacker_force = max(0.0, float(attacker_force or 0))
    defender_force = max(0.0, float(defender_force or 0))
    if defender_force <= 0:
        return 0.0
    ratio = attacker_force / defender_force
    return float(_clamp((ratio - 1.5) * 0.045, 0.0, HOMELAND_DEFENSE_BONUS_MAX))
    return bool(
        data.get("is_alive", True)
        and max(explicit_until, legacy_until) > int(turn_counter)
    )


def update_security_posture(data, turn_counter):
    """計算可讀的安全風險與脫保準備度；只提供狀態與學習訊號，不贈送資源。"""
    turn_counter = max(0, int(turn_counter or 0))
    protection_until = max(
        int(data.get("newbie_protection_until_turn", 0) or 0),
        int(data.get("rebuild_protection_until_turn", 0) or 0),
    )
    protection_started = int(data.get("rebuild_protection_started_turn", 0) or 0)
    if protection_started <= 0 and protection_until > 0:
        protection_started = max(0, protection_until - NEW_COUNTRY_PROTECTION_YEARS)
    remaining = max(0, protection_until - turn_counter)
    protected = bool(data.get("is_alive", True) and remaining > 0)
    total_duration = max(1, protection_until - protection_started)
    remaining_ratio = _clamp(remaining / total_duration, 0.0, 1.0) if protected else 0.0
    urgency = (
        _clamp(1.0 - remaining / max(1, SURVIVAL_PREPARATION_WINDOW_YEARS), 0.0, 1.0)
        if protected else 0.0
    )

    pop = max(1, int(data.get("pop_total", 1) or 1))
    soldiers = max(0, int(data.get("soldiers", 0) or 0))
    soldier_ratio = soldiers / pop
    fort = float(_clamp(data.get("fortification", 0), 0, 100))
    food = max(0.0, float(data.get("food", 0) or 0))
    metal = max(0.0, float(data.get("metal", 0) or 0))
    yearly_food_need = max(1.0, pop * 0.05 + soldiers * 0.50)
    yearly_metal_need = max(1.0, soldiers * 1.25)
    supply_years = min(food / yearly_food_need, metal / yearly_metal_need)

    prewar = float(_clamp(data.get("prewar_risk_score", 0), 0, 100))
    soldier_gap = _clamp(
        (SECURITY_TARGET_SOLDIER_RATIO - soldier_ratio) / SECURITY_TARGET_SOLDIER_RATIO,
        0.0, 1.0,
    )
    fort_gap = _clamp(
        (SECURITY_TARGET_FORTIFICATION - fort) / SECURITY_TARGET_FORTIFICATION,
        0.0, 1.0,
    )
    supply_gap = _clamp(
        (SECURITY_TARGET_SUPPLY_YEARS - supply_years) / SECURITY_TARGET_SUPPLY_YEARS,
        0.0, 1.0,
    )
    wars = len(data.get("current_wars", []) or [])
    risk = prewar * 0.50 + soldier_gap * 22.0 + fort_gap * 14.0 + supply_gap * 14.0
    if not data.get("current_alliance"):
        risk += 8.0
    else:
        risk -= min(10.0, float(data.get("alliance_power_ratio", 0) or 0) * 25.0)
    if wars == 1:
        risk += 22.0
    elif wars >= 2:
        risk += 38.0
    risk = float(_clamp(risk, 0.0, 100.0))

    if protected:
        label = "保護準備"
    elif risk >= SECURITY_CRITICAL_THRESHOLD:
        label = "危急"
    elif risk >= SECURITY_SAFE_THRESHOLD:
        label = "受威脅"
    else:
        label = "安全"

    years_after = max(0, turn_counter - protection_until) if protection_until > 0 else 0
    last_milestone = max(0, int(data.get("survival_milestone_awarded", 0) or 0))
    pending_reward = 0.0
    for milestone in SECURITY_POST_PROTECTION_MILESTONES:
        if years_after >= milestone and last_milestone < milestone:
            last_milestone = milestone
            pending_reward += {25: 0.4, 50: 0.7, 100: 1.2}.get(milestone, 0.4)

    data["protection_remaining_years"] = remaining
    data["protection_remaining_ratio"] = round(remaining_ratio, 4)
    data["survival_preparation_urgency"] = round(urgency, 4)
    data["war_supply_years"] = round(supply_years, 2)
    data["security_risk_score"] = round(risk, 2)
    data["security_posture"] = label
    data["survival_milestone_awarded"] = last_milestone
    if pending_reward > 0:
        data["survival_milestone_reward_pending"] = round(
            float(data.get("survival_milestone_reward_pending", 0) or 0) + pending_reward, 3
        )
    return label


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



def _repair_chronicle_regime_types(data):
    """
    V6.6.2 修復舊編年史的政權類型。

    舊版政變流程曾先把 data["regime_type"] 改成新政權，
    再關閉上一代編年史，導致「被政變推翻的舊世代」
    被倒寫成新政權類型。

    修復規則：
    - 某世代以「軍事政變」結束 → 下一世代是軍事政權。
    - 某世代以「民變革命」結束 → 下一世代是革命政權。
    - 某世代以「宮廷政變」結束 → 下一世代是宮廷政權。
    - 某世代以「滅國 / 亡國重建」結束 → 下一世代是重建政權。
    - 重建政權第一次正統/合法交接後 → 轉為正統政權。
    - 其他合法交接 → 延續原政權類型。
    """
    history = data.get("country_chronicle", []) or []
    if not history:
        return

    coup_to_new_type = {
        "軍事政變": "軍事政權",
        "民變革命": "革命政權",
        "宮廷政變": "宮廷政權",
    }

    expected_type = None

    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            continue

        stored_type = str(
            item.get("regime_type", "")
            or ""
        ).strip()
        end_reason = str(
            item.get("end_reason", "")
            or ""
        ).strip()

        if expected_type:
            current_type = expected_type
        else:
            current_type = stored_type or "正統政權"

            # 典型舊 Bug：
            # 「本世代因軍事政變結束」卻已被寫成軍事政權。
            # 第一筆若沒有更早上下文，就回復為正統政權。
            produced_type = coup_to_new_type.get(end_reason)
            if (
                idx == 0
                and produced_type
                and current_type == produced_type
            ):
                current_type = "正統政權"

        # 「舊檔未記錄」不要硬猜，除非前一筆已推導出明確類型。
        if (
            not expected_type
            and current_type == "舊檔未記錄"
        ):
            item["regime_type"] = current_type
        else:
            item["regime_type"] = current_type

        # 依「這一代如何結束」推導下一代應是什麼政權。
        if end_reason in coup_to_new_type:
            expected_type = coup_to_new_type[end_reason]

        elif (
            end_reason == "滅國"
            or end_reason == "亡國重建"
            or end_reason.startswith("舊存檔：滅亡")
        ):
            expected_type = "重建政權"

        elif end_reason in {
            "正統繼承",
            "正統交接",
            "合法交接",
        }:
            if current_type == "重建政權":
                expected_type = "正統政權"
            else:
                expected_type = current_type

        elif end_reason in {"", "現行世代"}:
            expected_type = None

        else:
            expected_type = current_type


def _ensure_country_chronicle(country_key, data, turn_counter=0):
    """確保新舊存檔都有 V6.6.2 編年史資料。"""
    old_schema = int(
        data.get("chronicle_schema_version", 0)
        or 0
    )

    if old_schema < CHRONICLE_SCHEMA_VERSION:
        if (
            not isinstance(data.get("country_chronicle"), list)
            or not data.get("country_chronicle")
        ):
            data["country_chronicle"] = (
                _rebuild_chronicle_from_regime_history(
                    country_key,
                    data,
                    turn_counter,
                )
            )

        # V6.6.2：修正既有存檔中「舊世代被倒寫成新政權」。
        _repair_chronicle_regime_types(data)

        data["chronicle_schema_version"] = (
            CHRONICLE_SCHEMA_VERSION
        )

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


def coalition_join_willingness(candidate, hegemon_key, countries, alliances, rl_agents, rank_map, turn_counter=0):
    """回傳 0~0.95 的參加反霸權聯軍意願。越曾受霸主威脅、越弱、越接近前段班，意願越高。"""
    if candidate == hegemon_key:
        return 0.0

    c = countries[candidate]
    h = countries[hegemon_key]
    if not c.get("is_alive", True):
        return 0.0
    if REBUILD_PROTECTION_BLOCK_ALLIANCE and _is_rebuild_protected(c, turn_counter):
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


def _country_effective_war_power(country_key, countries, active_wars, defending=False):
    """以戰力、補給、疲勞、城防與既有戰線估算新戰爭的可用力量。"""
    data = countries.get(country_key, {})
    if not data.get("is_alive", True):
        return 0.0
    power = max(0.0, float(data.get("power", 0) or 0))
    soldiers = max(1.0, float(data.get("soldiers", 0) or 0))
    food_ratio = float(data.get("food", 0) or 0) / max(50.0, soldiers * 0.80)
    metal_ratio = float(data.get("metal", 0) or 0) / max(20.0, soldiers * 0.30)
    wood_ratio = float(data.get("wood", 0) or 0) / max(10.0, soldiers * 0.10)
    supply = _clamp(min(food_ratio, metal_ratio, wood_ratio), 0.20, 1.0)
    exhaustion = _clamp(float(data.get("war_exhaustion", 0) or 0), 0.0, 100.0)
    exhaustion_factor = 1.0 - exhaustion * 0.0045
    front_count = _war_country_war_count(country_key, active_wars)
    front_factor = (
        1.0 if front_count == 0
        else WARSTATE["SECOND_FRONT_FORCE_MULTIPLIER"] if front_count == 1
        else 0.20
    )
    defense_factor = 1.0
    if defending:
        defense_factor += min(
            0.45,
            float(data.get("fortification", 0) or 0) * 0.0045,
        )
    return max(
        0.0,
        power
        * (0.55 + supply * 0.45)
        * exhaustion_factor
        * front_factor
        * defense_factor,
    )


def estimate_war_matchup(attacker_key, defender_key, countries, alliances, active_wars):
    """宣戰前估算雙方完整普通聯盟，回傳攻方勝算與有效戰力。"""
    attacker_entity = get_entity_info(attacker_key, countries, alliances)
    defender_entity = get_entity_info(defender_key, countries, alliances)
    attacker_members = list(attacker_entity.get("members", []) or [attacker_key])
    defender_members = list(defender_entity.get("members", []) or [defender_key])

    attacker_power = sum(
        _country_effective_war_power(m, countries, active_wars, defending=False)
        * (1.0 if m == attacker_key else 0.65)
        for m in attacker_members
    )
    defender_power = sum(
        _country_effective_war_power(m, countries, active_wars, defending=True)
        * (1.0 if m == defender_key else 0.78)
        for m in defender_members
    )
    homeland_bonus = _homeland_defense_bonus(attacker_power, defender_power)
    defender_power *= 1.0 + homeland_bonus
    win_chance = attacker_power / max(1.0, attacker_power + defender_power)
    return {
        "win_chance": float(_clamp(win_chance, 0.0, 1.0)),
        "attacker_power": int(round(attacker_power)),
        "defender_power": int(round(defender_power)),
        "attacker_members": attacker_members,
        "defender_members": defender_members,
        "homeland_defense_bonus": round(homeland_bonus, 4),
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
    # 未滿五人時降低對新成員的門檻。聯盟越小，加成越高；
    # 但交戰中、曾互相攻擊、惡名與仇恨等否決理由仍完整保留。
    score += float(
        ALLIANCE_UNDERFILLED_JOIN_BONUS.get(len(living_members), 0.0)
    )

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
    if (
        REBUILD_PROTECTION_BLOCK_ALLIANCE
        and candidate_key in countries
        and _is_rebuild_protected(countries[candidate_key], turn_counter)
    ):
        return {
            "kind": "入盟表決", "turn": int(turn_counter), "alliance": alliance_name,
            "candidate": candidate_key,
            "candidate_name": countries[candidate_key].get("display_name", candidate_key),
            "eligible": 0, "threshold": 1, "threshold_weight": 1, "total_weight": 0,
            "yes": 0, "no": 1, "abstain": 0, "yes_weight": 0, "no_weight": 0,
            "abstain_weight": 0, "vote_weights": {}, "passed": False,
            "result": "重建保護期禁止入盟", "votes": {},
            "reasons": {candidate_key: f"重建保護期至第 {int(countries[candidate_key].get('newbie_protection_until_turn', 0))} 年"},
        }
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
    newbie_economic_supporters = []

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
            # 新手保護期內仍可履行聯盟義務，但不直接投入主戰線，
            # 改成有限度的經濟支援，避免「加入聯盟＝立刻被拖進大戰」。
            protection_until = int(
                countries[member].get("newbie_protection_until_turn", 0) or 0
            )
            if (
                member != defender_key
                and protection_until > int(turn_counter)
            ):
                newbie_economic_supporters.append(member)
            else:
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
    refused = max(0, len(members) - len(supporters) - len(newbie_economic_supporters))

    # 新手盟員的經濟支援：各自拿出少量現有資源，不加入主戰線。
    economic_aid = {"gold": 0, "food": 0, "wood": 0, "metal": 0}
    for member in newbie_economic_supporters:
        donor = countries[member]
        receiver = countries.get(defender_key)
        if not receiver:
            continue
        for res, rate in (("gold", 0.03), ("food", 0.04), ("wood", 0.04), ("metal", 0.03)):
            stock = max(0, int(donor.get(res, 0) or 0))
            # 保留大部分家底，避免新手因履行盟約而失去發展能力。
            amount = min(stock, int(stock * rate))
            if amount <= 0:
                continue
            donor[res] = stock - amount
            receiver[res] = max(0, int(receiver.get(res, 0) or 0)) + amount
            economic_aid[res] += amount

    print(
        f"🛡️ [共同防禦表態] {alliance_name}｜"
        f"【{defender_name}】遭【{attacker_name}】攻擊："
        f"軍事支援 {len(supporters)}／新手經濟支援 {len(newbie_economic_supporters)}／拒絕 {refused}。"
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
        "yes": len(supporters) + len(newbie_economic_supporters),
        "no": refused,
        "abstain": 0,
        "passed": True,
        "result": f"軍事 {len(supporters)} 國＋新手經濟 {len(newbie_economic_supporters)} 國支援",
        "participants": supporters,
        "economic_supporters": newbie_economic_supporters,
        "economic_aid": economic_aid,
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
    沒有地理地圖，因此「軍備競賽」用排名前後各 2 國作為潛在攻擊者。
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
    # V8 貨幣與政策欄位；舊存檔由讀檔流程補發初始大洋。
    data.setdefault("gold", 0)
    data.setdefault("currency_version", CURRENCY_VERSION)
    data.setdefault("birth_policy_turns", 0)
    data.setdefault("production_policy_turns", 0)
    data.setdefault("policy_summary", "無")
    data.setdefault("infrastructure", 0)
    data.setdefault("industry_focus", "AUTO")
    data.setdefault("industry_focus_turns", 0)
    data.setdefault("alliance_attempts", 0)
    data.setdefault("alliance_successes", 0)
    data.setdefault("alliance_rejections", 0)
    data.setdefault("alliance_dissolutions", 0)
    data.setdefault("alliance_last_result", "尚未嘗試")
    data.setdefault("last_war_target", "尚未評估")
    data.setdefault("last_war_win_chance", 0.0)
    data.setdefault("last_war_assessment", "尚未評估")
    data.setdefault("war_assessment_cancellations", 0)

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
    countries[country_key]["alliance_last_result"] = f"因{reason}退出 {ally_name}"
    if len(members) >= 2:
        alliances[ally_name] = members
    else:
        alliances.pop(ally_name, None)
        countries[country_key]["alliance_dissolutions"] = max(
            0, int(countries[country_key].get("alliance_dissolutions", 0) or 0)
        ) + 1
        for m in members:
            if m in countries:
                countries[m]["current_alliance"] = ""
                countries[m]["alliance_dissolutions"] = max(
                    0, int(countries[m].get("alliance_dissolutions", 0) or 0)
                ) + 1
                countries[m]["alliance_last_result"] = f"{ally_name} 因成員退出而解散"
    print(
        f"🤝 [退盟]【{countries[country_key].get('display_name', country_key)}】"
        f"因{reason}退出 {ally_name}。"
    )
    return True


def _alliance_disband_thresholds(alive_count):
    """依存活國數回傳（單一盟員、聯盟整體）動態瓦解門檻。"""
    count = max(1, int(alive_count or 1))
    return (
        max(0.20, min(0.40, 1.50 / count)),
        max(0.45, min(0.65, 2.20 / count)),
    )


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
        current_regime_type = (
            data.get("regime_type", "正統政權")
            or "正統政權"
        )

        # 「重建政權」只標示復國後的第一個過渡世代。
        # 它第一次和平交接後，正式回歸正統政權。
        if current_regime_type in {
            "正統政權",
            "重建政權",
        }:
            succession_kind = "正統交接"
            next_regime_type = "正統政權"
        else:
            succession_kind = "合法交接"
            next_regime_type = current_regime_type

        # 關閉舊世代時，data["regime_type"] 尚未改動，
        # 因此編年史會保留真正的舊政權類型。
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

        data["regime_type"] = next_regime_type

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
        new_regime_type = "軍事政權"
        data["political_stability"] = 36.0
        data["military_target_ratio"] = float(
            _clamp(float(data.get("military_target_ratio", 0.30)) + 0.08, 0.18, 0.50)
        )
        data["infamy"] = int(data.get("infamy", 0) or 0) + 10
        leave_chance = 0.22
        kind_name = "軍事政變"

    elif kind == "REVOLUTION":
        new_name = _unique_regime_name(
            country_key,
            countries,
            ["共和國", "聯邦", "新政國", "公民國"],
        )
        new_regime_type = "革命政權"
        data["political_stability"] = 41.0
        data["infamy"] = max(0, int(data.get("infamy", 0) or 0) - 12)
        data["military_target_ratio"] = float(
            _clamp(float(data.get("military_target_ratio", 0.30)), 0.22, 0.38)
        )
        leave_chance = 0.55
        kind_name = "民變革命"

    else:  # PALACE
        new_name = _unique_regime_name(
            country_key,
            countries,
            ["王朝", "新朝", "攝政府", "皇朝"],
        )
        new_regime_type = "宮廷政權"
        data["political_stability"] = 46.0
        data["infamy"] = int(data.get("infamy", 0) or 0) + 3
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

    # 現在才切換到新政權，避免上一代編年史被倒寫。
    data["regime_type"] = new_regime_type

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

        changed = _apply_regime_change(
            key, countries, alliances, rl_agents, turn_counter, kind, active_wars
        )
        if changed and key in rl_agents:
            kind_name = {"MILITARY": "軍事政變", "REVOLUTION": "革命", "PALACE": "宮廷政變"}.get(kind, "政權變動")
            rl_agents[key].decay_political_memory(kind_name)
        return changed

    # 沒政變才判正統繼承；要先累積足夠在位時間。
    for key in shuffled:
        data = countries[key]
        if int(data.get("regime_tenure", 0) or 0) < SUCCESSION_MIN_TENURE:
            continue
        if int(turn_counter) - int(data.get("last_regime_change_turn", -999999) or -999999) < REGIME_CHANGE_COOLDOWN_TURNS:
            continue
        if random.random() < SUCCESSION_CHANCE_PER_COUNTRY:
            changed = _apply_regime_change(
                key, countries, alliances, rl_agents, turn_counter, "SUCCESSION", active_wars
            )
            if changed and key in rl_agents:
                rl_agents[key].decay_political_memory("正統交接")
            return changed

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


def _award_season_champion_rewards(champion_key, countries, alliances, world_bank, turn_counter):
    """
    屆末冠軍實體獎勵。
    設計原則：
    1. 冠軍本人拿固定獎金。
    2. 若冠軍有普通聯盟，另設固定聯盟獎池，平均分給當時仍存活的盟友。
    3. 獎金由世界銀行發行/支付，所有發放都有 LOG，避免「冠軍只有稱號沒有戰果」。
    """
    if champion_key not in countries or not countries[champion_key].get("is_alive", True):
        return {"champion": 0, "alliance_pool": 0, "members": []}
    champion = countries[champion_key]
    champion_paid = _world_bank_grant(
        world_bank, champion, policy_cost(SEASON_CHAMPION_GOLD_REWARD, world_bank), reason="賽季冠軍獎金"
    )

    alliance_name = get_country_alliance(champion_key, alliances)
    members = [
        m for m in (alliances.get(alliance_name, []) if alliance_name else [])
        if m in countries and countries[m].get("is_alive", True)
    ]
    # 冠軍自己已拿冠軍獎金；聯盟獎池只分給其他盟友。
    allies = [m for m in members if m != champion_key]
    pool = policy_cost(SEASON_CHAMPION_ALLIANCE_POOL, world_bank) if allies else 0
    per_member = int(pool / len(allies)) if allies else 0
    distributed = 0
    member_rewards = []
    if per_member > 0:
        # 先從銀行金庫支付；不足部分由世界銀行發行，保持規則一致。
        for m in allies:
            amount = per_member
            paid = _world_bank_grant(world_bank, countries[m], amount, reason="冠軍聯盟成員獎勵")
            distributed += paid
            member_rewards.append((m, paid))
    return {"champion": champion_paid, "alliance_pool": distributed, "members": member_rewards}


# ====================================================
# 【世紀帝國風 RTS 國家輔助系統】(含詳細 LOG 輸出)
# ====================================================
import math
import random


def _adaptive_worker_shares(data, food, wood, metal, market):
    """只在 AUTO 配工：庫存缺口為主、有效成交趨勢為輔；每輪最多變動 6 個百分點。

    不覆寫 AI 選擇的限時產業專精；不改 RL State/Action 或 Q-table。
    """
    stocks = {"food": food, "wood": wood, "metal": metal}
    baseline = {"food": 0.50, "wood": 0.36, "metal": 0.14}
    previous = data.get("adaptive_worker_shares", {})
    if not isinstance(previous, dict):
        previous = {}
    targets = {}
    latest = (market or {}).get("price_monitor", {}).get("latest", {})
    history = (market or {}).get("price_monitor", {}).get("history", []) or []
    for resource in MARKET_RESOURCES:
        reserve = max(1.0, _market_target_stock(data, resource))
        ratio = max(0.0, float(stocks[resource])) / reserve
        stock_signal = _clamp(1.0 - ratio, -0.9, 1.0) * 0.16
        price_signal = 0.0
        # 價格必須同時在相鄰兩個觀測窗有足夠真實成交，才可參與配工。
        if len(history) >= 2 and latest.get("turn") == history[-1].get("turn"):
            earlier = history[-2]
            old_price = (earlier.get("prices") or {}).get(resource)
            new_price = (latest.get("prices") or {}).get(resource)
            if (old_price and new_price and int(history[-1]["turn"]) - int(earlier["turn"]) == MARKET_MONITOR_INTERVAL):
                change = float(new_price) / max(0.01, float(old_price)) - 1.0
                price_signal = _clamp(change, -0.30, 0.30) * 0.12
        targets[resource] = max(0.01, baseline[resource] + stock_signal + price_signal)
    total = sum(targets.values())
    targets = {resource: value / total for resource, value in targets.items()}
    food_target = _clamp(targets["food"], 0.42, 0.78)
    wood_target = _clamp(targets["wood"], 0.18, min(0.56, 0.94 - food_target))
    # 平滑變化，避免個別國家一輪內突然撤走所有糧食工作者。
    food_share = _clamp(
        baseline["food"] if "food" not in previous else float(previous["food"]),
        0.38, 0.80)
    wood_share = _clamp(
        baseline["wood"] if "wood" not in previous else float(previous["wood"]),
        0.16, 0.56)
    food_share = _clamp(food_target, food_share - 0.06, food_share + 0.06)
    wood_share = _clamp(wood_target, wood_share - 0.06, wood_share + 0.06)
    wood_share = min(wood_share, 0.94 - food_share)
    metal_share = max(0.06, 1.0 - food_share - wood_share)
    data["adaptive_worker_shares"] = {
        "food": round(food_share, 5), "wood": round(wood_share, 5), "metal": round(metal_share, 5)
    }
    return food_share, wood_share, metal_share


def update_rts_economy_and_jobs(data, market=None):
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
    gold = max(0, int(data.get("gold", 0) or 0))
    birth_policy_turns = max(0, int(data.get("birth_policy_turns", 0) or 0))
    production_policy_turns = max(0, int(data.get("production_policy_turns", 0) or 0))
    birth_policy_mult = BIRTH_POLICY_MULT if birth_policy_turns > 0 else 1.0
    production_policy_mult = PRODUCTION_POLICY_MULT if production_policy_turns > 0 else 1.0
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
            * birth_policy_mult
        )
        if birth_policy_turns > 0:
            growth_target += max(1, min(20, int(math.ceil(pop_total * 0.012))))
        policy_birth_cap = (
            max(BALANCE["BIRTH_MAX_PER_TURN"], min(30, int(math.ceil(pop_total * 0.035))))
            if birth_policy_turns > 0
            else BALANCE["BIRTH_MAX_PER_TURN"]
        )
        growth_target = max(
            1,
            min(
                max(1, int(policy_birth_cap * world_birth_mult)),
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

    industry_focus = str(data.get("industry_focus", "AUTO") or "AUTO")
    industry_focus_turns = max(0, int(data.get("industry_focus_turns", 0) or 0))

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
    elif industry_focus_turns > 0 and industry_focus == "FOOD":
        food_share, wood_share, metal_share = 0.70, 0.18, 0.12
    elif industry_focus_turns > 0 and industry_focus == "WOOD":
        food_share, wood_share, metal_share = 0.45, 0.40, 0.15
    elif industry_focus_turns > 0 and industry_focus == "METAL":
        food_share, wood_share, metal_share = 0.45, 0.15, 0.40
    elif industry_focus_turns > 0 and industry_focus == "BALANCED":
        food_share, wood_share, metal_share = 0.50, 0.30, 0.20
    else:
        food_share, wood_share, metal_share = _adaptive_worker_shares(data, food, wood, metal, market)

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
    # 超過安全庫存時，木材採集繼續隨庫存比下降；避免長局持續正產出
    # 把市場目標遠遠拋在後面。最低效率保留供應，維修亦會持續消耗木材。
    if wood > pop_total * BALANCE["WOOD_RESERVE_PER_POP"]:
        reserve = max(1.0, pop_total * BALANCE["WOOD_RESERVE_PER_POP"])
        wood_factor = max(
            BALANCE["WOOD_SURPLUS_MIN_FACTOR"],
            BALANCE["SURPLUS_PRODUCTION_FACTOR"]
            * (reserve / wood) ** BALANCE["WOOD_SURPLUS_DAMPING_EXPONENT"],
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

    infrastructure = _clamp(float(data.get("infrastructure", 0) or 0), 0.0, INFRASTRUCTURE_MAX)
    infrastructure_efficiency = 1.0 + min(0.50, infrastructure * 0.005)
    event_efficiency = (
        float(data.get("event_action_efficiency", 1.0) or 1.0)
        * production_policy_mult
        * infrastructure_efficiency
    )
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
    # 與糧食維持費同時按本輪農民數計算；即使稍後發生飢荒死亡，
    # 本輪已產生的房屋裝修需求仍保留。
    farmer_wood_consumed = farmers * BALANCE["FARMER_WOOD_UPKEEP"]

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
    # 木材維護需求＝歷史未支付額＋房屋維修＋每名農民的裝修費；
    # 延用原本的欠費累積機制，木材不足時絕不扣成負數。
    maintenance_due = (float(data.get("wood_maintenance_accrued", 0) or 0)
                       + houses * BALANCE["HOUSE_WOOD_UPKEEP_PER_HOUSE"]
                       + farmer_wood_consumed)
    maintenance_paid = min(data["wood"], int(maintenance_due))
    data["wood"] -= maintenance_paid
    data["wood_maintenance_accrued"] = round(maintenance_due - maintenance_paid, 4)
    data["wood_maintenance_spent"] = max(0, int(data.get("wood_maintenance_spent", 0) or 0)) + maintenance_paid
    data["metal"] = max(0, int(round(metal)))
    data["gold"] = gold
    if birth_policy_turns > 0:
        data["birth_policy_turns"] = birth_policy_turns - 1
    if production_policy_turns > 0:
        data["production_policy_turns"] = production_policy_turns - 1
    if industry_focus_turns > 0:
        data["industry_focus_turns"] = industry_focus_turns - 1
        if data["industry_focus_turns"] <= 0:
            data["industry_focus"] = "AUTO"
    active_policies = []
    if data.get("birth_policy_turns", 0) > 0:
        active_policies.append(f"鼓勵生育{data['birth_policy_turns']}年")
    if data.get("production_policy_turns", 0) > 0:
        active_policies.append(f"增產補貼{data['production_policy_turns']}年")
    data["policy_summary"] = "、".join(active_policies) if active_policies else "無"
    data["military_target_ratio"] = float(_clamp(military_target_ratio, 0.10, 0.50))
    if data["pop_total"] >= pop_at_turn_start:
        data["last_population_change_reason"] = ""

    if "calculate_rts_power" in globals():
        data["power"] = calculate_rts_power(data)


# ====================================================
# 【自主學習 RL 大腦 V6】三層 Sub-policy + Expected SARSA(λ)
# ====================================================
# V7 取消固定人格與人格探索偏好。
# V8_2 因加入延遲評估、造訪統計及下一狀態 Action Mask，RL_VERSION 升為 5。
RL_VERSION = 8  # 第一維由「生存資源」改為「安全態勢」；戰略 Q 需乾淨重學
RL_ALGORITHM = "EXPECTED_SARSA_LAMBDA"
RL_LAMBDA = 0.80
RL_GAMMA = 0.975
RL_BASE_EPSILON = 0.20
RL_EPSILON_FLOOR = 0.05
RL_EPSILON_DECAY_V6 = 0.9995
RL_EXPLORATION_PULSE_INTERVAL = 750
RL_EXPLORATION_PULSE_LENGTH = 30
RL_EXPLORATION_PULSE_VALUE = 0.12

# 賽季競爭學習：屆中檢查只提供小額方向訊號，屆末冠軍則是最大終局獎勵。
# 這些數值直接作用於戰略層 Q 值，不再除以 10。
COMPETITION_CHECKPOINT_TURNS = 100
SEASON_CHAMPION_Q_REWARD = 6.0
SEASON_RUNNER_UP_Q_REWARD = 2.5
SEASON_THIRD_Q_REWARD = 1.5

# 屆末實體獎勵：採固定獎池，避免聯盟成員越多就無限印錢。
SEASON_CHAMPION_GOLD_REWARD = 150 * MONEY_RATIO
SEASON_CHAMPION_ALLIANCE_POOL = 100 * MONEY_RATIO

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
    3: "基礎建設投資",
    4: "背叛背刺",
    5: "加固防線",
    6: "戰時動員",
    7: "調整產業配置",
    8: "市場貿易",
    9: "修復聲望",
    10: "小規模襲擾",
    11: "裁軍休養",
    12: "鼓勵生育",
    13: "增產補貼",
    14: "外交金援",
    15: "聯盟援助",
}
RL_ACTION_SIZE = len(RL_ACTIONS)

STRATEGIC_ACTIONS = {
    0: "基礎建設投資",
    1: "產業與糧食配置",
    2: "軍備與動員",
    3: "防禦修復與休養",
    4: "結盟與共同防禦",
    5: "主動戰爭",
    6: "有限襲擾與施壓",
    7: "財政與人口政策",
    8: "反霸權與圍剿",
    9: "背叛與機會主義",
    10: "聲望與外交修復",
}
STRATEGIC_TO_ENGINE_ACTIONS = {
    0: (3,), 1: (7,), 2: (6,), 3: (5, 11),
    4: (1,), 5: (0,), 6: (10,), 7: (12, 13),
    8: (2,),
    9: (4,),
    10: (9,),
}
MARKET_ACTIONS = {
    0: "不交易", 1: "買糧", 2: "買木", 3: "買金屬",
    4: "賣糧", 5: "賣木", 6: "賣金屬",
}
MARKET_PRICE_ACTIONS = {0: "被動", 1: "中性", 2: "積極"}
MARKET_SIZE_ACTIONS = {0: "小額", 1: "中額", 2: "大額"}
ALLIANCE_ACTIONS = {
    0: "不行動", 1: "請求援助", 2: "一般援助",
    3: "盟內優惠交易", 4: "資源交換", 5: "緊急救援",
}


def _clamp(value, low, high):
    return max(low, min(high, value))


def _evaluate_prewar_mobilization(country_key, countries, active_wars, alive_sorted=None):
    """
    戰前軍事風險評估。

    V8.4.7.1 調整：不再把「世界戰力排名附近」當成潛在攻擊者。
    沒有地圖時，排名只能代表國力，不能代表地理位置或開戰意圖。

    新模型改成「潛在攻擊者選擇器」：
    1. 從所有存活、非本國、非普通同盟成員中建立候選池。
    2. 主要看「對我方的攻擊意圖」，而不是世界排名：
       - 對我方敵意（對方 -> 我方）
       - 最近是否攻擊過我方
       - 我方最近是否攻擊過對方（復仇風險）
       - 對方過去戰爭／侵略活動程度
    3. 再看「攻擊能力」：對方戰力與軍事人口比例。
    4. 正在多線作戰的國家降低短期新增戰線威脅。
    5. 最後從最高威脅候選中選出一名主要威脅，供 Q-learning 做戰前動員判斷。

    這樣「排名前後」只影響能力，不再直接決定誰是潛在攻擊者。
    """
    data = countries.get(country_key)
    if not data or not data.get("is_alive", True):
        return {"score": 0.0, "level": "CALM", "need": 0.0, "threat": None}

    # 已在戰爭中時不使用戰前評估，避免把戰時邏輯混進來。
    if data.get("current_wars"):
        return {"score": 0.0, "level": "WAR", "need": 0.0, "threat": None}

    alive = list(alive_sorted or sorted(
        [k for k, c in countries.items() if c.get("is_alive", True)],
        key=lambda k: countries[k].get("power", 0),
        reverse=True,
    ))

    my_power = max(1.0, float(data.get("power", 0) or 0))
    pop = max(1, int(data.get("pop_total", 1) or 1))
    soldiers = max(0, int(data.get("soldiers", 0) or 0))
    my_ratio = soldiers / pop
    farmers = max(0, int(data.get("farmers", 0) or 0))
    # 農民／士兵比本身就是戰備指標，不必等找到明確敵人。
    farmer_soldier_ratio = farmers / max(1, soldiers) if soldiers > 0 else 99.0
    if farmer_soldier_ratio >= PREWAR_FARMER_SOLDIER_CRITICAL_RATIO:
        force_balance_risk = PREWAR_FORCE_BALANCE_CRITICAL_SCORE
    elif farmer_soldier_ratio >= PREWAR_FARMER_SOLDIER_HIGH_RATIO:
        force_balance_risk = PREWAR_FORCE_BALANCE_HIGH_SCORE + _clamp((farmer_soldier_ratio - 4.0) / 0.5, 0.0, 1.0) * 17.0
    elif farmer_soldier_ratio >= PREWAR_FARMER_SOLDIER_ALERT_RATIO:
        force_balance_risk = PREWAR_FORCE_BALANCE_ALERT_SCORE + _clamp((farmer_soldier_ratio - 3.0) / 1.0, 0.0, 1.0) * 20.0
    else:
        force_balance_risk = _clamp((3.0 - farmer_soldier_ratio) / 3.0, 0.0, 1.0) * 25.0
    hostility_map = data.get("hostility", {}) or {}
    recent_attackers = set(data.get("recent_attackers", []) or [])
    my_alliance = data.get("current_alliance")

    candidates = []
    for n in alive:
        if n == country_key:
            continue
        nd = countries.get(n, {})
        if not nd.get("is_alive", True):
            continue
        # 普通同盟內部不是戰前外部威脅。只用國家自己的 current_alliance 欄位，
        # 不需要把 alliances 額外塞進評估器，因此仍可維持函式獨立。
        if my_alliance and nd.get("current_alliance") == my_alliance:
            continue

        n_power = max(1.0, float(nd.get("power", 0) or 0))
        n_pop = max(1, int(nd.get("pop_total", 1) or 1))
        n_soldiers = max(0, int(nd.get("soldiers", 0) or 0))
        n_ratio = n_soldiers / n_pop
        n_hostility_map = nd.get("hostility", {}) or {}

        # 「意圖」與「能力」分開算；避免單純因排名高就被視為會開戰。
        directed_hostility = _clamp(float(n_hostility_map.get(country_key, 0) or 0) / 100.0, 0.0, 1.0)
        our_hostility = _clamp(float(hostility_map.get(n, 0) or 0) / 100.0, 0.0, 1.0)
        recent_attack_pressure = 1.0 if n in recent_attackers else 0.0
        revenge_pressure = 1.0 if country_key in set(nd.get("recent_attackers", []) or []) else 0.0

        wars_fought = max(0, int(nd.get("wars_fought", 0) or 0))
        infamy = max(0, float(nd.get("infamy", 0) or 0))
        war_record_pressure = _clamp(wars_fought / 12.0, 0.0, 1.0)
        infamy_pressure = _clamp(infamy / 120.0, 0.0, 1.0)

        # 正在多線作戰代表短期再開新戰線的能力／意願下降。
        active_war_count = _war_country_war_count(n, active_wars)
        war_distraction = 0.0
        if active_war_count >= 2:
            war_distraction = 0.45
        elif active_war_count == 1:
            war_distraction = 0.20

        intent = (
            directed_hostility * 0.48
            + recent_attack_pressure * 0.24
            + revenge_pressure * 0.16
            + war_record_pressure * 0.07
            + infamy_pressure * 0.05
        )
        # 如果只是我方單方面仇視對方，不應直接被解讀成對方會打我。
        intent += our_hostility * 0.04
        intent = _clamp(intent * (1.0 - war_distraction), 0.0, 1.0)

        power_ratio = n_power / my_power
        power_pressure = _clamp((power_ratio - 0.75) / 1.25, 0.0, 1.0)
        military_pressure = _clamp((n_ratio - my_ratio + 0.03) / 0.30, 0.0, 1.0)
        capability = _clamp(power_pressure * 0.65 + military_pressure * 0.35, 0.0, 1.0)

        # 只有能力沒有意圖時，仍保留低度背景風險；但不讓它壓過真正有恩怨的國家。
        threat = intent * 72.0 + capability * 28.0
        candidates.append({
            "key": n,
            "power": n_power,
            "soldier_ratio": n_ratio,
            "hostility": float(n_hostility_map.get(country_key, 0) or 0),
            "intent": intent,
            "capability": capability,
            "threat": threat,
            "power_ratio": power_ratio,
            "active_wars": active_war_count,
        })

    # 不使用排名鄰近範圍；只保留最高威脅的少量候選，避免所有國家互相形成噪音。
    candidates.sort(key=lambda x: (x["threat"], x["intent"], x["capability"]), reverse=True)
    threat_pool = candidates[:PREWAR_THREAT_CANDIDATE_COUNT]
    top = threat_pool[0] if threat_pool else None

    if not top:
        score = 0.0
    else:
        score = float(top["threat"])

        # 世界局勢只放大「已經存在的威脅」，不會憑空指定敵人。
        world_code = str(data.get("world_mode_code", "NORMAL") or "NORMAL")
        if world_code == "ARMS_RACE":
            score *= 1.08
        elif world_code == "TOTAL_WAR":
            score *= 1.14
        elif world_code == "HEGEMONIC" and int(data.get("world_rank", 999) or 999) <= 10:
            score *= 1.05

        if top["soldier_ratio"] > my_ratio + 0.08:
            score += 6.0
        if top["power"] > my_power * 1.35:
            score += 6.0
        if top["intent"] >= 0.55 and top["power_ratio"] >= 1.0:
            score += 5.0

    # 自身兵力失衡是獨立危機來源：不能因為「目前沒找到敵人」就判定安全。
    score = max(score, force_balance_risk)
    if score > force_balance_risk and force_balance_risk >= PREWAR_FORCE_BALANCE_ALERT_SCORE:
        score += (force_balance_risk - PREWAR_FORCE_BALANCE_ALERT_SCORE) * 0.15

    score = _clamp(score, 0.0, 100.0)
    if score >= PREWAR_RISK_CRITICAL:
        level = "CRITICAL"
    elif score >= PREWAR_RISK_HIGH:
        level = "HIGH"
    elif score >= PREWAR_RISK_ALERT:
        level = "ALERT"
    else:
        level = "CALM"

    food = max(0.0, float(data.get("food", 0) or 0))
    metal = max(0.0, float(data.get("metal", 0) or 0))
    farmers = max(0, int(data.get("farmers", 0) or 0))
    food_runway = food / max(1.0, farmers + soldiers * 2.0)
    recruit_ready = (
        farmers >= max(10, int(pop * 0.10))
        and food_runway >= PREWAR_RESOURCE_FOOD_RUNWAY
        and metal >= max(20.0, pop * PREWAR_RESOURCE_METAL_PER_POP)
    )

    target_ratio = float(data.get("military_target_ratio", 0.30) or 0.30)
    ratio_gap = _clamp((target_ratio - my_ratio) / 0.30, 0.0, 1.0)
    force_balance_need = _clamp(
        (farmer_soldier_ratio - PREWAR_FARMER_SOLDIER_ALERT_RATIO) /
        (PREWAR_FARMER_SOLDIER_CRITICAL_RATIO - PREWAR_FARMER_SOLDIER_ALERT_RATIO),
        0.0, 1.0
    )
    need = _clamp(
        (score / 100.0) * 0.55 + ratio_gap * 0.25 + force_balance_need * 0.20,
        0.0, 1.0
    )
    if not recruit_ready:
        need *= 0.65

    return {
        "score": round(float(score), 2),
        "level": level,
        "need": round(float(need), 3),
        "threat": top["key"] if top else None,
        "threat_power_ratio": round(top["power_ratio"] if top else 0.0, 3),
        "threat_soldier_ratio": round(top["soldier_ratio"] if top else 0.0, 3),
        "threat_hostility": round(top["hostility"] if top else 0.0, 1),
        "threat_intent": round(top["intent"] if top else 0.0, 3),
        "threat_capability": round(top["capability"] if top else 0.0, 3),
        "farmer_soldier_ratio": round(farmer_soldier_ratio, 2),
        "force_balance_risk": round(force_balance_risk, 2),
        "neighbor_count": len(threat_pool),
        "recruit_ready": bool(recruit_ready),
        "food_runway": round(food_runway, 2),
    }


RL_SNAPSHOT_FIELDS = (
    "is_alive", "power", "pop_total", "farmers", "soldiers",
    "food", "wood", "metal", "gold", "current_alliance", "recent_attackers",
    "infamy", "prev_power", "annexed_count",
    "market_price_food", "market_price_wood", "market_price_metal",
    "current_wars", "political_stability", "war_exhaustion",
    "alliance_power_ratio", "international_dread",
    "prewar_risk_score", "prewar_risk_level", "prewar_mobilization_need",
    "prewar_threat_country", "prewar_threat_power_ratio", "prewar_threat_soldier_ratio",
    "prewar_threat_intent", "prewar_threat_capability",
    "prewar_farmer_soldier_ratio", "prewar_force_balance_risk",
    "season_phase", "world_rank", "top_three_contender",
    "infrastructure", "currency_denomination", "birth_policy_total_gain",
    "production_policy_total_gain",
    "protection_remaining_years", "protection_remaining_ratio",
    "survival_preparation_urgency", "war_supply_years",
    "security_risk_score", "security_posture",
    "survival_milestone_reward_pending", "survival_milestone_awarded",
)


def _rl_snapshot(data):
    """RL 只複製真正會用到的欄位，避免 deepcopy 整份國家歷史資料。"""
    snap = {}
    for key in RL_SNAPSHOT_FIELDS:
        value = data.get(key)
        if key in ("recent_attackers", "current_wars"):
            value = list(value or [])
        snap[key] = value
    return snap


# 國際忌憚值機制
COALITION_FORMATION_BOUNTY = COALITION_FORMATION_BOUNTY_BASE * MONEY_RATIO
COALITION_VICTORY_BOUNTY = COALITION_VICTORY_BOUNTY_BASE * MONEY_RATIO

def _international_dread_rank_delta(rank):
    """依本回合世界戰力排名計算國際忌憚值變化。1~10 名為正值，11 名後為負值。"""
    rank = max(1, int(rank or 1))
    if rank <= 10:
        return 110 - rank * 10  # 1:+100 ... 10:+10
    return -10 * (rank - 10)    # 11:-10 ... 20:-100 ... 100:-900


def update_international_dread(countries, alive_sorted):
    """每回合依排名更新國際忌憚值，最低為 0；死亡國家歸零。"""
    rank_map = {k: idx + 1 for idx, k in enumerate(alive_sorted)}
    for country_key, data in countries.items():
        if not data.get("is_alive", True):
            data["international_dread"] = 0
            continue
        rank = rank_map.get(country_key)
        if rank is None:
            data["international_dread"] = max(0, int(data.get("international_dread", 0) or 0))
            continue
        old = max(0, int(data.get("international_dread", 0) or 0))
        data["international_dread"] = max(0, old + _international_dread_rank_delta(rank))


def select_international_dread_coalition_targets(countries, alive_sorted, limit=None):
    """回傳所有達標目標；不同高忌憚國可各自對應一個圍剿聯盟。"""
    candidates = [
        k for k in alive_sorted
        if int(countries[k].get("international_dread", 0) or 0) >= INTERNATIONAL_DREAD_CANDIDATE_THRESHOLD
    ]
    candidates.sort(
        key=lambda k: (
            int(countries[k].get("international_dread", 0) or 0),
            int(countries[k].get("power", 0) or 0),
        ),
        reverse=True,
    )
    max_targets = COALITION_MAX_ACTIVE if limit is None else max(0, int(limit))
    return candidates[:max_targets]


def select_international_dread_coalition_target(countries, alive_sorted):
    """舊呼叫相容：僅取最高忌憚目標；新流程應使用複數版本。"""
    targets = select_international_dread_coalition_targets(countries, alive_sorted, 1)
    return targets[0] if targets else None


def _infrastructure_investment_cost(data):
    """依目前基建等級回傳下一次投資的大洋、木材與金屬成本。"""
    infrastructure = max(0, int(data.get("infrastructure", 0) or 0))
    tier = min(4, infrastructure // 20)
    return (
        policy_cost(INFRASTRUCTURE_GOLD_BASE + tier * 20 * MONEY_RATIO, data),
        INFRASTRUCTURE_WOOD_BASE + tier * 15,
        INFRASTRUCTURE_METAL_BASE + tier * 10,
    )


def _apply_infrastructure_investment(data, bank, gain=None):
    """支付真實資產並提升基建；成功時回傳成本與增幅。"""
    infrastructure = max(0, int(data.get("infrastructure", 0) or 0))
    gold_cost, wood_cost, metal_cost = _infrastructure_investment_cost(data)
    if infrastructure >= INFRASTRUCTURE_MAX:
        return None
    if MARKET_ECONOMY_ENABLED and (
        int(data.get("gold", 0) or 0) < gold_cost
        or int(data.get("wood", 0) or 0) < wood_cost
        or int(data.get("metal", 0) or 0) < metal_cost
    ):
        return None
    actual_gain = min(
        INFRASTRUCTURE_MAX - infrastructure,
        max(1, int(gain if gain is not None else random.randint(3, 6))),
    )
    if MARKET_ECONOMY_ENABLED:
        data["gold"] -= gold_cost
        data["wood"] -= wood_cost
        data["metal"] -= metal_cost
        _world_bank_collect(bank, gold_cost, category="policy")
        paid = {"gold": gold_cost, "wood": wood_cost, "metal": metal_cost}
    else:
        paid = _pay_mixed_resource_cost(data)
    data["infrastructure"] = infrastructure + actual_gain
    return {
        "gain": actual_gain, **paid,
    }


def get_valid_rl_actions(attacker_key, countries, alliances, anti_hegemon_coalitions, alive_sorted, turn_counter=0):
    """依照客觀條件建立 Action Mask；圍剿使用獨立臨時聯軍，不改變普通聯盟。"""
    c = countries[attacker_key]
    valid = {7}  # 產業配置不耗資源，至少永遠可做，避免無合法動作

    if not c.get("is_alive", True):
        return [3]

    pop = max(1, int(c.get("pop_total", 1)))
    farmers = max(0, int(c.get("farmers", 0)))
    soldiers = max(0, int(c.get("soldiers", 0)))
    food = max(0, c.get("food", 0))
    wood = max(0, c.get("wood", 0))
    metal = max(0, c.get("metal", 0))
    gold = max(0, int(c.get("gold", 0) or 0))
    current_alliance = c.get("current_alliance", "")

    # 3 基礎建設：成本隨等級提高，且必須真實支付三種資產。
    infrastructure = max(0, int(c.get("infrastructure", 0) or 0))
    infrastructure_gold_cost, infrastructure_wood_cost, infrastructure_metal_cost = (
        _infrastructure_investment_cost(c)
    )
    if (
        infrastructure < INFRASTRUCTURE_MAX
        and (not MARKET_ECONOMY_ENABLED or (
            gold >= infrastructure_gold_cost
            and wood >= infrastructure_wood_cost
            and metal >= infrastructure_metal_cost
        ))
    ):
        valid.add(3)

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
    if (
        not current_alliance
        and not (REBUILD_PROTECTION_BLOCK_ALLIANCE and _is_rebuild_protected(c, turn_counter))
        and any(
        k != attacker_key
        and countries[k].get("is_alive", True)
        and not (REBUILD_PROTECTION_BLOCK_ALLIANCE and _is_rebuild_protected(countries[k], turn_counter))
        for k in alive_sorted
        )
    ):
        valid.add(1)

    # 2 圍剿：自己不能是第一名，且全球圍剿聯盟未達上限。
    if (
        alive_sorted
        and alive_sorted[0] != attacker_key
        and len(alive_sorted) >= 4
        and len(anti_hegemon_coalitions) < COALITION_MAX_ACTIVE 
    ):
        valid.add(2)

    # 4 背叛：必須真的有活著的盟友可背刺。
    if current_alliance in alliances:
        partners = [
            m for m in alliances[current_alliance]
            if m != attacker_key and countries[m].get("is_alive", True)
        ]
        alliance_tenure = max(
            0,
            int(c.get("current_turn", 0) or 0)
            - int(c.get("alliance_join_turn", 0) or 0),
        )
        max_partner_hostility = max(
            [float((c.get("hostility", {}) or {}).get(m, 0) or 0) for m in partners]
            or [0.0]
        )
        dominant_partner = any(
            float(countries[m].get("power", 0) or 0)
            > max(1.0, float(c.get("power", 0) or 0)) * 2.20
            for m in partners
        )
        betrayal_crisis = (
            max_partner_hostility >= 55
            or float(c.get("political_stability", 75) or 75) < 30
            or dominant_partner
        )
        if partners and alliance_tenure >= 20 and betrayal_crisis:
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

    # 8 世界市場：有大洋可買，或有物資盈餘可賣。
    if MARKET_ECONOMY_ENABLED and (gold >= 25 * MONEY_RATIO or max(food, wood * 2, metal * 2) >= 150):
        valid.add(8)

    # 9 聲望修復：改以世界共同貨幣支付外交成本。
    if c.get("infamy", 0) > 0 and (not MARKET_ECONOMY_ENABLED or gold >= policy_cost(60 * MONEY_RATIO, c)):
        valid.add(9)

    # 10 襲擾：比全面戰爭成本低，但仍需基本兵力與敵對目標。
    if soldiers >= 5 and hostile_targets and food >= 30:
        valid.add(10)

    # 11 裁軍：有士兵才能裁。
    if soldiers > 0:
        valid.add(11)

    # 12 鼓勵生育：需要政策預算。
    if not MARKET_ECONOMY_ENABLED or gold >= policy_cost(BIRTH_POLICY_GOLD_COST, c):
        valid.add(12)

    # 13 增產補貼：需要政策預算。
    if not MARKET_ECONOMY_ENABLED or gold >= policy_cost(PRODUCTION_POLICY_GOLD_COST, c):
        valid.add(13)

    # 14 外交金援：需有大洋且世界上還有其他存活國家。
    if (not MARKET_ECONOMY_ENABLED or gold >= policy_cost(DIPLOMACY_GOLD_MIN, c)) and len(alive_sorted) >= 2:
        valid.add(14)

    # 15 聯盟援助：有存活盟友，且至少有一種可援助資產。
    if current_alliance in alliances:
        partners = [m for m in alliances[current_alliance] if m != attacker_key and countries[m].get("is_alive", True)]
        if partners and (not MARKET_ECONOMY_ENABLED or gold > policy_cost(180 * MONEY_RATIO, c) or food > 250 or wood > 150 or metal > 100):
            valid.add(15)

    return sorted(valid)


class ExpectedSarsaLambdaPolicy:
    """低成本、可解釋的表格型 Expected SARSA(λ) 子策略。"""

    def __init__(self, name, action_size, payload=None, max_states=2500):
        payload = payload if isinstance(payload, dict) else {}
        self.name = str(name)
        self.action_size = int(action_size)
        self.max_states = max(100, int(max_states))
        self.q_table = payload.get("q_table", {}) if isinstance(payload.get("q_table", {}), dict) else {}
        self.visit_counts = payload.get("visit_counts", {}) if isinstance(payload.get("visit_counts", {}), dict) else {}
        self.last_seen = payload.get("last_seen", {}) if isinstance(payload.get("last_seen", {}), dict) else {}
        self.action_stats = payload.get("action_stats", {}) if isinstance(payload.get("action_stats", {}), dict) else {}
        self.traces = {}
        self.decision_count = max(0, int(payload.get("decision_count", 0) or 0))
        self.prune_count = max(0, int(payload.get("prune_count", 0) or 0))
        self.td_error_ema = float(payload.get("td_error_ema", 0.0) or 0.0)
        self.shock_boost = max(0.0, float(payload.get("shock_boost", 0.0) or 0.0))
        self.last_decision_state = str(payload.get("last_decision_state", "") or "")
        raw_last_action = payload.get("last_decision_action")
        self.last_decision_action = (
            int(raw_last_action)
            if raw_last_action is not None and str(raw_last_action).lstrip("-").isdigit()
            else None
        )
        for state, values in list(self.q_table.items()):
            if not isinstance(values, list):
                values = []
            self.q_table[state] = (values + [0.0] * self.action_size)[:self.action_size]

    @staticmethod
    def state_key(state):
        return json.dumps(list(state), ensure_ascii=False, separators=(",", ":"))

    def effective_epsilon(self, state_key=None):
        base = max(RL_EPSILON_FLOOR, RL_BASE_EPSILON * (RL_EPSILON_DECAY_V6 ** self.decision_count))
        pulse_pos = self.decision_count % RL_EXPLORATION_PULSE_INTERVAL
        if pulse_pos < RL_EXPLORATION_PULSE_LENGTH:
            base = max(base, RL_EXPLORATION_PULSE_VALUE)
        if state_key is not None:
            visits = max(0, int(self.visit_counts.get(state_key, 0) or 0))
            base += min(0.10, 0.08 / math.sqrt(visits + 1.0))
        base += self.shock_boost
        self.shock_boost *= 0.97
        return float(_clamp(base, RL_EPSILON_FLOOR, 0.35))

    def trigger_exploration(self, amount=0.08):
        self.shock_boost = max(self.shock_boost, float(_clamp(amount, 0.0, 0.20)))

    def _ensure(self, state_key):
        values = self.q_table.get(state_key)
        if not isinstance(values, list):
            values = [0.0] * self.action_size
            self.q_table[state_key] = values
        elif len(values) != self.action_size:
            values = (values + [0.0] * self.action_size)[:self.action_size]
            self.q_table[state_key] = values
        self.last_seen[state_key] = self.decision_count
        if len(self.q_table) > self.max_states:
            protected = set(sorted(self.last_seen, key=self.last_seen.get, reverse=True)[:max(20, self.max_states // 20)])
            candidates = []
            for key, vec in self.q_table.items():
                if key in protected:
                    continue
                visits = max(0, int(self.visit_counts.get(key, 0) or 0))
                info = max((abs(float(v)) for v in vec), default=0.0)
                age = max(0, self.decision_count - int(self.last_seen.get(key, 0) or 0))
                score = math.log1p(visits) + min(5.0, info / 5.0) - min(6.0, age / 500.0)
                candidates.append((score, key))
            remove_n = min(max(1, self.max_states // 20), len(self.q_table) - self.max_states)
            for _score, key in sorted(candidates)[:remove_n]:
                self.q_table.pop(key, None)
                self.visit_counts.pop(key, None)
                self.last_seen.pop(key, None)
                self.prune_count += 1
        return values

    def choose(self, state, valid_actions=None):
        key = self.state_key(state)
        q_values = self._ensure(key)
        valid = [a for a in (valid_actions or range(self.action_size)) if 0 <= int(a) < self.action_size]
        if not valid:
            valid = [0]
        self.decision_count += 1
        self.visit_counts[key] = max(0, int(self.visit_counts.get(key, 0) or 0)) + 1
        epsilon = self.effective_epsilon(key)
        if random.random() < epsilon or max(q_values[a] for a in valid) - min(q_values[a] for a in valid) < 1e-12:
            action = random.choice(valid)
        else:
            best = max(q_values[a] for a in valid)
            action = random.choice([a for a in valid if abs(q_values[a] - best) < 1e-12])
        self._last_state = tuple(state)
        self._last_action = int(action)
        self._last_epsilon = epsilon
        self.last_decision_state = key
        self.last_decision_action = int(action)
        return int(action)

    def _expected_value(self, q_values, valid_actions, epsilon):
        valid = [a for a in valid_actions if 0 <= int(a) < self.action_size] or [0]
        best = max(q_values[a] for a in valid)
        greedy = [a for a in valid if abs(q_values[a] - best) < 1e-12]
        value = 0.0
        for action in valid:
            probability = epsilon / len(valid)
            if action in greedy:
                probability += (1.0 - epsilon) / len(greedy)
            value += probability * q_values[action]
        return value

    def learn(self, state, action, reward, next_state, next_valid_actions, success=None):
        state_key = self.state_key(state)
        next_key = self.state_key(next_state)
        q_now = self._ensure(state_key)
        q_next = self._ensure(next_key)
        epsilon_next = self.effective_epsilon(next_key)
        expected_next = self._expected_value(q_next, next_valid_actions, epsilon_next)
        delta = float(reward) + RL_GAMMA * expected_next - q_now[int(action)]
        trace_key = (state_key, int(action))
        self.traces[trace_key] = 1.0
        for (s_key, a_idx), eligibility in list(self.traces.items()):
            vec = self._ensure(s_key)
            visits = max(1, int(self.visit_counts.get(s_key, 1) or 1))
            alpha = max(0.025, 0.16 / (visits ** 0.20))
            vec[a_idx] += alpha * delta * eligibility
            new_trace = eligibility * RL_GAMMA * RL_LAMBDA
            if new_trace < 0.01:
                self.traces.pop((s_key, a_idx), None)
            else:
                self.traces[(s_key, a_idx)] = new_trace
        self.td_error_ema = self.td_error_ema * 0.95 + abs(delta) * 0.05
        key = str(int(action))
        stat = self.action_stats.setdefault(key, {"count": 0, "reward_sum": 0.0, "success": 0})
        stat["count"] += 1
        stat["reward_sum"] += float(reward)
        if success:
            stat["success"] += 1
        return delta

    def apply_event_reward(self, state_key, action, reward):
        """將延遲事件追溯到原決策，同時保留目前資格跡跡的影響。"""
        action = int(action)
        if not (0 <= action < self.action_size):
            return 0.0
        q_values = self._ensure(str(state_key))
        delta = float(reward) - q_values[action]
        self.traces[(str(state_key), action)] = 1.0
        for (trace_state, trace_action), eligibility in list(self.traces.items()):
            values = self._ensure(trace_state)
            visits = max(1, int(self.visit_counts.get(trace_state, 1) or 1))
            alpha = max(0.02, 0.10 / (visits ** 0.20))
            values[trace_action] += alpha * delta * eligibility
        self.td_error_ema = self.td_error_ema * 0.95 + abs(delta) * 0.05
        return delta

    def decay_memory(self, retention):
        retention = float(_clamp(retention, 0.0, 1.0))
        for values in self.q_table.values():
            for index in range(len(values)):
                values[index] *= retention
        for key in list(self.visit_counts):
            self.visit_counts[key] = int(self.visit_counts[key] * retention)
        self.traces.clear()
        self.trigger_exploration((1.0 - retention) * 0.18)

    def to_dict(self):
        return {
            "algorithm": RL_ALGORITHM,
            "action_size": self.action_size,
            "q_table": self.q_table,
            "visit_counts": self.visit_counts,
            "last_seen": self.last_seen,
            "action_stats": self.action_stats,
            "decision_count": self.decision_count,
            "prune_count": self.prune_count,
            "td_error_ema": self.td_error_ema,
            "shock_boost": self.shock_boost,
            "last_decision_state": self.last_decision_state,
            "last_decision_action": self.last_decision_action,
        }


class CountryRLAgent:
    """多層自主學習國家 AI；戰略層再解析為引擎動作與子策略。"""

    def __init__(
        self,
        country_name,
        action_size=RL_ACTION_SIZE,
        learning_rate=0.10,
        discount_factor=0.92,
        epsilon=0.22,
        q_table=None,
        decision_count=0,
        visit_counts=None,
        action_stats=None,
        pending_decisions=None,
        policy_data=None,
    ):
        self.country_name = country_name
        self.action_size = RL_ACTION_SIZE
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = float(epsilon)
        self.decision_count = max(0, int(decision_count or 0))
        self.q_table = q_table if isinstance(q_table, dict) else {}
        self.visit_counts = visit_counts if isinstance(visit_counts, dict) else {}
        self.action_stats = action_stats if isinstance(action_stats, dict) else {}
        self.pending_decisions = pending_decisions if isinstance(pending_decisions, list) else []
        policy_data = policy_data if isinstance(policy_data, dict) else {}
        self.strategic_policy = ExpectedSarsaLambdaPolicy(
            f"{country_name}:strategic", len(STRATEGIC_ACTIONS), policy_data.get("strategic"), max_states=3500
        )
        self.market_policy = ExpectedSarsaLambdaPolicy(
            f"{country_name}:market", len(MARKET_ACTIONS), policy_data.get("market"), max_states=1800
        )
        self.market_price_policy = ExpectedSarsaLambdaPolicy(
            f"{country_name}:market_price", len(MARKET_PRICE_ACTIONS), policy_data.get("market_price"), max_states=900
        )
        self.market_size_policy = ExpectedSarsaLambdaPolicy(
            f"{country_name}:market_size", len(MARKET_SIZE_ACTIONS), policy_data.get("market_size"), max_states=900
        )
        self.fiscal_policy = ExpectedSarsaLambdaPolicy(
            f"{country_name}:fiscal", len(FISCAL_ACTIONS), policy_data.get("fiscal"), max_states=200
        )
        self.alliance_policy = ExpectedSarsaLambdaPolicy(
            f"{country_name}:alliance", len(ALLIANCE_ACTIONS), policy_data.get("alliance"), max_states=1500
        )

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
        6惡名、7戰力趨勢、8世界局勢、9大洋流動性、10是否霸主。
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
        gold = max(0.0, float(country_data.get("gold", 0) or 0))

        # 所有資產先換回「基準大洋」再做人均分級，避免 MONEY_RATIO 放大後
        # 大洋一項獨占經濟狀態，使正常國家幾乎永遠被標成 RICH。
        monetary_wealth = (gold / max(1, policy_cost(MONEY_RATIO, country_data))
                           if MARKET_ECONOMY_ENABLED else 0.0)
        wealth_pc = (food + wood * 1.8 + metal * 3.2 + monetary_wealth) / pop
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
        gold_pc = gold / pop
        if not MARKET_ECONOMY_ENABLED:
            liquidity = "CURRENCY_OFF"
        elif gold_pc < policy_cost(1 * MONEY_RATIO, country_data):
            liquidity = "CASH_CRISIS"
        elif gold_pc < policy_cost(3 * MONEY_RATIO, country_data):
            liquidity = "CASH_LOW"
        elif gold_pc < policy_cost(8 * MONEY_RATIO, country_data):
            liquidity = "CASH_OK"
        else:
            liquidity = "CASH_RICH"
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
            liquidity,
            is_top,
        )

    def _get_strategic_state(self, country_data, total_world_power, max_power, alive_count):
        old = self._get_state_key(country_data, total_world_power, max_power, alive_count)
        power = {"VERY_WEAK": "WEAK", "WEAK": "WEAK", "NORMAL": "PEER", "STRONG": "STRONG", "SUPREME": "DOMINANT"}[old[0]]
        food = old[2]
        pop = max(1, int(country_data.get("pop_total", 1) or 1))
        soldiers = max(0, int(country_data.get("soldiers", 0) or 0))
        wood = max(0.0, float(country_data.get("wood", 0) or 0))
        metal = max(0.0, float(country_data.get("metal", 0) or 0))
        wood_ratio = wood / max(1.0, pop * BALANCE["WOOD_RESERVE_PER_POP"])
        metal_target = pop * BALANCE["METAL_RESERVE_PER_POP"] + soldiers * BALANCE["METAL_RESERVE_PER_SOLDIER"]
        material_ratio = min(wood_ratio, metal / max(1.0, metal_target))
        materials = "SHORT" if material_ratio < 0.6 else "OK" if material_ratio < 1.5 else "SURPLUS"
        obligations = max(1.0, soldiers * 0.2 + pop * 0.05)
        liquidity_turns = (
            max(0.0, float(country_data.get("gold", 0) or 0)) / max(1, policy_cost(MONEY_RATIO, country_data))
        ) / obligations
        liquidity = "CRISIS" if liquidity_turns < 3 else "OK" if liquidity_turns < 12 else "AMPLE"
        wars = len(country_data.get("current_wars", []) or [])
        attackers = len(country_data.get("recent_attackers", []) or [])
        if wars >= 2:
            war_pressure = "MULTI_FRONT"
        elif wars == 1:
            war_pressure = "WAR"
        elif attackers:
            war_pressure = "THREATENED"
        else:
            war_pressure = "PEACE"
        stability = float(country_data.get("political_stability", 75) or 75)
        exhaustion = float(country_data.get("war_exhaustion", 0) or 0)
        resilience_score = stability - exhaustion * 0.65
        resilience = "FRAGILE" if resilience_score < 30 else "NORMAL" if resilience_score < 70 else "STABLE"
        alliance_ratio = float(country_data.get("alliance_power_ratio", 0.0) or 0.0)
        diplomacy = "ISOLATED" if not country_data.get("current_alliance") else "ALLIED" if alliance_ratio < 0.20 else "STRONG_ALLIANCE"
        prewar_score = float(country_data.get("prewar_risk_score", 0) or 0)
        if prewar_score >= PREWAR_RISK_CRITICAL:
            prewar_risk = "CRITICAL"
        elif prewar_score >= PREWAR_RISK_HIGH:
            prewar_risk = "HIGH"
        elif prewar_score >= PREWAR_RISK_ALERT:
            prewar_risk = "ALERT"
        else:
            prewar_risk = "CALM"
        prewar_need = float(country_data.get("prewar_mobilization_need", 0) or 0)
        mobilization_need = "HIGH" if prewar_need >= 0.68 else "MEDIUM" if prewar_need >= 0.35 else "LOW"
        phase = str(country_data.get("season_phase", "EARLY") or "EARLY")
        gold = max(0, int(country_data.get("gold", 0) or 0))
        policy_floor = min(policy_cost(BIRTH_POLICY_GOLD_COST, country_data), policy_cost(PRODUCTION_POLICY_GOLD_COST, country_data))
        if gold < policy_floor:
            cash_power = "NO_POLICY_BUDGET"
        elif gold < policy_floor * 3:
            cash_power = "FUNDED"
        else:
            cash_power = "CAPITAL_RICH"
        rank = max(1, int(country_data.get("world_rank", 999) or 999))
        contender = "TOP3" if rank <= 3 else "TOP10" if rank <= 10 else "FIELD"
        existing_state = (
            power, food, materials, liquidity, war_pressure, resilience,
            diplomacy, prewar_risk, mobilization_need, old[8], phase, cash_power, contender,
        )
        # ===============V8.4.9 更新自主決策================
        # 七項分析腦只讀取現況，決策中樞只合入原有兩個風險欄位。
        # 不增加 State 維數或 Action 編號，舊戰略 Q-table 可繼續使用。
        # ===============V8.4.9 更新自主決策================
        
        report = NationalDecisionHub.analyze(
            country_data, total_world_power, alive_count, MONEY_RATIO
        )
        self.last_brain_report = report.as_dict()
        return strategic_state_256(NationalDecisionHub.strategic_state(existing_state, country_data, report), country_data)

    @staticmethod
    def _strategic_valid_actions(engine_valid_actions):
        valid = []
        engine_set = set(engine_valid_actions or [])
        for strategic_action, candidates in STRATEGIC_TO_ENGINE_ACTIONS.items():
            if any(action in engine_set for action in candidates):
                valid.append(strategic_action)
        return valid or [0, 1]

    def _resolve_engine_action(self, strategic_action, engine_valid_actions, country_data):
        candidates = [a for a in STRATEGIC_TO_ENGINE_ACTIONS[int(strategic_action)] if a in set(engine_valid_actions or [])]
        if not candidates:
            return 3 if 3 in engine_valid_actions else engine_valid_actions[0]
        if int(strategic_action) == 3:
            return 11 if (country_data.get("war_exhaustion", 0) > 45 or country_data.get("food", 0) < country_data.get("pop_total", 1) * 3) and 11 in candidates else candidates[0]
        if int(strategic_action) == 7:
            return 12 if country_data.get("food", 0) > country_data.get("pop_total", 1) * 8 and 12 in candidates else candidates[-1]
        return candidates[0]

    def describe_state(self, country_data, total_world_power, max_power, alive_count):
        s = self._get_state_key(country_data, total_world_power, max_power, alive_count)
        return (
            f"{s[0]}/{s[1]}/{s[2]}/{s[3]}/"
            f"{s[4]}/{s[5]}/{s[6]}/{s[7]}/{s[8]}/{s[9]}"
        )

    def choose_action(
        self,
        country_data,
        total_world_power,
        max_power,
        alive_count,
        valid_actions=None,
        bank=None,
        market=None,
    ):
        """
        V7 自主學習：
        - 不使用固定人格。
        - 不使用人格式 action weights。
        - 不用「和平/好戰/投機」預設偏好干預探索。
        - 探索時在所有有效行動中等機率嘗試。
        - 利用時只依目前 Q-Table 的最高 Q 值決策。

        Action Mask 仍保留，避免 AI 選擇客觀上無法執行的行動。
        State / Reward 仍保留，讓 AI 從戰力、經濟、糧食、威脅、
        惡名、世界局勢等實際結果自己學出策略。
        """
        engine_valid = [a for a in (valid_actions or range(self.action_size)) if 0 <= int(a) < self.action_size]
        # 受保護國可生產、築城、結盟與備戰，但不得躲在保護罩內主動開戰。
        if int(country_data.get("protection_remaining_years", 0) or 0) > 0:
            engine_valid = [a for a in engine_valid if a not in (0, 2, 4, 10)]
        if not engine_valid:
            engine_valid = [7]
        state = self._get_strategic_state(country_data, total_world_power, max_power, alive_count)
        strategic_valid = self._strategic_valid_actions(engine_valid)

        # 「保護準備」是全新的狀態，第一次遇到時給可被後續學習推翻的小幅先驗值。
        # 它不是強制動作：Q 值仍會依實際成敗更新；只是避免新國在脫保前 50 年
        # 面對全零 Q 值仍完全隨機，最後一年還跑去做無關緊要的事情。
        state_key = self.strategic_policy.state_key(state)
        if state and state[0] == "安全:保護準備" and int(self.strategic_policy.visit_counts.get(state_key, 0) or 0) == 0:
            q_values = self.strategic_policy._ensure(state_key)
            urgency = float(_clamp(country_data.get("survival_preparation_urgency", 0), 0, 1))
            soldier_ratio = max(0, int(country_data.get("soldiers", 0) or 0)) / max(1, int(country_data.get("pop_total", 1) or 1))
            fort = float(_clamp(country_data.get("fortification", 0), 0, 100))
            supply_years = max(0.0, float(country_data.get("war_supply_years", 0) or 0))
            priors = {
                0: 0.10 + urgency * 0.15,  # 基礎建設
                1: (0.20 + urgency * 0.35) if supply_years < SECURITY_TARGET_SUPPLY_YEARS else 0.08,
                2: (0.20 + urgency * 0.55) if soldier_ratio < SECURITY_TARGET_SOLDIER_RATIO else 0.06,
                3: (0.25 + urgency * 0.50) if fort < SECURITY_TARGET_FORTIFICATION else 0.08,
                4: (0.25 + urgency * 0.55) if not country_data.get("current_alliance") else 0.05,
                7: 0.10 + urgency * 0.20,
                5: -0.40,
                6: -0.30,
                8: -0.25,
                9: -0.35,
            }
            for strategic_idx, prior in priors.items():
                if strategic_idx in strategic_valid:
                    q_values[strategic_idx] = float(prior)

        # 風險由七個只讀分析腦提供給 State；Q 值與 Action Mask 決定動作。
        # 農夫／士兵比例、極端戰前風險不再越過 Q-learning 強制動員。
        strategic_action = self.strategic_policy.choose(state, strategic_valid)
        engine_action = self._resolve_engine_action(strategic_action, engine_valid, country_data)
        self._last_fiscal_state = None
        self._last_fiscal_action = None
        self._last_fiscal_cost = 0
        if strategic_action == 7 and bank is not None:
            reserved, _ = _market_order_reservations(market or {}, self.country_name) if MARKET_ECONOMY_ENABLED else (0, {})
            available = max(0, int(country_data.get("gold", 0) or 0) - reserved) if MARKET_ECONOMY_ENABLED else 0
            birth_cost = policy_cost(BIRTH_POLICY_GOLD_COST, bank)
            production_cost = policy_cost(PRODUCTION_POLICY_GOLD_COST, bank)
            infrastructure_cost = _infrastructure_investment_cost(country_data)
            fiscal_key = fiscal_state(
                country_data, bank, available,
                *(_market_target_stock(country_data, resource) for resource in MARKET_RESOURCES),
                birth_cost, production_cost,
            )
            if MARKET_ECONOMY_ENABLED:
                fiscal_valid = fiscal_valid_actions(country_data, engine_valid, available,
                                                     birth_cost, production_cost, infrastructure_cost)
            else:
                fiscal_valid = [0]
                if 12 in engine_valid:
                    fiscal_valid.append(1)
                if 13 in engine_valid:
                    fiscal_valid.append(2)
                if 3 in engine_valid:
                    fiscal_valid.append(3)
            fiscal_action = self.fiscal_policy.choose(fiscal_key, fiscal_valid)
            engine_action = {0: 7, 1: 12, 2: 13, 3: 3}[fiscal_action]
            self._last_fiscal_state = fiscal_key
            self._last_fiscal_action = fiscal_action
            self._last_fiscal_cost = (0 if not MARKET_ECONOMY_ENABLED else
                                      {0: 0, 1: birth_cost, 2: production_cost,
                                       3: infrastructure_cost[0]}[fiscal_action])

        self._last_strategic_state = state
        self._last_strategic_action = strategic_action
        self._last_state_str = self.strategic_policy.state_key(state)
        self.decision_count = self.strategic_policy.decision_count

        # engine_action = 0  # 動作測試

        return engine_action


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
        """V8_4 潛勢差分獎勵：量綱正規化，不再每回合固定獎勵存活/成功。"""
        if not after_data.get("is_alive", True):
            return -10.0

        def ratio_change(before, after, floor=1.0):
            before = max(float(floor), float(before or 0))
            return (float(after or 0) - before) / before

        def asset_value(data):
            return (
                (float(data.get("gold", 0) or 0) if MARKET_ECONOMY_ENABLED else 0.0)
                + float(data.get("food", 0) or 0) * max(0.01, float(data.get("market_price_food", 1.0) or 1.0))
                + float(data.get("wood", 0) or 0) * max(0.01, float(data.get("market_price_wood", 1.8) or 1.8))
                + float(data.get("metal", 0) or 0) * max(0.01, float(data.get("market_price_metal", 3.2) or 3.2))
            )

        reward = 0.0
        reward += _clamp(ratio_change(before_data.get("power"), after_data.get("power")) * 5.0, -2.0, 2.0)
        reward += _clamp(ratio_change(before_data.get("pop_total"), after_data.get("pop_total")) * 4.0, -1.5, 1.5)
        reward += _clamp(ratio_change(asset_value(before_data), asset_value(after_data), 100.0) * 3.0, -1.5, 1.5)
        before_runway = float(before_data.get("food", 0) or 0) / max(1.0, float(before_data.get("pop_total", 1) or 1))
        after_runway = float(after_data.get("food", 0) or 0) / max(1.0, float(after_data.get("pop_total", 1) or 1))
        reward += _clamp((after_runway - before_runway) * 0.20, -1.0, 1.0)
        reward += _clamp((float(after_data.get("political_stability", 75) or 75) - float(before_data.get("political_stability", 75) or 75)) / 20.0, -0.6, 0.6)
        reward += _clamp((float(before_data.get("war_exhaustion", 0) or 0) - float(after_data.get("war_exhaustion", 0) or 0)) / 25.0, -0.6, 0.6)
        annex_gain = max(0, int(after_data.get("annexed_count", 0) or 0) - int(before_data.get("annexed_count", 0) or 0))
        reward += min(4.0, annex_gain * 4.0)
        if action == 2:
            # 圍剿成功成立需多國響應，給予高於一般行動、但不壓過長期成長的獎勵。
            reward += 2.5 if action_success else -0.15

        # 安全態勢塑形：只獎勵實際降低風險與撐過脫保里程碑，不因單純受保護而加分。
        before_risk = float(before_data.get("security_risk_score", after_data.get("security_risk_score", 0)) or 0)
        after_risk = float(after_data.get("security_risk_score", before_risk) or before_risk)
        reward += _clamp((before_risk - after_risk) / 25.0, -0.8, 0.8)
        urgency = float(after_data.get("survival_preparation_urgency", 0) or 0)
        if int(after_data.get("protection_remaining_years", 0) or 0) > 0 and urgency > 0:
            if action_success and action in (1, 3, 5, 6, 7, 12, 13, 15):
                reward += 0.15 + urgency * 0.35
            elif action in (0, 2, 4, 10):
                reward -= 0.20 + urgency * 0.30
        reward += float(after_data.get("survival_milestone_reward_pending", 0) or 0)
        if not action_success:
            reward -= 0.10
        return float(_clamp(reward, -10.0, 10.0))

        # 以下保留 V8_3 舊獎勵程式作為對照，V8_4 不會執行。
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
                max(0.0, float(d.get("food", 0) or 0)) * max(0.01, float(d.get("market_price_food", 1.0) or 1.0))
                + max(0.0, float(d.get("wood", 0) or 0)) * max(0.01, float(d.get("market_price_wood", 1.8) or 1.8))
                + max(0.0, float(d.get("metal", 0) or 0)) * max(0.01, float(d.get("market_price_metal", 3.2) or 3.2))
                + (max(0.0, float(d.get("gold", 0) or 0)) if MARKET_ECONOMY_ENABLED else 0.0)
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

        # 6) 有效執行 vs 空轉。宣戰成立本身不再重賞，主要分數留待戰果結算。
        if action == 0:
            reward += 0.5 if action_success else -4.0
        else:
            reward += 3.0 if action_success else -4.0

        pwr, econ, food, military, alliance, threat, infamy, trend, world, liquidity, is_top = before_state

        # 7) Action-specific 情境合理化
        if action == 0:  # 全面戰爭
            if pwr == "VERY_WEAK":
                reward -= 14.0
            if food in ("FAMINE", "LOW"):
                reward -= 12.0
            if action_success and int(before_data.get("current_war_count", 0) or 0) >= 1:
                reward -= 4.0

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

        elif action == 3:  # 基礎建設投資
            reward += min(12.0, max(0.0, action_value) * 2.0) if action_success else -3.0
            # 資金危機時仍硬做長期投資並不合理。
            if econ == "CRISIS":
                reward -= 5.0
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

        elif action == 7:  # 產業配置
            reward += 5.0 if action_success else -2.0
            if food in ("FAMINE", "LOW") and after_data.get("industry_focus") == "FOOD":
                reward += 7.0

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

        elif action == 12:  # 鼓勵生育
            reward += 6.0 if action_success else -2.0
            if liquidity == "CASH_CRISIS":
                reward -= 5.0
            if food in ("SAFE", "SURPLUS"):
                reward += 3.0

        elif action == 13:  # 增產補貼
            reward += 6.0 if action_success else -2.0
            if econ in ("CRISIS", "POOR"):
                reward += 4.0
            if liquidity == "CASH_CRISIS":
                reward -= 4.0

        elif action == 14:  # 外交金援
            reward += 5.0 if action_success else -2.0
            if infamy in ("TARNISHED", "NOTORIOUS"):
                reward += 3.0

        elif action == 15:  # 聯盟援助
            reward += 7.0 if action_success else -2.0
            if threat in ("ALERT", "BESIEGED"):
                reward -= 2.0

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
        if after_state[10]:
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
        next_valid_actions=None,
        action_success=None,
    ):
        """V8_4：StrategicPolicy 使用 Expected SARSA(λ) 更新。"""
        state = getattr(
            self,
            "_last_strategic_state",
            self._get_strategic_state(country_data, total_world_power, max_power, alive_count),
        )
        strategic_action = getattr(self, "_last_strategic_action", 0)
        next_state = self._get_strategic_state(next_country_data, total_world_power, max_power, alive_count)
        next_strategic_valid = self._strategic_valid_actions(next_valid_actions or range(self.action_size))
        delta = self.strategic_policy.learn(
            state,
            strategic_action,
            float(_clamp(reward / 10.0, -10.0, 10.0)),
            next_state,
            next_strategic_valid,
            success=action_success,
        )
        self.q_table = self.strategic_policy.q_table
        self.visit_counts = self.strategic_policy.visit_counts
        self.action_stats = self.strategic_policy.action_stats
        return delta

    def policy_payload(self):
        return {
            "strategic": self.strategic_policy.to_dict(),
            "market": self.market_policy.to_dict(),
            "market_price": self.market_price_policy.to_dict(),
            "market_size": self.market_size_policy.to_dict(),
            "fiscal": self.fiscal_policy.to_dict(),
            "alliance": self.alliance_policy.to_dict(),
        }

    def inferred_personality(self):
        """只從戰略 Q 值反推已學成的風格，不反過來干預決策。

        V8_4_6 不再把從未嘗試、Q 值剛好為 0 的動作當成第二人格；
        同時改用各 State 內的相對 Q 優勢，避免不同 State 難度把總平均稀釋。
        """
        labels = {
            0: "經濟建設型", 1: "農業安全型", 2: "軍備動員型",
            3: "防禦休養型", 4: "外交聯盟型", 5: "征服擴張型",
            6: "襲擾施壓型", 7: "財政人口型", 8: "反霸權圍剿型",
            9: "背叛機會型",
            10: "聲望修復型",
        }
        totals = [0.0] * len(STRATEGIC_ACTIONS)
        weights = [0.0] * len(STRATEGIC_ACTIONS)
        minimum_samples = max(
            3,
            int(self.strategic_policy.decision_count * 0.008),
        )
        for state_key, values in self.strategic_policy.q_table.items():
            visits = max(1, int(self.strategic_policy.visit_counts.get(state_key, 1) or 1))
            weight = math.sqrt(visits)
            usable = [float(v) for v in values[:len(totals)]]
            state_mean = sum(usable) / max(1, len(usable))
            for index, value in enumerate(values[:len(totals)]):
                totals[index] += (float(value) - state_mean) * weight
                weights[index] += weight
        averages = []
        for index in range(len(totals)):
            samples = int(
                self.strategic_policy.action_stats.get(str(index), {}).get("count", 0)
                or 0
            )
            if samples < minimum_samples or not weights[index]:
                averages.append(float("-inf"))
            else:
                averages.append(totals[index] / weights[index])
        if not any(weights) or self.strategic_policy.decision_count < 12:
            return "尚在形成中（Q值樣本不足）"
        order = sorted(range(len(averages)), key=lambda i: averages[i], reverse=True)
        first, second = order[0], order[1]
        if not math.isfinite(averages[first]):
            return "尚在形成中（Q值樣本不足）"
        finite_scores = [score for score in averages if math.isfinite(score)]
        spread = max(finite_scores) - min(finite_scores) if len(finite_scores) >= 2 else 0.0
        gap = (
            averages[first] - averages[second]
            if math.isfinite(averages[second])
            else float("inf")
        )
        # 主型始終明確標示；只有 Q 值真的非常接近才附註次傾向。
        if math.isfinite(averages[second]) and gap <= max(0.008, spread * 0.10):
            return f"{labels[first]}（次傾向：{labels[second]}）"
        return labels[first]

    def apply_competition_reward(self, q_reward):
        """把排名／冠軍訊號追溯到最近一次戰略決策。

        Expected SARSA(λ) 現有的資格跡會再將終局訊號傳給近期決策，
        因此不需要預設任何固定人格。
        """
        state_key = str(
            getattr(self, "_last_state_str", "")
            or self.strategic_policy.last_decision_state
            or ""
        )
        action = getattr(
            self,
            "_last_strategic_action",
            self.strategic_policy.last_decision_action,
        )
        if not state_key or action is None:
            return False
        self.strategic_policy.apply_event_reward(
            state_key,
            int(action),
            float(_clamp(q_reward, -8.0, 8.0)),
        )
        self.q_table = self.strategic_policy.q_table
        self.visit_counts = self.strategic_policy.visit_counts
        self.action_stats = self.strategic_policy.action_stats
        return True

    def decay_political_memory(self, kind):
        retention = {
            "正統交接": (0.97, 0.99, 0.98),
            "宮廷政變": (0.75, 0.90, 0.72),
            "軍事政變": (0.62, 0.85, 0.60),
            "革命": (0.50, 0.78, 0.48),
            "亡國重建": (0.28, 0.65, 0.25),
        }.get(str(kind), (0.85, 0.92, 0.82))
        self.strategic_policy.decay_memory(retention[0])
        self.market_policy.decay_memory(retention[1])
        self.market_price_policy.decay_memory(retention[1])
        self.market_size_policy.decay_memory(retention[1])
        self.fiscal_policy.decay_memory(retention[1])
        self.alliance_policy.decay_memory(retention[2])

    def schedule_delayed_evaluation(self, state_data, action, turn_counter, action_success):
        fiscal_action = getattr(self, '_last_fiscal_action', None)
        if not action_success or action not in (0, 1, 3, 12, 13, 14, 15):
            return
        horizon = {0: 8, 1: 10, 3: 8, 12: BIRTH_POLICY_DURATION,
                   13: PRODUCTION_POLICY_DURATION, 14: 5, 15: 5}[action]
        self.pending_decisions.append({
            "state": getattr(self, "_last_state_str", str(tuple())),
            "action": int(getattr(self, "_last_strategic_action", 0)),
            "engine_action": int(action),
            "fiscal_state": (self.fiscal_policy.state_key(self._last_fiscal_state)
                             if fiscal_action in (1, 2, 3) else None),
            "fiscal_action": fiscal_action,
            "fiscal_cost": int(self._last_fiscal_cost),
            "fiscal_denomination": int(state_data.get('currency_denomination', 1) or 1),
            "due_turn": int(turn_counter) + horizon,
            "baseline": {
                "alive": bool(state_data.get("is_alive", True)),
                "power": max(0, int(state_data.get("power", 0) or 0)),
                "pop": max(0, int(state_data.get("pop_total", 0) or 0)),
                "pop_total": max(0, int(state_data.get("pop_total", 0) or 0)),
                "food": max(0, int(state_data.get("food", 0) or 0)),
                "wood": max(0, int(state_data.get("wood", 0) or 0)),
                "metal": max(0, int(state_data.get("metal", 0) or 0)),
                "infrastructure": max(0, int(state_data.get("infrastructure", 0) or 0)),
                "assets": sum(max(0, int(state_data.get(k, 0) or 0)) for k in ("food", "wood", "metal", "gold")),
                "wars_won": max(0, int(state_data.get("wars_won", 0) or 0)),
                "wars_lost": max(0, int(state_data.get("wars_lost", 0) or 0)),
                "capital_captures": max(0, int(state_data.get("capital_captures", 0) or 0)),
                "infamy": max(0, int(state_data.get("infamy", 0) or 0)),
                "alliance": str(state_data.get("current_alliance", "") or ""),
                "war_win_chance": float(state_data.get("last_war_win_chance", 0.5) or 0.5),
            },
        })
        self.pending_decisions = self.pending_decisions[-20:]

    def settle_delayed_evaluations(self, current_data, turn_counter):
        remaining = []
        settled = []
        for item in self.pending_decisions:
            if int(item.get("due_turn", 0) or 0) > int(turn_counter):
                remaining.append(item)
                continue
            base = item.get("baseline", {}) or {}
            action = int(item.get("action", 0) or 0)
            raw_engine_action = item.get("engine_action", 3)
            engine_action = int(3 if raw_engine_action is None else raw_engine_action)
            reward = 0.0
            if not current_data.get("is_alive", True):
                reward -= 35.0
            pop0 = max(1, int(base.get("pop", 1) or 1))
            power0 = max(1, int(base.get("power", 1) or 1))
            assets0 = max(1, int(base.get("assets", 1) or 1))
            reward += _clamp((int(current_data.get("pop_total", 0) or 0) - pop0) / pop0 * 18.0, -12.0, 12.0)
            reward += _clamp((int(current_data.get("power", 0) or 0) - power0) / power0 * 12.0, -10.0, 10.0)
            assets_now = sum(max(0, int(current_data.get(k, 0) or 0)) for k in ("food", "wood", "metal", "gold"))
            reward += _clamp((assets_now - assets0) / assets0 * 10.0, -8.0, 8.0)
            if engine_action == 0:
                wins = max(0, int(current_data.get("wars_won", 0) or 0) - int(base.get("wars_won", 0) or 0))
                losses = max(0, int(current_data.get("wars_lost", 0) or 0) - int(base.get("wars_lost", 0) or 0))
                reward += 12.0 * wins
                reward -= 14.0 * losses
                reward += 20.0 * max(0, int(current_data.get("capital_captures", 0) or 0) - int(base.get("capital_captures", 0) or 0))
                if wins:
                    estimated = float(base.get("war_win_chance", 0.5) or 0.5)
                    reward += wins * max(0.0, 0.50 - estimated) * 24.0
            if engine_action == 1:
                # 十年後仍在聯盟，才證明當初結盟不是一次性表面成果。
                if current_data.get("current_alliance"):
                    reward += 8.0
                    reward += 4.0 * max(
                        0,
                        int(current_data.get("wars_won", 0) or 0)
                        - int(base.get("wars_won", 0) or 0),
                    )
                else:
                    reward -= 6.0
            if engine_action == 14:
                reward += _clamp((int(base.get("infamy", 0) or 0) - int(current_data.get("infamy", 0) or 0)) * 0.5, 0.0, 8.0)
            reward = float(_clamp(reward, -40.0, 40.0))
            self.strategic_policy.apply_event_reward(
                str(item.get("state", "")), action, _clamp(reward / 10.0, -4.0, 4.0)
            )
            if item.get('fiscal_state') is not None and item.get('fiscal_action') in (1, 2, 3):
                fiscal_reward = delayed_fiscal_reward(
                    int(item['fiscal_action']), base, current_data,
                    int(item.get('fiscal_cost', 0) or 0),
                    int(item.get('fiscal_denomination', 1) or 1),
                )
                self.fiscal_policy.apply_event_reward(str(item['fiscal_state']),
                                                      int(item['fiscal_action']), fiscal_reward)
            settled.append((action, reward))
        self.pending_decisions = remaining
        return settled


# ====================================================
# 【獨立大腦 存檔與載入管理】
# ====================================================
def save_all_agents(rl_agents, file_path=None):
    """將所有國家的 RL Q-Tables 保存至 JSON 檔案"""
    file_path = file_path or save_path("rl_agents_q_tables.json")
    data = {}
    for name, agent in rl_agents.items():
        data[name] = {
            "rl_version": RL_VERSION,
            "action_size": RL_ACTION_SIZE,
            "policy": "SELF_LEARNING",
            "decision_count": agent.decision_count,
            "q_table": agent.q_table,
            "visit_counts": agent.visit_counts,
            "action_stats": agent.action_stats,
            "pending_decisions": agent.pending_decisions,
            "algorithm": RL_ALGORITHM,
            "policies": agent.policy_payload(),
        }
    try:
        _atomic_write_json(file_path, data, compact=True)
        # 同步輸出可讀的戰略 Q 表；原始 JSON 仍可供遊戲無損載入。
        readable_path = save_path("rl_strategic_q_readable.txt")
        _atomic_write_text(readable_path, readable_q_text(rl_agents, STRATEGIC_ACTIONS))
        _atomic_write_text(save_path('rl_fiscal_q_readable.txt'), fiscal_q_report(rl_agents))
    except Exception as e:
        print(f"⚠️ [RL] 所有國家 Q-Tables 保存失敗: {e}")


def load_all_agents(country_list, file_path=None):
    """從 JSON 檔案載入所有國家的獨立 RL 大腦，若無則初始化新大腦"""
    file_path = file_path or save_path("rl_agents_q_tables.json")
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
                versions = {int(v.get("rl_version", 0) or 0) for v in all_agent_data.values() if isinstance(v, dict)}
                if versions and versions != {RL_VERSION}:
                    migration_backup = file_path + f".pre_v{RL_VERSION}_backup"
                    if not os.path.exists(migration_backup):
                        shutil.copy2(file_path, migration_backup)
                    print(
                        f"🧬 [RL Migration] 舊版 {sorted(versions)} Q-Table 已封存為 {migration_backup}；"
                        "世界存檔保留，V8_4 三層策略從乾淨表格學習。"
                    )

        except Exception as e:
            print(
                f"⚠️ [RL] 載入獨立大腦失敗，將建立全新大腦: {e}"
            )

    agents = {}
    for name in country_list:
        a_info = all_agent_data.get(name, {})

        compatible = (
            a_info.get("rl_version") == RL_VERSION
            and a_info.get("action_size") == RL_ACTION_SIZE
        )

        if compatible:
            q_tab = a_info.get("q_table", {})
            decision_count = int(
                a_info.get("decision_count", 0)
                or 0
            )
            visit_counts = a_info.get("visit_counts", {})
            action_stats = a_info.get("action_stats", {})
            pending_decisions = a_info.get("pending_decisions", [])
            policy_data = a_info.get("policies", {})
        else:
            # V7 自主學習版：
            # 舊人格時代的 Q-table 與探索歷史不直接沿用，
            # 從乾淨的大腦重新學習；世界存檔本身不受影響。
            q_tab = {}
            decision_count = 0
            visit_counts = {}
            action_stats = {}
            pending_decisions = []
            # 只重置戰略層：市場價格／掛單量／聯盟 Q 值與舊動作統計保留。
            previous_policies = a_info.get("policies", {}) if isinstance(a_info, dict) else {}
            policy_data = {k: v for k, v in previous_policies.items()
                           if k in ("market", "market_price", "market_size", "alliance")}
            if policy_data:
                print(f"🧠 [戰略狀態更新] {name}：戰略 Q 值重新學習；市場與聯盟子策略保留。")

        agents[name] = CountryRLAgent(
            country_name=name,
            q_table=q_tab,
            decision_count=decision_count,
            visit_counts=visit_counts,
            action_stats=action_stats,
            pending_decisions=pending_decisions,
            policy_data=policy_data,
        )

    return agents


def current_strategic_state(country_key, countries):
    """依 UI 目前載入的世界快照，以 AI 相同公式取得當前戰略狀態；不學習。"""
    alive = [data for data in countries.values() if data.get('is_alive', True)]
    if country_key not in countries or not alive:
        return None
    total = sum(max(0, float(data.get('power', 0) or 0)) for data in alive)
    strongest = max(max(0, float(data.get('power', 0) or 0)) for data in alive)
    preview = CountryRLAgent(country_name=country_key)
    return preview._get_strategic_state(countries[country_key], total, strongest, len(alive))


def _gini(values):
    values = sorted(max(0.0, float(value or 0)) for value in values)
    total = sum(values)
    if not values or total <= 0:
        return 0.0
    n = len(values)
    return sum((2 * index - n - 1) * value for index, value in enumerate(values, 1)) / (n * total)


def _write_rl_monitoring(turn_counter, countries, agents, world_market, world_bank=None):
    """每 100 回合留下一列健康指標，便於比較固定 Seed 實驗。"""
    policies = [policy for agent in agents.values() for policy in (
        agent.strategic_policy, agent.market_policy, agent.alliance_policy
    )]
    strategic_counts = {
        STRATEGIC_ACTIONS[index]: sum(
            int(agent.strategic_policy.action_stats.get(str(index), {}).get("count", 0) or 0)
            for agent in agents.values()
        ) for index in STRATEGIC_ACTIONS
    }
    record = {
        "turn": int(turn_counter),
        "alive": sum(1 for data in countries.values() if data.get("is_alive", True)),
        "power_gini": round(_gini(data.get("power", 0) for data in countries.values() if data.get("is_alive", True)), 6),
        "wealth_gini": round(_gini(data.get("gold", 0) for data in countries.values() if data.get("is_alive", True)), 6),
        "q_states": sum(len(policy.q_table) for policy in policies),
        "td_error_mean": round(sum(policy.td_error_ema for policy in policies) / max(1, len(policies)), 6),
        "epsilon_mean": round(sum(policy.effective_epsilon() for policy in policies) / max(1, len(policies)), 6),
        "food_price": round(float(world_market.get("stats", {}).get("food", {}).get("last_price", 0) or 0), 4),
        "wood_price": round(float(world_market.get("stats", {}).get("wood", {}).get("last_price", 0) or 0), 4),
        "metal_price": round(float(world_market.get("stats", {}).get("metal", {}).get("last_price", 0) or 0), 4),
        "market_price_index": world_market.get("price_monitor", {}).get("latest", {}).get("index"),
        "market_price_index_valid": world_market.get("price_monitor", {}).get("latest", {}).get("reliable", False),
        "market_10turn_volume": world_market.get("price_monitor", {}).get("latest", {}).get("volume", 0),
        "market_diagnosis": world_market.get("price_monitor", {}).get("latest", {}).get("diagnosis", "尚無樣本"),
        "market_floor_cash_stress": world_market.get("price_monitor", {}).get("latest", {}).get("floor_cash_stress", False),
        "market_floor_pressure_resources": world_market.get("price_monitor", {}).get("latest", {}).get("floor_pressure_resources", []),
        "market_cash_stressed_fraction": world_market.get("price_monitor", {}).get("latest", {}).get("cash_stressed", 0),
        "bank_treasury_share": round(max(0, int((world_bank or {}).get('treasury', 0) or 0)) /
                                     max(1, int((world_bank or {}).get('issued_total', 0) or 0)), 6),
        "bank_recycled_total": int((world_bank or {}).get('fiscal_recycle_total', 0) or 0),
        "bank_issued_total": int((world_bank or {}).get('issued_total', 0) or 0),
        "strategy_diversity": sum(1 for count in strategic_counts.values() if count > 0),
        "strategic_actions": strategic_counts,
    }
    _atomic_write_json(save_path("rl_monitor_latest.json"), record, compact=False)
    csv_path = save_path("rl_monitor_history.csv")
    flat = {key: value for key, value in record.items() if key not in
            ("strategic_actions", "market_price_index", "market_price_index_valid",
             "market_10turn_volume", "market_diagnosis", "market_floor_cash_stress",
             "market_floor_pressure_resources", "market_cash_stressed_fraction",
             "bank_treasury_share", "bank_recycled_total", "bank_issued_total")}
    flat["strategic_actions"] = json.dumps(strategic_counts, ensure_ascii=False, separators=(",", ":"))
    write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat))
        if write_header:
            writer.writeheader()
        writer.writerow(flat)
    # 獨立新表，保留舊版 rl_monitor_history.csv 的欄位格式供續跑讀取。
    liquidity_path = save_path('market_liquidity_history.csv')
    liquidity = {
        'turn': int(turn_counter),
        'bank_treasury_share': record['bank_treasury_share'],
        'bank_treasury': int((world_bank or {}).get('treasury', 0) or 0),
        'issued_total': record['bank_issued_total'],
        'recycled_total': record['bank_recycled_total'],
        'policy_collected_total': int((world_bank or {}).get('policy_collected', 0) or 0),
        'fees_collected_total': int((world_bank or {}).get('transaction_fees_collected', 0) or 0),
        'cash_stressed_fraction': record['market_cash_stressed_fraction'],
        'floor_cash_stress': record['market_floor_cash_stress'],
        'floor_resources': ','.join(record['market_floor_pressure_resources']),
        'food_buy_qty': int(world_market['stats']['food'].get('buy_qty', 0) or 0),
        'food_sell_qty': int(world_market['stats']['food'].get('sell_qty', 0) or 0),
        'food_price': record['food_price'],
        'market_10turn_volume': record['market_10turn_volume'],
    }
    with open(liquidity_path, 'a', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(liquidity))
        if stream.tell() == 0:
            writer.writeheader()
        writer.writerow(liquidity)


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
    "SECOND_FRONT_INITIAL_WOOD_MULTIPLIER": 1.00,

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
    "SURRENDER_FOOD_RATE": 0.8,
    "SURRENDER_WOOD_RATE": 0.8,
    "SURRENDER_METAL_RATE": 0.8,
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



def _war_add_troop_contribution(
    war,
    field_name,
    member_values,
):
    """
    累積各國在同一場正式戰爭中的出兵貢獻。

    member_values:
        {country_key: 本次實際/有效投入兵力}

    用「累積投入兵力」而不是最後剩餘戰力，
    避免打到最後傷亡較大的盟友反而完全分不到戰後人口。
    """
    contribution = war.setdefault(field_name, {})
    if not isinstance(contribution, dict):
        contribution = {}
        war[field_name] = contribution

    for member, value in (member_values or {}).items():
        value = max(0, int(value or 0))
        if value <= 0:
            continue
        contribution[member] = (
            max(0, int(contribution.get(member, 0) or 0))
            + value
        )

    return contribution


def _war_effective_member_forces(
    members,
    countries,
    war_id,
    active_wars,
):
    """回傳此戰線各國當回合真正可投入的有效兵力。"""
    result = {}
    for member in _war_live_members(members, countries):
        soldiers = max(
            0,
            int(countries[member].get("soldiers", 0) or 0),
        )
        multiplier = _war_front_multiplier(
            member,
            war_id,
            active_wars,
        )
        result[member] = max(
            0,
            int(soldiers * multiplier),
        )
    return result


def _split_integer_by_weights(
    amount,
    members,
    weights,
):
    """
    將整數 amount 依權重精確分配，總和一定等於 amount。

    採最大餘數法：
    例如 100 人、權重 60:30:10 -> 60/30/10。
    若權重無效或全部為 0，才退回平均分配。
    """
    amount = max(0, int(amount or 0))
    unique_members = list(dict.fromkeys(members or []))
    if not unique_members:
        return {}

    clean_weights = {
        member: max(
            0,
            int((weights or {}).get(member, 0) or 0),
        )
        for member in unique_members
    }

    total_weight = sum(clean_weights.values())
    if total_weight <= 0:
        clean_weights = {
            member: 1
            for member in unique_members
        }
        total_weight = len(unique_members)

    shares = {
        member: 0
        for member in unique_members
    }

    fractional = []
    allocated = 0

    for order, member in enumerate(unique_members):
        numerator = amount * clean_weights[member]
        base = numerator // total_weight
        remainder = numerator % total_weight

        shares[member] = int(base)
        allocated += int(base)

        fractional.append(
            (
                int(remainder),
                clean_weights[member],
                -order,
                member,
            )
        )

    remaining = amount - allocated

    # 餘數大的優先補 1；同餘數時出兵權重大的優先。
    fractional.sort(reverse=True)

    idx = 0
    while remaining > 0 and fractional:
        member = fractional[idx % len(fractional)][3]
        shares[member] += 1
        remaining -= 1
        idx += 1

    return shares


def _war_capture_contribution_weights(
    attacker_members,
    countries,
    contribution_weights=None,
):
    """
    國都陷落時取得戰後分配權重。

    優先順序：
    1. 本戰爭已累積的實際出兵貢獻。
    2. 舊存檔沒有貢獻欄位時，以目前存活士兵數暫代。
    3. 全部皆為 0 時才平均分配。
    """
    winners = _war_live_members(
        attacker_members,
        countries,
    )

    weights = {
        member: max(
            0,
            int(
                (contribution_weights or {}).get(
                    member,
                    0,
                )
                or 0
            ),
        )
        for member in winners
    }

    if sum(weights.values()) <= 0:
        weights = {
            member: max(
                0,
                int(
                    countries[member].get(
                        "soldiers",
                        0,
                    )
                    or 0
                ),
            )
            for member in winners
        }

    if sum(weights.values()) <= 0:
        weights = {
            member: 1
            for member in winners
        }

    return weights


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
    """
    戰敗方正式求和時支付「戰敗金 + 資源賠款」。
    賠款依勝方實際出兵比例分配；不憑空創造資源。
    """
    winners = _war_live_members(winner_members, countries)
    losers = _war_live_members(loser_members, countries)
    if not winners or not losers:
        return {"food": 0, "wood": 0, "metal": 0, "gold": 0}

    paid = {"food": 0, "wood": 0, "metal": 0, "gold": 0}
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

    # 戰敗金：敗方現有大洋的 12%，至少 1；避免打贏卻完全沒有戰果。
    if MARKET_ECONOMY_ENABLED:
        for m in losers:
            stock = max(0, int(countries[m].get("gold", 0) or 0))
            take = min(stock, max(0, int(stock * 0.12)))
            countries[m]["gold"] = stock - take
            paid["gold"] += take

    weights = [max(1, int(countries[m].get("soldiers", 0) or 0)) for m in winners]
    total_weight = max(1, sum(weights))
    for res in paid:
        remaining = paid[res]
        for idx, (m, weight) in enumerate(zip(winners, weights)):
            gain = remaining if idx == len(winners) - 1 else min(remaining, int(paid[res] * weight / total_weight))
            countries[m][res] = max(0, int(countries[m].get(res, 0) or 0)) + gain
            remaining -= gain
    return paid


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
    contribution_weights=None,
    attacker_name="",
):
    """
    國都陷落後：
    - 戰亂死亡人口照舊扣除。
    - 生還農民按進攻聯盟各國「累積出兵貢獻比例」分配。
    - 不再全部塞給最後戰力最大的國家。
    - 戰利資源/部分房屋仍由主要攻城國接收，避免一次改動太多既有平衡。
    """
    if (
        loser_key not in countries
        or not countries[loser_key].get("is_alive", True)
    ):
        return None

    winners = _war_live_members(
        attacker_members,
        countries,
    )
    if not winners:
        return None

    loser = countries[loser_key]

    weights = _war_capture_contribution_weights(
        winners,
        countries,
        contribution_weights,
    )

    old_pop = max(
        1,
        int(loser.get("pop_total", 1) or 1),
    )

    deaths = max(
        1,
        min(
            old_pop - 1,
            int(
                round(
                    old_pop
                    * random.uniform(
                        WARSTATE["CAPITAL_DEATH_MIN"],
                        WARSTATE["CAPITAL_DEATH_MAX"],
                    )
                )
            ),
        ),
    )

    survivors = max(0, old_pop - deaths)

    note_population_loss(
        loser_key,
        deaths,
        "國都陷落：戰亂死亡",
    )

    # --------------------------------------------------------
    # 生還農民依「累積出兵貢獻」分給所有實際參戰的勝方國家。
    # --------------------------------------------------------
    survivor_shares = _split_integer_by_weights(
        survivors,
        winners,
        weights,
    )

    for member in winners:
        gain = max(
            0,
            int(survivor_shares.get(member, 0) or 0),
        )
        if gain <= 0:
            continue

        countries[member]["pop_total"] = (
            max(
                1,
                int(
                    countries[member].get(
                        "pop_total",
                        1,
                    )
                    or 1
                ),
            )
            + gain
        )

        countries[member]["farmers"] = (
            max(
                0,
                int(
                    countries[member].get(
                        "farmers",
                        0,
                    )
                    or 0
                ),
            )
            + gain
        )

        enforce_farmer_majority(
            countries[member]
        )
        countries[member]["power"] = (
            calculate_rts_power(
                countries[member]
            )
        )

    # 「主要攻城國」改依本戰累積出兵貢獻決定，而不是直接看現有總戰力。
    primary_key = max(
        winners,
        key=lambda member: (
            int(weights.get(member, 0) or 0),
            int(survivor_shares.get(member, 0) or 0),
            int(countries[member].get("soldiers", 0) or 0),
            int(countries[member].get("power", 0) or 0),
        ),
    )
    primary = countries[primary_key]

    # 原本的戰利品/部分房屋機制保留，由主要攻城國接收。
    primary["houses"] = (
        max(
            1,
            int(primary.get("houses", 1) or 1),
        )
        + int(
            max(0, loser.get("houses", 0))
            * 0.55
        )
    )

    captured = {}
    for res in ("food", "wood", "metal"):
        gain = int(
            max(0, loser.get(res, 0))
            * 0.35
        )
        primary[res] = (
            max(0, primary.get(res, 0))
            + gain
        )
        captured[res] = gain

    # 大洋是共同貨幣，不在滅國時憑空消失：全部由主要攻城國接收。
    captured_gold = max(0, int(loser.get("gold", 0) or 0)) if MARKET_ECONOMY_ENABLED else 0
    if MARKET_ECONOMY_ENABLED:
        primary["gold"] = max(0, int(primary.get("gold", 0) or 0)) + captured_gold
    captured["gold"] = captured_gold

    primary["annexed_count"] = (
        int(
            primary.get(
                "annexed_count",
                0,
            )
            or 0
        )
        + 1
    )
    primary["capital_captures"] = (
        int(
            primary.get(
                "capital_captures",
                0,
            )
            or 0
        )
        + 1
    )

    enforce_farmer_majority(primary)
    primary["power"] = calculate_rts_power(
        primary
    )

    loser_name = loser.get(
        "display_name",
        loser_key,
    )
    primary_name = primary.get(
        "display_name",
        primary_key,
    )

    positive_receivers = [
        member
        for member in winners
        if int(survivor_shares.get(member, 0) or 0) > 0
    ]

    # 多國聯合作戰時，編年史「兇手」優先記錄戰爭陣營/聯盟名稱。
    # 單國戰爭則維持顯示主要攻城國國名。
    if (
        len(positive_receivers) > 1
        and str(attacker_name or "").strip()
    ):
        ended_by = str(attacker_name).strip()
    else:
        ended_by = primary_name

    _chronicle_close_current(
        loser_key,
        loser,
        turn_counter,
        "滅國",
        ended_by=ended_by,
    )

    distribution_parts = []
    total_weight = max(
        1,
        sum(
            max(0, int(weights.get(m, 0) or 0))
            for m in winners
        ),
    )

    for member in winners:
        gain = int(
            survivor_shares.get(member, 0)
            or 0
        )
        if gain <= 0:
            continue

        weight = max(
            0,
            int(weights.get(member, 0) or 0),
        )
        pct = (
            weight
            / total_weight
            * 100.0
        )

        member_name = countries[member].get(
            "display_name",
            member,
        )

        distribution_parts.append(
            f"{member_name}:{gain}人"
            f"({pct:.1f}%)"
        )

    distribution_text = (
        "、".join(distribution_parts)
        if distribution_parts
        else "無"
    )

    loser["last_population_audit"] = (
        f"國都陷落：{deaths} 人死亡；"
        f"{survivors} 名生還農民按勝方出兵比例分配："
        f"{distribution_text}"
    )

    loser["is_alive"] = False
    loser["power"] = 0
    loser["pop_total"] = 0
    loser["farmers"] = 0
    loser["soldiers"] = 0
    loser["food"] = 0
    loser["wood"] = 0
    loser["metal"] = 0
    loser["gold"] = 0
    loser["houses"] = 0
    loser["fortification"] = 0
    loser["death_respawn_cooldown"] = 6
    loser["current_wars"] = []
    loser["war_status"] = (
        "國都陷落，等待新世代重建"
    )

    print(
        f"🏯 [國都陷落]【{loser_name}】政權崩潰！"
        f"戰亂死亡 {deaths} 人；"
        f"生還農民 {survivors} 人依累積出兵比例分配："
        f"{distribution_text}。"
        f"主要攻城國【{primary_name}】接收戰利資源 "
        f"糧:{captured['food']}/木:{captured['wood']}/金:{captured['metal']}。"
    )

    return primary_key


def _war_impose_vassalage(
    loser_key,
    attacker_members,
    countries,
    turn_counter,
    attacker_name="",
):
    """第一次國都陷落先喪失部分主權與資源，不直接刪除國家。"""
    if loser_key not in countries or not countries[loser_key].get("is_alive", True):
        return None
    winners = _war_live_members(attacker_members, countries)
    if not winners:
        return None
    primary_key = max(winners, key=lambda m: int(countries[m].get("power", 0) or 0))
    primary = countries[primary_key]
    loser = countries[loser_key]
    transferred = {}
    for resource in ("food", "wood", "metal"):
        stock = max(0, int(loser.get(resource, 0) or 0))
        amount = min(stock, int(stock * VASSAL_REPARATION_RATE))
        loser[resource] = stock - amount
        primary[resource] = max(0, int(primary.get(resource, 0) or 0)) + amount
        transferred[resource] = amount
    if MARKET_ECONOMY_ENABLED:
        stock = max(0, int(loser.get("gold", 0) or 0))
        amount = min(stock, int(stock * VASSAL_REPARATION_RATE))
        loser["gold"] = stock - amount
        primary["gold"] = max(0, int(primary.get("gold", 0) or 0)) + amount
        transferred["gold"] = amount

    loser["subjugation_count"] = max(0, int(loser.get("subjugation_count", 0) or 0)) + 1
    loser["protector_country"] = primary_key
    loser["vassal_until_turn"] = int(turn_counter) + VASSAL_DURATION_YEARS
    loser["capitulation_protection_until_turn"] = int(turn_counter) + CAPITULATION_PROTECTION_YEARS
    loser["last_capitulation_turn"] = int(turn_counter)
    loser["political_stability"] = float(_clamp(loser.get("political_stability", 75) - 18, 15, 100))
    loser["war_exhaustion"] = float(_clamp(loser.get("war_exhaustion", 0) + 20, 0, 100))
    loser["international_dread"] = int(max(0, loser.get("international_dread", 0)) * 0.70)
    loser["war_status"] = f"附庸於{primary.get('display_name', primary_key)}"
    loser["last_event"] = (
        f"國都陷落後向{attacker_name or primary.get('display_name', primary_key)}臣服；"
        f"附庸至第{loser['vassal_until_turn']}年"
    )
    loser["fortification"] = max(0, int(loser.get("fortification", 0) or 0))
    loser["power"] = calculate_rts_power(loser)
    primary["power"] = calculate_rts_power(primary)
    print(
        f"🏳️ [附庸臣服]【{loser.get('display_name', loser_key)}】國都失守但政權未滅，"
        f"向【{primary.get('display_name', primary_key)}】臣服至第 {loser['vassal_until_turn']} 年；"
        f"割讓 糧:{transferred.get('food', 0)}/木:{transferred.get('wood', 0)}/金屬:{transferred.get('metal', 0)}，"
        f"獲得 {CAPITULATION_PROTECTION_YEARS} 年戰後重整期。"
    )
    return primary_key


def _war_resolve_capital_defeat(
    loser_key,
    attacker_members,
    countries,
    note_population_loss,
    turn_counter,
    contribution_weights=None,
    attacker_name="",
):
    """第一次重大戰敗先附庸；已曾臣服的政權再次失守才執行滅國。"""
    loser = countries.get(loser_key, {})
    if int(loser.get("subjugation_count", 0) or 0) < SUBJUGATION_BEFORE_ANNEXATION:
        return (
            "SUBJUGATED"
            if _war_impose_vassalage(
                loser_key, attacker_members, countries, turn_counter, attacker_name
            )
            else None
        )
    return (
        "ANNEXED"
        if _war_execute_capital_fall(
            loser_key,
            attacker_members,
            countries,
            note_population_loss,
            turn_counter,
            contribution_weights=contribution_weights,
            attacker_name=attacker_name,
        )
        else None
    )



def _war_convert_captured_soldiers_to_war_slaves(winner_members, war, countries):
    """把本場戰爭中「擊殺的敵方士兵」的一定比例轉為戰奴，加入勝方士兵。"""
    winners = _war_live_members(winner_members, countries)
    if not winners:
        return 0
    killed = max(0, int(war.get("defender_soldier_losses", 0) or 0))
    ratio = 0.35  # 35% 的敵軍戰死轉為戰奴，直接補入勝方軍隊。
    slaves = int(killed * ratio)
    if slaves <= 0:
        return 0
    weights = [max(1, int(countries[m].get("soldiers", 0) or 0)) for m in winners]
    total = max(1, sum(weights))
    remaining = slaves
    for idx, (m, weight) in enumerate(zip(winners, weights)):
        gain = remaining if idx == len(winners) - 1 else min(remaining, int(slaves * weight / total))
        # 戰奴是「人口轉軍隊」，因此同時增加總人口與現役士兵；
        # 仍受 50% 軍事人口上限約束，避免戰勝國瞬間全軍化。
        cap = max(0, int(countries[m].get("pop_total", 0) or 0) // 2 - int(countries[m].get("soldiers", 0) or 0))
        gain = min(gain, cap)
        if gain > 0:
            countries[m]["pop_total"] = int(countries[m].get("pop_total", 0) or 0) + gain
            countries[m]["soldiers"] = int(countries[m].get("soldiers", 0) or 0) + gain
        remaining -= gain
        enforce_farmer_majority(countries[m])
        countries[m]["power"] = calculate_rts_power(countries[m])
    actual = slaves - remaining
    war["war_slaves_captured"] = actual
    return actual


def _war_apply_victory_benefits(war, winner_members, loser_members, countries):
    """所有「非滅國」勝利也要有明確戰果：戰敗金 + 戰奴。"""
    winners = _war_live_members(winner_members, countries)
    losers = _war_live_members(loser_members, countries)
    if not winners or not losers:
        return {"gold": 0, "slaves": 0}
    # 勝利後強制收取一筆比「求和」更高的戰敗金。
    gold_paid = 0
    if MARKET_ECONOMY_ENABLED:
        for m in losers:
            stock = max(0, int(countries[m].get("gold", 0) or 0))
            take = min(stock, int(stock * 0.18))
            countries[m]["gold"] = stock - take
            gold_paid += take
    weights = [max(1, int(countries[m].get("soldiers", 0) or 0)) for m in winners]
    total = max(1, sum(weights))
    remaining = gold_paid
    for idx, (m, weight) in enumerate(zip(winners, weights)):
        gain = remaining if idx == len(winners) - 1 else min(remaining, int(gold_paid * weight / total))
        if MARKET_ECONOMY_ENABLED:
            countries[m]["gold"] = max(0, int(countries[m].get("gold", 0) or 0)) + gain
        remaining -= gain
    slaves = _war_convert_captured_soldiers_to_war_slaves(winners, war, countries)


    return {"gold": gold_paid, "slaves": slaves}


def _war_decide_surrender(war, attacker_members, defender_members, countries):
    """
    求和不是自動成功：先由防守方提出，再由進攻方依戰況決定接受或拒絕。
    回傳 (accept, reason)。拒絕後由上層直接進入滅國結算，避免戰爭卡死。
    """
    if not attacker_members or not defender_members:
        return False, "缺少有效參戰國"
    att_initial = max(1, int(war.get("attacker_initial_soldiers", 1) or 1))
    def_initial = max(1, int(war.get("defender_initial_soldiers", 1) or 1))
    att_now = _war_total_soldiers(attacker_members, countries)
    def_now = _war_total_soldiers(defender_members, countries)
    att_ratio = att_now / att_initial
    def_ratio = def_now / def_initial
    rounds = int(war.get("rounds", 0) or 0)
    attacker_exhaustion = sum(float(countries[m].get("war_exhaustion", 0) or 0) for m in attacker_members) / max(1, len(attacker_members))

    # 進攻方越疲憊、己方剩餘兵力越低，越願意拿賠款停戰；
    # 若仍保持壓倒性兵力，則有較高機率拒絕並繼續攻城。
    acceptance_score = 0.20
    acceptance_score += max(0.0, 0.45 - att_ratio) * 1.20
    acceptance_score += min(0.25, attacker_exhaustion / 100.0 * 0.35)
    acceptance_score += min(0.15, rounds / 100.0)
    acceptance_score -= max(0.0, 0.40 - def_ratio) * 0.45
    acceptance_score = _clamp(acceptance_score, 0.05, 0.80)
    accept = random.random() < acceptance_score
    reason = (
        f"進攻剩餘{att_ratio:.0%}、防守剩餘{def_ratio:.0%}、"
        f"戰爭疲勞{attacker_exhaustion:.1f}、接受分數{acceptance_score:.0%}"
    )
    return accept, reason


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
    att_member_forces = _war_effective_member_forces(
        att_members,
        countries,
        war_id,
        active_wars,
    )
    def_member_forces = _war_effective_member_forces(
        def_members,
        countries,
        war_id,
        active_wars,
    )

    att_s = sum(att_member_forces.values())
    def_s = sum(def_member_forces.values())
    homeland_defense_bonus = _homeland_defense_bonus(att_s, def_s)

    # 每一回合都累積各國真正投入此戰線的有效兵力。
    # 第二戰線已自動套用 55% 有效兵力，因此不會重複灌水。
    _war_add_troop_contribution(
        war,
        "attacker_troop_contribution",
        att_member_forces,
    )
    _war_add_troop_contribution(
        war,
        "defender_troop_contribution",
        def_member_forces,
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
        defense = (
            1.0
            + (_war_avg_fort(def_members, countries) / 100.0) * 0.35
            + homeland_defense_bonus
        )
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
        fort_before = _war_avg_fort(def_members, countries)
        fort_damage, house_damage = _war_damage_fort(
            def_members, countries,
            WARSTATE["FORT_SIEGE_MIN"], WARSTATE["FORT_SIEGE_MAX"],
            True,
        )
        # 舊版無論守方有沒有兵，都按攻方總兵力扣 1%~4%，造成「守方 -0、攻方 -500」。
        # 現在傷亡由實際守軍與城防造成；完全無守軍時只有少量攻城事故／陷阱傷亡，
        # 並設攻方兵力 0.5% 的硬上限，避免大軍因自身規模反而憑空大量死亡。
        if def_s > 0:
            siege_attacker_loss = int(
                min(att_s * 0.025, def_s * random.uniform(0.04, 0.12) + fort_before * 0.45)
            )
        else:
            siege_attacker_loss = int(
                min(
                    att_s * UNDEFENDED_SIEGE_ATTACKER_LOSS_RATE_CAP,
                    fort_before * UNDEFENDED_SIEGE_ATTACKER_LOSS_PER_FORT,
                )
            )
        att_loss = _war_apply_soldier_losses(
            att_members, countries, siege_attacker_loss,
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
    war["defender_soldier_losses"] = int(war.get("defender_soldier_losses", 0) or 0) + def_loss
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

    # 空城失守規則：人口多寡不是城池能否繼續抵抗的理由，真正條件是
    # 「仍有沒有守軍」與「城防還能撐多久」。無守軍時只允許短暫被動抵抗。
    def_total_pop = sum(max(0, int(countries[m].get("pop_total", 0) or 0)) for m in def_members)
    def_total_soldiers = _war_total_soldiers(def_members, countries)
    if def_total_soldiers <= 0 and cur_att > 0:
        war["undefended_siege_years"] = int(war.get("undefended_siege_years", 0) or 0) + 1
        empty_city_falls = avg_fort <= UNDEFENDED_CAPITAL_FORT_THRESHOLD
        siege_time_exhausted = (
            int(war.get("undefended_siege_years", 0) or 0)
            >= UNDEFENDED_MAX_SIEGE_YEARS
        )
        fall_reason = None
        if empty_city_falls:
            fall_reason = "守軍與城防均已歸零，國都當年陷落"
        elif siege_time_exhausted:
            fall_reason = f"守軍歸零後已孤城抵抗 {UNDEFENDED_MAX_SIEGE_YEARS} 年，國都陷落"

        if fall_reason:
            loser_key = war.get("defender_anchor")
            if loser_key not in def_members:
                loser_key = min(def_members, key=lambda m: countries[m].get("pop_total", 0))
            defeat_result = _war_resolve_capital_defeat(
                loser_key,
                att_members,
                countries,
                note_population_loss,
                turn_counter,
                contribution_weights=war.get("attacker_troop_contribution", {}),
                attacker_name=war.get("attacker_name", ""),
            )
            if defeat_result:
                reason = (fall_reason + "，轉為附庸") if defeat_result == "SUBJUGATED" else fall_reason
                return {"ended": True, "winner": "ATTACKER", "reason": reason}
    else:
        # 守軍補回或攻方已無兵時重新計算；避免不同階段的零散年份相加。
        war["undefended_siege_years"] = 0

    # 極小殘國的舊規則保留為保險，但正常情況會先由上述空城規則結算。
    if def_total_soldiers <= 0 and def_total_pop <= 12 and round_no >= 2 and cur_att > 0:
        loser_key = war.get("defender_anchor")
        if loser_key not in def_members:
            loser_key = min(def_members, key=lambda m: countries[m].get("pop_total", 0))
        defeat_result = _war_resolve_capital_defeat(loser_key, att_members, countries, note_population_loss, turn_counter, contribution_weights=war.get("attacker_troop_contribution", {}), attacker_name=war.get("attacker_name", ""))
        if defeat_result:
            reason = "殘國已無軍隊，轉為附庸" if defeat_result == "SUBJUGATED" else "殘國再次失守，滅國"
            return {"ended": True, "winner": "ATTACKER", "reason": reason}

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
            defeat_result = _war_resolve_capital_defeat(
                loser_key,
                att_members,
                countries,
                note_population_loss,
                turn_counter,
                contribution_weights=war.get(
                    "attacker_troop_contribution",
                    {},
                ),
                attacker_name=war.get(
                    "attacker_name",
                    "",
                ),
            )
            if defeat_result:
                reason = "國都陷落，轉為附庸" if defeat_result == "SUBJUGATED" else "國都再次陷落，滅國"
                return {"ended": True, "winner": "ATTACKER", "reason": reason}

    # 至少 3 回合後才允許撤軍或求和
    if round_no >= 3:
        if att_ratio <= 0.30 or int(war.get("attacker_loss_streak", 0) or 0) >= 3:
            if random.random() < 0.70:
                return {"ended": True, "winner": "DEFENDER", "reason": "進攻方攻勢耗盡撤軍"}

        if def_ratio <= 0.40 and avg_fort < 30:
            # 防守方正式提出求和；進攻方自己判斷是否值得接受。
            accept_surrender, decision_reason = _war_decide_surrender(
                war, att_members, def_members, countries
            )
            if accept_surrender:
                reparations = _war_collect_reparations(
                    att_members, def_members, countries
                )
                print(
                    f"🏳️ [求和接受] {war_id}：【{def_name}】向【{att_name}】求和；"
                    f"進攻方接受。{decision_reason}。"
                    f"支付戰敗金 {reparations["gold"]}；賠款 糧:{reparations["food"]}/木:{reparations["wood"]}/金屬:{reparations["metal"]}。"
                )
                war["surrender_reparations"] = reparations
                return {"ended": True, "winner": "ATTACKER", "reason": "防守方求和，進攻方接受"}

            # 求和被拒絕後，不再讓弱國無限拖延：直接執行國都陷落／滅國。
            loser_key = war.get("defender_anchor")
            if loser_key not in def_members:
                loser_key = min(def_members, key=lambda m: countries[m].get("soldiers", 0))
            defeat_result = _war_resolve_capital_defeat(
                loser_key, att_members, countries, note_population_loss, turn_counter,
                contribution_weights=war.get("attacker_troop_contribution", {}),
                attacker_name=war.get("attacker_name", ""),
            )
            if defeat_result:
                print(
                    f"☠️ [求和遭拒] {war_id}：【{att_name}】拒絕【{def_name}】求和，"
                    f"進入主權結算。{decision_reason}。"
                )
                reason = "求和遭拒，轉為附庸" if defeat_result == "SUBJUGATED" else "求和遭拒，再次失守滅國"
                return {"ended": True, "winner": "ATTACKER", "reason": reason}

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


def _war_refresh_country_status(countries, active_wars, turn_counter=0):
    for c in countries.values():
        c["current_wars"] = []
        protector_key = c.get("protector_country", "")
        protector_name = countries.get(protector_key, {}).get("display_name", protector_key)
        if (
            protector_key
            and int(c.get("vassal_until_turn", 0) or 0) > int(turn_counter)
        ):
            c["war_status"] = f"附庸於【{protector_name}】"
        else:
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
    print(f"⚙️ [經濟模式] MARKET_ECONOMY_ENABLED={MARKET_ECONOMY_ENABLED}｜"
          f"{'貨幣與市場啟用' if MARKET_ECONOMY_ENABLED else '無貨幣模式：市場、交易 AI、銀行與換幣停用'}")
    """主要模擬循環線程：處理經濟、外交、戰爭、RL學習與紀錄存檔"""
    global last_sync_time, world_stage_g, COALITION_MAX_ACTIVE

    seed_text = os.environ.get("亂世演算_SEED", "").strip()
    simulation_seed = int(seed_text) if seed_text else random.SystemRandom().randint(1, 2**31 - 1)
    random.seed(simulation_seed)
    max_turns = max(0, int(os.environ.get("亂世演算_MAX_TURNS", "0") or 0))
    configured_delay = os.environ.get("亂世演算_LOOP_DELAY", "").strip()
    if configured_delay:
        set_simulation_speed(float(configured_delay))
    print(f"⚔️ 全球多維度戰局與高級 RL 模擬系統 啟動！Seed={simulation_seed}")

    

    start_time = time.time()  # 紀錄本屆賽事開始時間
    time_total = max(
        1.0,
        # float(os.environ.get("亂世演算_SEASON_SECONDS", "1000") or 1000),
        SEASON_SECONDS,
    )  # 每屆賽事持續時間；測試可用環境變數縮短。
    num = max(2, int(os.environ.get("亂世演算_COUNTRIES", "100") or 100))
    dead_mode = 0  # 復活模式設定 (0 代表冷卻後會以第二代/第三代復活)

    # 檔案儲存路徑定義
    countries_file = save_path("war_live_countries.json")
    alliances_file = save_path("war_live_alliances.json")
    q_tables_file = save_path("rl_agents_q_tables.json")

    # V5.2 斷點續跑：
    # JSON 供程式恢復；TXT 供人工直接查看目前跑到第幾屆、幾秒。
    runtime_checkpoint_file = save_path("亂世演算_執行進度.json")
    runtime_progress_text_file = save_path("亂世演算_執行進度.txt")

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

    # V8 世界共同貨幣與報價市場。
    world_bank = _default_world_bank()
    world_market = _default_world_market()
    world_bank["simulation_seed"] = simulation_seed

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
    loaded_season_start_turn = None
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
            saved_countries_data, saved_alliances_data, loaded_c_path, loaded_a_path = (
                _load_consistent_snapshot_pair(countries_file, alliances_file)
            )
            if loaded_c_path != countries_file or loaded_a_path != alliances_file:
                print(f"🛟 [存檔復原] 已載入一致備份：{loaded_c_path}／{loaded_a_path}")

            country_snapshot_id = saved_countries_data.get("snapshot_id")
            alliance_snapshot_id = saved_alliances_data.get("snapshot_id")
            if country_snapshot_id and alliance_snapshot_id and country_snapshot_id != alliance_snapshot_id:
                raise RuntimeError(
                    f"存檔快照不一致：國家={country_snapshot_id}，聯盟={alliance_snapshot_id}；"
                    "已停止載入以避免覆寫。"
                )

            saved_seed = saved_countries_data.get("simulation_seed")
            if saved_seed is not None:
                simulation_seed = int(saved_seed)
            saved_rng_state = saved_countries_data.get("rng_state")
            if saved_rng_state:
                random.setstate(_tuple_tree(saved_rng_state))

            saved_countries = saved_countries_data.get("countries", {})
            had_saved_world_bank = isinstance(saved_countries_data.get("world_bank"), dict)
            world_bank = _normalize_world_bank(saved_countries_data.get("world_bank"))
            world_bank["simulation_seed"] = simulation_seed
            world_market = _normalize_world_market(saved_countries_data.get("world_market"))
            # 舊存檔沒有市場面額欄位；其計價基準以銀行保存的面額為準。
            world_market["currency_denomination"] = world_bank["currency_denomination"]

            if saved_countries:
                countries = saved_countries
                # 為舊版存檔補齊可能缺失的鍵值
                for base_name, c_data in countries.items():
                    c_data.setdefault("championship_records", [])
                    c_data.setdefault("championship_count", 0)
                    c_data.setdefault("death_respawn_cooldown", 0)
                    c_data.setdefault("newbie_protection_until_turn", 0)
                    c_data.setdefault("annexed_count", 0)
                    c_data.setdefault("infamy", 0)
                    c_data.setdefault("international_dread", 0)
                    c_data["international_dread"] = max(0, int(c_data.get("international_dread", 0) or 0))
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

                    # V8 舊存檔第一次升級時，由世界銀行一次性發行初始大洋。
                    if MARKET_ECONOMY_ENABLED and (int(c_data.get("currency_version", 0) or 0) < CURRENCY_VERSION or "gold" not in c_data):
                        initial_gold = random.randint(BALANCE["START_GOLD_MIN"], BALANCE["START_GOLD_MAX"])
                        c_data["gold"] = initial_gold
                        c_data["currency_version"] = CURRENCY_VERSION
                        world_bank["issued_total"] = max(0, int(world_bank.get("issued_total", 0) or 0)) + initial_gold
                    else:
                        c_data["gold"] = max(0, int(c_data.get("gold", 0) or 0))
                        INIT_GOLD = c_data["gold"]

                    loaded_balance_version = int(c_data.get("balance_version", 0) or 0)
                    if loaded_balance_version < BALANCE_VERSION:
                        old_target = float(c_data.get("military_target_ratio", 0.30) or 0.30)
                        if old_target <= 0.16:
                            c_data["military_target_ratio"] = 0.30
                        c_data["balance_version"] = BALANCE_VERSION
                    c_data.setdefault("current_wars", [])
                    c_data.setdefault("prewar_risk_score", 0.0)
                    c_data.setdefault("prewar_risk_level", "CALM")
                    c_data.setdefault("prewar_mobilization_need", 0.0)
                    c_data.setdefault("prewar_threat_country", None)
                    c_data.setdefault("prewar_threat_power_ratio", 0.0)
                    c_data.setdefault("prewar_threat_soldier_ratio", 0.0)
                    c_data.setdefault("prewar_threat_hostility", 0.0)
                    c_data.setdefault("prewar_threat_intent", 0.0)
                    c_data.setdefault("prewar_threat_capability", 0.0)
                    c_data.setdefault("prewar_farmer_soldier_ratio", 0.0)
                    c_data.setdefault("prewar_force_balance_risk", 0.0)
                    c_data.setdefault("prewar_threat_candidate_count", 0)
                    c_data.setdefault("prewar_recruit_ready", False)
                    c_data.setdefault("prewar_food_runway", 0.0)
                    c_data.setdefault("protection_remaining_years", 0)
                    c_data.setdefault("protection_remaining_ratio", 0.0)
                    c_data.setdefault("survival_preparation_urgency", 0.0)
                    c_data.setdefault("war_supply_years", 0.0)
                    c_data.setdefault("security_risk_score", 0.0)
                    c_data.setdefault("security_posture", "安全")
                    c_data.setdefault("survival_milestone_awarded", 0)
                    c_data.setdefault("survival_milestone_reward_pending", 0.0)
                    c_data.setdefault("subjugation_count", 0)
                    c_data.setdefault("protector_country", "")
                    c_data.setdefault("vassal_until_turn", 0)
                    c_data.setdefault("capitulation_protection_until_turn", 0)
                    c_data.setdefault("last_capitulation_turn", 0)
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
                if saved_alliances_data.get("season_start_turn") is not None:
                    loaded_season_start_turn = int(saved_alliances_data.get("season_start_turn", 0) or 0)

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

                if not had_saved_world_bank:
                    world_bank["issued_total"] = max(
                        int(world_bank.get("issued_total", 0) or 0),
                        sum(max(0, int(d.get("gold", 0) or 0)) for d in countries.values())
                        + max(0, int(world_bank.get("treasury", 0) or 0)),
                    )
                if MARKET_ECONOMY_ENABLED:
                    _market_prune_orders(world_market, countries, turn_counter)
                else:
                    _disable_market_runtime(world_market)
                is_loaded = True
                print(
                    f"📁 [讀檔成功] 已成功載入第 {count_round} 屆資料，"
                    f"本屆已完成 {loaded_season_elapsed:.1f}/{time_total} 秒，"
                    f"共 {len(countries)} 個國家。"
                )
        except Exception as e:
            print(f"🛑 [讀檔失敗] ({e})；為保護既有存檔，本次不建立新局也不覆寫檔案。")
            return

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
                t4 = (random.randint(BALANCE["START_GOLD_MIN"], BALANCE["START_GOLD_MAX"])
                      if MARKET_ECONOMY_ENABLED else 0)
    
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
                    "gold": t4,
                    "currency_version": CURRENCY_VERSION,
                    "birth_policy_turns": 0,
                    "production_policy_turns": 0,
                    "policy_summary": "無",
                    "infrastructure": 0,
                    "industry_focus": "AUTO",
                    "industry_focus_turns": 0,
                    "industry_focus_name": "自動配置",
                    "alliance_attempts": 0,
                    "alliance_successes": 0,
                    "alliance_rejections": 0,
                    "alliance_dissolutions": 0,
                    "alliance_last_result": "尚未嘗試",
                    "last_war_target": "尚未評估",
                    "last_war_win_chance": 0.0,
                    "last_war_assessment": "尚未評估",
                    "war_assessment_cancellations": 0,
                    "power": 0,
                    "is_alive": True,
                    "annexed_count": 0,
                    "death_respawn_cooldown": 3,
                    "newbie_protection_until_turn": NEW_COUNTRY_PROTECTION_YEARS,
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
                    "prewar_risk_score": 0.0,
                    "prewar_risk_level": "CALM",
                    "prewar_mobilization_need": 0.0,
                    "prewar_threat_country": None,
                    "prewar_threat_power_ratio": 0.0,
                    "prewar_threat_soldier_ratio": 0.0,
                    "prewar_threat_hostility": 0.0,
                    "prewar_threat_intent": 0.0,
                    "prewar_threat_capability": 0.0,
                    "prewar_farmer_soldier_ratio": 0.0,
                    "prewar_force_balance_risk": 0.0,
                    "prewar_threat_candidate_count": 0,
                    "prewar_recruit_ready": False,
                    "prewar_food_runway": 0.0,
                    "protection_remaining_years": NEW_COUNTRY_PROTECTION_YEARS,
                    "protection_remaining_ratio": 1.0,
                    "survival_preparation_urgency": 0.0,
                    "war_supply_years": 0.0,
                    "security_risk_score": 0.0,
                    "security_posture": "保護準備",
                    "survival_milestone_awarded": 0,
                    "survival_milestone_reward_pending": 0.0,
                    "subjugation_count": 0,
                    "protector_country": "",
                    "vassal_until_turn": 0,
                    "capitulation_protection_until_turn": 0,
                    "last_capitulation_turn": 0,
                    "war_status": "和平",
                    "war_log_terms": [],
                    "top_hostility_target": "無",
                    "recent_attackers": [],
                    "international_dread": 0,
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

            world_bank["issued_total"] = sum(max(0, int(d.get("gold", 0) or 0)) for d in countries.values())
            world_bank["last_action"] = (f"開局發行 {world_bank['issued_total']} 大洋"
                                         if MARKET_ECONOMY_ENABLED else "無貨幣模式：未發行貨幣")

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

    if loaded_season_start_turn is not None:
        season_start_turn = min(int(turn_counter), int(loaded_season_start_turn))
    elif is_loaded:
        # 舊存檔只有秒數；升級時依「2 秒=1 年」換算一次，之後永久使用回合欄位。
        inferred_years = min(
            YEARS_PER_SEASON,
            max(0, int(round(float(loaded_season_elapsed) / SECONDS_PER_YEAR))),
        )
        season_start_turn = max(0, int(turn_counter) - inferred_years)
    else:
        season_start_turn = int(turn_counter)

    loaded_season_elapsed = max(0, int(turn_counter) - season_start_turn) * SECONDS_PER_YEAR
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

    # 開局或舊存檔以當前經濟作基準；已有基準的存檔沿用原設定。
    old_index_schema = int(world_bank.get("policy_index_schema", 0) or 0)
    if MARKET_ECONOMY_ENABLED:
        policy_index_initialize(world_bank, countries)
    else:
        world_bank["policy_price_index"] = 1.0
        world_bank["last_action"] = "市場與貨幣功能已關閉；既有餘額凍結"
        _disable_market_runtime(world_market)
    if old_index_schema < 4 and loaded_season_elapsed > 0:
        print(f"📊 [價格指數修正] 現在使用累計發行／最初發行作整屆倍率；當屆指數 {world_bank['policy_price_index']:.3f}。")
    # 主遊戲運行迴圈 (Game Loop)
    while True:
        _wait_for_simulation_permission()
        loop_started_at = time.monotonic()
        world_bank["current_season_round"] = int(count_round)
        season_elapsed_years = max(0, int(turn_counter) - int(season_start_turn))
        season_remaining_years = max(0, YEARS_PER_SEASON - season_elapsed_years)
        season_progress = _clamp(season_elapsed_years / max(1.0, float(YEARS_PER_SEASON)), 0.0, 1.0)
        season_phase = "EARLY" if season_progress < 1/3 else "MIDDLE" if season_progress < 2/3 else "LATE"
        season_phase_name = {"EARLY": "本屆前段", "MIDDLE": "本屆中段", "LATE": "本屆後段"}[season_phase]
        for data in countries.values():
            data["season_phase"] = season_phase
            data["season_phase_name"] = season_phase_name
            data["season_progress"] = round(season_progress, 4)
            world_bank["birth_policy_cost"] = policy_cost(BIRTH_POLICY_GOLD_COST, world_bank)
            data["policy_price_index"] = world_bank["policy_price_index"]
            data["currency_denomination"] = world_bank["currency_denomination"]
            cash = max(0, int(data.get("gold", 0) or 0))
            data["cash_status"] = (
                "無政策預算" if cash < min(policy_cost(BIRTH_POLICY_GOLD_COST, data), policy_cost(PRODUCTION_POLICY_GOLD_COST, data))
                else "可執行政策" if cash < min(policy_cost(BIRTH_POLICY_GOLD_COST, data), policy_cost(PRODUCTION_POLICY_GOLD_COST, data)) * 3
                else "資金充裕"
            )
        regime_counts_before = {
            name: int(data.get("regime_change_count", 0) or 0)
            for name, data in countries.items()
        }
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

        # 政權變動會局部遺忘舊政府經驗，並短期提高探索率。
        for name, c_data in countries.items():
            if int(c_data.get("regime_change_count", 0) or 0) <= regime_counts_before.get(name, 0):
                continue
            history = c_data.get("regime_history", []) or []
            kind = history[-1].get("kind", "政權變動") if history and isinstance(history[-1], dict) else "政權變動"
            if name in rl_agents:
                rl_agents[name].decay_political_memory(kind)

        # 1. 經濟與人口產出更新（僅限存活國家）
        for name, c_data in countries.items():
            if c_data["is_alive"]:
                # 保存上一輪戰力，讓 State 的 RISING/STABLE/FALLING 真正有時間差。
                c_data["prev_power"] = c_data.get("power", 0)

                econ_pop_before = int(c_data.get("pop_total", 0) or 0)
                update_rts_economy_and_jobs(c_data, world_market)
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
        for rank, country_key in enumerate(alive_sorted, 1):
            countries[country_key]["world_rank"] = rank
            countries[country_key]["top_three_contender"] = rank <= 3

        # 每 100 回合提供一次小額「爭冠方向訊號」：進步有獎、退步有懲罰。
        # 屆中獎勵明顯小於屆末冠軍獎勵，避免 AI 只守住短期名次。
        if turn_counter > 0 and turn_counter % COMPETITION_CHECKPOINT_TURNS == 0:
            alive_count_now = max(1, len(alive_sorted))
            for rank, country_key in enumerate(alive_sorted, 1):
                data = countries[country_key]
                previous_rank = max(
                    1,
                    int(data.get("last_competition_rank", rank) or rank),
                )
                progress_reward = _clamp(
                    (previous_rank - rank) * 0.035,
                    -0.45,
                    0.60,
                )
                if rank == 1:
                    standing_reward = 0.40
                elif rank == 2:
                    standing_reward = 0.22
                elif rank == 3:
                    standing_reward = 0.14
                elif rank <= 10:
                    standing_reward = 0.06
                else:
                    standing_reward = -0.08 * (
                        (rank - 10) / max(1, alive_count_now - 10)
                    )
                checkpoint_reward = float(
                    _clamp(progress_reward + standing_reward, -0.55, 0.75)
                )
                agent = rl_agents.get(country_key)
                if agent:
                    agent.apply_competition_reward(checkpoint_reward)
                data["last_competition_rank"] = rank
                data["last_competition_reward"] = round(checkpoint_reward, 3)

        # RL 資產估值使用市場移動均價；尚無成交才回退種子價格。
        for data in countries.values():
            for resource in MARKET_RESOURCES:
                stat = world_market.get("stats", {}).get(resource, {}) or {}
                data[f"market_price_{resource}"] = max(
                    0.01,
                    float(stat.get("vwap_10", stat.get("last_price", MARKET_RESOURCE_META[resource]["seed_price"])) or MARKET_RESOURCE_META[resource]["seed_price"]),
                )
        for country_key, data in countries.items():
            alliance_name = data.get("current_alliance", "")
            alliance_power = sum(
                max(0, int(countries.get(member, {}).get("power", 0) or 0))
                for member in alliances.get(alliance_name, [])
            ) if alliance_name else 0
            data["alliance_power_ratio"] = alliance_power / max(1.0, total_world_power)

        # 結算跨回合政策、戰爭與援助效果，修正只看當下損益的短視學習。
        for country_key, agent in rl_agents.items():
            if country_key in countries:
                settled = agent.settle_delayed_evaluations(countries[country_key], turn_counter)
                if settled:
                    countries[country_key]["last_delayed_reward"] = round(sum(v for _a, v in settled), 2)
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

        # 🌐 國際忌憚值：本回合排名確定後累積。
        update_international_dread(countries, alive_sorted)

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

        # 國際忌憚值達標後，進入圍剿候選池；每回合候選者各有 10% 中籤率。
        dread_coalition_targets = select_international_dread_coalition_targets(
            countries, alive_sorted, COALITION_MAX_ACTIVE
        )
        coalition_candidate_targets = list(dread_coalition_targets)
        if rare_coalition_target in countries and rare_coalition_target not in coalition_candidate_targets:
            coalition_candidate_targets.append(rare_coalition_target)
        coalition_candidate_targets = coalition_candidate_targets[:COALITION_MAX_ACTIVE]
        if dread_coalition_targets:
            rare_coalition_target = dread_coalition_targets[0]

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

            # 舊版「戰力門檻 + 2%」稀有抽籤已移除，改由國際忌憚值候選池觸發。

        # 3. 普通聯盟瓦解與分裂檢測機制（反霸權聯軍不在 alliances，因此不受此規則影響）
        alliances_to_remove = []
        alive_count_for_alliance = max(1, len(alive_sorted))
        # 小世界不能套用固定 12%：存活國越少，單國自然占比越高。
        member_disband_threshold, alliance_disband_threshold = (
            _alliance_disband_thresholds(alive_count_for_alliance)
        )
        for ally_name, members in list(alliances.items()):
            alive_m = [m for m in members if countries[m]["is_alive"]]
            ally_power = sum(countries[m]["power"] for m in alive_m)

            for m in alive_m:
                pwr = countries[m]["power"]
                is_overpowered = (
                    total_world_power > 0
                    and (pwr / total_world_power) >= member_disband_threshold
                )

                if is_overpowered:
                    print(
                        f"[霸權瓦解] 【{countries[m]['display_name']}】戰力佔比達 {pwr/total_world_power:.1%}，"
                        f"超過動態門檻 {member_disband_threshold:.1%}！【{ally_name}】自動瓦解！"
                    )
                    alliances_to_remove.append(ally_name)
                    break

            # 普通同盟整體過強時仍可能內鬥；臨時反霸權聯軍不走這個資料結構。
            if ally_name not in alliances_to_remove:
                if (
                    total_world_power > 0
                    and (ally_power / total_world_power) >= alliance_disband_threshold
                ):
                    print(f"[聯盟分裂] 【{ally_name}】 勢力過大引發內鬥解散！")
                    alliances_to_remove.append(ally_name)

        # 執行刪除過大同盟
        for ally_n in set(alliances_to_remove):
            if ally_n in alliances:
                for member in alliances[ally_n]:
                    if member in countries:
                        countries[member]["alliance_dissolutions"] = max(
                            0, int(countries[member].get("alliance_dissolutions", 0) or 0)
                        ) + 1
                        countries[member]["alliance_last_result"] = f"{ally_n} 瓦解"
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

        # event_type = "BIGWATER"

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
                    new_pop = max(1, int(old_pop * random.uniform(0.97, 0.99)))
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

            elif event_type == "BIGWATER":  # 隕石浩劫：全體損失人口與資源
                            for k in alive_sorted:
                                print(
                                    f"☄️ [大洪水]【{countries[k].get('display_name', k)}】"
                                    f"受大洪水影響，全球物資腐敗地所剩無幾.... "
                                )
                                countries[k]["power"] = calculate_rts_power(countries[k])
                                countries[k]["food"] = int(countries[k]["food"] * 0.1)
                                countries[k]["wood"] = int(countries[k]["wood"] * 0.1)
                                countries[k]["metal"] = int(countries[k]["metal"] * 0.1)

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
                    victory_benefits = _war_apply_victory_benefits(war, att_members, def_members, countries)
                    print(f"💰 [戰勝結算] {war_id}：勝方取得戰敗金 {victory_benefits["gold"]}，並將 {victory_benefits["slaves"]} 名戰俘編入軍隊。")
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
                    if war.get("is_coalition_war"):
                        bounty_total = 0
                        for member in att_members:
                            if member not in countries:
                                continue
                            paid = _world_bank_pay_bounty(
                                world_bank, countries[member], policy_cost(COALITION_VICTORY_BOUNTY, world_bank),
                                reason="反霸權圍剿勝利懸賞",
                            )
                            bounty_total += paid
                            countries[member]["coalition_victories"] = max(0, int(countries[member].get("coalition_victories", 0) or 0)) + 1
                            countries[member]["last_coalition_bounty"] = paid
                            agent = rl_agents.get(member)
                            if agent:
                                agent.strategic_policy.apply_event_reward(
                                    getattr(agent, "_last_state_str", "[]"), 8, 4.0
                                )
                        print(
                            f"🎯 [圍剿勝利] {war.get('attacker_name', '聯軍')}"
                            f"成功討伐【{war.get('defender_name', '霸權')}】，"
                            f"世界銀行從現有庫存支付懸賞 {bounty_total} 大洋。"
                        )
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

        _war_refresh_country_status(countries, active_wars, turn_counter)

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
        for rank, country_key in enumerate(alive_sorted, 1):
            countries[country_key]["world_rank"] = rank
            countries[country_key]["top_three_contender"] = rank <= 3

        # 6. 主行動階段：RL Agent 決策與執行行動
        active_countries = []
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
            # 越接近屆末，前三名越有機會取得主動決策，但不保證必然行動。
            contender_chance = {"EARLY": 0.35, "MIDDLE": 0.60, "LATE": 0.90}[season_phase]
            for contender in alive_sorted[:3]:
                if contender not in active_countries and random.random() < contender_chance:
                    active_countries.append(contender)

            # 脫保前最後階段保證每年有一次「自主決策機會」。只加入決策名單，
            # 實際做什麼仍由安全態勢 Q 值與 Action Mask 決定。
            for country_key in alive_sorted:
                country_data = countries[country_key]
                protection_until = max(
                    int(country_data.get("newbie_protection_until_turn", 0) or 0),
                    int(country_data.get("rebuild_protection_until_turn", 0) or 0),
                )
                remaining = protection_until - int(turn_counter)
                if 0 < remaining <= PRE_RELEASE_GUARANTEED_ACTION_YEARS:
                    if country_key not in active_countries:
                        active_countries.append(country_key)

            # 已到討伐期限的聯軍統籌者必須取得本回合決策權，否則隨機抽樣可能
            # 讓聯軍成立後數百年都沒有任何共同軍事行動。
            for coalition_info in anti_hegemon_coalitions.values():
                if not isinstance(coalition_info, dict):
                    continue
                if turn_counter < int(coalition_info.get("next_attack_turn", turn_counter + 1) or (turn_counter + 1)):
                    continue
                live_members = [
                    m for m in (coalition_info.get("members") or [])
                    if m in countries and countries[m].get("is_alive", True)
                ]
                if live_members and live_members[0] not in active_countries:
                    active_countries.append(live_members[0])

            attacked_this_round = set()  # 本輪已承受新宣戰的國家
            acted_this_round = set()  # 本輪已採取過行動的國家

            for attacker_key in active_countries:
                c_data = countries[attacker_key]
                if not c_data["is_alive"]:  # 防護檢查
                    continue
                c_data["current_turn"] = turn_counter

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
                    attacker_key, countries, alliances, anti_hegemon_coalitions, alive_sorted, turn_counter
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

                # 為本國挑選尚未有對應聯軍的高忌憚目標。目標以忌憚值排序，
                # 因此同一回合可依序替多個目標各成立一個聯軍，而不是全世界只盯第一名。
                coalition_target_for_action = next(
                    (
                        target for target in coalition_candidate_targets
                        if target != attacker_key
                        and target in countries
                        and countries[target].get("is_alive", True)
                        and int(coalition_target_cooldowns.get(target, 0) or 0) <= turn_counter
                        and not any(
                            isinstance(info, dict) and info.get("target") == target
                            for info in anti_hegemon_coalitions.values()
                        )
                    ),
                    None,
                )

                # Action 2 只有在「真正霸權／高忌憚 + 無冷卻 + 本國未參加其他聯軍」時才開放。
                if 2 in valid_actions:
                    # 若本回合有國際忌憚值抽中的圍剿目標，Action 2 直接以該國為目標；
                    # 沒有抽中時才沿用第一名霸權目標。
                    hegemon_key_for_mask = (
                        coalition_target_for_action
                        if coalition_target_for_action in countries
                        and countries[coalition_target_for_action].get("is_alive", True)
                        else (alive_sorted[0] if alive_sorted else None)
                    )
                    coalition_action_ready = bool(
                        hegemon_key_for_mask
                        and hegemon_key_for_mask != attacker_key
                        and (
                            hegemon_streaks.get(
                                hegemon_key_for_mask, 0
                            )
                            >= HEGEMON_REQUIRED_STREAK
                            or hegemon_key_for_mask in coalition_candidate_targets
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

                # 戰前風險評估：每次主動決策前更新一次，讓 AI 在和平期就能看到威脅。
                # 這裡使用本輪最新戰力／排名／外交資料，不等到戰爭建立後才計算。
                prewar = _evaluate_prewar_mobilization(
                    attacker_key, countries, active_wars, alive_sorted
                )
                c_data["prewar_risk_score"] = prewar.get("score", 0.0)
                c_data["prewar_risk_level"] = prewar.get("level", "CALM")
                c_data["prewar_mobilization_need"] = prewar.get("need", 0.0)
                c_data["prewar_threat_country"] = prewar.get("threat")
                c_data["prewar_threat_power_ratio"] = prewar.get("threat_power_ratio", 0.0)
                c_data["prewar_threat_soldier_ratio"] = prewar.get("threat_soldier_ratio", 0.0)
                c_data["prewar_threat_hostility"] = prewar.get("threat_hostility", 0.0)
                c_data["prewar_threat_intent"] = prewar.get("threat_intent", 0.0)
                c_data["prewar_threat_capability"] = prewar.get("threat_capability", 0.0)
                c_data["prewar_threat_candidate_count"] = prewar.get("neighbor_count", 0)
                c_data["prewar_recruit_ready"] = prewar.get("recruit_ready", False)
                c_data["prewar_food_runway"] = prewar.get("food_runway", 0.0)
                update_security_posture(c_data, turn_counter)

                if prewar.get("level") in ("ALERT", "HIGH", "CRITICAL"):
                    threat_name = countries.get(prewar.get("threat"), {}).get("display_name", "未知") if prewar.get("threat") else "未知"
                    print(
                        f"⚠️ [戰前軍事預警]【{c_data.get('display_name', attacker_key)}】"
                        f"風險 {prewar.get('score', 0):.0f}/100（{prewar.get('level')}），"
                        f"主要威脅【{threat_name}】，動員需求 {prewar.get('need', 0):.0%}。"
                    )

                action = agent.choose_action(
                    c_data,
                    total_world_power,
                    top_power,
                    len(alive_sorted),
                    valid_actions=valid_actions,
                    bank=world_bank,
                    market=world_market,
                )

                # 聯軍由第一位仍存活的成員擔任本次統籌者。到了出兵期限且尚未
                # 與目標交戰，就直接提出共同討伐，不再等待隨機抽中戰爭 Action。
                forced_coalition_attack = False
                due_coalition_name = get_country_coalition(attacker_key, anti_hegemon_coalitions)
                due_coalition_info = anti_hegemon_coalitions.get(due_coalition_name, {}) if due_coalition_name else {}
                due_target = due_coalition_info.get("target") if isinstance(due_coalition_info, dict) else None
                due_members = [
                    m for m in (due_coalition_info.get("members", []) if isinstance(due_coalition_info, dict) else [])
                    if m in countries and countries[m].get("is_alive", True)
                ]
                if (
                    due_members
                    and attacker_key == due_members[0]
                    and due_target in countries
                    and countries[due_target].get("is_alive", True)
                    and turn_counter >= int(due_coalition_info.get("next_attack_turn", turn_counter) or turn_counter)
                    and not _war_countries_share_war(attacker_key, due_target, active_wars)
                    and current_war_count < WARSTATE["MAX_ACTIVE_WARS_PER_COUNTRY"]
                    and exhaustion_now < 88
                ):
                    action = 0
                    forced_coalition_attack = True

                # 高忌憚目標不能只靠 RL 偶然抽到 Action 2。若仍有聯軍名額，
                # 讓符合條件且尚未加入聯軍的國家主動嘗試號召；失敗時後續國家仍可接手。
                if (
                    coalition_target_for_action
                    and 2 in valid_actions
                    and len(anti_hegemon_coalitions) < COALITION_MAX_ACTIVE
                    and not get_country_coalition(attacker_key, anti_hegemon_coalitions)
                ):
                    action = 2

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
                        and not (
                            REBUILD_PROTECTION_BLOCK_ATTACK
                            and _is_rebuild_protected(countries[k], turn_counter)
                        )
                        and int(countries[k].get("newbie_protection_until_turn", 0) or 0) <= int(turn_counter)
                        and not _is_capitulation_protected(countries[k], turn_counter)
                        and _war_country_can_join_new_war(k, active_wars)
                        and not _war_countries_share_war(
                            attacker_key, k, active_wars
                        )
                        and not _war_is_truce(
                            attacker_key, k, war_truces, turn_counter
                        )
                    ]

                    if possible_defenders:
                        action_success = False
                        defender_key = None
                        hostility_map = c_data.get("hostility", {}) or {}
                        recent_attackers = set(c_data.get("recent_attackers", []) or [])
                        matchup_cache = {
                            k: estimate_war_matchup(
                                attacker_key,
                                k,
                                countries,
                                alliances,
                                active_wars,
                            )
                            for k in possible_defenders
                        }

                        def has_high_risk_war_reason(k):
                            return (
                                k in recent_attackers
                                or float(hostility_map.get(k, 0) or 0) >= 80.0
                                or (coalition_target and k == coalition_target)
                            )

                        # 一般戰爭至少需35%估計勝算；復仇、極高敵意或圍剿可承擔風險，
                        # 但低於20%仍視為近乎自殺而不宣戰。
                        viable_defenders = [
                            k for k in possible_defenders
                            if (forced_coalition_attack and k == coalition_target)
                            or matchup_cache[k]["win_chance"] >= 0.35
                            or (
                                has_high_risk_war_reason(k)
                                and matchup_cache[k]["win_chance"] >= 0.20
                            )
                        ]

                        if not viable_defenders:
                            best_key = max(
                                possible_defenders,
                                key=lambda k: matchup_cache[k]["win_chance"],
                            )
                            best = matchup_cache[best_key]
                            c_data["last_war_target"] = countries[best_key].get("display_name", best_key)
                            c_data["last_war_win_chance"] = round(best["win_chance"], 4)
                            c_data["last_war_assessment"] = "勝算過低，取消宣戰"
                            c_data["war_assessment_cancellations"] = max(
                                0,
                                int(c_data.get("war_assessment_cancellations", 0) or 0),
                            ) + 1
                            print(
                                f"🧠 [戰爭評估]【{c_data['display_name']}】評估最佳目標"
                                f"【{countries[best_key].get('display_name', best_key)}】勝算僅 "
                                f"{best['win_chance']:.1%}（{best['attacker_power']}:{best['defender_power']}），取消宣戰。"
                            )
                            possible_defenders = []

                        # 聯軍成員約 70% 的全面戰爭會優先履行共同討伐任務。
                        if (
                            coalition_target
                            and coalition_target in viable_defenders
                            and countries.get(coalition_target, {}).get("is_alive", False)
                            and (forced_coalition_attack or random.random() < 0.70)
                        ):
                            defender_key = coalition_target
                            use_coalition_force = True

                        if not defender_key:
                            # 15% 保留不可預測性；其餘依恩怨、復仇、弱點與資源價值選敵。
                            if viable_defenders and random.random() < 0.15:
                                defender_key = random.choice(viable_defenders)
                            else:
                                my_power = max(1, c_data.get("power", 0))

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

                                    # V7：不再依人格挑選敵人。
                                    # AI 先自行學會「要不要開戰」；
                                    # 一旦決定開戰，再依客觀情勢選擇目標。
                                    score = (
                                        hostility * 2.0
                                        + revenge
                                        + event_target_bonus
                                        + weakness * 22.0
                                        + resource_bonus * 0.75
                                        + fat_sheep_bonus * 0.35
                                        + (matchup_cache[k]["win_chance"] - 0.50) * 120.0
                                    )

                                    transition_year = _protection_transition_year(d, turn_counter)
                                    if (
                                        transition_year is not None
                                        and 0 <= transition_year < POST_PROTECTION_TRANSITION_YEARS
                                    ):
                                        remaining_grace = 1.0 - transition_year / max(1, POST_PROTECTION_TRANSITION_YEARS)
                                        score -= POST_PROTECTION_TARGET_SCORE_PENALTY * remaining_grace
                                    if int(d.get("vassal_until_turn", 0) or 0) > int(turn_counter):
                                        score -= 30.0

                                    return score + random.uniform(0.0, 6.0)

                                if viable_defenders:
                                    defender_key = max(viable_defenders, key=war_target_score)

                        if not defender_key:
                            _finalize_rejected_war_action(
                                agent,
                                c_data,
                                before_data,
                                action,
                                -6.0,
                                total_world_power,
                                top_power,
                                len(alive_sorted),
                            )
                            continue

                        selected_matchup = matchup_cache[defender_key]
                        c_data["last_war_target"] = countries[defender_key].get("display_name", defender_key)
                        c_data["last_war_win_chance"] = round(selected_matchup["win_chance"], 4)
                        c_data["last_war_assessment"] = (
                            f"預估勝算 {selected_matchup['win_chance']:.1%}｜"
                            f"有效戰力 {selected_matchup['attacker_power']}:{selected_matchup['defender_power']}"
                        )

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

                        # 表決完成後以真正參戰名單再算一次；避免預估可打，卻在盟友拒戰後
                        # 仍由發起國單獨撞上整個防守聯盟。
                        actual_att_power = sum(
                            _country_effective_war_power(
                                m, countries, active_wars, defending=False
                            )
                            for m in att_entity["members"]
                            if m in countries
                        )
                        actual_def_power = sum(
                            _country_effective_war_power(
                                m, countries, active_wars, defending=True
                            )
                            for m in def_entity["members"]
                            if m in countries
                        )
                        actual_win_chance = actual_att_power / max(
                            1.0, actual_att_power + actual_def_power
                        )
                        risky_reason = has_high_risk_war_reason(defender_key)
                        minimum_chance = 0.20 if risky_reason else 0.35
                        c_data["last_war_win_chance"] = round(actual_win_chance, 4)
                        c_data["last_war_assessment"] = (
                            f"最終勝算 {actual_win_chance:.1%}｜"
                            f"參戰戰力 {int(actual_att_power)}:{int(actual_def_power)}"
                        )
                        if actual_win_chance < minimum_chance:
                            action_success = False
                            c_data["war_assessment_cancellations"] = max(
                                0,
                                int(c_data.get("war_assessment_cancellations", 0) or 0),
                            ) + 1
                            print(
                                f"🛑 [理性撤回宣戰]【{c_data['display_name']}】在盟友表態後，"
                                f"對【{countries[defender_key].get('display_name', defender_key)}】"
                                f"實際勝算僅 {actual_win_chance:.1%}，低於 {minimum_chance:.0%} 門檻。"
                            )
                            _finalize_rejected_war_action(
                                agent,
                                c_data,
                                before_data,
                                action,
                                -6.0,
                                total_world_power,
                                top_power,
                                len(alive_sorted),
                            )
                            continue
                        action_success = True

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
                            transition_year = _protection_transition_year(
                                countries[defender_key], turn_counter
                            )
                            if (
                                transition_year is not None
                                and 0 <= transition_year < POST_PROTECTION_TRANSITION_YEARS
                            ):
                                c_data["infamy"] = max(0, int(c_data.get("infamy", 0) or 0)) + POST_PROTECTION_ATTACK_INFAMY
                                c_data["international_dread"] = max(0, int(c_data.get("international_dread", 0) or 0)) + POST_PROTECTION_ATTACK_DREAD
                                c_data["political_stability"] = float(
                                    _clamp(
                                        c_data.get("political_stability", 75) - POST_PROTECTION_ATTACK_STABILITY_LOSS,
                                        0,
                                        100,
                                    )
                                )
                                print(
                                    f"🌐 [侵略反彈]【{c_data.get('display_name', attacker_key)}】攻擊剛脫保"
                                    f" {transition_year} 年的【{countries[defender_key].get('display_name', defender_key)}】，"
                                    f"惡名 +{POST_PROTECTION_ATTACK_INFAMY}、國際忌憚 +{POST_PROTECTION_ATTACK_DREAD:,}、"
                                    f"政治穩定 -{POST_PROTECTION_ATTACK_STABILITY_LOSS:.0f}。"
                                )
                            war_sequence += 1
                            war_id = f"W{war_sequence:05d}"
                            active_wars[war_id] = {
                                "attacker_anchor": attacker_key,
                                "defender_anchor": defender_key,
                                "attacker_members": list(dict.fromkeys(att_entity["members"])),
                                "defender_members": list(dict.fromkeys(def_entity["members"])),
                                "attacker_name": att_entity["name"],
                                "defender_name": def_entity["name"],
                                "is_coalition_war": bool(use_coalition_force),
                                "coalition_name": coalition_name if use_coalition_force else "",
                                "coalition_target": coalition_target if use_coalition_force else None,
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
                                    "defender_soldier_losses": 0,
                                # V6.6.4：
                                # 戰後生還人口按「累積實際出兵貢獻」分配，
                                # 不再只交給最後戰力最大的國家。
                                "attacker_troop_contribution": {},
                                "defender_troop_contribution": {},
                                "attacker_loss_streak": 0,
                                "defender_loss_streak": 0,
                                "undefended_siege_years": 0,
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
                            if use_coalition_force and coalition_name in anti_hegemon_coalitions:
                                coalition_record = anti_hegemon_coalitions[coalition_name]
                                coalition_record["last_attack_turn"] = turn_counter
                                coalition_record["next_attack_turn"] = (
                                    turn_counter + COALITION_ATTACK_INTERVAL_YEARS
                                )
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
                        total_war_wood_cost = 0

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
                            wood_rate = BALANCE["WAR_WOOD_PER_SOLDIER"]

                            if front_no >= 2:
                                food_rate *= WARSTATE[
                                    "SECOND_FRONT_INITIAL_FOOD_MULTIPLIER"
                                ]
                                metal_rate *= WARSTATE[
                                    "SECOND_FRONT_INITIAL_METAL_MULTIPLIER"
                                ]
                                wood_rate *= WARSTATE[
                                    "SECOND_FRONT_INITIAL_WOOD_MULTIPLIER"
                                ]

                            max_by_food = int(
                                countries[m].get("food", 0)
                                // max(0.01, food_rate)
                            )
                            max_by_metal = int(
                                countries[m].get("metal", 0)
                                // max(0.01, metal_rate)
                            )
                            max_by_wood = int(
                                countries[m].get("wood", 0)
                                // max(0.01, wood_rate)
                            )

                            deployed = min(
                                intended,
                                max_by_food,
                                max_by_metal,
                                max_by_wood,
                            )

                            if deployed <= 0:
                                continue

                            food_cost_m = int(
                                math.ceil(deployed * food_rate)
                            )
                            metal_cost_m = int(
                                math.ceil(deployed * metal_rate)
                            )
                            wood_cost_m = int(
                                math.ceil(deployed * wood_rate)
                            )

                            countries[m]["food"] = max(
                                0, countries[m]["food"] - food_cost_m
                            )
                            countries[m]["metal"] = max(
                                0, countries[m]["metal"] - metal_cost_m
                            )
                            countries[m]["wood"] = max(
                                0, countries[m]["wood"] - wood_cost_m
                            )

                            att_deployments[m] = deployed

                            total_war_food_cost += food_cost_m
                            total_war_metal_cost += metal_cost_m
                            total_war_wood_cost += wood_cost_m

                        att_soldiers = sum(att_deployments.values())

                        # 宣戰當年的第一波實際出兵就算入戰爭貢獻。
                        if (
                            war_id in active_wars
                            and isinstance(active_wars.get(war_id), dict)
                        ):
                            _war_add_troop_contribution(
                                active_wars[war_id],
                                "attacker_troop_contribution",
                                att_deployments,
                            )

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
                            f"消耗 {total_war_food_cost} 糧草、"
                            f"{total_war_metal_cost} 兵器、"
                            f"{total_war_wood_cost} 木材。"
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
                                    defense_factor = (
                                        1.0
                                        + (fortification / 100.0) * 0.35
                                        + _homeland_defense_bonus(att_soldiers, def_soldiers)
                                    )
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
                                    # 宣戰首輪至少保留 1 名平民，主權結算交給持續戰爭；
                                    # 避免第一波會戰直接把小國人口清零、繞過附庸階段。
                                    farmer_kills = min(max(0, def_farmers - 1), overkill)

                                    kills = soldier_kills + farmer_kills  # 總死亡人數

                                    # 更新防守方人口
                                    countries[def_m]["soldiers"] -= soldier_kills
                                    countries[def_m]["farmers"] -= farmer_kills
                                    countries[def_m]["pop_total"] = (
                                        countries[def_m]["soldiers"] + countries[def_m]["farmers"]
                                    )

                                else:
                                    # 無守軍時進入占領／攻城，不再於宣戰第一年直接屠殺農夫。
                                    # 國都是否臣服或滅亡由持續戰爭的主權結算統一處理。
                                    soldier_kills = 0
                                    farmer_kills = 0
                                    kills = 0
                                    fortification = float(
                                        _clamp(countries[def_m].get("fortification", 0), 0, 100)
                                    )
                                    att_loss = int(
                                        min(
                                            att_soldiers * UNDEFENDED_SIEGE_ATTACKER_LOSS_RATE_CAP,
                                            fortification * UNDEFENDED_SIEGE_ATTACKER_LOSS_PER_FORT,
                                        )
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
                    if (
                        not c_data["current_alliance"]
                        and not (
                            REBUILD_PROTECTION_BLOCK_ALLIANCE
                            and _is_rebuild_protected(c_data, turn_counter)
                        )
                    ):  # 尚未入盟且不在重建保護期
                        c_data["alliance_attempts"] = max(
                            0, int(c_data.get("alliance_attempts", 0) or 0)
                        ) + 1
                        existing_alliances = [
                            a_name
                            for a_name, members in alliances.items()
                            if len(
                                [
                                    m
                                    for m in members
                                    if countries[m]["is_alive"]
                                ]
                            ) < ALLIANCE_MAX_MEMBERS
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

                        # 未滿五人的聯盟優先吸收成員；仍保留少量創建新盟的可能，
                        # 避免世界最後只剩幾個超大型政治集團。
                        # 加入現有聯盟改由現有存活盟員正式投票。
                        if existing_alliances and random.random() < ALLIANCE_EXISTING_JOIN_CHANCE:
                            # 成員較多、接近五人的聯盟權重較高，協助 2～4 人聯盟真正補滿；
                            # 不是硬指定，因此小聯盟仍有機會收到申請。
                            target_ally = random.choices(
                                existing_alliances,
                                weights=[
                                    max(
                                        1,
                                        len([
                                            m for m in alliances.get(a_name, [])
                                            if m in countries and countries[m].get("is_alive", True)
                                        ]) ** 2,
                                    )
                                    for a_name in existing_alliances
                                ],
                                k=1,
                            )[0]

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
                                c_data["alliance_successes"] = max(
                                    0, int(c_data.get("alliance_successes", 0) or 0)
                                ) + 1
                                c_data["alliance_last_result"] = f"加入 {target_ally}"
                                c_data["alliance_join_turn"] = turn_counter
                                action_success = True
                                print(
                                    f"🤝 [入盟通過] 【{c_data['display_name']}】"
                                    f"經盟內表決獲准加入 {target_ally}！"
                                    f"（成員數：{len(alliances[target_ally])}）"
                                )
                            else:
                                c_data["alliance_rejections"] = max(
                                    0, int(c_data.get("alliance_rejections", 0) or 0)
                                ) + 1
                                c_data["alliance_last_result"] = f"加入 {target_ally} 遭否決"
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
                                and not (
                                    REBUILD_PROTECTION_BLOCK_ALLIANCE
                                    and _is_rebuild_protected(countries[k], turn_counter)
                                )
                                and not _war_countries_are_opponents(attacker_key, k, active_wars)
                            ]
                            if len(unallied) >= 1:
                                # 不再隨機亂邀：優先共同敵人、低敵意、戰力互補及同受威脅者。
                                def alliance_partner_score(candidate_key):
                                    candidate = countries[candidate_key]
                                    attackers_a = set(c_data.get("recent_attackers", []) or [])
                                    attackers_b = set(candidate.get("recent_attackers", []) or [])
                                    common = attackers_a & attackers_b
                                    mutual_hostility = (
                                        float((c_data.get("hostility", {}) or {}).get(candidate_key, 0) or 0)
                                        + float((candidate.get("hostility", {}) or {}).get(attacker_key, 0) or 0)
                                    )
                                    my_power = max(1.0, float(c_data.get("power", 0) or 0))
                                    partner_power = max(1.0, float(candidate.get("power", 0) or 0))
                                    ratio = partner_power / my_power
                                    complement = 18.0 if 0.55 <= ratio <= 1.80 else 8.0 if 0.30 <= ratio <= 2.50 else 0.0
                                    shared_threat = 8.0 if attackers_a and attackers_b else 0.0
                                    candidate_infamy = float(candidate.get("infamy", 0) or 0)
                                    return (
                                        len(common) * 35.0 + complement + shared_threat
                                        - mutual_hostility * 0.35 - candidate_infamy * 0.08
                                        + random.uniform(0.0, 4.0)
                                    )

                                partner = max(unallied, key=alliance_partner_score)
                                attackers_a = set(c_data.get("recent_attackers", []))
                                attackers_b = set(countries[partner].get("recent_attackers", []))
                                common_enemies = attackers_a.intersection(attackers_b)  # 尋找共同敵人

                                alliance_success_rate = 0.45  # 基礎成功率提高為 45%
                                # 惡名會讓別國不信任；修復聲望因此具有長期價值。
                                alliance_success_rate -= min(0.20, c_data.get("infamy", 0) / 350.0)
                                mutual_hostility = (
                                    float((c_data.get("hostility", {}) or {}).get(partner, 0) or 0)
                                    + float((countries[partner].get("hostility", {}) or {}).get(attacker_key, 0) or 0)
                                )
                                alliance_success_rate -= min(0.18, mutual_hostility / 700.0)
                                my_power = max(1.0, float(c_data.get("power", 0) or 0))
                                partner_power = max(1.0, float(countries[partner].get("power", 0) or 0))
                                power_ratio = partner_power / my_power
                                if 0.55 <= power_ratio <= 1.80:
                                    alliance_success_rate += 0.08
                                if attackers_a and attackers_b:
                                    alliance_success_rate += 0.05
                                alliance_success_rate = max(0.10, alliance_success_rate)
                                alliance_success_rate *= float(
                                    c_data.get("world_alliance_bias", 1.0) or 1.0
                                )
                                alliance_success_rate = float(
                                    _clamp(alliance_success_rate, 0.03, 0.95)
                                )
                                if common_enemies:  # 若有共同強敵，結盟成功率大幅提高
                                    alliance_success_rate += min(0.30, len(common_enemies) * 0.18)
                                    print(
                                        f"[同仇敵儾] 【{c_data['display_name']}】與 【{countries[partner]['display_name']}】"
                                        f"擁有共同強敵 {list(common_enemies)}！結盟意願暴增至 {min(alliance_success_rate*100, 100):.0f}%"
                                    )

                                if random.random() < alliance_success_rate:  # 判定是否成功結盟
                                    ally_name = generate_awesome_alliance_name()
                                    alliances[ally_name] = [attacker_key, partner]
                                    c_data["current_alliance"] = ally_name
                                    countries[partner]["current_alliance"] = ally_name
                                    c_data["alliance_successes"] = max(
                                        0, int(c_data.get("alliance_successes", 0) or 0)
                                    ) + 1
                                    countries[partner]["alliance_successes"] = max(
                                        0, int(countries[partner].get("alliance_successes", 0) or 0)
                                    ) + 1
                                    c_data["alliance_last_result"] = f"創立 {ally_name}"
                                    countries[partner]["alliance_last_result"] = f"共同創立 {ally_name}"
                                    c_data["alliance_join_turn"] = turn_counter
                                    countries[partner]["alliance_join_turn"] = turn_counter
                                    action_success = True
                                    print(f"[外交策略] 【{c_data['display_name']}】與 【{countries[partner]['display_name']}】締結盟約，創立 {ally_name}！")               
                                else:
                                    c_data["alliance_rejections"] = max(
                                        0, int(c_data.get("alliance_rejections", 0) or 0)
                                    ) + 1
                                    c_data["alliance_last_result"] = f"遭 {countries[partner]['display_name']} 婉拒"
                            else:
                                c_data["alliance_rejections"] = max(
                                    0, int(c_data.get("alliance_rejections", 0) or 0)
                                ) + 1
                                c_data["alliance_last_result"] = "沒有可結盟對象"

                # ----------------------------------------------------
                # Action 2: 號召反霸權聯軍（臨時軍事聯軍，不改變普通聯盟）
                # ----------------------------------------------------
                elif action == 2:
                    if len(anti_hegemon_coalitions) < COALITION_MAX_ACTIVE and len(alive_sorted) >= 4:
                        # 優先鎖定本回合被國際忌憚值抽中的圍剿目標；
                        # 否則才鎖定當前第一名。
                        hegemon_key = (
                            coalition_target_for_action
                            if coalition_target_for_action in countries
                            and countries[coalition_target_for_action].get("is_alive", True)
                            else alive_sorted[0]
                        )
                        hegemon = countries[hegemon_key]

                        # 一般霸權仍需連續 3 Loop；國際忌憚值中籤者可直接成為目標。
                        target_ready = (
                            hegemon_streaks.get(
                                hegemon_key, 0
                            )
                            >= HEGEMON_REQUIRED_STREAK
                            or hegemon_key in coalition_candidate_targets
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
                                    k, hegemon_key, countries, alliances, rl_agents, rank_map, turn_counter
                                )
                                eligible.append((k, willingness))

                            # 發起國自己至少要有合理的參戰意願；避免 AI 無腦開聯軍。
                            initiator_willingness = coalition_join_willingness(
                                attacker_key, hegemon_key, countries, alliances, rl_agents, rank_map, turn_counter
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
                                        "last_attack_turn": None,
                                        "next_attack_turn": turn_counter + COALITION_INITIAL_ATTACK_DELAY_YEARS,
                                    }
                                    for m in accepted:
                                        countries[m]["current_coalition"] = coalition_name

                                    formation_bounty = 0
                                    for m in accepted:
                                        paid = _world_bank_pay_bounty(
                                            world_bank, countries[m], policy_cost(COALITION_FORMATION_BOUNTY, world_bank),
                                            reason="反霸權聯軍成立懸賞",
                                        )
                                        formation_bounty += paid
                                        countries[m]["last_coalition_bounty"] = paid

                                    action_success = True
                                    action_value += len(accepted) * 12 + formation_bounty / max(1, MONEY_RATIO)
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
                                        f"起因：{coalition_reason}；成員保留原有普通聯盟；"
                                        f"成立懸賞 {formation_bounty} 大洋。"
                                    )
                                else:
                                    print(
                                        f"[圍剿未成] 【{c_data['display_name']}】試圖號召各國牽制【{hegemon['display_name']}】，"
                                        f"但響應國不足 {COALITION_MIN_MEMBERS} 國。"
                                    )

                # Action 3: 基礎建設投資（支付現有資產，換取永久效率）
                elif action == 3:
                    investment = _apply_infrastructure_investment(c_data, world_bank)
                    if investment:
                        gain = investment["gain"]
                        c_data["last_infrastructure_investment"] = {"turn": turn_counter, **investment}
                        action_success = True
                        action_value = gain
                        if MARKET_ECONOMY_ENABLED:
                            cost_text = f"大洋 {investment['gold']}、木材 {investment['wood']}、金屬 {investment['metal']}"
                        else:
                            cost_text = _format_mixed_cost(investment)
                        print(f"[基礎建設] 【{c_data['display_name']}】支付 {cost_text}，基建 +{gain}，"
                              f"目前 {c_data['infrastructure']}/{INFRASTRUCTURE_MAX}。")

                # ----------------------------------------------------
                # Action 4: 背叛背刺同盟
                # ----------------------------------------------------                
                elif action == 4:
                    curr_a = c_data["current_alliance"]
                    if curr_a and curr_a in alliances:
                        partners = [m for m in alliances[curr_a] if m != attacker_key and countries[m]["is_alive"]]
                        if partners:
                            victim = random.choice(partners)  # 隨機選擇一名盟友背刺
                            steal_food = int(countries[victim]["food"] * 0.10)  # 偷取 10%
                            countries[victim]["food"] -= steal_food
                            c_data["food"] += steal_food
                            _war_add_hostility(
                                countries,
                                victim,
                                attacker_key,
                                WARSTATE["HOSTILITY_BETRAY"],
                            )

                            _leave_alliance(
                                attacker_key,
                                countries,
                                alliances,
                                reason="背叛背刺",
                            )
                            c_data["infamy"] = c_data.get("infamy", 0) + 50
                            action_success = True
                            action_value += steal_food
                            print(f"[背叛背刺] 【{c_data['display_name']}】撕毀條約！偷襲盟友【{countries[victim]['display_name']}】掠奪{steal_food}糧草！")

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
                        _clamp(c_data.get("military_target_ratio", 0.30) + 0.04, 0.10, 0.50)
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
                # Action 7: 調整產業配置（只移動勞動比例，不直接產生資源）
                # ----------------------------------------------------
                elif action == 7:
                    stock_ratios = {
                        resource: max(0.0, float(c_data.get(resource, 0) or 0))
                        / max(1.0, float(_market_target_stock(c_data, resource)))
                        for resource in MARKET_RESOURCES
                    }
                    shortage = min(stock_ratios, key=stock_ratios.get)
                    focus = {
                        "food": "FOOD", "wood": "WOOD", "metal": "METAL",
                    }[shortage]
                    if stock_ratios[shortage] >= 1.0:
                        focus = "BALANCED"
                    focus_name = {
                        "FOOD": "糧食優先", "WOOD": "木材優先",
                        "METAL": "金屬優先", "BALANCED": "均衡生產",
                    }[focus]
                    c_data["industry_focus"] = focus
                    c_data["industry_focus_turns"] = INDUSTRY_FOCUS_DURATION
                    c_data["industry_focus_name"] = focus_name
                    action_success = True
                    action_value = max(0.0, 1.0 - stock_ratios[shortage]) * 10.0
                    print(
                        f"[產業配置] 【{c_data['display_name']}】改採{focus_name}，"
                        f"持續 {INDUSTRY_FOCUS_DURATION} 年；本次沒有直接增加任何資源。"
                    )

                # ----------------------------------------------------
                # Action 8: 世界市場掛牌 / 報價
                # ----------------------------------------------------
                elif action == 8:
                    order = _market_place_ai_order(
                        attacker_key,
                        countries,
                        world_market,
                        turn_counter,
                    )
                    if order:
                        action_success = True
                        side_text = "買入" if order["side"] == "BUY" else "賣出"
                        action_value += order["qty"] * order["price"]
                        print(
                            f"📈 [世界市場掛牌] 【{c_data['display_name']}】{side_text}"
                            f" {order['qty']} {order['resource_name']}，"
                            f"報價 {order['price']:.2f} {world_bank.get('currency', WORLD_CURRENCY_NAME)}/單位。"
                        )
                        trades_now = _market_match_orders(
                            countries,
                            world_market,
                            world_bank,
                            turn_counter,
                        )
                        action_value += sum(
                            int(t.get("gross_gold", 0) or 0)
                            for t in trades_now
                            if t.get("buyer") == attacker_key
                            or t.get("seller") == attacker_key
                        )

                # ----------------------------------------------------
                # Action 9: 修復聲望（以大洋進行外交斡旋）
                # ----------------------------------------------------
                elif action == 9:
                    old_infamy = int(c_data.get("infamy", 0) or 0)
                    gold_stock = max(0, int(c_data.get("gold", 0) or 0))
                    if old_infamy > 0 and (not MARKET_ECONOMY_ENABLED or gold_stock >= policy_cost(60 * MONEY_RATIO, world_bank)):
                        if MARKET_ECONOMY_ENABLED:
                            min_cost = policy_cost(60 * MONEY_RATIO, world_bank)
                            max_cost = min(gold_stock, max(policy_cost(80 * MONEY_RATIO, world_bank), int(gold_stock * 0.16)))
                            diplomacy_cost = random.randint(min_cost, max(min_cost, max_cost))
                            c_data["gold"] -= diplomacy_cost
                            _world_bank_collect(world_bank, diplomacy_cost, category="policy")
                            cost_text = f"{diplomacy_cost} {world_bank.get('currency', WORLD_CURRENCY_NAME)}"
                            cost_bonus = int(min(10, diplomacy_cost / max(1, policy_cost(20 * MONEY_RATIO, world_bank))))
                        else:
                            diplomacy_cost = _pay_mixed_resource_cost(c_data)
                            cost_text = _format_mixed_cost(diplomacy_cost)
                            cost_bonus = min(10, _mixed_cost_value(diplomacy_cost) // 20)
                        reduction = random.randint(14, 28) + cost_bonus
                        c_data["infamy"] = max(0, old_infamy - reduction)
                        action_success = True
                        action_value += old_infamy - c_data["infamy"]
                        print(
                            f"🤝 [外交修復] 【{c_data['display_name']}】支付 {cost_text} 進行外交斡旋，"
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
                        and not _is_capitulation_protected(countries[k], turn_counter)
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

                # ----------------------------------------------------
                # Action 12: 鼓勵生育政策
                # ----------------------------------------------------
                elif action == 12:
                    action_success, spent = _apply_birth_policy(c_data, world_bank)
                    if action_success:
                        action_value += _mixed_cost_value(spent) if isinstance(spent, dict) else spent
                        immediate_births = max(0, int(c_data.get("last_birth_policy_gain", 0) or 0))
                        spent_text = (_format_mixed_cost(spent) if isinstance(spent, dict)
                                      else f"{spent} {world_bank.get('currency', WORLD_CURRENCY_NAME)}")
                        print(
                            f"👶 [鼓勵生育] 【{c_data['display_name']}】投入 {spent_text}，"
                            f"當期新增 {immediate_births} 人，未來 {BIRTH_POLICY_DURATION} 年出生率提高。"
                        )

                # ----------------------------------------------------
                # Action 13: 增產資源政策
                # ----------------------------------------------------
                elif action == 13:
                    action_success, spent = _apply_production_policy(c_data, world_bank)
                    if action_success:
                        action_value += _mixed_cost_value(spent) if isinstance(spent, dict) else spent
                        immediate = c_data.get("last_production_policy_gain", {}) or {}
                        spent_text = (_format_mixed_cost(spent) if isinstance(spent, dict)
                                      else f"{spent} {world_bank.get('currency', WORLD_CURRENCY_NAME)}")
                        print(
                            f"🏭 [增產補貼] 【{c_data['display_name']}】投入 {spent_text}，"
                            f"當期增產 糧:{immediate.get('food', 0)}／木:{immediate.get('wood', 0)}／"
                            f"金屬:{immediate.get('metal', 0)}，未來 {PRODUCTION_POLICY_DURATION} 年繼續增產。"
                        )

                # ----------------------------------------------------
                # Action 14: 外交金援
                # ----------------------------------------------------
                elif action == 14:
                    aid = _diplomatic_gold_aid(attacker_key, countries, alliances)
                    if aid:
                        target = aid["target"]
                        amount = aid["amount"]
                        action_success = True
                        action_value += amount
                        aid_text = (_format_mixed_cost(aid["transfers"])
                                    if not MARKET_ECONOMY_ENABLED else f"{amount} 大洋")
                        print(
                            f"💰 [外交金援] 【{c_data['display_name']}】向"
                            f"【{countries[target].get('display_name', target)}】提供 {aid_text}，"
                            f"以改善雙邊關係。"
                        )

                # ----------------------------------------------------
                # Action 15: 聯盟資源援助
                # ----------------------------------------------------
                elif action == 15:
                    aid = _alliance_resource_aid(attacker_key, countries, alliances)
                    if aid:
                        target = aid["target"]
                        transfers = aid["transfers"]
                        action_success = True
                        action_value += sum(int(v or 0) for v in transfers.values())
                        labels = {"food": "糧", "wood": "木", "metal": "金屬", "gold": "大洋"}
                        detail = "/".join(f"{labels.get(k,k)}:{v}" for k, v in transfers.items())
                        print(
                            f"🫱🏻‍🫲🏼 [聯盟援助] 【{c_data['display_name']}】支援"
                            f"【{countries[target].get('display_name', target)}】 {detail}。"
                        )

                # 重新計算最終戰力
                c_data["power"] = calculate_rts_power(c_data)

                # ----------------------------------------------------
                # RL V2 Reward：使用真正的 before -> after 快照
                # ----------------------------------------------------
                enforce_farmer_majority(c_data)
                c_data["power"] = calculate_rts_power(c_data)
                c_data["fortification"] = int(_clamp(c_data.get("fortification", 0), 0, 100))

                if action == 0:
                    before_data["last_war_win_chance"] = float(
                        c_data.get("last_war_win_chance", 0.5) or 0.5
                    )
                    before_data["current_war_count"] = current_war_count

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
                c_data["survival_milestone_reward_pending"] = 0.0

                c_data["last_action"] = RL_ACTIONS.get(action, str(action))
                c_data["last_reward"] = round(reward, 2)
                c_data["ai_decision_count"] = agent.decision_count
                c_data["ai_action_stats"] = agent.action_stats
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
                    next_valid_actions=get_valid_rl_actions(
                        attacker_key, countries, alliances, anti_hegemon_coalitions, alive_sorted, turn_counter
                    ),
                    action_success=action_success,
                )
                if agent._last_fiscal_state is not None:
                    next_reserved, _ = (_market_order_reservations(world_market, attacker_key)
                                        if MARKET_ECONOMY_ENABLED else (0, {}))
                    next_cash = (max(0, int(c_data.get('gold', 0) or 0) - next_reserved)
                                 if MARKET_ECONOMY_ENABLED else 0)
                    birth_cost = policy_cost(BIRTH_POLICY_GOLD_COST, world_bank)
                    production_cost = policy_cost(PRODUCTION_POLICY_GOLD_COST, world_bank)
                    next_fiscal_state = fiscal_state(
                        c_data, world_bank, next_cash,
                        *(_market_target_stock(c_data, r) for r in MARKET_RESOURCES),
                        birth_cost, production_cost,
                    )
                    next_engine_valid = get_valid_rl_actions(
                        attacker_key, countries, alliances, anti_hegemon_coalitions, alive_sorted, turn_counter)
                    if MARKET_ECONOMY_ENABLED:
                        next_fiscal_valid = fiscal_valid_actions(
                            c_data, next_engine_valid, next_cash, birth_cost, production_cost,
                            _infrastructure_investment_cost(c_data),
                        )
                    else:
                        next_fiscal_valid = [0] + ([1] if 12 in next_engine_valid else []) \
                            + ([2] if 13 in next_engine_valid else []) \
                            + ([3] if 3 in next_engine_valid else [])
                    fiscal_reward = (0.0 if agent._last_fiscal_action == 0
                                     else -0.02 if action_success else -0.12)
                    agent.fiscal_policy.learn(
                        agent._last_fiscal_state, agent._last_fiscal_action,
                        fiscal_reward, next_fiscal_state, next_fiscal_valid,
                        success=action_success,
                    )
                agent.schedule_delayed_evaluation(
                    before_data,
                    action,
                    turn_counter,
                    action_success,
                )

        # V8_4 Layer B：市場子策略獨立決策，不再與國家戰略搶同一次 Action。
        if not MARKET_ECONOMY_ENABLED:
            _disable_market_runtime(world_market)
        market_records = []
        for country_key in (active_countries if MARKET_ECONOMY_ENABLED else []):
            if country_key not in countries or not countries[country_key].get("is_alive", True):
                continue
            agent = rl_agents[country_key]
            before_market = _rl_snapshot(countries[country_key])
            market_state = _market_layer_state(countries[country_key], world_market)
            need_ratios = {
                res: max(0.0, float(countries[country_key].get(res, 0) or 0))
                / max(1.0, _market_target_stock(countries[country_key], res))
                for res in MARKET_RESOURCES
            }
            countries[country_key]["market_need_resource"] = MARKET_RESOURCE_META[min(need_ratios, key=need_ratios.get)]["name"]
            market_valid = _market_layer_valid_actions(country_key, countries, world_market)
            market_action = agent.market_policy.choose(market_state, market_valid)
            price_state = market_state + (MARKET_ACTIONS[market_action],)
            price_action = agent.market_price_policy.choose(price_state, range(3)) if market_action else 1
            size_action = agent.market_size_policy.choose(price_state, range(3)) if market_action else 0
            order = _market_place_layered_order(
                country_key, countries, world_market, turn_counter,
                market_action, price_action, size_action,
            )
            market_records.append({
                "country": country_key, "state": market_state, "action": market_action,
                "price_state": price_state, "price_action": price_action, "size_action": size_action,
                "order_id": order.get("id") if order else None,
                "order": dict(order) if order else None, "before": before_market,
            })

        # V8_4 Layer C：聯盟子策略可與戰略及市場同輪執行。
        for country_key in active_countries:
            if country_key not in countries or not countries[country_key].get("is_alive", True):
                continue
            agent = rl_agents[country_key]
            state = _alliance_layer_state(country_key, countries, alliances)
            valid = _alliance_layer_valid_actions(country_key, countries, alliances)
            action = agent.alliance_policy.choose(state, valid)
            own_before = min(
                countries[country_key].get(res, 0) / max(1.0, _market_target_stock(countries[country_key], res))
                for res in MARKET_RESOURCES
            )
            success, value, detail = _alliance_execute_layer_action(
                country_key, action, countries, alliances, world_market, world_bank, turn_counter
            )
            own_after = min(
                countries[country_key].get(res, 0) / max(1.0, _market_target_stock(countries[country_key], res))
                for res in MARKET_RESOURCES
            )
            reward = (0.15 if success else (-0.05 if action else 0.0)) + _clamp((own_after - own_before) * 0.4, -1.0, 0.4)
            next_state = _alliance_layer_state(country_key, countries, alliances)
            next_valid = _alliance_layer_valid_actions(country_key, countries, alliances)
            agent.alliance_policy.learn(state, action, reward, next_state, next_valid, success=success)
            countries[country_key]["last_alliance_policy"] = ALLIANCE_ACTIONS[action]
            countries[country_key]["last_alliance_reward"] = round(reward, 3)

        trades_this_turn = (_market_match_orders(countries, world_market, world_bank, turn_counter)
                            if MARKET_ECONOMY_ENABLED else [])
        traded_order_ids = {
            order_id
            for trade in trades_this_turn
            for order_id in (trade.get("buy_order_id"), trade.get("sell_order_id"))
            if order_id
        }
        for record in market_records:
            country_key = record["country"]
            agent = rl_agents[country_key]
            after_market = _rl_snapshot(countries[country_key])
            before = record["before"]
            def safety(snapshot):
                return min(
                    max(0.0, float(snapshot.get(res, 0) or 0)) / max(1.0, _market_target_stock(snapshot, res))
                    for res in MARKET_RESOURCES
                )
            filled = bool(record["order_id"] and record["order_id"] in traded_order_ids)
            own_trades = [t for t in trades_this_turn if record["order_id"] in
                          (t.get("buy_order_id"), t.get("sell_order_id"))] if filled else []
            market_reward = _clamp((safety(after_market) - safety(before)) * 1.5, -1.0, 1.0)
            before_ratios = {
                res: max(0.0, float(before.get(res, 0) or 0)) / max(1.0, _market_target_stock(before, res))
                for res in MARKET_RESOURCES
            }
            shortage_resource = min(before_ratios, key=before_ratios.get)
            surplus_resource = max(before_ratios, key=before_ratios.get)
            action_index = int(record["action"])
            if 1 <= action_index <= 3:
                bought = MARKET_RESOURCES[action_index - 1]
                if bought == shortage_resource and before_ratios[bought] < 1.0:
                    market_reward += 0.12 + min(0.18, (1.0 - before_ratios[bought]) * 0.20)
                elif before_ratios[shortage_resource] < 0.75:
                    market_reward -= 0.10
            elif 4 <= action_index <= 6:
                sold = MARKET_RESOURCES[action_index - 4]
                if sold == surplus_resource and before_ratios[sold] > 1.25:
                    market_reward += 0.10
                elif before_ratios[sold] < 0.90:
                    market_reward -= 0.16
            if record["action"]:
                market_reward += 0.10 if filled else -0.04
            elif safety(before) < 0.75:
                minimum_price = min(float(meta["seed_price"]) for meta in MARKET_RESOURCE_META.values())
                if float(before.get("gold", 0) or 0) >= minimum_price:
                    market_reward -= 0.10
            next_state = _market_layer_state(countries[country_key], world_market)
            next_valid = _market_layer_valid_actions(country_key, countries, world_market)
            agent.market_policy.learn(record["state"], record["action"], market_reward, next_state, next_valid, success=filled)
            if record["action"]:
                next_price_state = next_state + (MARKET_ACTIONS[record["action"]],)
                price_reward = _clamp(market_reward + _market_quote_quality(record["order"], own_trades), -1.0, 1.0)
                agent.market_price_policy.learn(record["price_state"], record["price_action"], price_reward, next_price_state, range(3), success=filled)
                agent.market_size_policy.learn(record["price_state"], record["size_action"], market_reward, next_price_state, range(3), success=filled)
            countries[country_key]["last_market_policy"] = MARKET_ACTIONS[record["action"]]
            countries[country_key]["last_market_reward"] = round(market_reward, 3)

        if MARKET_ECONOMY_ENABLED:
            _market_health_update(world_market, world_bank, countries, turn_counter)
        recycled = (treasury_circulation(world_bank, countries, turn_counter,
                                         money_ratio=MONEY_RATIO)
                    if MARKET_ECONOMY_ENABLED else [])
        if recycled:
            # 同輪不重複走原本的逆週期發行路徑；先使用既有金庫。
            world_bank['stabilization_last_turn'] = turn_counter
            print(f"🏦 [金庫回流] 回流 {sum(amount for _key, amount in recycled)}"
                  f" {world_bank.get('currency', WORLD_CURRENCY_NAME)}，"
                  f"支援 {len(recycled)} 國，發行量不變。")
        elif MARKET_ECONOMY_ENABLED:
            _world_bank_recirculate_liquidity(world_bank, countries, turn_counter, world_market)
        currency_audit = (_currency_audit(countries, world_bank, raise_on_error=False)
                          if MARKET_ECONOMY_ENABLED else {"ok": True})
        if MARKET_ECONOMY_ENABLED and not currency_audit["ok"]:
            print(
                f"🚨 [貨幣稽核] 守恆差額 {currency_audit['gap']}；"
                f"發行 {currency_audit['issued']}／可核對 {currency_audit['accounted']}。"
            )
        if turn_counter % 100 == 0:
            try:
                _write_rl_monitoring(turn_counter, countries, rl_agents, world_market, world_bank)
            except Exception as error:
                print(f"⚠️ [RL 監測] 寫入失敗: {error}")

        # 6. 死亡與世代重生機制 (Respawn Logic)
        for name, data in countries.items():
            if not data["is_alive"]:
                if dead_mode == 0:  # 冷卻模式
                    if data["death_respawn_cooldown"] > 0:
                        data["death_respawn_cooldown"] -= 1  # 扣除冷卻回合
                    else:
                        # V6.6.2 亡國重建：
                        # 延續滅亡前最後的國號根，Roman 世代 +1；
                        # 復國後的第一個世代政權類型統一標示為「重建政權」。
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
                        if name in rl_agents:
                            rl_agents[name].decay_political_memory("亡國重建")
                        
                        # 重置基礎資源與人口
                        data["houses"] = 5
                        data["pop_total"] = 10
                        data["farmers"] = 7
                        data["soldiers"] = 3
                        data["food"] = random.randint(180, 300)
                        data["wood"] = random.randint(100, 180)
                        data["metal"] = random.randint(60, 120)
                        data["gold"] = 0
                        data["currency_version"] = CURRENCY_VERSION
                        # 復國後視為新手國家：依頂部 REBUILD_PROTECTION_YEARS 設定保護期。
                        data["newbie_protection_until_turn"] = int(turn_counter) + REBUILD_PROTECTION_YEARS
                        data["rebuild_protection_started_turn"] = int(turn_counter)
                        data["rebuild_protection_until_turn"] = int(turn_counter) + REBUILD_PROTECTION_YEARS
                        data["protection_remaining_years"] = REBUILD_PROTECTION_YEARS
                        data["protection_remaining_ratio"] = 1.0
                        data["survival_preparation_urgency"] = 0.0
                        data["war_supply_years"] = 0.0
                        data["security_risk_score"] = 0.0
                        data["security_posture"] = "保護準備"
                        data["survival_milestone_awarded"] = 0
                        data["survival_milestone_reward_pending"] = 0.0
                        data["subjugation_count"] = 0
                        data["protector_country"] = ""
                        data["vassal_until_turn"] = 0
                        data["capitulation_protection_until_turn"] = 0
                        data["last_capitulation_turn"] = 0
                        data["birth_policy_turns"] = 0
                        data["production_policy_turns"] = 0
                        data["policy_summary"] = "無"
                        _world_bank_grant(
                            world_bank,
                            data,
                            policy_cost(WORLD_BANK_RESPAWN_GRANT, world_bank),
                            reason="重建援助",
                        )
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
                        # 國號仍延續滅亡前最後名稱；
                        # 但復國後第一代明確標記為「重建政權」。
                        # 例如：
                        # 挫蛋先鋒(五世) → 滅國 → 挫蛋先鋒II【重建政權】
                        # 下一次正統交接後再回到「正統政權」。
                        data["regime_type"] = "重建政權"
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

        # 7. 臨時反霸權聯軍：使命完成、威脅解除、逾期與冷卻
        rank_map = {
            k: idx + 1
            for idx, k in enumerate(alive_sorted)
        }

        for coalition_name in list(anti_hegemon_coalitions.keys()):
            info = anti_hegemon_coalitions.get(coalition_name, {})

            if not isinstance(info, dict):
                del anti_hegemon_coalitions[coalition_name]
                continue

            target_id = info.get("target")
            target_c = countries.get(target_id)
            info.setdefault("last_attack_turn", None)
            info.setdefault(
                "next_attack_turn",
                int(info.get("created_turn", turn_counter) or turn_counter)
                + COALITION_INITIAL_ATTACK_DELAY_YEARS,
            )

            members = [
                m
                for m in (info.get("members") or [])
                if m in countries
                and countries[m].get("is_alive", True)
            ]

            info["members"] = members

            end_reason = None

            # ------------------------------------------------------------
            # ① 目標已滅亡
            # ------------------------------------------------------------
            if not target_c or not target_c.get("is_alive", True):
                end_reason = "討伐目標已覆滅"

            # ------------------------------------------------------------
            # ② 聯軍有效成員不足
            # ------------------------------------------------------------
            elif len(members) < 2:
                end_reason = "聯軍有效成員不足"

            # ------------------------------------------------------------
            # ③ 聯軍期限已滿
            # ------------------------------------------------------------
            elif turn_counter >= int(
                info.get(
                    "expires_turn",
                    turn_counter + 1,
                )
            ):
                end_reason = "聯軍任務期限已滿"

            else:
                target_rank = rank_map.get(
                    target_id,
                    999,
                )

                target_power = max(
                    0,
                    target_c.get("power", 0),
                )

                target_share = (
                    target_power
                    / max(
                        1,
                        total_world_power,
                    )
                )

                other_powers = [
                    countries[k].get("power", 0)
                    for k in alive_sorted
                    if k != target_id
                ]

                strongest_other = (
                    max(other_powers)
                    if other_powers
                    else 1
                )

                lead_ratio = (
                    target_power
                    / max(
                        1,
                        strongest_other,
                    )
                )

                age = (
                    turn_counter
                    - int(
                        info.get(
                            "created_turn",
                            turn_counter,
                        )
                    )
                )

                # --------------------------------------------------------
                # ④ 取得目前國際忌憚值
                # --------------------------------------------------------
                international_dread = max(
                    0,
                    int(
                        target_c.get(
                            "international_dread",
                            0,
                        )
                        or 0
                    ),
                )

                # --------------------------------------------------------
                # ⑤ 威脅解除
                #
                # 至少維持 3 Loop。
                #
                # 只有當「國際忌憚值已降至門檻以下」，
                # 且霸權地位／軍力優勢也明顯下降時，
                # 才提前解除聯軍。
                #
                # 這樣可以避免：
                #
                #   忌憚值 30,000
                #   ↓
                #   某一回合跌到第 4 名
                #   ↓
                #   聯軍立即消失
                #
                # 而是讓國際社會仍然記得它過去造成的威脅。
                # --------------------------------------------------------
                if age >= 3:

                    # 情況 A：
                    # 忌憚值已經低於 10,000，
                    # 且已經跌出世界前三。
                    if (
                        international_dread
                        < INTERNATIONAL_DREAD_CANDIDATE_THRESHOLD
                        and target_rank > 3
                    ):
                        end_reason = (
                            "國際忌憚值已解除，"
                            "且霸權已跌出前三名"
                        )

                    # 情況 B：
                    # 忌憚值低於 10,000，
                    # 同時世界總體力量占比低，
                    # 且不再具有明顯軍力領先。
                    elif (
                        international_dread
                        < INTERNATIONAL_DREAD_CANDIDATE_THRESHOLD
                        and target_share < 0.10
                        and lead_ratio < 1.30
                    ):
                        end_reason = (
                            "國際忌憚與霸權軍力優勢均已解除"
                        )

                # --------------------------------------------------------
                # ⑥ 聯軍仍然存在
                # --------------------------------------------------------
                if end_reason is None:
                    if age % 10 == 0:
                        print(
                            f"[聯軍持續] {coalition_name}｜"
                            f"目標【{target_c.get('display_name', target_id)}】｜"
                            f"世界排名 #{target_rank}｜"
                            f"國際忌憚值 {international_dread:,}｜"
                            f"聯軍年齡 {age}/{COALITION_MAX_DURATION}。"
                        )

            # ------------------------------------------------------------
            # ⑦ 執行聯軍解散
            # ------------------------------------------------------------
            if end_reason:
                target_name = (
                    target_c.get(
                        "display_name",
                        target_id,
                    )
                    if target_c
                    else "霸權"
                )

                print(
                    f"[聯軍解散] {coalition_name} "
                    f"對【{target_name}】的任務結束："
                    f"{end_reason}。"
                    f"各國保留原有普通聯盟。"
                )

                # 目標冷卻
                if target_id:
                    coalition_target_cooldowns[
                        target_id
                    ] = (
                        turn_counter
                        + COALITION_COOLDOWN_YEARS
                    )

                # 成員冷卻
                for m in members:
                    coalition_member_cooldowns[
                        m
                    ] = (
                        turn_counter
                        + COALITION_COOLDOWN_YEARS
                    )

                    if (
                        countries.get(m, {}).get(
                            "current_coalition"
                        )
                        == coalition_name
                    ):
                        countries[m][
                            "current_coalition"
                        ] = ""

                del anti_hegemon_coalitions[
                    coalition_name
                ]


        # ------------------------------------------------------------
        # 清理已過期冷卻
        # 避免 dict 永久膨脹
        # ------------------------------------------------------------
        coalition_target_cooldowns = {
            k: v
            for k, v in coalition_target_cooldowns.items()
            if int(v or 0) > turn_counter
        }

        coalition_member_cooldowns = {
            k: v
            for k, v in coalition_member_cooldowns.items()
            if int(v or 0) > turn_counter
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

        season_elapsed_years = max(0, int(turn_counter) - int(season_start_turn))
        season_remaining_years = max(0, YEARS_PER_SEASON - season_elapsed_years)
        rank_text = f"===== 亂世演算 第 {count_round} 屆 戰力大戰 ===== 剩餘 {season_remaining_years} 年結束\n"
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
            ai_action = data.get("last_action", "")
            ai_reward = data.get("last_reward", 0.0)
            ai_personality = data.get("ai_personality", "尚未查明")
            ai_str = f" [{ai_personality}]"
            # ai_str = f" [{ai_action} R:{ai_reward:+.1f}]" if ai_action else ""
            war_str = " [⚔戰中]" if data.get("current_wars") else ""

            if i == 0:  # 第一名霸主處理
                if pwr > max_power:  # 更新歷史最高戰力紀錄
                    max_power = pwr
                    max_person = disp_label
                    max_round = count_round
                rank_text += f"歷史最高霸主紀錄 = {max_power} ({max_person} 第{max_round}屆)\n"
                rank_text += f"{medals[i]} {pwr} - {disp_label}{ai_str}{war_str}{champions_str}{status_str}\n"
            else:  # 其他名次顯示與前一名的戰力差距 (-diff)
                diff = sorted_countries[i - 1][1]["power"] - pwr
                rank_text += f"{medals[i]} {pwr} - {disp_label}{ai_str}{war_str}{champions_str}{status_str} (-{diff})\n"

        # 寫入文字檔排行榜：原子替換，避免 UI 讀到半份內容。
        try:
            _atomic_write_text(save_path("Live_Ranking.txt"), rank_text.strip())
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
            _war_refresh_country_status(countries, active_wars, turn_counter)

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
                    # 只做事後解釋：個性由已學到的 Q 值反推，不回頭干預決策。
                    c_data["ai_personality"] = agent.inferred_personality()
                    c_data.pop("personality", None)
                    c_data["ai_policy"] = RL_ALGORITHM
                    c_data["ai_decision_count"] = agent.decision_count
                    c_data["ai_epsilon"] = round(agent.strategic_policy.effective_epsilon(), 4)
                    c_data["q_state_count"] = len(agent.strategic_policy.q_table)
                    c_data["market_q_state_count"] = len(agent.market_policy.q_table)
                    c_data["alliance_q_state_count"] = len(agent.alliance_policy.q_table)
                    c_data["strategic_td_error"] = round(agent.strategic_policy.td_error_ema, 4)

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
            current_season_elapsed_years = min(
                YEARS_PER_SEASON,
                max(0, int(turn_counter) - int(season_start_turn)),
            )
            current_season_elapsed = current_season_elapsed_years * SECONDS_PER_YEAR
            current_season_remaining = max(
                0.0,
                SEASON_DURATION_SECONDS - current_season_elapsed,
            )
            cumulative_runtime_seconds = (
                float(completed_runtime_seconds)
                + current_season_elapsed
            )
            snapshot_id = f"R{int(count_round)}-T{int(turn_counter)}-{uuid.uuid4().hex[:12]}"
            # 存檔前再次核對，涵蓋本輪稍早發生的亡國重建與援助。
            _currency_audit(countries, world_bank, raise_on_error=True)

            # 國家 / 外交 / 戰爭檔使用 atomic + compact JSON，降低 I/O 並防止半寫入。
            _atomic_write_json(
                countries_file,
                {
                    "countries": countries,
                    "world_mode": current_world_mode,
                    "world_bank": world_bank,
                    "world_market": world_market,
                    "turn_counter": turn_counter,
                    "season_start_turn": int(season_start_turn),
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
                    "engine_version": ENGINE_VERSION,
                    "snapshot_id": snapshot_id,
                    "simulation_seed": simulation_seed,
                    "rng_state": random.getstate(),
                },
                compact=COMPACT_FORMAT,
            )

            _atomic_write_json(
                alliances_file,
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
                    "season_start_turn": int(season_start_turn),
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
                    "engine_version": ENGINE_VERSION,
                    "simulation_seed": simulation_seed,
                    "snapshot_id": snapshot_id,
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
                "season_start_turn": int(season_start_turn),
                "season_elapsed_years": int(current_season_elapsed_years),
                "season_remaining_years": int(max(0, YEARS_PER_SEASON - current_season_elapsed_years)),
                "saved_at_unix": round(checkpoint_now, 3),
                "engine_version": ENGINE_VERSION,
                "simulation_seed": simulation_seed,
                "snapshot_id": snapshot_id,
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
        if (int(turn_counter) - int(season_start_turn)) >= YEARS_PER_SEASON:
            if sorted_countries:
                champion_key, champion_data = sorted_countries[0]
                champion_power = champion_data["power"]

                # 屆末終局獎勵：冠軍遠高於亞軍、季軍與其他名次。
                # 所有國家都收到排名結果，讓「爭取當屆第一」成為共同最終目標。
                season_size = max(1, len(sorted_countries))
                for finish_rank, (country_key, data) in enumerate(sorted_countries, 1):
                    if finish_rank == 1:
                        season_q_reward = SEASON_CHAMPION_Q_REWARD
                    elif finish_rank == 2:
                        season_q_reward = SEASON_RUNNER_UP_Q_REWARD
                    elif finish_rank == 3:
                        season_q_reward = SEASON_THIRD_Q_REWARD
                    elif finish_rank <= 10:
                        season_q_reward = 0.80 - (finish_rank - 4) * 0.10
                    elif finish_rank <= 25:
                        season_q_reward = 0.10
                    else:
                        percentile = (finish_rank - 25) / max(1, season_size - 25)
                        season_q_reward = -0.15 - 0.70 * percentile
                    if not data.get("is_alive", True):
                        season_q_reward = min(season_q_reward, -1.50)
                    agent = rl_agents.get(country_key)
                    credited = bool(
                        agent and agent.apply_competition_reward(season_q_reward)
                    )
                    data["last_season_finish_rank"] = finish_rank
                    data["last_season_q_reward"] = round(season_q_reward, 3)
                    data["last_season_reward_credited"] = credited

                if not isinstance(champion_data.get("championship_records"), list):
                    champion_data["championship_records"] = []

                # 紀錄冠軍歷史
                champion_data["championship_records"].append(
                    f"R{count_round}__{champion_power}__{champion_data['display_name']}"
                )
                physical_rewards = _award_season_champion_rewards(
                    champion_key, countries, alliances, world_bank, turn_counter
                )
                alliance_reward_text = "、".join(
                    f"{countries[m].get('display_name', m)}:{amount}"
                    for m, amount in physical_rewards.get("members", [])
                ) or "無"
                print(
                    f"💰 [冠軍實體獎勵] 冠軍【{champion_data['display_name']}】獲 {physical_rewards['champion']} 大洋；"
                    f"聯盟成員獎勵合計 {physical_rewards['alliance_pool']}（{alliance_reward_text}）。"
                )
                print(f"🏆 [第 {count_round} 屆結算] 恭喜【{champion_data['display_name']}】以 {champion_power} 戰力獲勝！")
                print(
                    f"🧠 [爭冠學習] 冠軍 Q 獎勵 +{SEASON_CHAMPION_Q_REWARD:.1f}；"
                    f"亞軍 +{SEASON_RUNNER_UP_Q_REWARD:.1f}；"
                    f"季軍 +{SEASON_THIRD_Q_REWARD:.1f}，其餘依名次递減。"
                )
                # 終局獎勵屬於重要學習結果，不等下一個定期存檔點。
                save_all_agents(rl_agents, file_path=q_tables_file)

            # 本屆正式完成；累積時間只計本屆規定秒數，
            # 避免 Game Loop 排程延遲造成額外秒數灌入下一屆。
            old_policy_index = float(world_bank.get("policy_price_index", 1.0) or 1.0)
            new_policy_index = (policy_index_settle_season(
                world_bank, countries, world_market, MARKET_RESOURCE_META, count_round, turn_counter
            ) if MARKET_ECONOMY_ENABLED else old_policy_index)
            world_bank["currency_rename_trigger_rate"] = WORLD_BANK_ISSUE_TRIGGER_RATE
            changed_resource = (settle_currency_name(
                world_bank, world_market, MARKET_RESOURCE_META,
                WORLD_CURRENCY_NAME_OPTIONS, count_round, turn_counter
            ) if MARKET_ECONOMY_ENABLED else None)
            if changed_resource:
                _redenominate_currency(world_bank, countries, world_market, factor=10)
                print(f"💱 [貨幣重定面額] {MARKET_RESOURCE_META[changed_resource]['name']}降至預設價 10% 或以下；"
                      f"幣名改為 {world_bank['currency']}，國家餘額、銀行帳本及市場報價均乘 10，無新發購買。")
            if abs(new_policy_index - old_policy_index) > 1e-8:
                print(f"📊 [政策價格指數] 第 {count_round} 屆：{old_policy_index:.4f} → {new_policy_index:.4f}；"
                      f"下屆生育費 {policy_cost(BIRTH_POLICY_GOLD_COST, world_bank):,} {world_bank['currency']}。")
            completed_runtime_seconds += float(time_total)
            count_round += 1  # 進入下一屆
            season_start_turn = int(turn_counter)

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
        if max_turns and turn_counter >= max_turns:
            print(f"🧪 [測試模式] 已完成指定的 {max_turns} 輪，正常停止。")
            flush_game_log(force=True)
            break
        with _simulation_speed_lock:
            loop_delay = _simulation_delay_seconds
        # 每回合總週期預設精準控制為 2 秒；運算本身花費的時間不再額外疊加。
        time.sleep(max(0.0, loop_delay - (time.monotonic() - loop_started_at)))
        if turn_counter % GC_INTERVAL_TURNS == 0:
            gc.collect()


# 程式進入點 (Main Entry)
if __name__ == "__main__":
    # 建立多線程背景執行 thread_stat_monitor 函式 (Daemon 模式隨主線程結束)
    t2 = threading.Thread(target=thread_stat_monitor, daemon=True)
    t2.start()  # 啟動線程

    try:
        while t2.is_alive():
            t2.join(timeout=1.0)
    except KeyboardInterrupt:  # 監聽 Ctrl+C 終止訊號，實現平滑離開
        pass
