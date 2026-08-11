"""cogs/world_events.py — Module 9: الأحداث العالمية (المجاعة، الكسوف، التيتان).
الحالة العالمية أصبحت دائمة بالكامل في قاعدة البيانات (#1) بدل متغيرات وحدة في الذاكرة،
حتى تنجو الأحداث الجارية من إعادة تشغيل البوت."""
import discord
import asyncio
from datetime import datetime, timedelta, timezone
from discord import app_commands
from discord.ext import commands, tasks

from config import NEWS_CHANNEL_ID, WORLD_LOG_CHANNEL_ID, GUILD_ID
import database as db
import embeds
from titan_view import TitanAttackView
from logger import get_logger

log = get_logger("world_events")


class WorldEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.weekly_check.start()
        self.titan_watchdog.start()

    def cog_unload(self):
        self.weekly_check.cancel()
        self.titan_watchdog.cancel()

    async def cog_load(self):
        # إعادة تفعيل زر مهاجمة التيتان إذا كانت الغارة لا تزال جارية بعد إعادة التشغيل
        titan = await db.get_world_state("titan")
        if titan and titan.get("hp", 0) > 0 and titan.get("message_id"):
            self.bot.add_view(TitanAttackView(), message_id=titan["message_id"])

    async def _world_log(self, text: str, color: int = 0x95A5A6):
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return
        ch = guild.get_channel(WORLD_LOG_CHANNEL_ID)
        if ch:
            await ch.send(embed=embeds.mail_log_embed("📰 سجل عالمي", text, color))

    @tasks.loop(hours=1)
    async def weekly_check(self):
        now = datetime.now(timezone.utc)
        if now.weekday() in (0, 3) and now.hour == 12:  # الاثنين=0 الخميس=3
            import random
            event = random.choice(["famine", "eclipse", "titan"])
            await self._trigger(event)

    @weekly_check.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    async def titan_watchdog(self):
        titan = await db.get_world_state("titan")
        if not titan:
            return
        now = datetime.now(timezone.utc)
        ends_at = datetime.fromisoformat(titan["ends_at"])
        if now >= ends_at:
            guild = self.bot.get_guild(GUILD_ID)
            news_ch = guild.get_channel(NEWS_CHANNEL_ID) if guild else None
            if titan["hp"] <= 0:
                text = "🎉 هُزم التيتان! كل اللاعبين يحصلون على +10,000🪙 و +5,000⛓️"
                for p in await db.get_all_players():
                    await db.update_player_resources(p.user_id, gold=10000, iron=5000)
            else:
                text = "💀 نجا التيتان! كل اللاعبين يخسرون 10% من طعامهم."
                for p in await db.get_all_players():
                    await db.update_player_resources(p.user_id, food=-round(p.food * 0.10))
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed("👹 انتهت غارة التيتان", text, 0x7F8C8D))
            await self._world_log(f"انتهت غارة التيتان — {text}")
            await db.delete_world_state("titan")

    @titan_watchdog.before_loop
    async def before_titan(self):
        await self.bot.wait_until_ready()

    async def _trigger(self, event: str):
        guild = self.bot.get_guild(GUILD_ID)
        news_ch = guild.get_channel(NEWS_CHANNEL_ID) if guild else None

        if event == "famine":
            await db.set_world_state("famine_active", True)
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed(
                    "☠️ المجاعة الكبرى بدأت!", "إنتاج الطعام ينخفض 50% لجميع اللاعبين لمدة 24 ساعة.", 0x7F1D1D))
            await self._world_log("بدأت المجاعة الكبرى (24 ساعة).", 0x7F1D1D)
            await asyncio.sleep(86400)
            await db.set_world_state("famine_active", False)
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed("☀️ انتهت المجاعة الكبرى", "", 0x27AE60))
            await self._world_log("انتهت المجاعة الكبرى.", 0x27AE60)

        elif event == "eclipse":
            await db.set_world_state("eclipse_active", True)
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed(
                    "🌑 الكسوف الصوفي بدأ!", "نسبة نجاح البعثات السحرية ارتفعت إلى 20% لمدة 24 ساعة.", 0x2C3E50))
            await self._world_log("بدأ الكسوف الصوفي (24 ساعة).", 0x2C3E50)
            await asyncio.sleep(86400)
            await db.set_world_state("eclipse_active", False)
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed("🌕 انتهى الكسوف الصوفي", "", 0x27AE60))
            await self._world_log("انتهى الكسوف الصوفي.", 0x27AE60)

        elif event == "titan":
            titan = {
                "hp": 1_000_000, "max_hp": 1_000_000,
                "ends_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            }
            if news_ch:
                e = discord.Embed(
                    title="👹 غارة التيتان!",
                    description=f"❤️ الصحة المتبقية: **{titan['hp']:,} / {titan['max_hp']:,}** (100.0%)",
                    color=0x922B21,
                )
                view = TitanAttackView()
                msg = await news_ch.send(embed=e, view=view)
                titan["message_id"] = msg.id
                self.bot.add_view(view, message_id=msg.id)
            await db.set_world_state("titan", titan)
            await self._world_log("بدأت غارة التيتان! ❤️ 1,000,000 نقطة صحة.", 0x922B21)

    @app_commands.command(name="trigger_event", description="[أدمن] إطلاق حدث عالمي يدوياً")
    @app_commands.describe(event="famine / eclipse / titan")
    @app_commands.checks.has_permissions(administrator=True)
    async def trigger_event(self, interaction: discord.Interaction, event: str):
        if event not in ("famine", "eclipse", "titan"):
            await interaction.response.send_message("❌ استخدم: famine / eclipse / titan", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ جارٍ إطلاق حدث: {event}", ephemeral=True)
        self.bot.loop.create_task(self._trigger(event))


async def setup(bot: commands.Bot):
    await bot.add_cog(WorldEvents(bot))
