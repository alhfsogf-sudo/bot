"""cogs/onboarding.py — نشر لوحة التسجيل (زر بدلاً من أمر /start)."""
import discord
from discord import app_commands
from discord.ext import commands

from config import GUIDE_CHANNEL_ID
import embeds
from culture_select import StartRegistrationView


class Onboarding(commands.Cog):
    """Module 1: التسجيل عبر الأزرار فقط."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # تسجيل الأزرار الدائمة حتى تعمل بعد إعادة تشغيل البوت
        self.bot.add_view(StartRegistrationView())

    @app_commands.command(name="setup_guide", description="[أدمن] ينشر لوحة بدء اللعبة في قناة الدليل")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_guide(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(GUIDE_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ لم يتم العثور على قناة الدليل.", ephemeral=True)
            return
        await channel.send(embed=embeds.guide_embed(), view=StartRegistrationView())
        await interaction.response.send_message("✅ تم نشر لوحة بدء اللعبة.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
