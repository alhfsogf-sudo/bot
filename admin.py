"""cogs/admin.py — Module 10: أدوات الأدمن ومكافحة الغش + لوحة أدمن مرئية (#11) +
فحص توازن تلقائي (#21) + أرشفة نهاية الموسم (#22) + وضع الصيانة (#23).
تبقى هذه أوامر (أدمن فقط) لأنها أدوات إدارية وليست تجربة لاعب — الطلب كان استبدال أوامر *اللاعبين* بأزرار."""
import io
import discord
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands, tasks

from config import ADMIN_LOG_CHANNEL_ID, NEWS_CHANNEL_ID, GUILD_ID
import database as db
from exceptions import PlayerNotFound
import embeds
from game_math import military_power
from logger import get_logger

log = get_logger("admin")

CHEAT_RAID_THRESHOLD = 5
BALANCE_OUTLIER_RATIO = 3.0  # لاعب يُعتبر خارجاً عن التوازن إذا قوته > 3× متوسط القوة


# ------------------------------------------------------------------
# (#11) لوحة أدمن مرئية بأزرار بدل أوامر متفرقة
# ------------------------------------------------------------------
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="📊 إحصائيات السيرفر", style=discord.ButtonStyle.primary)
    async def stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = await db.get_all_players()
        rows = await db.get_leaderboard_by_power(1)
        avg_power = 0
        if players:
            all_rows = await db.get_leaderboard_by_power(len(players))
            avg_power = sum(r["power"] for r in all_rows) / len(all_rows)
        maintenance = await db.is_maintenance_mode()
        e = discord.Embed(title="📊 إحصائيات السيرفر", color=0x34495E)
        e.add_field(name="عدد اللاعبين", value=str(len(players)), inline=True)
        e.add_field(name="متوسط القوة", value=f"{avg_power:,.0f}", inline=True)
        e.add_field(name="وضع الصيانة", value="🚧 مفعّل" if maintenance else "✅ متوقف", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="👥 قائمة اللاعبين", style=discord.ButtonStyle.secondary)
    async def list_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = await db.get_all_players()
        lines = [f"<@{p.user_id}> — {p.empire_name or p.culture} — 🪙{p.gold:,}" for p in players[:40]]
        await interaction.response.send_message(
            embed=embeds.mail_log_embed(f"👥 اللاعبون ({len(players)})", "\n".join(lines) or "لا يوجد", 0x34495E),
            ephemeral=True)

    @discord.ui.button(label="🚧 تبديل وضع الصيانة", style=discord.ButtonStyle.danger)
    async def toggle_maintenance(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = await db.is_maintenance_mode()
        await db.set_maintenance_mode(not current)
        state = "🚧 تم تفعيل" if not current else "✅ تم إيقاف"
        await interaction.response.send_message(f"{state} وضع الصيانة.", ephemeral=True)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.balance_check.start()

    def cog_unload(self):
        self.balance_check.cancel()

    async def _log(self, guild: discord.Guild, text: str):
        ch = guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if ch:
            await ch.send(embed=embeds.mail_log_embed("🛠️ سجل الأدمن", text, 0x34495E))

    # ------------------------------------------------------------
    @app_commands.command(name="admin_panel", description="[أدمن] لوحة تحكم مرئية موحّدة (#11)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_panel(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=embeds.mail_log_embed("🛠️ لوحة تحكم الأدمن", "اختر إجراءً من الأزرار أدناه.", 0x34495E),
            view=AdminPanelView(), ephemeral=True)

    @app_commands.command(name="admin_give", description="[أدمن] إعطاء موارد للاعب")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_give(self, interaction: discord.Interaction, member: discord.Member,
                          resource: str, amount: int):
        try:
            await db.update_player_resources(member.id, **{resource: amount})
            await interaction.response.send_message(f"✅ أُعطي {member.mention} {amount} {resource}", ephemeral=True)
            await self._log(interaction.guild, f"{interaction.user.mention} أعطى {member.mention} {amount} {resource}")
        except Exception as e:
            await interaction.response.send_message(f"❌ خطأ: {e}", ephemeral=True)
            log.error(f"admin_give فشل: {e}", exc_info=True)

    @app_commands.command(name="admin_remove_shield", description="[أدمن] إزالة درع لاعب")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_remove_shield(self, interaction: discord.Interaction, member: discord.Member):
        await db.remove_shield(member.id)
        await interaction.response.send_message(f"✅ أُزيل درع {member.mention}", ephemeral=True)
        await self._log(interaction.guild, f"{interaction.user.mention} أزال درع {member.mention}")

    @app_commands.command(name="admin_reset_player", description="[أدمن] حذف إمبراطورية لاعب بالكامل")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_reset_player(self, interaction: discord.Interaction, member: discord.Member):
        try:
            player = await db.get_player(member.id)
            guild = interaction.guild
            for ch_id in (player.king_channel_id, player.war_channel_id, player.magic_channel_id,
                          player.guide_channel_id, player.ally_channel_id):
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.delete(reason="حذف إمبراطورية")
            cat = guild.get_channel(player.category_id)
            if cat:
                await cat.delete(reason="حذف إمبراطورية")
            await db.delete_player(member.id)
            await interaction.response.send_message(f"✅ حُذفت إمبراطورية {member.mention}", ephemeral=True)
            await self._log(guild, f"{interaction.user.mention} حذف إمبراطورية {member.mention}")
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @app_commands.command(name="admin_list_players", description="[أدمن] عرض قائمة اللاعبين المسجلين")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_list_players(self, interaction: discord.Interaction):
        players = await db.get_all_players()
        lines = [f"<@{p.user_id}> — {p.culture} — 🪙{p.gold}" for p in players[:40]]
        await interaction.response.send_message(
            embed=embeds.mail_log_embed(f"👥 اللاعبون ({len(players)})", "\n".join(lines) or "لا يوجد", 0x34495E),
            ephemeral=True)

    # ------------------------------------------------------------
    # (#23) وضع الصيانة
    # ------------------------------------------------------------
    @app_commands.command(name="admin_maintenance", description="[أدمن] تبديل وضع الصيانة تشغيل/إيقاف")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_maintenance(self, interaction: discord.Interaction):
        current = await db.is_maintenance_mode()
        await db.set_maintenance_mode(not current)
        state = "🚧 مفعّل الآن" if not current else "✅ مُوقف الآن"
        await interaction.response.send_message(f"وضع الصيانة {state}.", ephemeral=True)
        await self._log(interaction.guild, f"{interaction.user.mention} بدّل وضع الصيانة إلى: {state}")

    # ------------------------------------------------------------
    # (#22) أرشفة الموسم عند الانتهاء
    # ------------------------------------------------------------
    @app_commands.command(name="admin_end_season", description="[أدمن] إعلان نهاية الموسم مع أرشفة كاملة للإحصائيات")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_end_season(self, interaction: discord.Interaction, winner: discord.Member):
        await interaction.response.defer(ephemeral=True, thinking=True)
        news_ch = interaction.guild.get_channel(NEWS_CHANNEL_ID)
        if news_ch:
            await news_ch.send(embed=embeds.mail_log_embed(
                "🏆 نهاية الموسم!", f"الفائز بالموسم هو {winner.mention}! تهانينا لملك العالم الجديد 👑", 0xF1C40F))

        rows = await db.get_leaderboard_by_power(1000)
        lines = ["#\tاللاعب\tالثقافة\tالقوة"]
        for i, r in enumerate(rows, start=1):
            lines.append(f"{i}\t{r['user_id']}\t{r['culture']}\t{round(r['power'])}")
        content = "\n".join(lines)
        file = discord.File(io.BytesIO(content.encode("utf-8")),
                             filename=f"season_archive_{datetime.now(timezone.utc).date()}.txt")

        await interaction.followup.send("✅ أُعلنت نهاية الموسم وأُرفق أرشيف الإحصائيات.", file=file, ephemeral=True)
        await self._log(interaction.guild, f"{interaction.user.mention} أنهى الموسم — الفائز: {winner.mention}")

    # ------------------------------------------------------------
    # (#21) فحص توازن تلقائي — تنبيه الأدمن عند وجود لاعب متفوق بشكل غير طبيعي
    # ------------------------------------------------------------
    @tasks.loop(hours=24)
    async def balance_check(self):
        rows = await db.get_leaderboard_by_power(1000)
        if len(rows) < 5:
            return
        powers = [r["power"] for r in rows]
        avg_power = sum(powers) / len(powers)
        if avg_power <= 0:
            return
        outliers = [r for r in rows if r["power"] > avg_power * BALANCE_OUTLIER_RATIO]
        if not outliers:
            return
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return
        lines = [f"<@{r['user_id']}> — قوة {round(r['power']):,} (المتوسط: {round(avg_power):,})" for r in outliers]
        await self._log(guild, "⚖️ فحص التوازن اليومي رصد لاعبين متفوقين بشكل غير طبيعي:\n" + "\n".join(lines))
        log.info(f"فحص التوازن: {len(outliers)} لاعب خارج عن التوازن.")

    @balance_check.before_loop
    async def before_balance_check(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------
    # مكافحة الغش
    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_raid_initiated_for_cheat_check(self, attacker_id: int, defender_id: int):
        counts = await db.count_raids_on_all_last_24h(attacker_id)
        total = sum(counts.values())
        if total > CHEAT_RAID_THRESHOLD:
            guild = self.bot.get_guild(GUILD_ID)
            if guild:
                await self._log(guild, f"⚠️ اشتباه غش: <@{attacker_id}> نفّذ {total} غارة خلال 24 ساعة.")
                log.warning(f"اشتباه غش: {attacker_id} نفّذ {total} غارة خلال 24 ساعة.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
