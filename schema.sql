-- sql/schema.sql — هيكل قاعدة البيانات المصحح لدعم الأرقام الضخمة وبلا حدود

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
