"""cogs/quests.py — Module 12: نظام المهام اليومية (#9)."""
import discord
import random
from datetime import datetime, timezone, time as dtime
from discord.ext import commands, tasks

import database as db
from exceptions import PlayerNotFound
import embeds
from config import DAILY_QUEST_COUNT
from logger import get_logger

log = get_logger("quests")

QUEST_POOL = [
    {"quest_type": "train", "targets": [20, 50, 100], "reward": [300, 600, 1000]},
    {"quest_type": "upgrade", "targets": [1, 2], "reward": [500, 900]},
    {"quest_type": "raid_win", "targets": [1, 2, 3], "reward": [800, 1500, 2200]},
]


def _roll_quests() -> list[dict]:
    chosen = random.sample(QUEST_POOL, k=min(DAILY_QUEST_COUNT, len(QUEST_POOL)))
    quests = []
    for q in chosen:
        idx = random.randrange(len(q["targets"]))
        quests.append({
            "quest_type": q["quest_type"],
            "target": q["targets"][idx],
            "reward_gold": q["reward"][idx],
        })
    return quests


async def assign_quests_to_player(user_id: int):
    await db.assign_daily_quests(user_id, _roll_quests())


class QuestsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎁 استلام مكافآت المهام المكتملة", style=discord.ButtonStyle.success,
                        custom_id="siyada:claim_quests")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            await db.get_player(user_id)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
            return

        quests = await db.get_today_quests(user_id)
        total = 0
        for q in quests:
            if q["completed"] and not q["claimed"]:
                total += await db.claim_quest_reward(q["id"], user_id)
        if total > 0:
            await db.update_player_resources(user_id, gold=total)
            await interaction.response.send_message(
                embed=embeds.success_embed(f"🎉 استلمت {total:,} 🪙 من مهامك المكتملة!"), ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=embeds.error_embed("لا توجد مكافآت متاحة للاستلام الآن."), ephemeral=True)


class Quests(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_reset.start()

    def cog_unload(self):
        self.daily_reset.cancel()

    async def cog_load(self):
        self.bot.add_view(QuestsView())

    @tasks.loop(time=dtime(hour=0, minute=0, tzinfo=timezone.utc))
    async def daily_reset(self):
        players = await db.get_all_players()
        for p in players:
            try:
                await assign_quests_to_player(p.user_id)
            except Exception as e:
                log.error(f"فشل تعيين مهام للاعب {p.user_id}: {e}")
        log.info(f"تم تجديد المهام اليومية لـ {len(players)} لاعب.")

    @daily_reset.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Quests(bot))
