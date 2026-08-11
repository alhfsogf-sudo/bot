"""
bot.py — نقطة الدخول الرئيسية للبوت.
"""
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, GUILD_ID
from database import init_pool, close_pool, create_tables
from logger import get_logger

log = get_logger("bot")

COGS = [
    "onboarding",
    "economy",
    "buildings",
    "military",
    "combat",
    "magic",
    "alliances",
    "market",
    "world_events",
    "quests",
    "tickets",
    "admin",
    "help",
]


class SiyadaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        log.info("يتصل بقاعدة البيانات...")
        await init_pool()
        await create_tables()
        log.info("قاعدة البيانات جاهزة.")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"تم تحميل {cog}")
            except Exception as e:
                log.error(f"فشل تحميل {cog}: {e}", exc_info=True)

        # تسجيل الأزرار الدائمة الإضافية (المستقلة عن الـ cogs الفردية)
        from main_menu import MainStatusView
        from battle_result_view import BattleResultView
        self.add_view(MainStatusView())
        self.add_view(BattleResultView(loser_id=0, winner_id=0))  # placeholder ثابت custom_id فقط

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info(f"تمت مزامنة {len(synced)} أمر Slash (أدمن + /guide فقط).")

    async def on_ready(self):
        log.info(f"{self.user} جاهز ومتصل!")
        await self.change_presence(activity=discord.Game(name="⚔️ سيادة الأمم | /guide"))

    async def on_error(self, event_method, *args, **kwargs):
        log.error(f"خطأ غير متوقع في {event_method}", exc_info=True)

    async def close(self):
        await close_pool()
        await super().close()


def main():
    bot = SiyadaBot()
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
