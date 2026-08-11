-- sql/schema.sql — هيكل قاعدة البيانات الكامل (مرجعية / نشر يدوي)
-- ملاحظة: database.py ينشئ هذه الجداول تلقائياً بـ CREATE TABLE IF NOT EXISTS عند كل تشغيل

CREATE TABLE IF NOT EXISTS players (
    user_id             BIGINT PRIMARY KEY,
    guild_id            BIGINT NOT NULL,
    culture             TEXT NOT NULL,
    gold                INTEGER NOT NULL DEFAULT 0,
    wood                INTEGER NOT NULL DEFAULT 0,
    iron                INTEGER NOT NULL DEFAULT 0,
    food                INTEGER NOT NULL DEFAULT 0,
    essence             INTEGER NOT NULL DEFAULT 0,
    category_id         BIGINT,
    king_channel_id     BIGINT,
    war_channel_id      BIGINT,
    magic_channel_id    BIGINT,
    guide_channel_id    BIGINT,
    ally_channel_id     BIGINT,
    shield_expires_at   TIMESTAMPTZ,
    alliance_id         INTEGER,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_status_update  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS buildings (
    user_id  BIGINT PRIMARY KEY REFERENCES players(user_id) ON DELETE CASCADE,
    farm     INTEGER NOT NULL DEFAULT 1,
    mine     INTEGER NOT NULL DEFAULT 1,
    lumber   INTEGER NOT NULL DEFAULT 1,
    castle   INTEGER NOT NULL DEFAULT 1,
    altar    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS troops (
    user_id            BIGINT PRIMARY KEY REFERENCES players(user_id) ON DELETE CASCADE,
    infantry           INTEGER NOT NULL DEFAULT 0,
    cavalry            INTEGER NOT NULL DEFAULT 0,
    archers            INTEGER NOT NULL DEFAULT 0,
    wounded            INTEGER NOT NULL DEFAULT 0,
    wizard             TEXT,
    wizard_expires_at  TIMESTAMPTZ,
    beast              TEXT,
    beast_expires_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS alliances (
    alliance_id         SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    tag                 TEXT NOT NULL,
    leader_id           BIGINT NOT NULL,
    hq_channel_id       BIGINT,
    war_room_channel_id BIGINT,
    role_id             BIGINT,
    bank_gold           INTEGER NOT NULL DEFAULT 0,
    bank_wood           INTEGER NOT NULL DEFAULT 0,
    bank_iron           INTEGER NOT NULL DEFAULT 0,
    bank_food           INTEGER NOT NULL DEFAULT 0,
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
