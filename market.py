"""cogs/market.py — Module 8: تسجيل View السوق الدائم + أمر أدمن لنشره.
عند إعادة تشغيل البوت، تُعاد إحياء أزرار كل عروض السوق النشطة من قاعدة البيانات (#1)."""
import discord
from discord import app_commands
from discord.ext import commands

from market_view import MarketView, BuyListingView
import database as db
import embeds
from logger import get_logger

log = get_logger("market")


class Market(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(MarketView())
        listings = await db.get_active_market_listings()
        restored = 0
        for listing in listings:
            if listing.get("message_id"):
                self.bot.add_view(BuyListingView(listing["id"]), message_id=listing["message_id"])
                restored += 1
        log.info(f"أُعيد تفعيل {restored} عرض سوق نشط بعد إعادة التشغيل.")

    @app_commands.command(name="setup_market", description="[أدمن] ينشر لوحة السوق الحرة في هذه القناة")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_market(self, interaction: discord.Interaction):
        e = embeds.mail_log_embed(
            "🤝 السوق الحرة",
            "اعرض مواردك للبيع بزر واحد، أو اشترِ من أي عرض معروض في هذه القناة.",
            0xF1C40F,
        )
        await interaction.channel.send(embed=e, view=MarketView())
        await interaction.response.send_message("✅ تم النشر.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Market(bot))
