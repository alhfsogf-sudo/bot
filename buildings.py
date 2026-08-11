"""cogs/buildings.py — Module 3: تسجيل View الترقية الدائم + أمر أدمن لإعادة نشره."""
import discord
from discord import app_commands
from discord.ext import commands

from dashboard_view import DashboardView
import database as db
import embeds


class Buildings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(DashboardView())  # يشتغل بعد إعادة التشغيل بفضل custom_id ثابت

    @app_commands.command(name="setup_throne", description="[أدمن] إعادة نشر لوحة قاعة العرش في هذه القناة")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_throne(self, interaction: discord.Interaction):
        try:
            player = await db.get_player(interaction.user.id)
        except Exception:
            await interaction.response.send_message("❌ استخدم هذا الأمر داخل قناة قاعة عرش لاعب مسجّل.",
                                                      ephemeral=True)
            return
        buildings = await db.get_buildings(player.user_id)
        await interaction.channel.send(embed=embeds.throne_hall_embed(player, buildings), view=DashboardView())
        await interaction.response.send_message("✅ تم النشر.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Buildings(bot))
