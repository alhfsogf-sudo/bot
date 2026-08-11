"""cogs/alliances.py — Module 7: تسجيل Views التحالف الدائمة + أمر أدمن لنشر المركز."""
import discord
from discord import app_commands
from discord.ext import commands

from alliance_view import AllianceHQView, AllianceHubView
from ally_view import PersonalAllyView
from siege_view import SiegeStartView
import embeds


class Alliances(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(AllianceHQView())
        self.bot.add_view(AllianceHubView())
        self.bot.add_view(SiegeStartView())
        # قناة 'ally' الشخصية لها حالتان بأزرار مختلفة — نسجّل الاثنتين حتى تعمل الأزرار بعد إعادة التشغيل
        self.bot.add_view(PersonalAllyView(in_alliance=False))
        self.bot.add_view(PersonalAllyView(in_alliance=True))

    @app_commands.command(name="setup_alliance_hub",
                           description="[أدمن] ينشر لوحة تأسيس/الانضمام للتحالفات في هذه القناة")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_alliance_hub(self, interaction: discord.Interaction):
        e = embeds.mail_log_embed(
            "🛡️ مركز التحالفات",
            "أسّس تحالفك الخاص (50,000 ذهب) أو انضم لتحالف موجود عبر الأزرار أدناه.",
            0x3498DB,
        )
        await interaction.channel.send(embed=e, view=AllianceHubView())
        await interaction.response.send_message("✅ تم النشر.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Alliances(bot))
