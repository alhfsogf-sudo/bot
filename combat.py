"""cogs/combat.py — Module 5: محرك المعارك. يستمع لأحداث raid_initiated / scout_initiated
التي تُطلقها نوافذ (modals) ديوان الحرب بدل أوامر /raid و /scout."""
import discord
import random
from discord.ext import commands

import database as db
from exceptions import PlayerNotFound, ShieldActive, OutOfPowerRange, RaidLimitReached
import embeds
from constants import SCOUT_COST, SCOUT_SUCCESS_RATE, RAID_LIMIT_PER_TARGET_24H, TROOP_TYPES
from game_math import military_power, can_attack
from config import NEWS_CHANNEL_ID, MAX_DISTINCT_TARGETS_PER_DAY
from logger import get_logger
from exceptions import GameError

log = get_logger("combat")


class TooManyTargets(GameError):
    def __init__(self, limit: int):
        super().__init__(f"🚫 وصلت للحد الأقصى ({limit}) من الأهداف المختلفة خلال 24 ساعة. حاول لاحقاً.")

ATTACKER_WIN_LOOT_RATIO = 0.10
ATTACKER_WIN_LOSS_RATIO = 0.30
DEFENDER_WIN_ATTACKER_LOSS_RATIO = 0.70
WOUNDED_RATIO = 0.70
DEAD_RATIO = 0.30


def _dominant_type(sent: dict) -> str:
    return max(sent, key=lambda k: sent[k]) if any(sent.values()) else "infantry"


class Combat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_raid_initiated(self, interaction: discord.Interaction, target_id: int, sent: dict):
        try:
            attacker = await db.get_player(interaction.user.id)
            defender = await db.try_get_player(target_id)
            if defender is None:
                await self._notify(interaction, "❌ لا يوجد لاعب مسجّل بهذا الآيدي.")
                return
            if defender.user_id == attacker.user_id:
                await self._notify(interaction, "❌ لا يمكنك مهاجمة نفسك.")
                return
            if defender.shield_active:
                raise ShieldActive()

            raids_count = await db.count_raids_last_24h(attacker.user_id, defender.user_id)
            if raids_count >= RAID_LIMIT_PER_TARGET_24H:
                raise RaidLimitReached()

            distinct_targets = await db.count_distinct_targets_today(attacker.user_id)
            if raids_count == 0 and distinct_targets >= MAX_DISTINCT_TARGETS_PER_DAY:
                raise TooManyTargets(MAX_DISTINCT_TARGETS_PER_DAY)

            atk_troops = await db.get_troops(attacker.user_id)
            def_troops = await db.get_troops(defender.user_id)

            available = {"infantry": atk_troops.infantry, "cavalry": atk_troops.cavalry, "archers": atk_troops.archers}
            for t, amt in sent.items():
                if amt > available.get(t, 0):
                    await self._notify(interaction, f"❌ لا تملك {amt} من {TROOP_TYPES[t]['name']}.")
                    return

            atk_power = military_power(sent.get("infantry", 0), sent.get("cavalry", 0),
                                        sent.get("archers", 0), attacker.culture, atk_troops.mercenary_power)
            def_power = military_power(def_troops.infantry, def_troops.cavalry, def_troops.archers,
                                        defender.culture, def_troops.mercenary_power)

            if not can_attack(atk_power, def_power):
                raise OutOfPowerRange()

            attacker_wins = atk_power >= def_power

            if attacker_wins:
                loot = {res: round(getattr(defender, res) * ATTACKER_WIN_LOOT_RATIO)
                        for res in ("gold", "wood", "iron", "food")}
                await db.update_player_resources(defender.user_id, **{k: -v for k, v in loot.items()})
                await db.update_player_resources(attacker.user_id, **loot)
                loss_ratio = ATTACKER_WIN_LOSS_RATIO
                result_text = f"🏆 **{interaction.user.display_name}** انتصر! نهب: " + \
                              ", ".join(f"{v} {k}" for k, v in loot.items() if v)
            else:
                loss_ratio = DEFENDER_WIN_ATTACKER_LOSS_RATIO
                result_text = f"🛡️ **{defender.user_id}** صدّ الهجوم بنجاح!"

            for t, amt in sent.items():
                if amt <= 0:
                    continue
                lost = round(amt * loss_ratio)
                wounded = round(lost * WOUNDED_RATIO)
                dead = lost - wounded
                await db.update_troops(attacker.user_id, **{t: -lost, "wounded": wounded})

            await db.log_raid(attacker.user_id, defender.user_id, "attacker_win" if attacker_wins else "defender_win")
            self.bot.dispatch("raid_initiated_for_cheat_check", attacker.user_id, defender.user_id)
            if attacker_wins:
                await db.increment_quest_progress(attacker.user_id, "raid_win", 1)

            await self._notify(interaction, result_text)

            # (#5) إشعار خاص (DM) فوري للمدافع بمجرد تعرضه لغارة — بدل انتظاره مراجعة الروم
            defender_member = interaction.guild.get_member(defender.user_id)
            if defender_member:
                try:
                    await defender_member.send(embed=embeds.mail_log_embed(
                        "🚨 تعرّضت لغارة!",
                        f"هاجمك {interaction.user.mention} في **{interaction.guild.name}**.\n{result_text}",
                        0xC0392B,
                    ))
                except discord.Forbidden:
                    pass  # اللاعب مغلق الرسائل الخاصة — يُتجاهل بأمان
                except discord.HTTPException:
                    pass

            # تحديث لوحة ديوان الحرب لكل من المهاجم والمدافع
            await self._refresh_war_panel(interaction.guild, attacker.user_id)
            await self._refresh_war_panel(interaction.guild, defender.user_id)

            # نشر النتيجة في الأخبار العالمية مع أزرار انتقام/استنجاد
            news_ch = interaction.guild.get_channel(NEWS_CHANNEL_ID)
            if news_ch:
                from battle_result_view import BattleResultView
                e = embeds.mail_log_embed(
                    "⚔️ نتيجة معركة",
                    f"{interaction.user.mention} ⚔️ {defender_member.mention if defender_member else defender.user_id}\n{result_text}",
                    0xC0392B if attacker_wins else 0x2ECC71,
                )
                await news_ch.send(embed=e, view=BattleResultView(loser_id=defender.user_id if attacker_wins else attacker.user_id,
                                                                    winner_id=attacker.user_id if attacker_wins else defender.user_id))

            # صندوق بريد الطرفين
            for uid, msg in ((attacker.user_id, result_text), (defender.user_id, result_text)):
                p = await db.try_get_player(uid)
                if p:
                    mail_ch = interaction.guild.get_channel(p.king_channel_id)
                    if mail_ch:
                        await mail_ch.send(embed=embeds.mail_log_embed("⚔️ نتيجة الغارة", msg, 0xC0392B))

        except (PlayerNotFound, ShieldActive, OutOfPowerRange, RaidLimitReached, TooManyTargets) as e:
            await self._notify(interaction, e.message)

    async def _refresh_war_panel(self, guild: discord.Guild, user_id: int):
        from war_view import WarView
        from economy import _find_and_update_panel
        p = await db.try_get_player(user_id)
        if not p:
            return
        t = await db.get_troops(user_id)
        power = military_power(t.infantry, t.cavalry, t.archers, p.culture, t.mercenary_power)
        ch = guild.get_channel(p.war_channel_id)
        await _find_and_update_panel(ch, embeds.war_divan_embed(p, t, power), WarView(), title_prefix="⚔️")

    async def _notify(self, interaction: discord.Interaction, text: str):
        try:
            channel = interaction.channel
            await channel.send(content=f"{interaction.user.mention}", embed=embeds.mail_log_embed("⚔️ نتيجة", text, 0x95A5A6))
        except Exception:
            pass

    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_scout_initiated(self, interaction: discord.Interaction, target_id: int):
        try:
            attacker = await db.get_player(interaction.user.id)
            defender = await db.try_get_player(target_id)
            if defender is None:
                await interaction.response.send_message(embed=embeds.error_embed("لا يوجد لاعب بهذا الآيدي."),
                                                          ephemeral=True)
                return
            if attacker.gold < SCOUT_COST:
                await interaction.response.send_message(
                    embed=embeds.error_embed(f"تحتاج {SCOUT_COST} ذهب للتجسس."), ephemeral=True)
                return

            await db.update_player_resources(attacker.user_id, gold=-SCOUT_COST)

            def_troops = await db.get_troops(defender.user_id)
            has_illusionist = def_troops.wizard == "illusionist"

            if has_illusionist or random.random() > SCOUT_SUCCESS_RATE:
                await db.log_scout_attempt(attacker.user_id, defender.user_id, success=False)
                await interaction.response.send_message(embed=embeds.error_embed("🌀 فشلت مهمة التجسس!"),
                                                          ephemeral=True)
                return

            await db.log_scout_attempt(attacker.user_id, defender.user_id, success=True)
            e = discord.Embed(title="🔎 تقرير التجسس", color=0x34495E)
            e.add_field(name="الجيش", value=(
                f"⚔️ مشاة: {def_troops.infantry}\n🐎 فرسان: {def_troops.cavalry}\n🏹 رماة: {def_troops.archers}"
            ))
            await interaction.response.send_message(embed=e, ephemeral=True)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Combat(bot))
