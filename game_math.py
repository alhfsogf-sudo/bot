"""utils/game_math.py — كل الحسابات الرياضية للعبة."""
from constants import TROOP_TYPES, CULTURES

BUILDING_COST_MULTIPLIER = 1.6
BUILDING_BASE_COST = {
    "farm": {"gold": 200, "wood": 150},
    "mine": {"gold": 250, "wood": 100},
    "lumber": {"gold": 200, "iron": 100},
    "castle": {"gold": 500, "wood": 300, "iron": 300},
    "altar": {"gold": 400, "iron": 200, "wood": 200},
}

BUILDING_PRODUCTION_RATE = {
    "farm": {"food": 50},
    "mine": {"iron": 40, "gold": 20},
    "lumber": {"wood": 50},
    "castle": {},          # +500 دفاع للحصن لكل مستوى — يُستخدم في القتال لا الإنتاج
    "altar": {"essence": 10},
}

CASTLE_DEFENSE_PER_LEVEL = 500

CULTURE_MILITARY_BONUS = {"military": 1.15, "trade": 1.0, "industrial": 1.0}
CULTURE_TRAINING_DISCOUNT = {"military": 0.10, "trade": 0.0, "industrial": 0.0}
CULTURE_GOLD_BONUS = {"trade": 0.20, "military": 0.0, "industrial": 0.0}
CULTURE_BUILD_DISCOUNT = {"industrial": 0.15, "military": 0.0, "trade": 0.0}


def building_upgrade_cost(building: str, current_level: int, culture: str = None) -> dict:
    """تكلفة الترقية = تكلفة القاعدة × 1.6^المستوى الحالي (مع خصم البنّاء 15%)."""
    base = BUILDING_BASE_COST[building]
    multiplier = BUILDING_COST_MULTIPLIER ** current_level
    discount = 1 - CULTURE_BUILD_DISCOUNT.get(culture, 0.0)
    return {res: round(amount * multiplier * discount) for res, amount in base.items()}


def hourly_production(building: str, level: int, culture: str = None) -> dict:
    """إنتاج كل ساعة = معدل × مستوى (مع مكافأة ذهب لثقافة التجارة على المنجم)."""
    rates = BUILDING_PRODUCTION_RATE.get(building, {})
    result = {}
    for res, rate in rates.items():
        amount = rate * level
        if res == "gold" and culture:
            amount *= (1 + CULTURE_GOLD_BONUS.get(culture, 0.0))
        result[res] = round(amount)
    return result


def training_cost(troop_type: str, amount: int, culture: str = None) -> dict:
    base = TROOP_TYPES[troop_type]["cost"]
    discount = 1 - CULTURE_TRAINING_DISCOUNT.get(culture, 0.0)
    return {res: round(v * amount * discount) for res, v in base.items()}


def military_power(infantry: int, cavalry: int, archers: int, culture: str = None,
                    mercenary_power: int = 0) -> float:
    power = (
        infantry * TROOP_TYPES["infantry"]["power"]
        + cavalry * TROOP_TYPES["cavalry"]["power"]
        + archers * TROOP_TYPES["archers"]["power"]
    )
    bonus = CULTURE_MILITARY_BONUS.get(culture, 1.0)
    return power * bonus + mercenary_power


def can_attack(atk_power: float, def_power: float) -> bool:
    if def_power <= 0:
        return atk_power > 0
    ratio = atk_power / def_power
    return 0.80 <= ratio <= 1.20


def corruption_upkeep_multiplier(total_troops: int) -> float:
    """كلما كبر الجيش زادت الصيانة (فساد). يبدأ من 1.0 ويزيد تدريجياً."""
    if total_troops <= 200:
        return 1.0
    elif total_troops <= 500:
        return 1.15
    elif total_troops <= 1000:
        return 1.35
    else:
        return 1.6


def type_advantage_bonus(attacker_type: str, defender_dominant_type: str) -> float:
    """+25% إذا كان نوع المهاجم يتفوق على نوع المدافع الأكثر عدداً."""
    if TROOP_TYPES[attacker_type]["beats"] == defender_dominant_type:
        return 1.25
    return 1.0
