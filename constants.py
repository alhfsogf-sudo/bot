"""utils/constants.py — كل الثوابت الثابتة في اللعبة."""
from dataclasses import dataclass, field

EMOJI = {
    "gold": "🪙",
    "wood": "🪵",
    "iron": "⛓️",
    "food": "🌾",
    "essence": "🔮",
    "infantry": "⚔️",
    "cavalry": "🐎",
    "archers": "🏹",
    "wounded": "🩹",
    "shield": "🛡️",
    "farm": "🌾",
    "mine": "⛏️",
    "lumber": "🪓",
    "castle": "🏰",
    "altar": "🔮",
}


@dataclass
class Culture:
    key: str
    name: str
    emoji: str
    color: int
    description: str
    perks: str


CULTURES = {
    "military": Culture(
        key="military",
        name="قائد عسكري",
        emoji="⚔️",
        color=0xC0392B,
        description="+15% قوة قتالية، -10% تكلفة التدريب",
        perks="military_power_bonus=0.15,training_discount=0.10",
    ),
    "trade": Culture(
        key="trade",
        name="بارون التجارة",
        emoji="💰",
        color=0xF1C40F,
        description="+20% إنتاج ذهب، -10% رسوم السوق",
        perks="gold_production_bonus=0.20,market_fee_discount=0.10",
    ),
    "industrial": Culture(
        key="industrial",
        name="كبير البنّائين",
        emoji="🔨",
        color=0x2980B9,
        description="-15% تكلفة البناء، +20% سرعة التطوير",
        perks="building_discount=0.15,build_speed_bonus=0.20",
    ),
}

STARTING_RESOURCES = {
    "military": {"gold": 1000, "wood": 500, "iron": 500, "food": 800, "essence": 0},
    "trade": {"gold": 1500, "wood": 400, "iron": 300, "food": 700, "essence": 0},
    "industrial": {"gold": 800, "wood": 800, "iron": 600, "food": 700, "essence": 0},
}

# --- أسماء القنوات الخاصة (بالإنجليزية بحسب طلب صاحب البوت) ---
CHANNEL_KING = "👑┃king"
CHANNEL_WAR = "⚔️┃war"
CHANNEL_MAGIC = "🔮┃magic"
CHANNEL_GUIDE = "📖┃guide"
CHANNEL_ALLY = "🤝┃ally"

# --- الجنود ---
TROOP_TYPES = {
    "infantry": {"name": "مشاة", "emoji": "⚔️", "power": 10,
                 "cost": {"gold": 50, "food": 10, "iron": 20}, "beats": "archers"},
    "archers": {"name": "رماة", "emoji": "🏹", "power": 12,
                "cost": {"gold": 70, "food": 10, "iron": 10, "wood": 20}, "beats": "cavalry"},
    "cavalry": {"name": "فرسان", "emoji": "🐎", "power": 15,
                "cost": {"gold": 120, "food": 20, "iron": 30}, "beats": "infantry"},
}

# --- السحرة والمخلوقات ---
WIZARDS = {
    "pyromancer": {"name": "Pyromancer 🔥", "cost": {"gold": 5000, "iron": 2000, "essence": 500},
                   "effect": "يدمر 15% من حصن الهدف قبل كل معركة"},
    "arch_healer": {"name": "Arch-healer 💚", "cost": {"gold": 4000, "food": 2000, "essence": 400},
                     "effect": "جرحاك يصلون 90% بدل 70%"},
    "illusionist": {"name": "Illusionist 🌀", "cost": {"gold": 6000, "wood": 1500, "essence": 600},
                     "effect": "يعمي الجواسيس ويلغي مكافأة التصدي ضدك"},
}

BEASTS = {
    "dragon": {"name": "Dragon 🐉", "cost": {"gold": 20000, "iron": 10000, "essence": 2000},
               "effect": "يحرق مزارع العدو 6 ساعات (-50% طعام)"},
    "phoenix": {"name": "Phoenix 🦅", "cost": {"gold": 15000, "food": 8000, "essence": 1500},
                "effect": "يُحيي 50% من قتلاك عند الدفاع (مرة واحدة)"},
    "golem": {"name": "Golem 🗿", "cost": {"gold": 18000, "iron": 12000, "essence": 1800},
              "effect": "يضاعف دفاع قلعتك ×3"},
}

SUMMON_DURATION_DAYS = 7
EXPEDITION_COST_RATIO = 0.5
EXPEDITION_SUCCESS_RATE = 0.05
EXPEDITION_SUCCESS_RATE_ECLIPSE = 0.20

# --- حدود أسعار السوق (لمنع التلاعب) ---
MARKET_PRICE_LIMITS = {
    "wood": (1, 20),
    "iron": (2, 40),
    "food": (1, 15),
    "essence": (10, 200),
}

# --- التحالفات ---
ALLIANCE_CREATION_COST = 50_000

# --- الغارات ---
SCOUT_COST = 200
SCOUT_SUCCESS_RATE = 0.70
RAID_LIMIT_PER_TARGET_24H = 3
POWER_RANGE_MIN = 0.80
POWER_RANGE_MAX = 1.20
HEAL_COST_GOLD_PER_UNIT = 30
HEAL_COST_FOOD_PER_UNIT = 15
