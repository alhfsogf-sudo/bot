"""
core/database.py — قاعدة البيانات معدلة لدعم أرقام الموارد بلا حدود (NUMERIC).
"""
import asyncpg
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import DATABASE_URL, NEWBIE_SHIELD_HOURS
from models import Player, Buildings, Troops, Alliance
from exceptions import PlayerNotFound, PlayerAlreadyExists

_pool: Optional[asyncpg.Pool] = None


# ------------------------------------------------------------------
# إدارة الـ Pool
# ------------------------------------------------------------------
async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("قاعدة البيانات غير متصلة بعد — تأكد من استدعاء init_pool() أولاً.")
    return _pool


async def create_tables():
    schema = """
    CREATE TABLE IF NOT EXISTS players (
        user_id             BIGINT PRIMARY KEY,
        guild_id            BIGINT NOT NULL,
        culture             TEXT NOT NULL,
        gold                NUMERIC NOT NULL DEFAULT 0,
        wood                NUMERIC NOT NULL DEFAULT 0,
        iron                NUMERIC NOT NULL DEFAULT 0,
        food                NUMERIC NOT NULL DEFAULT 0,
        essence             NUMERIC NOT NULL DEFAULT 0,
        category_id         BIGINT,
        king_channel_id     BIGINT,
        war_channel_id      BIGINT,
        magic_channel_id    BIGINT,
        guide_channel_id    BIGINT,
        ally_channel_id     BIGINT,
        shield_expires_at   TIMESTAMPTZ,
        alliance_id         INTEGER,
        registered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_status_update  TIMESTAMPTZ,
        empire_name         TEXT,
        shield_warned       BOOLEAN NOT NULL DEFAULT false,
        last_tip_at         TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS buildings (
        user_id  BIGINT PRIMARY KEY REFERENCES players(user_id) ON DELETE CASCADE,
        farm     BIGINT NOT NULL DEFAULT 1,
        mine     BIGINT NOT NULL DEFAULT 1,
        lumber   BIGINT NOT NULL DEFAULT 1,
        castle   BIGINT NOT NULL DEFAULT 1,
        altar    BIGINT NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS troops (
        user_id              BIGINT PRIMARY KEY REFERENCES players(user_id) ON DELETE CASCADE,
        infantry             NUMERIC NOT NULL DEFAULT 0,
        cavalry              NUMERIC NOT NULL DEFAULT 0,
        archers              NUMERIC NOT NULL DEFAULT 0,
        wounded              NUMERIC NOT NULL DEFAULT 0,
        wizard               TEXT,
        wizard_expires_at    TIMESTAMPTZ,
        beast                TEXT,
        beast_expires_at     TIMESTAMPTZ,
        mercenary_power      NUMERIC NOT NULL DEFAULT 0,
        mercenary_expires_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS alliances (
        alliance_id         SERIAL PRIMARY KEY,
        name                TEXT NOT NULL,
        tag                 TEXT NOT NULL,
        leader_id           BIGINT NOT NULL,
        hq_channel_id       BIGINT,
        war_room_channel_id BIGINT,
        role_id             BIGINT,
        bank_gold           NUMERIC NOT NULL DEFAULT 0,
        bank_wood           NUMERIC NOT NULL DEFAULT 0,
        bank_iron           NUMERIC NOT NULL DEFAULT 0,
        bank_food           NUMERIC NOT NULL DEFAULT 0,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS raid_log (
        id          SERIAL PRIMARY KEY,
        attacker_id BIGINT NOT NULL,
        defender_id BIGINT NOT NULL,
        result      TEXT NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_raid_log_pair_time
        ON raid_log (attacker_id, defender_id, created_at);

    CREATE TABLE IF NOT EXISTS world_state (
        key         TEXT PRIMARY KEY,
        value       JSONB NOT NULL,
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS market_listings (
        id          SERIAL PRIMARY KEY,
        seller_id   BIGINT NOT NULL,
        resource    TEXT NOT NULL,
        amount      NUMERIC NOT NULL,
        price       NUMERIC NOT NULL,
        channel_id  BIGINT,
        message_id  BIGINT,
        active      BOOLEAN NOT NULL DEFAULT true,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS daily_quests (
        id           SERIAL PRIMARY KEY,
        user_id      BIGINT NOT NULL,
        quest_type   TEXT NOT NULL,
        target       BIGINT NOT NULL,
        progress     BIGINT NOT NULL DEFAULT 0,
        reward_gold  NUMERIC NOT NULL DEFAULT 0,
        completed    BOOLEAN NOT NULL DEFAULT false,
        claimed      BOOLEAN NOT NULL DEFAULT false,
        assigned_date DATE NOT NULL DEFAULT CURRENT_DATE
    );
    CREATE INDEX IF NOT EXISTS idx_daily_quests_user_date ON daily_quests (user_id, assigned_date);

    CREATE TABLE IF NOT EXISTS scout_log (
        id          SERIAL PRIMARY KEY,
        scout_id    BIGINT NOT NULL,
        target_id   BIGINT NOT NULL,
        success     BOOLEAN NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_scout_log_target_time ON scout_log (target_id, created_at);

    CREATE TABLE IF NOT EXISTS tickets (
        id          SERIAL PRIMARY KEY,
        user_id     BIGINT NOT NULL,
        channel_id  BIGINT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'open',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ترقية الجداول الحالية تلقائياً بدعم الأرقام اللانهائية
    ALTER TABLE players ALTER COLUMN gold TYPE NUMERIC USING gold::NUMERIC;
    ALTER TABLE players ALTER COLUMN wood TYPE NUMERIC USING wood::NUMERIC;
    ALTER TABLE players ALTER COLUMN iron TYPE NUMERIC USING iron::NUMERIC;
    ALTER TABLE players ALTER COLUMN food TYPE NUMERIC USING food::NUMERIC;
    ALTER TABLE players ALTER COLUMN essence TYPE NUMERIC USING essence::NUMERIC;

    ALTER TABLE alliances ALTER COLUMN bank_gold TYPE NUMERIC USING bank_gold::NUMERIC;
    ALTER TABLE alliances ALTER COLUMN bank_wood TYPE NUMERIC USING bank_wood::NUMERIC;
    ALTER TABLE alliances ALTER COLUMN bank_iron TYPE NUMERIC USING bank_iron::NUMERIC;
    ALTER TABLE alliances ALTER COLUMN bank_food TYPE NUMERIC USING bank_food::NUMERIC;

    ALTER TABLE market_listings ALTER COLUMN amount TYPE NUMERIC USING amount::NUMERIC;
    ALTER TABLE market_listings ALTER COLUMN price TYPE NUMERIC USING price::NUMERIC;

    ALTER TABLE troops ALTER COLUMN infantry TYPE NUMERIC USING infantry::NUMERIC;
    ALTER TABLE troops ALTER COLUMN cavalry TYPE NUMERIC USING cavalry::NUMERIC;
    ALTER TABLE troops ALTER COLUMN archers TYPE NUMERIC USING archers::NUMERIC;
    ALTER TABLE troops ALTER COLUMN wounded TYPE NUMERIC USING wounded::NUMERIC;
    ALTER TABLE troops ALTER COLUMN mercenary_power TYPE NUMERIC USING mercenary_power::NUMERIC;
    """
    async with get_pool().acquire() as conn:
        await conn.execute(schema)


# ------------------------------------------------------------------
# اللاعبون
# ------------------------------------------------------------------
def _row_to_player(row) -> Player:
    return Player(**dict(row))


async def get_player(user_id: int) -> Player:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM players WHERE user_id = $1", user_id)
        if not row:
            raise PlayerNotFound()
        return _row_to_player(row)


async def try_get_player(user_id: int) -> Optional[Player]:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM players WHERE user_id = $1", user_id)
        return _row_to_player(row) if row else None


async def player_exists(user_id: int) -> bool:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM players WHERE user_id = $1", user_id)
        return row is not None


async def get_all_players() -> list[Player]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM players")
        return [_row_to_player(r) for r in rows]


async def create_player(
    user_id: int,
    guild_id: int,
    culture: str,
    starting_resources: dict,
    category_id: int,
    king_channel_id: int,
    war_channel_id: int,
    magic_channel_id: int,
    guide_channel_id: int,
    ally_channel_id: int,
) -> Player:
    if await player_exists(user_id):
        raise PlayerAlreadyExists()

    shield_expires = datetime.now(timezone.utc) + timedelta(hours=NEWBIE_SHIELD_HOURS)

    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO players (
                    user_id, guild_id, culture, gold, wood, iron, food, essence,
                    category_id, king_channel_id, war_channel_id, magic_channel_id,
                    guide_channel_id, ally_channel_id, shield_expires_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                """,
                user_id, guild_id, culture,
                starting_resources.get("gold", 0),
                starting_resources.get("wood", 0),
                starting_resources.get("iron", 0),
                starting_resources.get("food", 0),
                starting_resources.get("essence", 0),
                category_id, king_channel_id, war_channel_id,
                magic_channel_id, guide_channel_id, ally_channel_id, shield_expires,
            )
            await conn.execute("INSERT INTO buildings (user_id) VALUES ($1)", user_id)
            await conn.execute("INSERT INTO troops (user_id) VALUES ($1)", user_id)

    return await get_player(user_id)


async def update_player_resources(user_id: int, **deltas):
    if not deltas:
        return
    allowed = {"gold", "wood", "iron", "food", "essence"}
    sets = []
    values = [user_id]
    for i, (key, delta) in enumerate(deltas.items(), start=2):
        if key not in allowed:
            continue
        sets.append(f"{key} = GREATEST(0, {key} + ${i})")
        values.append(delta)
    if not sets:
        return
    query = f"UPDATE players SET {', '.join(sets)} WHERE user_id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, *values)


async def set_player_resources(user_id: int, **absolutes):
    allowed = {"gold", "wood", "iron", "food", "essence"}
    sets = []
    values = [user_id]
    for i, (key, val) in enumerate(absolutes.items(), start=2):
        if key not in allowed:
            continue
        sets.append(f"{key} = ${i}")
        values.append(max(0, val))
    if not sets:
        return
    query = f"UPDATE players SET {', '.join(sets)} WHERE user_id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, *values)


async def touch_status_update(user_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE players SET last_status_update = now() WHERE user_id = $1", user_id
        )


async def set_alliance_id(user_id: int, alliance_id: Optional[int]):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE players SET alliance_id = $1 WHERE user_id = $2", alliance_id, user_id
        )


async def remove_shield(user_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE players SET shield_expires_at = NULL WHERE user_id = $1", user_id
        )


async def delete_player(user_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("DELETE FROM players WHERE user_id = $1", user_id)


# ------------------------------------------------------------------
# المباني
# ------------------------------------------------------------------
async def get_buildings(user_id: int) -> Buildings:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM buildings WHERE user_id = $1", user_id)
        if not row:
            raise PlayerNotFound()
        return Buildings(**dict(row))


async def upgrade_building(user_id: int, building: str):
    if building not in {"farm", "mine", "lumber", "castle", "altar"}:
        raise ValueError("مبنى غير معروف")
    async with get_pool().acquire() as conn:
        await conn.execute(
            f"UPDATE buildings SET {building} = {building} + 1 WHERE user_id = $1", user_id
        )


# ------------------------------------------------------------------
# الجيوش
# ------------------------------------------------------------------
async def get_troops(user_id: int) -> Troops:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM troops WHERE user_id = $1", user_id)
        if not row:
            raise PlayerNotFound()
        return Troops(**dict(row))


async def update_troops(user_id: int, **deltas):
    allowed = {"infantry", "cavalry", "archers", "wounded"}
    sets = []
    values = [user_id]
    for i, (key, delta) in enumerate(deltas.items(), start=2):
        if key not in allowed:
            continue
        sets.append(f"{key} = GREATEST(0, {key} + ${i})")
        values.append(delta)
    if not sets:
        return
    query = f"UPDATE troops SET {', '.join(sets)} WHERE user_id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, *values)


async def set_wizard(user_id: int, wizard: Optional[str], expires_at: Optional[datetime]):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE troops SET wizard = $1, wizard_expires_at = $2 WHERE user_id = $3",
            wizard, expires_at, user_id,
        )


async def set_beast(user_id: int, beast: Optional[str], expires_at: Optional[datetime]):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE troops SET beast = $1, beast_expires_at = $2 WHERE user_id = $3",
            beast, expires_at, user_id,
        )


# ------------------------------------------------------------------
# سجل الغارات
# ------------------------------------------------------------------
async def count_raids_last_24h(attacker_id: int, defender_id: int) -> int:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS c FROM raid_log
            WHERE attacker_id = $1 AND defender_id = $2
              AND created_at > now() - interval '24 hours'
            """,
            attacker_id, defender_id,
        )
        return row["c"]


async def count_raids_on_all_last_24h(attacker_id: int) -> dict:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT defender_id, COUNT(*) AS c FROM raid_log
            WHERE attacker_id = $1 AND created_at > now() - interval '24 hours'
            GROUP BY defender_id
            """,
            attacker_id,
        )
        return {r["defender_id"]: r["c"] for r in rows}


async def log_raid(attacker_id: int, defender_id: int, result: str):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO raid_log (attacker_id, defender_id, result) VALUES ($1,$2,$3)",
            attacker_id, defender_id, result,
        )


# ------------------------------------------------------------------
# التحالفات
# ------------------------------------------------------------------
async def create_alliance(name: str, tag: str, leader_id: int) -> Alliance:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO alliances (name, tag, leader_id) VALUES ($1,$2,$3) RETURNING *",
            name, tag, leader_id,
        )
        return Alliance(**dict(row))


async def get_alliance(alliance_id: int) -> Optional[Alliance]:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM alliances WHERE alliance_id = $1", alliance_id)
        return Alliance(**dict(row)) if row else None


async def set_alliance_channel_role(alliance_id: int, hq_channel_id: int, war_room_channel_id: int, role_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE alliances SET hq_channel_id = $1, war_room_channel_id = $2, role_id = $3 WHERE alliance_id = $4",
            hq_channel_id, war_room_channel_id, role_id, alliance_id,
        )


async def update_alliance_bank(alliance_id: int, **deltas):
    allowed = {"bank_gold", "bank_wood", "bank_iron", "bank_food"}
    sets = []
    values = [alliance_id]
    for i, (key, delta) in enumerate(deltas.items(), start=2):
        if key not in allowed:
            continue
        sets.append(f"{key} = GREATEST(0, {key} + ${i})")
        values.append(delta)
    if not sets:
        return
    query = f"UPDATE alliances SET {', '.join(sets)} WHERE alliance_id = $1"
    async with get_pool().acquire() as conn:
        await conn.execute(query, *values)


async def get_alliance_members(alliance_id: int) -> list[Player]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM players WHERE alliance_id = $1", alliance_id)
        return [_row_to_player(r) for r in rows]


async def delete_alliance(alliance_id: int):
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE players SET alliance_id = NULL WHERE alliance_id = $1", alliance_id
            )
            await conn.execute("DELETE FROM alliances WHERE alliance_id = $1", alliance_id)


# ------------------------------------------------------------------
# اسم الإمبراطورية / الدرع
# ------------------------------------------------------------------
async def set_empire_name(user_id: int, name: str):
    async with get_pool().acquire() as conn:
        await conn.execute("UPDATE players SET empire_name = $1 WHERE user_id = $2", name, user_id)


async def mark_shield_warned(user_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("UPDATE players SET shield_warned = true WHERE user_id = $1", user_id)


async def get_players_with_expiring_shield(within_minutes: int) -> list[Player]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM players
            WHERE shield_expires_at IS NOT NULL
              AND shield_warned = false
              AND shield_expires_at BETWEEN now() AND now() + ($1 || ' minutes')::interval
            """,
            str(within_minutes),
        )
        return [_row_to_player(r) for r in rows]


async def mark_tip_sent(user_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("UPDATE players SET last_tip_at = now() WHERE user_id = $1", user_id)


# ------------------------------------------------------------------
# الحالة العالمية الدائمة
# ------------------------------------------------------------------
import json as _json


async def get_world_state(key: str, default=None):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM world_state WHERE key = $1", key)
        if not row:
            return default
        return _json.loads(row["value"])


async def set_world_state(key: str, value):
    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO world_state (key, value, updated_at) VALUES ($1, $2, now())
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
            """,
            key, _json.dumps(value),
        )


async def delete_world_state(key: str):
    async with get_pool().acquire() as conn:
        await conn.execute("DELETE FROM world_state WHERE key = $1", key)


# ------------------------------------------------------------------
# السوق الحرة
# ------------------------------------------------------------------
async def create_market_listing(seller_id: int, resource: str, amount: int, price: int) -> int:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO market_listings (seller_id, resource, amount, price)
            VALUES ($1,$2,$3,$4) RETURNING id
            """,
            seller_id, resource, amount, price,
        )
        return row["id"]


async def set_market_listing_message(listing_id: int, channel_id: int, message_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE market_listings SET channel_id = $1, message_id = $2 WHERE id = $3",
            channel_id, message_id, listing_id,
        )


async def get_market_listing(listing_id: int):
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM market_listings WHERE id = $1 AND active = true", listing_id)
        return dict(row) if row else None


async def close_market_listing(listing_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("UPDATE market_listings SET active = false WHERE id = $1", listing_id)


async def get_active_market_listings() -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM market_listings WHERE active = true ORDER BY created_at DESC")
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# المهام اليومية
# ------------------------------------------------------------------
async def assign_daily_quests(user_id: int, quests: list[dict]):
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM daily_quests WHERE user_id = $1 AND assigned_date = CURRENT_DATE", user_id
            )
            for q in quests:
                await conn.execute(
                    """
                    INSERT INTO daily_quests (user_id, quest_type, target, reward_gold)
                    VALUES ($1,$2,$3,$4)
                    """,
                    user_id, q["quest_type"], q["target"], q["reward_gold"],
                )


async def get_today_quests(user_id: int) -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM daily_quests WHERE user_id = $1 AND assigned_date = CURRENT_DATE ORDER BY id", user_id
        )
        return [dict(r) for r in rows]


async def increment_quest_progress(user_id: int, quest_type: str, amount: int = 1):
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            UPDATE daily_quests SET progress = LEAST(target, progress + $1)
            WHERE user_id = $2 AND quest_type = $3 AND assigned_date = CURRENT_DATE AND completed = false
            RETURNING id, progress, target
            """,
            amount, user_id, quest_type,
        )
        for r in rows:
            if r["progress"] >= r["target"]:
                await conn.execute("UPDATE daily_quests SET completed = true WHERE id = $1", r["id"])


async def claim_quest_reward(quest_id: int, user_id: int) -> int:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE daily_quests SET claimed = true
            WHERE id = $1 AND user_id = $2 AND completed = true AND claimed = false
            RETURNING reward_gold
            """,
            quest_id, user_id,
        )
        return row["reward_gold"] if row else 0


# ------------------------------------------------------------------
# التجسس
# ------------------------------------------------------------------
async def log_scout_attempt(scout_id: int, target_id: int, success: bool):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO scout_log (scout_id, target_id, success) VALUES ($1,$2,$3)",
            scout_id, target_id, success,
        )


async def get_recent_scouts_on(target_id: int, limit: int = 5) -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM scout_log WHERE target_id = $1 ORDER BY created_at DESC LIMIT $2",
            target_id, limit,
        )
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# الغارات
# ------------------------------------------------------------------
async def count_distinct_targets_today(attacker_id: int) -> int:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(DISTINCT defender_id) AS c FROM raid_log
            WHERE attacker_id = $1 AND created_at > now() - interval '24 hours'
            """,
            attacker_id,
        )
        return row["c"]


async def get_battle_history(user_id: int, limit: int = 10) -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM raid_log WHERE attacker_id = $1 OR defender_id = $1
            ORDER BY created_at DESC LIMIT $2
            """,
            user_id, limit,
        )
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# لوحة الصدارة
# ------------------------------------------------------------------
async def get_leaderboard_by_power(limit: int = 10) -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.user_id, p.culture, p.empire_name,
                   (t.infantry*10 + t.cavalry*15 + t.archers*12 + t.mercenary_power) AS power
            FROM players p JOIN troops t ON p.user_id = t.user_id
            ORDER BY power DESC LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# المرتزقة
# ------------------------------------------------------------------
async def set_mercenaries(user_id: int, power: int, expires_at):
    async with get_pool().acquire() as conn:
        await conn.execute(
            "UPDATE troops SET mercenary_power = $1, mercenary_expires_at = $2 WHERE user_id = $3",
            power, expires_at, user_id,
        )


# ------------------------------------------------------------------
# التذاكر
# ------------------------------------------------------------------
async def create_ticket(user_id: int, channel_id: int) -> int:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO tickets (user_id, channel_id) VALUES ($1,$2) RETURNING id", user_id, channel_id
        )
        return row["id"]


async def close_ticket(channel_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = $1", channel_id)


async def has_open_ticket(user_id: int) -> bool:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM tickets WHERE user_id = $1 AND status = 'open'", user_id
        )
        return row is not None


# ------------------------------------------------------------------
# وضع الصيانة
# ------------------------------------------------------------------
async def is_maintenance_mode() -> bool:
    return bool(await get_world_state("maintenance_mode", False))


async def set_maintenance_mode(active: bool):
    await set_world_state("maintenance_mode", active)
