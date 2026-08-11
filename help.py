"""cogs/help.py — الأمر الوحيد المتبقي للاعبين: /guide — يشرح فكرة اللعبة كاملة.
كل شيء آخر تحوّل لأزرار بناءً على طلب تحسين تجربة المستخدم."""
import discord
from discord import app_commands
from discord.ext import commands

from guide_view import build_guide_pages, GuidePaginatorView


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="guide", description="📖 اشرح لي فكرة اللعبة بالكامل خطوة بخطوة")
    async def guide(self, interaction: discord.Interaction):
        pages = build_guide_pages()
        view = GuidePaginatorView(pages)
        view._sync_buttons()
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
