"""core/models.py — تمثيل صفوف قاعدة البيانات ككائنات Python."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class Player:
    user_id: int
    guild_id: int
    culture: str
    gold: int
    wood: int
    iron: int
    food: int
    essence: int
    category_id: Optional[int]
    king_channel_id: Optional[int]
    war_channel_id: Optional[int]
    magic_channel_id: Optional[int]
    guide_channel_id: Optional[int]
    ally_channel_id: Optional[int]
    shield_expires_at: Optional[datetime]
    alliance_id: Optional[int]
    registered_at: datetime
    last_status_update: Optional[datetime] = None
    empire_name: Optional[str] = None
    shield_warned: bool = False
    last_tip_at: Optional[datetime] = None

    @property
    def shield_active(self) -> bool:
        if not self.shield_expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires = self.shield_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now < expires

    @property
    def shield_time_left(self) -> Optional[timedelta]:
        if not self.shield_active:
            return None
        expires = self.shield_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires - datetime.now(timezone.utc)

    @property
    def resources(self) -> dict:
        return {
            "gold": self.gold,
            "wood": self.wood,
            "iron": self.iron,
            "food": self.food,
            "essence": self.essence,
        }


@dataclass
class Buildings:
    user_id: int
    farm: int
    mine: int
    lumber: int
    castle: int
    altar: int


@dataclass
class Troops:
    user_id: int
    infantry: int
    cavalry: int
    archers: int
    wounded: int
    wizard: Optional[str]
    wizard_expires_at: Optional[datetime]
    beast: Optional[str]
    beast_expires_at: Optional[datetime]
    mercenary_power: int = 0
    mercenary_expires_at: Optional[datetime] = None


@dataclass
class Alliance:
    alliance_id: int
    name: str
    tag: str
    leader_id: int
    hq_channel_id: Optional[int]
    war_room_channel_id: Optional[int]
    role_id: Optional[int]
    bank_gold: int
    bank_wood: int
    bank_iron: int
    bank_food: int
    created_at: datetime
