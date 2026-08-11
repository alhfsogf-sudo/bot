"""
cogs/economy.py — Module 2: محرك الموارد التلقائي.
تحسين UX: نفس الدورة تُحدّث لوحات قاعة العرش/ديوان الحرب/المذبح تلقائياً كل ساعة.
يضم أيضاً: تحذير انتهاء الدرع (#14)، التلميحات الذكية (#15)، وانتهاء صلاحية المرتزقة (#19).
"""
import discord
from datetime import datetime, timezone
from discord.ext import commands, tasks

import database as db
import embeds
from game_math import (
    hourly_production, corruption_upkeep_multiplier, military_power,
)
from dashboard_view import DashboardView
from war_view import WarView
from magic_view import MagicView
from config import STATUS_REFRESH_HOURS, SHIELD_WARNING_MINUTES_BEFORE
from logger import get_logger

log = get_logger("economy")

FOOD_CRISIS_DEATH_RATE = 0.05
GOLD_CRISIS_PRODUCTION_PENALTY = 0.30
SMART_TIP_GOLD_THRESHOLD = 5000
SMART_TIP_COOLDOWN_HOURS = 24


async def _find_and_update_panel(channel: discord.abc.GuildChannel, embed: discord.Embed, view: discord.ui.View,
                                  title_prefix: str = None):
    """يبحث عن آخر رسالة للبوت تطابق عنوان اللوحة (title_prefix) ويحدّثها، أو ينشر واحدة جديدة إذا لم توجد.
    استخدام title_prefix ضروري في القنوات المدمجة (مثل king) التي تحتوي أكثر من نوع رسالة Embed."""
    if channel is None:
        return
    try:
        async for msg in channel.history(limit=50):
            if msg.author.id != channel.guild.me.id or not msg.embeds:
                continue
            if title_prefix is None or (msg.embeds[0].title or "").startswith(title_prefix):
                await msg.edit(embed=embed, view=view)
                return
        await channel.send(embed=embed, view=view)
    except discord.HTTPException:
        pass


class Economy(commands.Cog):
    """Module 2: نظام الموارد التلقائي — أهم نظام في اللعبة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hourly_tick.start()
        self.shield_warning_check.start()

    def cog_unload(self):
        self.hourly_tick.cancel()
        self.shield_warning_check.cancel()

    # ------------------------------------------------------------
    @tasks.loop(hours=STATUS_REFRESH_HOURS)
    async def hourly_tick(self):
        players = await db.get_all_players()
        for player in players:
            try:
                await self._process_player_tick(player)
            except Exception as e:
                log.error(f"خطأ أثناء معالجة اللاعب {player.user_id}: {e}", exc_info=True)

    @hourly_tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------
    # (#14) تحذير خاص (DM) قبل انتهاء درع المبتدئين بساعة
    # ------------------------------------------------------------
    @tasks.loop(minutes=15)
    async def shield_warning_check(self):
        players = await db.get_players_with_expiring_shield(SHIELD_WARNING_MINUTES_BEFORE)
        for p in players:
            guild = self.bot.get_guild(p.guild_id)
            member = guild.get_member(p.user_id) if guild else None
            if member:
                try:
                    await member.send(embed=embeds.mail_log_embed(
                        "🛡️ درعك على وشك الانتهاء!",
                        f"درع الحماية عن **{p.empire_name or 'إمبراطوريتك'}** سينتهي خلال أقل من ساعة. "
                        "تأكد من تجهيز دفاعاتك.",
                        0xE67E22,
                    ))
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass
            await db.mark_shield_warned(p.user_id)

    @shield_warning_check.before_loop
    async def before_shield_warning(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------
    async def _process_player_tick(self, player):
        buildings = await db.get_buildings(player.user_id)
        troops = await db.get_troops(player.user_id)
        guild = self.bot.get_guild(player.guild_id)
        if guild is None:
            return

        report_lines = []

        # 0) انتهاء صلاحية المرتزقة (#19)
        if troops.mercenary_power > 0 and troops.mercenary_expires_at:
            expires = troops.mercenary_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires:
                await db.set_mercenaries(player.user_id, 0, None)
                report_lines.append("💰 انتهت مدة استئجار مرتزقتك وغادروا جيشك.")
                troops = await db.get_troops(player.user_id)

        # 1) الإنتاج
        famine_active = await db.get_world_state("famine_active", False)

        production = {"gold": 0, "wood": 0, "iron": 0, "food": 0, "essence": 0}
        gold_crisis = player.gold <= 0
        for b in ("farm", "mine", "lumber", "altar"):
            level = getattr(buildings, b)
            if level <= 0:
                continue
            prod = hourly_production(b, level, player.culture)
            for res, amt in prod.items():
                if gold_crisis and res in ("wood", "iron", "essence"):
                    amt = round(amt * (1 - GOLD_CRISIS_PRODUCTION_PENALTY))
                if famine_active and res == "food":
                    amt = round(amt * 0.5)
                production[res] += amt

        if any(production.values()):
            report_lines.append(
                "📈 الإنتاج: " + ", ".join(f"+{v} {k}" for k, v in production.items() if v)
            )

        # 2) صيانة الطعام والذهب
        total_troops = troops.infantry + troops.cavalry + troops.archers
        corruption = corruption_upkeep_multiplier(total_troops)
        food_upkeep = round(total_troops * 1 * corruption)
        gold_upkeep = round((troops.cavalry * 2 + troops.archers * 1) * corruption)

        production["food"] -= food_upkeep
        production["gold"] -= gold_upkeep
        if food_upkeep or gold_upkeep:
            report_lines.append(f"🍖 صيانة: -{food_upkeep} طعام، -{gold_upkeep} ذهب (فساد ×{corruption})")

        await db.update_player_resources(player.user_id, **production)
        player = await db.get_player(player.user_id)

        # 3) أزمة الطعام — موت الجنود
        if player.food <= 0 and total_troops > 0:
            deaths = max(1, round(total_troops * FOOD_CRISIS_DEATH_RATE))
            inf_d = round(deaths * (troops.infantry / total_troops)) if total_troops else 0
            cav_d = round(deaths * (troops.cavalry / total_troops)) if total_troops else 0
            arc_d = max(0, deaths - inf_d - cav_d)
            await db.update_troops(player.user_id, infantry=-inf_d, cavalry=-cav_d, archers=-arc_d)
            report_lines.append(f"☠️ أزمة طعام! مات {deaths} جندي بسبب الجوع.")

        # 4) أزمة السحر — مغادرة الكيانات
        if player.essence <= 0:
            if troops.wizard:
                await db.set_wizard(player.user_id, None, None)
                report_lines.append(f"🔮 نفد السحر — غادرك ساحرك **{troops.wizard}**!")
            if troops.beast:
                await db.set_beast(player.user_id, None, None)
                report_lines.append(f"🔮 نفد السحر — غادرك مخلوقك **{troops.beast}**!")

        # 5) التلميحات الذكية (#15) — موارد متراكمة بلا استخدام
        if (player.gold > SMART_TIP_GOLD_THRESHOLD and any(getattr(buildings, b) < 5 for b in
                                                             ("farm", "mine", "lumber", "castle", "altar"))):
            last_tip = player.last_tip_at
            if last_tip and last_tip.tzinfo is None:
                last_tip = last_tip.replace(tzinfo=timezone.utc)
            tip_due = last_tip is None or \
                (datetime.now(timezone.utc) - last_tip).total_seconds() > SMART_TIP_COOLDOWN_HOURS * 3600
            if tip_due:
                report_lines.append(
                    f"💡 تلميح: لديك {player.gold:,} 🪙 متراكمة دون استخدام — فكّر بترقية أحد مبانيك!")
                await db.mark_tip_sent(player.user_id)

        # إعادة الجلب النهائي بعد كل التعديلات
        player = await db.get_player(player.user_id)
        buildings = await db.get_buildings(player.user_id)
        troops = await db.get_troops(player.user_id)
        power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture, troops.mercenary_power)

        # 6) تحديث اللوحات الثلاث تلقائياً (تحسين UX الأساسي المطلوب)
        king_ch = guild.get_channel(player.king_channel_id)
        war_ch = guild.get_channel(player.war_channel_id)
        magic_ch = guild.get_channel(player.magic_channel_id)

        await _find_and_update_panel(king_ch, embeds.throne_hall_embed(player, buildings), DashboardView(),
                                      title_prefix="🏰")
        await _find_and_update_panel(war_ch, embeds.war_divan_embed(player, troops, power), WarView(),
                                      title_prefix="⚔️")
        await _find_and_update_panel(magic_ch, embeds.magic_altar_embed(player, buildings, troops), MagicView(),
                                      title_prefix="🔮")

        # 7) تقرير الساعة يُرسل كرسالة جديدة أسفل لوحة king (سجل نظام مدمج بدل قناة بريد منفصلة)
        if king_ch and report_lines:
            await king_ch.send(embed=embeds.mail_log_embed(
                "🕐 تقرير الساعة", "\n".join(report_lines), 0x3498DB
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
