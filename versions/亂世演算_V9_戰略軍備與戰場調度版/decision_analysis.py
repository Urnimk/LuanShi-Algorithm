"""V8 小幅重構：七個只讀分析腦，輸出 0～1 訊號供既有戰略 Q 決策使用。

不持有世界物件，不修改國家資料，不產生資源，也不執行 Action。
"""
from __future__ import annotations

from dataclasses import dataclass


def bounded(value):
    return max(0.0, min(1.0, float(value)))


def number(country, key, default=0):
    return float(country.get(key, default) or 0)


@dataclass(frozen=True)
class BrainReport:
    economy: float
    military: float
    diplomacy: float
    population: float
    domestic: float
    intelligence: float
    strategy: float

    def as_dict(self):
        return {field: round(getattr(self, field), 4) for field in self.__dataclass_fields__}


class EconomyBrain:
    @staticmethod
    def analyze(country, money_ratio):
        pop = max(1.0, number(country, "pop_total", 1))
        food_need = max(1.0, number(country, "farmers") + number(country, "soldiers") * 2)
        food_runway = bounded(number(country, "food") / food_need / 8)
        cash_per_person = bounded(number(country, "gold") / max(1, money_ratio) / pop / 8)
        materials = bounded((number(country, "wood") + number(country, "metal") * 2) / pop / 5)
        return bounded((food_runway + cash_per_person + materials) / 3)


class MilitaryBrain:
    @staticmethod
    def analyze(country):
        pop = max(1.0, number(country, "pop_total", 1))
        target = max(0.12, number(country, "military_target_ratio", .30))
        soldier_coverage = bounded(number(country, "soldiers") / pop / target)
        fort = bounded(number(country, "fortification") / 100)
        exhaustion = bounded(number(country, "war_exhaustion") / 100)
        return bounded(soldier_coverage * .65 + fort * .20 + (1 - exhaustion) * .15)


class DiplomacyBrain:
    @staticmethod
    def analyze(country):
        hostility = max((float(v or 0) for v in (country.get("hostility") or {}).values()), default=0.0)
        allied = 1.0 if country.get("current_alliance") else 0.0
        return bounded(.35 + allied * .50 - bounded(hostility / 100) * .30)


class PopulationBrain:
    @staticmethod
    def analyze(country):
        pop = max(1.0, number(country, "pop_total", 1))
        farmers = bounded(number(country, "farmers") / pop)
        housing_capacity = max(1.0, number(country, "houses") * 10)
        space = bounded((housing_capacity - pop) / housing_capacity)
        return bounded(farmers * .60 + space * .40)


class DomesticBrain:
    @staticmethod
    def analyze(country):
        stability = bounded(number(country, "political_stability", 75) / 100)
        exhaustion = bounded(number(country, "war_exhaustion") / 100)
        return bounded(stability * .75 + (1 - exhaustion) * .25)


class IntelligenceBrain:
    @staticmethod
    def analyze(country):
        # 已有的戰前評估兼顧敵意和能力，不把「對方比較強」直接當作進攻意圖。
        return bounded(number(country, "prewar_risk_score") / 100)


class StrategyBrain:
    @staticmethod
    def analyze(country, total_world_power, alive_count):
        average = max(1.0, float(total_world_power) / max(1, alive_count))
        power_position = bounded(number(country, "power") / average / 2)
        foundation = bounded(number(country, "infrastructure") / 100)
        return bounded(power_position * .75 + foundation * .25)


class NationalDecisionHub:
    """保留舊 Q-table 的維數與標籤，將連續風險合入既有狀態。"""

    @staticmethod
    def analyze(country, total_world_power, alive_count, money_ratio=1000):
        report = BrainReport(
            EconomyBrain.analyze(country, money_ratio),
            MilitaryBrain.analyze(country),
            DiplomacyBrain.analyze(country),
            PopulationBrain.analyze(country),
            DomesticBrain.analyze(country),
            IntelligenceBrain.analyze(country),
            StrategyBrain.analyze(country, total_world_power, alive_count),
        )
        return report

    @staticmethod
    def strategic_state(existing_state, country, report):
        # 只收斂到原有 prewar_risk / mobilization_need 兩個維度，不擴增 Q 狀態空間。
        old = list(existing_state)
        threat = max(number(country, "prewar_risk_score") / 100, report.intelligence)
        # 經濟或勞動力不足時調低建議動員需求；僅調整觀察訊號，不封鎖動作。
        readiness_gap = 1 - report.military
        workforce_pressure = bounded(.25 - report.population)
        context_factor = ((.65 + report.economy * .35)
                          * (.90 + report.domestic * .10)
                          * (.90 + report.diplomacy * .10)
                          * (.90 + report.strategy * .10))
        advisory_need = bounded((threat * .55 + readiness_gap * .35 + workforce_pressure * .10)
                                * context_factor)
        need = max(bounded(number(country, "prewar_mobilization_need")), advisory_need)
        if threat >= .85: old[7] = "CRITICAL"
        elif threat >= .65: old[7] = "HIGH"
        elif threat >= .45: old[7] = "ALERT"
        else: old[7] = "CALM"
        old[8] = "HIGH" if need >= .68 else "MEDIUM" if need >= .35 else "LOW"
        return tuple(old)
