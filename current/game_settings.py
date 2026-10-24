"""V12 遊戲集中設定：修改後請關閉並重新啟動遊戲。

快速導覽（可用 Ctrl+F 搜尋以下段名或參數名）：
  總開關 / 世界、聯盟、戰爭、經濟與AI / 介面、字型、顏色與欄寬
  聯盟信心與歷史保留 / 持續戰爭與援軍 / 軍備子策略 / 國家編年史 / 世界圖書館

所有設定保留移植前的預設值。機率通常使用0至1，時間註明秒／毫秒／世界年。
修改基本參數會在下次啟動時重新推算其下方的衍生值；衍生值通常不直接改。
已寫入存檔的國家資產、貨幣名稱與其他世界狀態不會因改初始設定而重建。
結構版本、行動編碼、Q表維度與執行中的快取留在原模組，不作調整參數。
字典鍵名代表現有功能的索引；修改數值即可，請保留鍵名。
"""
import os
from copy import deepcopy as _deepcopy

# ============================================================================
# 總開關
# ============================================================================
# 世界圖書館：True啟用；False停止觀測、出版、AI查閱、回顧及檔案讀寫，並隱藏分頁。
# 關閉不刪除既有world_library.json。此包沿用上次設定：預設關閉。
WORLD_LIBRARY_ENABLED = False


def world_library_enabled():
    """相容環境變數：0可另行強制關閉，1不會蓋過上面的False。"""
    return bool(WORLD_LIBRARY_ENABLED) and os.environ.get("亂世演算_LIBRARY_ENABLED", "1") != "0"


def get_setting(name):
    """各模組在啟動時取值；可變容器複製一份，避免執行期改動污染設定模板。"""
    return _deepcopy(globals()[name])


# ============================================================================
# 世界、聯盟、戰爭、經濟與AI
# ============================================================================
# 貨幣與市場總開關；True啟用金幣帳本及交易AI，False按資源比例支付政策成本。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_ECONOMY_ENABLED
MARKET_ECONOMY_ENABLED = False

# 市場關閉時的政策資源成本比例，例如0.10代表10%。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RESOURCE_POLICY_COST_RATE
RESOURCE_POLICY_COST_RATE = 0.10

# 世界曆顯示的起始年份；不會替既有存檔重算年份。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_START_YEAR
WORLD_START_YEAR = 1

# 每回合對應的世界年數；本版時間流程以1年一回合設計，維持1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: YEARS_PER_TURN
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
YEARS_PER_TURN = 1

# 啟動時預設每世界年等待幾秒；遊戲內速度控制可在執行時覆蓋此值。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECONDS_PER_YEAR
SECONDS_PER_YEAR = 2.0

# 每屆持續的回合／年數；預設500。進階參數：圖書館的百年模板仍按500年設計，變更屆長前請先關閉圖書館。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: YEARS_PER_SEASON
YEARS_PER_SEASON = 500

# 自動推算：每屆預設現實秒數＝屆長×每年秒數，通常不直接改。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_DURATION_SECONDS
SEASON_DURATION_SECONDS = YEARS_PER_SEASON * SECONDS_PER_YEAR

# 自動推算：每屆現實秒數的舊名稱相容別名。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_SECONDS
SEASON_SECONDS = SEASON_DURATION_SECONDS

# 新世界初始國家的保護期，單位：世界年。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: NEW_COUNTRY_PROTECTION_YEARS
NEW_COUNTRY_PROTECTION_YEARS = 10

# 國家重建後的保護期，單位：世界年。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: REBUILD_PROTECTION_YEARS
REBUILD_PROTECTION_YEARS = 200

# True會限制保護期主動攻擊及相關參戰行為；False取消此限制。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: REBUILD_PROTECTION_BLOCK_ATTACK
REBUILD_PROTECTION_BLOCK_ATTACK = True

# True會限制重建保護期結盟；False允許結盟。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: REBUILD_PROTECTION_BLOCK_ALLIANCE
REBUILD_PROTECTION_BLOCK_ALLIANCE = False

# 保護結束前多少年開始加強生存與備戰評估。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SURVIVAL_PREPARATION_WINDOW_YEARS
SURVIVAL_PREPARATION_WINDOW_YEARS = 50

# 生存風險分數低於此值時視為安全。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECURITY_SAFE_THRESHOLD
SECURITY_SAFE_THRESHOLD = 35

# 生存風險分數達此值時視為危急。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECURITY_CRITICAL_THRESHOLD
SECURITY_CRITICAL_THRESHOLD = 70

# 保護結束時期望達成的最低士兵／人口比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECURITY_TARGET_SOLDIER_RATIO
SECURITY_TARGET_SOLDIER_RATIO = 0.25

# 安全準備評估期望達成的城防值。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECURITY_TARGET_FORTIFICATION
SECURITY_TARGET_FORTIFICATION = 40

# 安全準備評估期望保留的戰爭補給年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECURITY_TARGET_SUPPLY_YEARS
SECURITY_TARGET_SUPPLY_YEARS = 5.0

# 保護結束後的存續獎勵檢查時間點，單位：年。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SECURITY_POST_PROTECTION_MILESTONES
SECURITY_POST_PROTECTION_MILESTONES = (25, 50, 100)

# 普通聯盟最多成員國數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_MAX_MEMBERS
ALLIANCE_MAX_MEMBERS = 5

# 有空缺聯盟時，優先申請加入現有聯盟的機率；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_EXISTING_JOIN_CHANCE
ALLIANCE_EXISTING_JOIN_CHANCE = 0.80

# 按目前盟員數給予的入盟加成；字典鍵為成員數，值為額外機率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_UNDERFILLED_JOIN_BONUS
ALLIANCE_UNDERFILLED_JOIN_BONUS = {
    1: 0.20,
    2: 0.16,
    3: 0.10,
    4: 0.05,
}

# 主權結算前允許先附庸幾次；0直接滅國、1首次先附庸。拒和淪陷分支仍依本版既有規則處理。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SUBJUGATION_BEFORE_ANNEXATION
SUBJUGATION_BEFORE_ANNEXATION = 0

# 保護結束前最後幾年，確保國家可獲自主決策機會。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PRE_RELEASE_GUARANTEED_ACTION_YEARS
PRE_RELEASE_GUARANTEED_ACTION_YEARS = 50

# 保護結束後仍套用過渡期外交保護的年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: POST_PROTECTION_TRANSITION_YEARS
POST_PROTECTION_TRANSITION_YEARS = 50

# 攻擊剛脫保國家時，攻擊目標評分扣分。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: POST_PROTECTION_TARGET_SCORE_PENALTY
POST_PROTECTION_TARGET_SCORE_PENALTY = 45.0

# 攻擊過渡期國家造成的額外惡名。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: POST_PROTECTION_ATTACK_INFAMY
POST_PROTECTION_ATTACK_INFAMY = 18

# 攻擊過渡期國家造成的額外國際忌憚值。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: POST_PROTECTION_ATTACK_DREAD
POST_PROTECTION_ATTACK_DREAD = 6000

# 攻擊過渡期國家造成的國內穩定損失。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: POST_PROTECTION_ATTACK_STABILITY_LOSS
POST_PROTECTION_ATTACK_STABILITY_LOSS = 6.0

# 極端敵我兵力差下，本土防禦加成的最高比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: HOMELAND_DEFENSE_BONUS_MAX
HOMELAND_DEFENSE_BONUS_MAX = 0.35

# 附庸狀態的持續年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: VASSAL_DURATION_YEARS
VASSAL_DURATION_YEARS = 150

# 投降或主權結算後適用的保護年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: CAPITULATION_PROTECTION_YEARS
CAPITULATION_PROTECTION_YEARS = 40

# 附庸相關資源賠付比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: VASSAL_REPARATION_RATE
VASSAL_REPARATION_RATE = 0.12

# 宣戰後集結期的最短年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WAR_MUSTER_YEARS_MIN
WAR_MUSTER_YEARS_MIN = 10

# 宣戰後集結期的最長年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WAR_MUSTER_YEARS_MAX
WAR_MUSTER_YEARS_MAX = 20

# 士兵占人口低於此比例時，可能進入生存戒嚴。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARTIAL_LAW_TRIGGER_SOLDIER_RATIO
MARTIAL_LAW_TRIGGER_SOLDIER_RATIO = 0.05

# 士兵占人口回升至此比例後解除生存戒嚴。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARTIAL_LAW_RELEASE_SOLDIER_RATIO
MARTIAL_LAW_RELEASE_SOLDIER_RATIO = 0.30

# 戒嚴時徵兵能力的倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARTIAL_LAW_RECRUIT_MULTIPLIER
MARTIAL_LAW_RECRUIT_MULTIPLIER = 4.0

# 戒嚴時維持成本的倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARTIAL_LAW_UPKEEP_MULTIPLIER
MARTIAL_LAW_UPKEEP_MULTIPLIER = 2.0

# 屆末爭冠時每年確保決策機會的前幾名國家。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: LATE_SEASON_CONTENDER_COUNT
LATE_SEASON_CONTENDER_COUNT = 10

# 符合復名條件的政變中，恢復原始國名的機率；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RESTORATION_COUP_CHANCE
RESTORATION_COUP_CHANCE = 0.20

# 同時可存在的反霸權聯軍數上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_MAX_ACTIVE
COALITION_MAX_ACTIVE = 4

# 反霸權聯軍成立所需的最少成員國數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_MIN_MEMBERS
COALITION_MIN_MEMBERS = 3

# 每個反霸權聯軍的成員上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_MAX_MEMBERS
COALITION_MAX_MEMBERS = 5

# True代表同一目標同時只容許一個反霸權聯軍。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_ONE_PER_TARGET
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
COALITION_ONE_PER_TARGET = True

# 聯軍對目標主動討伐的時間間隔，單位：年。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_ATTACK_INTERVAL_YEARS
COALITION_ATTACK_INTERVAL_YEARS = 100

# 聯軍成立後首次討伐的延遲年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_INITIAL_ATTACK_DELAY_YEARS
COALITION_INITIAL_ATTACK_DELAY_YEARS = 10

# 聯軍招募停止時的目標戰力／被圍剿國戰力比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_TARGET_POWER_RATIO
COALITION_TARGET_POWER_RATIO = 0.95

# 反霸權聯軍存在的最長年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_MAX_DURATION
COALITION_MAX_DURATION = 500

# 聯軍解散後，相關目標及成員的冷卻年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_COOLDOWN_YEARS
COALITION_COOLDOWN_YEARS = 12

# 單國戰力占世界戰力達此比例，可能被視為霸權候選。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: HEGEMON_SHARE_TRIGGER
HEGEMON_SHARE_TRIGGER = 0.15

# 第一名戰力達第二名幾倍，可能被視為霸權候選。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: HEGEMON_LEAD_TRIGGER
HEGEMON_LEAD_TRIGGER = 1.80

# 霸權條件連續成立幾年後，納入一般圍剿目標。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: HEGEMON_REQUIRED_STREAK
HEGEMON_REQUIRED_STREAK = 3

# 國際忌憚值達此門檻時，可納入圍剿候選池。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INTERNATIONAL_DREAD_CANDIDATE_THRESHOLD
INTERNATIONAL_DREAD_CANDIDATE_THRESHOLD = 100000

# 成立聯軍的懸賞基數；實際金額再乘貨幣倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_FORMATION_BOUNTY_BASE
COALITION_FORMATION_BOUNTY_BASE = 10

# 聯軍勝利的懸賞基數；實際金額再乘貨幣倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_VICTORY_BOUNTY_BASE
COALITION_VICTORY_BOUNTY_BASE = 60

# 攻擊無守軍城市時，每點城防造成的攻方損失係數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: UNDEFENDED_SIEGE_ATTACKER_LOSS_PER_FORT
UNDEFENDED_SIEGE_ATTACKER_LOSS_PER_FORT = 0.35

# 無守軍攻城時，攻方按兵力計算損失的比例上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: UNDEFENDED_SIEGE_ATTACKER_LOSS_RATE_CAP
UNDEFENDED_SIEGE_ATTACKER_LOSS_RATE_CAP = 0.005

# 無守軍國都的城防降到此值時，可判定陷落。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: UNDEFENDED_CAPITAL_FORT_THRESHOLD
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
UNDEFENDED_CAPITAL_FORT_THRESHOLD = 0

# 無守軍但尚有城防時，繼續抵抗的最長年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: UNDEFENDED_MAX_SIEGE_YEARS
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
UNDEFENDED_MAX_SIEGE_YEARS = 10

# 主引擎game.log記憶與保留的最新行數上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MAX_LOG_LINES
MAX_LOG_LINES = 1000

# 主引擎日誌緩衝的寫檔間隔，單位：秒。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: LOG_FLUSH_INTERVAL
LOG_FLUSH_INTERVAL = 0.25

# 每回合觸發全世界一般隨機事件的機率；不是每國各抽一次。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: GLOBAL_EVENT_CHANCE
GLOBAL_EVENT_CHANCE = 0.05

# JSON輸出格式：True緊湊以節省空間，False保留縮排。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COMPACT_FORMAT
COMPACT_FORMAT = True

# 每回合觸發全球動態事件的機率；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: DYNAMIC_EVENT_CHANCE
DYNAMIC_EVENT_CHANCE = 0.045

# 各國保留的動態事件歷史筆數上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: EVENT_HISTORY_MAX
EVENT_HISTORY_MAX = 20

# 政權變更相關判斷的冷卻回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: REGIME_CHANGE_COOLDOWN_TURNS
REGIME_CHANGE_COOLDOWN_TURNS = 90

# 正統繼承發生前，政權至少存續的年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SUCCESSION_MIN_TENURE
SUCCESSION_MIN_TENURE = 2500

# 符合政權壽命條件後，每國每回合正統交接機率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SUCCESSION_CHANCE_PER_COUNTRY
SUCCESSION_CHANCE_PER_COUNTRY = 0.1

# 自動推算：初始新國保護年數的舊名稱相容別名。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: NEWBIE_PROTECTION_TURNS
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
NEWBIE_PROTECTION_TURNS = NEW_COUNTRY_PROTECTION_YEARS

# 戰前威脅評估納入的潛在敵國數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_THREAT_CANDIDATE_COUNT
PREWAR_THREAT_CANDIDATE_COUNT = 5

# 戰前風險達此分數視為警戒。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_RISK_ALERT
PREWAR_RISK_ALERT = 45

# 戰前風險達此分數視為高風險。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_RISK_HIGH
PREWAR_RISK_HIGH = 65

# 戰前風險達此分數視為危急。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_RISK_CRITICAL
PREWAR_RISK_CRITICAL = 85

# 戰前軟性動員傾向的最低機率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_MOBILIZE_SOFT_CHANCE_MIN
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
PREWAR_MOBILIZE_SOFT_CHANCE_MIN = 0.10

# 戰前軟性動員傾向的最高機率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_MOBILIZE_SOFT_CHANCE_MAX
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
PREWAR_MOBILIZE_SOFT_CHANCE_MAX = 0.45

# 戰前危急判斷使用的士兵占人口比例門檻。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_CRITICAL_SOLDIER_RATIO
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
PREWAR_CRITICAL_SOLDIER_RATIO = 0.22

# 戰前準備的最低糧食續航年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_RESOURCE_FOOD_RUNWAY
PREWAR_RESOURCE_FOOD_RUNWAY = 4.0

# 戰前準備的金屬／人口比例門檻。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_RESOURCE_METAL_PER_POP
PREWAR_RESOURCE_METAL_PER_POP = 0.20

# 農民／士兵比例達此值時，提高軍民失衡警戒。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_FARMER_SOLDIER_ALERT_RATIO
PREWAR_FARMER_SOLDIER_ALERT_RATIO = 3.0

# 農民／士兵比例達此值時，視為較嚴重軍民失衡。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_FARMER_SOLDIER_HIGH_RATIO
PREWAR_FARMER_SOLDIER_HIGH_RATIO = 4.0

# 農民／士兵比例達此值時，視為危急軍民失衡。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_FARMER_SOLDIER_CRITICAL_RATIO
PREWAR_FARMER_SOLDIER_CRITICAL_RATIO = 4.5

# 軍民兵力平衡風險的警戒分數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_FORCE_BALANCE_ALERT_SCORE
PREWAR_FORCE_BALANCE_ALERT_SCORE = 45.0

# 軍民兵力平衡風險的高風險分數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_FORCE_BALANCE_HIGH_SCORE
PREWAR_FORCE_BALANCE_HIGH_SCORE = 65.0

# 軍民兵力平衡風險的危急分數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PREWAR_FORCE_BALANCE_CRITICAL_SCORE
PREWAR_FORCE_BALANCE_CRITICAL_SCORE = 82.0

# 短期動態效果的持續回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: EVENT_DURATION_SHORT
EVENT_DURATION_SHORT = 5

# 一般動態效果的持續回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: EVENT_DURATION_NORMAL
EVENT_DURATION_NORMAL = 8

# 長期動態效果的持續回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: EVENT_DURATION_LONG
EVENT_DURATION_LONG = 10

# 金幣面額／成本的共同倍率；只修改這裡，相關衍生初始成本自動推算。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MONEY_RATIO
MONEY_RATIO = 1

# 初始金幣的相容參數；具體建國資產另見BALANCE的START_GOLD_MIN/MAX。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INIT_GOLD
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
INIT_GOLD = 0

# 基礎建設等級上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INFRASTRUCTURE_MAX
INFRASTRUCTURE_MAX = 100

# 基礎建設投資的金幣基礎成本。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INFRASTRUCTURE_GOLD_BASE
INFRASTRUCTURE_GOLD_BASE = 60 * MONEY_RATIO

# 基礎建設投資的木材基礎成本。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INFRASTRUCTURE_WOOD_BASE
INFRASTRUCTURE_WOOD_BASE = 50

# 基礎建設投資的金屬基礎成本。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INFRASTRUCTURE_METAL_BASE
INFRASTRUCTURE_METAL_BASE = 20

# 產業重點配置的持續年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: INDUSTRY_FOCUS_DURATION
INDUSTRY_FOCUS_DURATION = 8

# 人口、住房、生產、消耗、徵兵、戰爭與初始資產的平衡表；各鍵用途見行內註解。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: BALANCE
BALANCE = {
    # 人口與住房
    # 新增住房容量所需木材。
    "HOUSE_WOOD_COST": 100,
    # 房屋接近滿載才擴建，避免容量長期遠高於人口。
    # 住房使用率達此比例才擴建。
    "HOUSE_BUILD_THRESHOLD": 0.93,
    # 若房屋容量長期超過人口 30%，每輪會有少量閒置房屋自然荒廢。
    # 住房容量超過人口幾倍後視為過量。
    "HOUSE_EXCESS_CAPACITY_RATIO": 2.0,
    # 每年最多荒廢的過量住房容量。
    "HOUSE_ABANDON_MAX_PER_TURN": 6,
    # 每新增人口的糧食成本。
    "FOOD_COST_PER_BIRTH": 8,
    # 生育所需最低存糧續航回合。
    "BIRTH_MIN_RESERVE_TURNS": 5.0,
    # 每回合人口成長率下限。
    "BIRTH_RATE_MIN": 0.015,
    # 每回合人口成長率上限。
    "BIRTH_RATE_MAX": 0.030,
    # 每回合新增人口上限。
    "BIRTH_MAX_PER_TURN": 10,

    # 農民基礎產能（每名被分派到該工作的農民／每輪）
    # 每名糧食工人每回合產糧。
    "FOOD_PER_WORKER": 6.0,  # 4.2
    # 每名木材工人每回合產木。
    "WOOD_PER_WORKER": 3.0,
    # 每名金屬工人每回合產金屬。
    "METAL_PER_WORKER": 2.0, # 1.7 

    # 每輪消耗
    # 每名農民每回合耗糧。
    "FARMER_FOOD_UPKEEP": 1.0,
    # 每名農民每輪另需 0.5 木材，用於住宅裝修；金屬、糧食消耗不變。
    # 每名農民每回合耗木。
    "FARMER_WOOD_UPKEEP": 0,
    # 每名士兵每回合耗糧。
    "SOLDIER_FOOD_UPKEEP": 2.0,
    # 每名士兵每回合耗金屬。
    "SOLDIER_METAL_UPKEEP": 0.20,
    # 房屋每年維修消耗木材，按小數累積至整數再扣。
    # 每單位住房每回合維修木材。
    "HOUSE_WOOD_UPKEEP_PER_HOUSE": 0.05,
    # 住房不足時的糧食成本倍率。
    "OVERCROWD_FOOD_PENALTY": 1.5,

    # 徵兵
    # 每名徵兵的金屬成本。
    "RECRUIT_METAL_COST": 8,
    # 每名徵兵的糧食成本。
    "RECRUIT_FOOD_COST": 3,
    # 一般自動徵兵會隨人口動態放大，不再永遠只有 4~12 人。
    # 一般徵兵批量下限。
    "RECRUIT_BATCH_MIN": 8,
    # 一般徵兵批量上限。
    "RECRUIT_BATCH_MAX": 36,
    # 一般動態徵兵占人口比例。
    "RECRUIT_DYNAMIC_POP_RATIO": 0.012,
    # 一般動態徵兵人數上限。
    "RECRUIT_DYNAMIC_MAX": 60,

    # Action 6「戰時動員」可一次動員約人口 3%，但封頂避免瞬間抽乾農民。
    # 主動動員占人口比例。
    "MOBILIZE_POP_RATIO": 0.030,
    # 主動動員人數下限。
    "MOBILIZE_MIN": 18,
    # 主動動員人數上限。
    "MOBILIZE_MAX": 120,

    # 糧食安全與勞工配置
    # 飢荒警訊使用的糧食續航門檻。
    "FAMINE_WARNING_TURNS": 3.0,
    # 低存糧判斷的續航門檻。
    "LOW_FOOD_TURNS": 6.0,
    # 過剩存糧判斷的續航門檻。
    "SURPLUS_FOOD_TURNS": 8.5,

    # 庫存過高時，採集效率下降（不是硬砍庫存）
    # 非糧食資源過剩時的產能係數。
    "SURPLUS_PRODUCTION_FACTOR": 0.12,
    # 糧食過剩時的產能係數。
    "SURPLUS_FOOD_PRODUCTION_FACTOR": 0.28,
    # 木材過剩時最低產能係數。
    "WOOD_SURPLUS_MIN_FACTOR": 0.005,
    # 木材過剩的產能衰減指數。
    "WOOD_SURPLUS_DAMPING_EXPONENT": 8,
    # 每人口期望木材庫存。
    "WOOD_RESERVE_PER_POP": 3.0,
    # 每人口期望金屬庫存。
    "METAL_RESERVE_PER_POP": 0.8,
    # 每士兵期望金屬庫存。
    "METAL_RESERVE_PER_SOLDIER": 2.5,

    # 非戰鬥人口／軍力保護
    # 糧食或金屬不足時只允許「逐步退伍」，禁止一輪把數百士兵全部轉回農夫。
    # 糧荒等緊急裁軍每回合占人口比例上限。
    "EMERGENCY_DEMOB_MAX_RATIO": 0.02,       # 每輪最多退伍總人口 2%
    # 緊急裁軍每回合人數上限。
    "EMERGENCY_DEMOB_MAX_COUNT": 20,         # 且最多 20 人
    # 缺金屬裁軍每回合占人口比例上限。
    "METAL_SHORTAGE_DEMOB_MAX_RATIO": 0.03,  # 金屬不足每輪最多退伍總人口 3%
    # 缺金屬裁軍每回合人數上限。
    "METAL_SHORTAGE_DEMOB_MAX_COUNT": 25,

    # 飢荒採漸進制：第一次欠糧先進入配給，不立即大量死亡。
    # 飢荒配給寬限回合數。
    "FAMINE_GRACE_TURNS": 1,
    # 每死亡人口所對應的缺糧量。
    "FAMINE_DEFICIT_PER_DEATH": 6.0,
    # 飢荒每回合人口損失比例上限。
    "FAMINE_MAX_POP_LOSS_RATIO": 0.015,      # 每輪最多死亡總人口 1.5%
    # 飢荒每回合死亡人數上限。
    "FAMINE_MAX_DEATHS_PER_TURN": 40,

    # 全面戰爭：每名「實際出征士兵」的一次性補給
    # 全面戰爭派兵比例下限。
    "WAR_DEPLOY_MIN": 0.45,
    # 全面戰爭派兵比例上限。
    "WAR_DEPLOY_MAX": 0.65,
    # 全面戰爭每出征士兵的一次性糧食成本。
    "WAR_FOOD_PER_SOLDIER": 0.80,
    # 全面戰爭每出征士兵的一次性金屬成本。
    "WAR_METAL_PER_SOLDIER": 0.90,
    # 全面戰爭每出征士兵的一次性木材成本。
    "WAR_WOOD_PER_SOLDIER": 0.50,

    # 正面交戰規模與傷亡
    # 正面交戰的參戰兵力比例下限。
    "BATTLE_CLASH_MIN": 0.25,
    # 正面交戰的參戰兵力比例上限。
    "BATTLE_CLASH_MAX": 0.45,
    # 正面交戰傷亡係數下限。
    "BATTLE_LOSS_MIN": 0.65,
    # 正面交戰傷亡係數上限。
    "BATTLE_LOSS_MAX": 0.95,

    # 戰爭掠奪負重（每名實際出征士兵）
    # 每名士兵可攜帶掠奪糧食量。
    "PLUNDER_FOOD_PER_SOLDIER": 5,
    # 每名士兵可攜帶掠奪木材量。
    "PLUNDER_WOOD_PER_SOLDIER": 3,
    # 每名士兵可攜帶掠奪金屬量。
    "PLUNDER_METAL_PER_SOLDIER": 2,

    # 滅國後可帶走的敵方現有庫存比例
    # 滅國後可取得敵方現存庫存比例。
    "CONQUEST_CAPTURE_RATE": 0.25,

    # 小規模襲擾
    # 襲擾出兵占可用軍隊比例。
    "RAID_FORCE_RATIO": 0.15,
    # 襲擾每兵糧食成本。
    "RAID_FOOD_PER_SOLDIER": 0.60,
    # 襲擾每兵金屬成本。
    "RAID_METAL_PER_SOLDIER": 0.25,
    # 襲擾傷亡比例下限。
    "RAID_LOSS_MIN": 0.03,
    # 襲擾傷亡比例上限。
    "RAID_LOSS_MAX": 0.08,

    # 初始國家資源
    # 建國初始糧食下限。
    "START_FOOD_MIN": 700,
    # 建國初始糧食上限。
    "START_FOOD_MAX": 1200,
    # 建國初始木材下限。
    "START_WOOD_MIN": 250,
    # 建國初始木材上限。
    "START_WOOD_MAX": 450,
    # 建國初始金屬下限。
    "START_METAL_MIN": 150,
    # 建國初始金屬上限。
    "START_METAL_MAX": 300,
    # V8 世界共同貨幣：由世界銀行發行，不可由各國自行印鈔。
    # 建國初始金幣下限。
    "START_GOLD_MIN": 400*MONEY_RATIO,
    # 建國初始金幣上限。
    "START_GOLD_MAX": 400*MONEY_RATIO,
}

# 世界銀行的顯示名稱。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_NAME
WORLD_BANK_NAME = "世界銀行"

# 新世界預設貨幣名稱；既有存檔可能沿用已保存名稱。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_CURRENCY_NAME
WORLD_CURRENCY_NAME = "大洋"

# 世界貨幣可選名稱清單；僅改顯示名稱，不改金幣帳本或自動兌換。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_CURRENCY_NAME_OPTIONS
WORLD_CURRENCY_NAME_OPTIONS = (
    "大洋", "銀幣", "白銀", "銀元", "銀圓", "通寶", "世界幣", "聯邦幣", "商幣", "國際幣",
    "銀兩", "銀票", "銀盾", "月銀", "星幣", "海元", "商銀", "環球幣", "銀冠", "新大洋", "曜銀",
)

# 市場模式下的國家重建補助金幣。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_RESPAWN_GRANT
WORLD_BANK_RESPAWN_GRANT = 120*MONEY_RATIO

# 世界銀行收取的交易費比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_TRANSACTION_FEE_RATE
WORLD_BANK_TRANSACTION_FEE_RATE = 0.01

# 世界銀行檢查流動性的間隔年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_LIQUIDITY_INTERVAL
WORLD_BANK_LIQUIDITY_INTERVAL = 10

# 世界銀行維持的最低金幣準備。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_MIN_RESERVE
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
WORLD_BANK_MIN_RESERVE = WORLD_BANK_RESPAWN_GRANT * 3

# 流動性支援的分配比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_LIQUIDITY_SHARE
WORLD_BANK_LIQUIDITY_SHARE = 0.20

# 單次流動性支援的金額上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_LIQUIDITY_GRANT_CAP
WORLD_BANK_LIQUIDITY_GRANT_CAP = 60*MONEY_RATIO

# 貨幣守恆稽核允許的數量誤差。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: CURRENCY_AUDIT_TOLERANCE
CURRENCY_AUDIT_TOLERANCE = 0

# 市場各資源的顯示名稱與初始參考價格。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_RESOURCE_META
MARKET_RESOURCE_META = {
    "food": {"name": "糧食", "seed_price": 1.00*MONEY_RATIO},
    "wood": {"name": "木材", "seed_price": 1.80*MONEY_RATIO},
    "metal": {"name": "金屬", "seed_price": 3.20*MONEY_RATIO},
}

# 市場掛單的有效年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_ORDER_TTL
MARKET_ORDER_TTL = 4

# 市場保留掛單的筆數上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_MAX_ORDERS
MARKET_MAX_ORDERS = 300

# 保留已成交交易的歷史筆數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_TRADE_HISTORY_MAX
MARKET_TRADE_HISTORY_MAX = 60

# 保留價格歷史的節點上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_PRICE_HISTORY_MAX
MARKET_PRICE_HISTORY_MAX = 40

# 市場價格上下波動限制的比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_PRICE_LIMIT_RATE
MARKET_PRICE_LIMIT_RATE = 0.20

# 成交量加權平均價使用的觀察窗長。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_VWAP_WINDOW
MARKET_VWAP_WINDOW = 10

# 掛單價格相對參考價的最低比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_PRICE_FLOOR_RATE
MARKET_PRICE_FLOOR_RATE = 0.00001

# 掛單價格相對參考價的最高比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_PRICE_CEILING_RATE
MARKET_PRICE_CEILING_RATE = 2.50

# 世界銀行發行貨幣判斷的準備／流通量門檻比例。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_BANK_ISSUE_TRIGGER_RATE
WORLD_BANK_ISSUE_TRIGGER_RATE = 0.10

# 市場價格與流動性監測的間隔年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_MONITOR_INTERVAL
MARKET_MONITOR_INTERVAL = 10

# 保留市場監測視窗的數量。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_MONITOR_HISTORY
MARKET_MONITOR_HISTORY = 24

# 單一資源成交量至少達此數量，才列為有效監測樣本。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_MONITOR_MIN_RESOURCE_QTY
MARKET_MONITOR_MIN_RESOURCE_QTY = 3

# 監測期間整體成交量的最低門檻。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_MONITOR_MIN_TOTAL_QTY
MARKET_MONITOR_MIN_TOTAL_QTY = 20

# 市場價格指數的資源權重；糧食、木材、金屬加總應為1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_BASKET_WEIGHTS
MARKET_BASKET_WEIGHTS = {"food": 0.50, "wood": 0.30, "metal": 0.20}

# 連續三個觀測窗累積跌幅達此比例，視為通縮訊號。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_DEFLATION_3WINDOW
MARKET_DEFLATION_3WINDOW = 0.03

# 最近成交量相對前兩窗平均低於此比例，視為量縮。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_VOLUME_CONTRACTION
MARKET_VOLUME_CONTRACTION = 0.80

# 存活國家中缺乏流動性的比例門檻。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_CASH_STRESS_FRACTION
MARKET_CASH_STRESS_FRACTION = 0.50

# 單次貨幣操作可新增的流通量比例上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_ISSUE_PER_OPERATION
MARKET_ISSUE_PER_OPERATION = 0.001

# 每屆累計可新增的期初流通量比例上限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MARKET_ISSUE_PER_SEASON
MARKET_ISSUE_PER_SEASON = 0.01

# 鼓勵生育政策的金幣成本；市場模式關閉時另按資源比例換算。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: BIRTH_POLICY_GOLD_COST
BIRTH_POLICY_GOLD_COST = 120*MONEY_RATIO

# 鼓勵生育政策持續年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: BIRTH_POLICY_DURATION
BIRTH_POLICY_DURATION = 12

# 鼓勵生育政策的出生倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: BIRTH_POLICY_MULT
BIRTH_POLICY_MULT = 1.80

# 增產補貼政策的金幣成本；市場模式關閉時另按資源比例換算。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PRODUCTION_POLICY_GOLD_COST
PRODUCTION_POLICY_GOLD_COST = 150*MONEY_RATIO

# 增產補貼政策持續年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PRODUCTION_POLICY_DURATION
PRODUCTION_POLICY_DURATION = 10

# 增產補貼政策的生產倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: PRODUCTION_POLICY_MULT
PRODUCTION_POLICY_MULT = 1.50

# 外交金幣行動的最低金額。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: DIPLOMACY_GOLD_MIN
DIPLOMACY_GOLD_MIN = 60*MONEY_RATIO

# 外交金幣行動的最高金額。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: DIPLOMACY_GOLD_MAX
DIPLOMACY_GOLD_MAX = 150*MONEY_RATIO

# 聯盟戰爭議案的最短冷卻年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_WAR_VOTE_COOLDOWN_MIN
ALLIANCE_WAR_VOTE_COOLDOWN_MIN = 4

# 聯盟戰爭議案的最長冷卻年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_WAR_VOTE_COOLDOWN_MAX
ALLIANCE_WAR_VOTE_COOLDOWN_MAX = 6

# 聯盟入盟投票的最短冷卻年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_JOIN_VOTE_COOLDOWN_MIN
ALLIANCE_JOIN_VOTE_COOLDOWN_MIN = 5

# 聯盟入盟投票的最長冷卻年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: ALLIANCE_JOIN_VOTE_COOLDOWN_MAX
ALLIANCE_JOIN_VOTE_COOLDOWN_MAX = 8

# 世界局勢持續的最短年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODE_MIN_DURATION
WORLD_MODE_MIN_DURATION = 14

# 世界局勢持續的最長年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODE_MAX_DURATION
WORLD_MODE_MAX_DURATION = 24

# 兩次世界局勢間平常狀態的最短年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODE_PEACE_GAP_MIN
WORLD_MODE_PEACE_GAP_MIN = 5

# 兩次世界局勢間平常狀態的最長年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODE_PEACE_GAP_MAX
WORLD_MODE_PEACE_GAP_MAX = 9

# 新世界首次世界局勢開始前的最短等待年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODE_FIRST_START_MIN
WORLD_MODE_FIRST_START_MIN = 6

# 新世界首次世界局勢開始前的最長等待年數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODE_FIRST_START_MAX
WORLD_MODE_FIRST_START_MAX = 10

# 世界局勢類型的名稱、說明與抽選權重；代碼及鍵名需保留，調整權重可改出現頻率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WORLD_MODES
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

# Expected SARSA的資格跡衰減係數；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_LAMBDA
RL_LAMBDA = 0.80

# AI未來獎勵折扣係數；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_GAMMA
RL_GAMMA = 0.975

# AI基礎探索機率；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_BASE_EPSILON
RL_BASE_EPSILON = 0.20

# AI探索率下限；0至1。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EPSILON_FLOOR
RL_EPSILON_FLOOR = 0.05

# AI探索率的衰減倍率；接近1代表衰減較慢。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EPSILON_DECAY_V6
RL_EPSILON_DECAY_V6 = 0.9995

# AI探索脈衝的間隔回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EXPLORATION_PULSE_INTERVAL
RL_EXPLORATION_PULSE_INTERVAL = 750

# 每次探索脈衝的持續回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EXPLORATION_PULSE_LENGTH
RL_EXPLORATION_PULSE_LENGTH = 30

# 探索脈衝期間的探索率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EXPLORATION_PULSE_VALUE
RL_EXPLORATION_PULSE_VALUE = 0.12

# 賽季中排名／競爭獎勵的檢查間隔回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COMPETITION_CHECKPOINT_TURNS
COMPETITION_CHECKPOINT_TURNS = 100

# 冠軍結算給AI的Q學習獎勵。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_CHAMPION_Q_REWARD
SEASON_CHAMPION_Q_REWARD = 6.0

# 亞軍結算給AI的Q學習獎勵。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_RUNNER_UP_Q_REWARD
SEASON_RUNNER_UP_Q_REWARD = 2.5

# 季軍結算給AI的Q學習獎勵。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_THIRD_Q_REWARD
SEASON_THIRD_Q_REWARD = 1.5

# 冠軍結算的金幣獎勵，依貨幣倍率推算。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_CHAMPION_GOLD_REWARD
SEASON_CHAMPION_GOLD_REWARD = 150 * MONEY_RATIO

# 冠軍所屬聯盟的金幣獎勵池，依貨幣倍率推算。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: SEASON_CHAMPION_ALLIANCE_POOL
SEASON_CHAMPION_ALLIANCE_POOL = 100 * MONEY_RATIO

# 每個AI的Q表狀態數上限；超限後觸發修剪。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MAX_Q_STATES_PER_AGENT
MAX_Q_STATES_PER_AGENT = 1200

# 每次修剪Q表時刪除的狀態筆數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: Q_PRUNE_BATCH
Q_PRUNE_BATCH = 120

# Q表檔案容量控制門檻，單位：MB。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: MAX_QTABLE_FILE_MB
MAX_QTABLE_FILE_MB = 80

# Q表寫檔間隔回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: QTABLE_SAVE_INTERVAL_TURNS
QTABLE_SAVE_INTERVAL_TURNS = 10

# 舊探索流程的探索率下限。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EPSILON_MIN
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
RL_EPSILON_MIN = 0.07

# 舊探索流程的探索率衰減倍率。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: RL_EPSILON_DECAY
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
RL_EPSILON_DECAY = 0.9997

# 執行垃圾回收的間隔回合數。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: GC_INTERVAL_TURNS
GC_INTERVAL_TURNS = 30

# 自動推算：成立聯軍懸賞基數×貨幣倍率，通常不直接改。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_FORMATION_BOUNTY
COALITION_FORMATION_BOUNTY = COALITION_FORMATION_BOUNTY_BASE * MONEY_RATIO

# 自動推算：聯軍勝利懸賞基數×貨幣倍率，通常不直接改。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: COALITION_VICTORY_BOUNTY
COALITION_VICTORY_BOUNTY = COALITION_VICTORY_BOUNTY_BASE * MONEY_RATIO

# 正式戰爭的兵力、城防、傷亡、雙線成本與休戰設定；各鍵用途見行內註解。
# 原引用：亂世演算_V12_冠軍路徑與階段學習版.py :: WARSTATE
WARSTATE = {
    # 每回合隨機行動國數下限。
    "ACTIVE_COUNTRIES_MIN": 10,
    # 每回合隨機行動國數上限。
    "ACTIVE_COUNTRIES_MAX": 18,
    # 舊即時戰鬥顯示期下限。
    "WAR_DURATION_MIN": 3,
    # 舊即時戰鬥顯示期上限。
    "WAR_DURATION_MAX": 8,
    # 舊戰鬥類型中圍城權重。
    "SIEGE_WEIGHT": 0.20,
    # 舊戰鬥類型中會戰權重。
    "BATTLE_WEIGHT": 0.55,
    # 舊戰鬥類型中襲擾權重。
    "RAID_WEIGHT": 0.25,
    # 正式戰爭交戰兵力比例下限。
    "CLASH_MIN": 0.25,
    # 正式戰爭交戰兵力比例上限。
    "CLASH_MAX": 0.45,
    # 圍城城防損耗下限。
    "FORT_SIEGE_MIN": 10,
    # 圍城城防損耗上限。
    "FORT_SIEGE_MAX": 20,
    # 會戰城防損耗下限。
    "FORT_BATTLE_MIN": 3,
    # 會戰城防損耗上限。
    "FORT_BATTLE_MAX": 8,
    # 國都相關判斷的連續失利次數門檻。
    "CAPITAL_LOSS_STREAK": 2,
    # 國都相關判斷的剩餘守軍比例。
    "CAPITAL_SOLDIER_RATIO": 0.25,
    # 國都相關判斷的城防門檻。
    "CAPITAL_FORT": 20,
    # 舊國都失守抽選機率下限。
    "CAPITAL_CHANCE_MIN": 0.45,
    # 舊國都失守抽選機率上限。
    "CAPITAL_CHANCE_MAX": 0.65,
    # 國都失守人口損失比例下限。
    "CAPITAL_DEATH_MIN": 0.10,
    # 國都失守人口損失比例上限。
    "CAPITAL_DEATH_MAX": 0.18,
    # 主動戰爭增加的敵意值。
    "HOSTILITY_ATTACK": 20,
    # 攻擊盟友相關增加的敵意值。
    "HOSTILITY_ALLY_ATTACK": 10,
    # 襲擾增加的敵意值。
    "HOSTILITY_RAID": 15,
    # 背叛增加的敵意值。
    "HOSTILITY_BETRAY": 40,
    # 每年自然減少的敵意值。
    "HOSTILITY_DECAY": 1,

    # ========================================================
    # 雙線作戰
    # ========================================================
    # 每個國家最多同時參加 2 場正式戰爭。
    # 單國同時正式參戰的戰線上限。
    "MAX_ACTIVE_WARS_PER_COUNTRY": 2,

    # 僅保留於不再執行的舊即時戰鬥對照程式；V9持續戰爭以實際分配計算。
    # 已停用舊即時戰鬥的第二戰線兵力倍率。
    "SECOND_FRONT_FORCE_MULTIPLIER": 0.55,

    # 新開第二戰線時，第一波遠征補給更昂貴。
    # 第二戰線初次出征的糧食成本倍率。
    "SECOND_FRONT_INITIAL_FOOD_MULTIPLIER": 1.35,
    # 第二戰線初次出征的金屬成本倍率。
    "SECOND_FRONT_INITIAL_METAL_MULTIPLIER": 1.25,
    # 第二戰線初次出征的木材成本倍率。
    "SECOND_FRONT_INITIAL_WOOD_MULTIPLIER": 1.00,

    # 每個持續戰爭回合，第二戰線還會額外支付維持費。
    # 第二戰線每兵每回合額外糧食維持費。
    "SECOND_FRONT_UPKEEP_FOOD_PER_SOLDIER": 0.18,
    # 第二戰線每兵每回合額外金屬維持費。
    "SECOND_FRONT_UPKEEP_METAL_PER_SOLDIER": 0.04,

    # 所有正式戰爭每回合都要維持前線補給；第二戰線另外再加上上面的額外成本。
    # 正式前線每兵每回合糧食維持費。
    "WAR_ROUND_FOOD_PER_SOLDIER": 0.10,
    # 正式前線每兵每回合金屬維持費。
    "WAR_ROUND_METAL_PER_SOLDIER": 0.02,

    # 戰後短暫休戰，避免同一批國家隔一輪立刻重打。
    # 戰後休戰回合數。
    "TRUCE_TURNS": 4,
    # 到期時戰況差距超過此值才判定勝負，接近才是真和局。
    # 到期戰況差距超過此比例才判勝負，否則可能和局。
    "DEADLINE_DECISION_MARGIN": 0.10,
    # 戰敗求和賠款（只搬動現有庫存，不創造資源）。
    # 求和資源結算的糧食庫存比例。
    "SURRENDER_FOOD_RATE": 0.8,
    # 求和資源結算的木材庫存比例。
    "SURRENDER_WOOD_RATE": 0.8,
    # 求和資源結算的金屬庫存比例。
    "SURRENDER_METAL_RATE": 0.8,
}



# ============================================================================
# 介面、字型、顏色與欄寬
# ============================================================================
# 主視窗頂部標題列所顯示的文字名稱
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: WINDOW_TITLE
WINDOW_TITLE = "亂世演算_V9_1_1_聯盟自動切換版"

# 應用程式啟動時的預設視窗解析度 (寬度x高度，單位：像素)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: WINDOW_SIZE
WINDOW_SIZE = "1500x900"

# 背景 UI 定時器自動抓取檔案與刷新的時間間隔 (單位：毫秒，1500ms = 1.5 秒)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: REFRESH_INTERVAL_MS
REFRESH_INTERVAL_MS = 1000

# 右下角「全域即時戰鬥 LOG」視窗最多讀取並顯示的最新日誌行數上限
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: MAX_GLOBAL_LOG_LINES
MAX_GLOBAL_LOG_LINES = 25

# 左側「國家詳細查詢」與「聯盟詳細查詢」分頁中，下方專屬 LOG 視窗顯示的歷史事件最大筆數
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: MAX_SPECIFIC_LOG_LINES
MAX_SPECIFIC_LOG_LINES = 10

# 介面主要文字與標籤使用的預設字體 family (微軟正黑體)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_FAMILY_MAIN
FONT_FAMILY_MAIN = "Microsoft JhengHei"

# 排版需要等寬對齊時 (如世界即時排名) 所採用的 monospace 字體 family
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_FAMILY_MONO
FONT_FAMILY_MONO = "Consolas"

# 下拉選單、提示標籤等通用 UI 元件的文字級階大小
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_SIZE_UI
FONT_SIZE_UI = 12

# 表格 (Treeview) 頂部欄位標題與標題框 (LabelFrame) 的文字大小
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_SIZE_HEADER
FONT_SIZE_HEADER = 12

# 國家與聯盟詳細資訊文本框 (Text Area) 內部內文的文字大小
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_SIZE_DETAIL
FONT_SIZE_DETAIL = 12

# 右上角世界即時排名列表區塊的文字大小
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_SIZE_RANK
FONT_SIZE_RANK = 12

# 所有事件日誌 (LOG) 區域的文字大小
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_SIZE_LOG
FONT_SIZE_LOG = 12

# 國家與聯盟詳細資訊欄位內容字體大小
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: CONFIGURE_FONT
CONFIGURE_FONT = 14

# 封裝一般 UI 元件使用的標準字型設定 (字體, 字號)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_UI_NORMAL
FONT_UI_NORMAL = (FONT_FAMILY_MAIN, FONT_SIZE_UI)

# 封裝一般 UI 元件使用的粗體字型設定 (字體, 字號, 粗體)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_UI_BOLD
FONT_UI_BOLD = (FONT_FAMILY_MAIN, FONT_SIZE_UI, "bold")

# 封裝標題欄位與區塊標題使用的粗體字型設定
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_HEADER_BOLD
FONT_HEADER_BOLD = (FONT_FAMILY_MAIN, FONT_SIZE_HEADER, "bold")

# 封裝詳細查詢內文區域使用的標準字型設定
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_DETAIL_TEXT
# 狀態：目前主流程未引用此相容設定；單獨修改它不會改變現行行為。
FONT_DETAIL_TEXT = (FONT_FAMILY_MAIN, FONT_SIZE_DETAIL)

# 封裝世界排名文字區塊使用的等寬字型設定
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_RANK_MONO
FONT_RANK_MONO = (FONT_FAMILY_MONO, FONT_SIZE_RANK)

# 封裝事件日誌區域使用的標準字型設定
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_LOG_TEXT
FONT_LOG_TEXT = (FONT_FAMILY_MAIN, FONT_SIZE_LOG)

# 封裝事件日誌區域內部重點高亮使用的粗體字型設定
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: FONT_LOG_BOLD
FONT_LOG_BOLD = (FONT_FAMILY_MAIN, FONT_SIZE_LOG, "bold")

# 主視窗與大多數容器背景的底色 (深灰近黑)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_BG_MAIN
COLOR_BG_MAIN = "#1E1E1E"

# 事件 LOG 輸入框等更深層區塊的背景顏色 (極深灰)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_BG_DARK
COLOR_BG_DARK = "#181818"

# 文本輸入框、列表格 (Treeview) 與下拉選單等數據展示區的背景色 (暗灰)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_BG_FIELD
COLOR_BG_FIELD = "#252526"

# 左側分頁標籤 (Notebook Tab) 未選取時的背景顏色
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_BG_TAB
COLOR_BG_TAB = "#2D2D2D"

# 左側分頁標籤 (Notebook Tab) 當前被選中時的高亮背景顏色 (經典 VSCode 藍)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_BG_TAB_ACTIVE
COLOR_BG_TAB_ACTIVE = "#007ACC"

# 表格 (Treeview) 頂部欄位 Header 的背景顏色
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_BG_HEADER
COLOR_BG_HEADER = "#333333"

# 一般主要標題與高亮文字的文字顏色 (純白)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_FG_WHITE
COLOR_FG_WHITE = "#FFFFFF"

# 未選中的分頁頁籤或次要內容的文字顏色 (淺灰)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_FG_MUTED
COLOR_FG_MUTED = "#CCCCCC"

# 標準內文與一般日誌文字的預設前景色 (灰白)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_FG_TEXT
COLOR_FG_TEXT = "#D4D4D4"

# 世界即時排名內文的預設前景色 (明亮灰)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_FG_RANK
COLOR_FG_RANK = "#DCDCDC"

# 區塊外框標題與重點強調標籤的前景色 (天藍)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_FG_ACCENT
COLOR_FG_ACCENT = "#007ACC"

# 世界排名中標示聯盟名稱高亮的前景色 (明亮黃)
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COLOR_FG_YELLOW
COLOR_FG_YELLOW = "#FFE066"

# 國家總覽列表中，「國家名稱」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_NAME
COL_WIDTH_COUNTRY_NAME = 120

# 國家總覽列表中，「世代」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_GEN
COL_WIDTH_COUNTRY_GEN = 50

# 國家總覽列表中，「戰力」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_POWER
COL_WIDTH_COUNTRY_POWER = 80

# 國家總覽列表中，「總人口」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_POP
COL_WIDTH_COUNTRY_POP = 70

# 國家總覽列表中，「士兵」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_SOLDIERS
COL_WIDTH_COUNTRY_SOLDIERS = 60

# 國家總覽列表中，「糧草」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_FOOD
COL_WIDTH_COUNTRY_FOOD = 70

# 國家總覽列表中，「狀態 (存活/滅亡)」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_COUNTRY_STATUS
COL_WIDTH_COUNTRY_STATUS = 210

# 聯盟總覽列表中，「聯盟名稱」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_ALLIANCE_NAME
COL_WIDTH_ALLIANCE_NAME = 150

# 聯盟總覽列表中，「總戰力」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_ALLIANCE_POWER
COL_WIDTH_ALLIANCE_POWER = 90

# 聯盟總覽列表中，「成員數量」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_ALLIANCE_MEMBERS
COL_WIDTH_ALLIANCE_MEMBERS = 80

# 聯盟總覽列表中，「圍剿目標」欄位的預設顯示寬度
# 原引用：亂世演算_V12_冠軍路徑與階段學習版_啟動.py :: COL_WIDTH_ALLIANCE_TARGET
COL_WIDTH_ALLIANCE_TARGET = 80



# ============================================================================
# 聯盟信心與歷史保留
# ============================================================================
# 聯盟信心評估的間隔年數。
# 原引用：alliance_confidence.py :: REVIEW_YEARS
ALLIANCE_CONFIDENCE_REVIEW_YEARS = 10

# 低信心判斷的分數門檻。
# 原引用：alliance_confidence.py :: LOW_CONFIDENCE
ALLIANCE_CONFIDENCE_LOW_CONFIDENCE = 35

# 低信心連續出現幾次評估後，才考慮退盟流程。
# 原引用：alliance_confidence.py :: LOW_REVIEWS
ALLIANCE_CONFIDENCE_LOW_REVIEWS = 3

# 成員開始考慮一般退盟前，至少待盟多少年。
# 原引用：alliance_confidence.py :: MIN_TENURE
ALLIANCE_CONFIDENCE_MIN_TENURE = 40

# 提出退盟告知後的等待年數。
# 原引用：alliance_confidence.py :: NOTICE_YEARS
ALLIANCE_CONFIDENCE_NOTICE_YEARS = 10

# 退盟相關外交行動的冷卻年數。
# 原引用：alliance_confidence.py :: COOLDOWN_YEARS
ALLIANCE_CONFIDENCE_COOLDOWN_YEARS = 30

# 聯盟信心JSONL只保留最近幾個年份，包含目前年。
# 原引用：alliance_confidence.py :: JOURNAL_RETENTION_YEARS
ALLIANCE_CONFIDENCE_JOURNAL_RETENTION_YEARS = 1000



# ============================================================================
# 持續戰爭與援軍
# ============================================================================
# 持續戰爭的最長作戰年數。
# 原引用：war_strategy.py :: MAX_COMBAT_YEARS
WAR_STRATEGY_MAX_COMBAT_YEARS = 30

# 一般占領判斷所需年數；拒和直接亡國分支依本版既有規則處理。
# 原引用：war_strategy.py :: OCCUPATION_YEARS
WAR_STRATEGY_OCCUPATION_YEARS = 3

# 一般國都占領判斷的剩餘守軍比例門檻。
# 原引用：war_strategy.py :: CAPTURE_SOLDIER_RATIO
WAR_STRATEGY_CAPTURE_SOLDIER_RATIO = .25

# 一般國都占領判斷的城防門檻。
# 原引用：war_strategy.py :: CAPTURE_FORT
WAR_STRATEGY_CAPTURE_FORT = 25

# 空城圍攻可持續的最長年數。
# 原引用：war_strategy.py :: EMPTY_CITY_MAX_YEARS
WAR_STRATEGY_EMPTY_CITY_MAX_YEARS = 10

# 戰爭調度重新評估的間隔年數。
# 原引用：war_strategy.py :: REVIEW_INTERVAL
WAR_STRATEGY_REVIEW_INTERVAL = 5

# 援軍抵達前的行軍年數。
# 原引用：war_strategy.py :: REINFORCEMENT_TRAVEL
WAR_STRATEGY_REINFORCEMENT_TRAVEL = 2



# ============================================================================
# 軍備子策略
# ============================================================================
# 軍備子策略可選的長期士兵／人口比例；保持六個選項以相容既有Q表。
# 原引用：military_strategy.py :: TARGETS
MILITARY_TARGETS = (.18, .25, .30, .36, .42, .48)

# 每次軍備規劃最多調整幾個比例點；0.03代表3個百分點。
# 原引用：military_strategy.py :: STEP
MILITARY_STEP = .03

# 兩次軍備規劃的最短間隔年數。
# 原引用：military_strategy.py :: COOLDOWN
MILITARY_COOLDOWN = 5



# ============================================================================
# 國家編年史
# ============================================================================
# 各國編年史只保留最近幾代政權。
# 原引用：chronicle_retention.py :: GENERATION_LIMIT
CHRONICLE_GENERATION_LIMIT = 50



# ============================================================================
# 世界圖書館
# ============================================================================
# 圖書館藏書總上限；各書架另有既有分類配額。
# 原引用：world_library.py :: MAX_BOOKS
LIBRARY_MAX_BOOKS = 100

# 每國保留的代表性已完成決策案例上限。
# 原引用：world_library.py :: MAX_CASES
LIBRARY_MAX_CASES = 24

# 每國本屆年表保留的節點數上限。
# 原引用：world_library.py :: MAX_TRACK_POINTS
LIBRARY_MAX_TRACK_POINTS = 32

# 每本書正文年表的節點數上限。
# 原引用：world_library.py :: MAX_BOOK_POINTS
LIBRARY_MAX_BOOK_POINTS = 24

# 最近保留的研習與回顧紀錄筆數。
# 原引用：world_library.py :: MAX_READINGS
LIBRARY_MAX_READINGS = 200

# 圖書館追蹤的國家槽位上限。
# 原引用：world_library.py :: MAX_COUNTRIES
LIBRARY_MAX_COUNTRIES = 200

# 採用書籍路徑後幾年回顧；滅亡或換代可提前中斷。
# 原引用：world_library.py :: REVIEW_YEARS
LIBRARY_REVIEW_YEARS = 200

# 單次行動輔助案例的後續觀測年數。
# 原引用：world_library.py :: CASE_YEARS
LIBRARY_CASE_YEARS = 15

# 兩次研習採用的最短冷卻年數；進行中的回顧也會阻止新研習。
# 原引用：world_library.py :: CONSULT_COOLDOWN
LIBRARY_CONSULT_COOLDOWN = 25

# 圖書館對單個策略選擇分數的調整上限；不是成功機率。
# 原引用：world_library.py :: BIAS_LIMIT
LIBRARY_BIAS_LIMIT = .18



# ============================================================================
# 國家大腦繼承工具
# ============================================================================
# 國家大腦繼承工具預設操作的Q表檔名。
# 原引用：亂世演算_國家大腦繼承工具.py :: DEFAULT_FILENAME
BRAIN_DEFAULT_FILENAME = "rl_agents_q_tables.json"


# 圖書館各書架配額；總藏書同時受LIBRARY_MAX_BOOKS限制。
# 增加總上限時也需提高相應書架配額；兩者較小的限制仍有效。
LIBRARY_SHELF_CAPS = {"冠軍成就": 40, "成長與復甦": 28, "失敗與興亡": 32}


# 聯盟命名：普通聯盟與臨時聯軍共用前綴，同時存續時避免重複。
# 解散的前綴自下一年重新開放；舊存檔既有重複盟名不會被強制更名。

# 聯盟名稱前綴庫；不可為空。
ALLIANCE_NAME_PREFIXES = (
    '至高', '帝冠', '王座', '皇權', '霸業', '君臨', '天命', '天威',
    '至尊', '不朽', '萬世', '永恆', '榮耀', '凱旋', '征服', '鐵血',
    '雄獅', '龍威', '蒼龍', '黑龍', '金獅', '戰鷹', '鐵翼', '王者',
    '神聖', '聖光', '聖焰', '聖盾', '神諭', '神罰', '天譴', '裁決',
    '審判', '誓約', '守望', '救贖', '創世', '起源', '諸神', '泰坦',
    '英靈', '戰神', '龍魂', '鳳凰', '涅槃', '命運', '真理', '秩序',
    '蒼穹', '星穹', '星辰', '群星', '繁星', '北辰', '天樞', '銀河',
    '星海', '星隕', '極光', '曙光', '黎明', '破曉', '旭日', '烈日',
    '日冕', '赤月', '新月', '月蝕', '日蝕', '長夜', '永夜', '天幕',
    '雷霆', '風暴', '烈焰', '烽火', '燎原', '赤焰', '熾火', '雷火',
    '鋼鐵', '黑鐵', '玄鐵', '秘銀', '黑曜', '赤鋼', '鐵壁', '堅盾',
    '利劍', '斷刃', '鋒芒', '戰歌', '軍魂', '先鋒', '鐵衛', '無畏',
    '山河', '崑崙', '蒼岳', '群峰', '磐石', '巨岩', '滄海', '深海',
    '怒濤', '狂瀾', '洪流', '寒潮', '凜冬', '冰封', '霜寒', '霜狼',
    '北境', '荒原', '大漠', '長風', '凌霄', '飛雪', '玄冰', '蒼嵐',
    '暗影', '幽冥', '深淵', '黑潮', '暮光', '黃昏', '終焉', '末日',
    '天啟', '浩劫', '劫火', '逆命', '破軍', '七殺', '無疆', '不滅',
    '自由', '正義', '和平', '共和', '同心', '共榮', '復興', '希望',
    '庇護', '守護', '忠誠', '堅毅', '眾志', '萬邦', '四海', '遠征',
)

# 聯盟名稱後綴庫；不可為空。
ALLIANCE_NAME_SUFFIXES = (
    '同盟', '聯盟', '同盟會', '聯合會', '協約', '盟約', '公約', '憲章',
    '協定', '議定書', '共同體', '協約組織', '同盟議會', '聯合議會', '邦聯', '諸國同盟',
    '列國協約', '萬國議會', '共榮圈', '合作體系', '戰線', '陣線', '聯合陣線', '防衛陣線',
    '共同防線', '聯合防線', '防衛同盟', '軍事同盟', '戰略同盟', '聯防組織', '聯防協約', '共同防衛體',
    '聯合司令部', '戰爭議會', '遠征同盟', '守望同盟', '鐵壁', '壁壘', '戰團', '軍團',
    '禁衛軍', '先鋒軍', '誓盟', '血盟', '聖盟', '王盟', '永誓', '誓約',
    '鐵誓', '血誓', '聖約', '密約', '戰誓', '遠征誓約', '守護誓約', '不戰之約',
    '兄弟會', '圓桌會', '守望者', '捍衛者', '征服者', '執劍者', '王庭', '聖庭',
    '議庭', '樞密院', '最高議會', '統合體', '霸權同盟', '秩序同盟', '戰略體系', '安全體系',
    '和平協約', '復興同盟', '自由陣線', '解放戰線', '保衛同盟', '制衡同盟',
)
