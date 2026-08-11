"""cogs/military.py — Module 4: تسجيل View ديوان الحرب الدائم + أمر أدمن لإعادة نشره."""
import discord
from discord import app_commands
from discord.ext import commands

from war_view import WarView
import database as db
import embeds
from game_math import military_power


class Military(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(WarView())

    @app_commands.command(name="setup_war", description="[أدمن] إعادة نشر لوحة ديوان الحرب في هذه القناة")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_war(self, interaction: discord.Interaction):
        try:
            player = await db.get_player(interaction.user.id)
            troops = await db.get_troops(player.user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture, troops.mercenary_power)
            await interaction.channel.send(embed=embeds.war_divan_embed(player, troops, power), view=WarView())
            await interaction.response.send_message("✅ تم النشر.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ تعذر تنفيذ الأمر: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Military(bot))
