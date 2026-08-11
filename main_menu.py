"""ui/main_menu.py — لوحة 'حالة إمبراطوريتي' العامة + زر تحديثها يدوياً (تحسين UX رئيسي)."""
import discord
import time

import database as db
from exceptions import PlayerNotFound, OnCooldown
import embeds
from game_math import military_power
from config import MANUAL_REFRESH_COOLDOWN_SECONDS

_last_refresh: dict[int, float] = {}


def _check_cooldown(user_id: int):
    now = time.time()
    last = _last_refresh.get(user_id, 0)
    if now - last < MANUAL_REFRESH_COOLDOWN_SECONDS:
        raise OnCooldown(int(MANUAL_REFRESH_COOLDOWN_SECONDS - (now - last)))
    _last_refresh[user_id] = now


class MainStatusView(discord.ui.View):
    """يُنشر في صندوق البريد — يعطي اللاعب نظرة شاملة وزر تحديث فوري بدون أوامر."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 تحديث حالتي الآن", style=discord.ButtonStyle.success,
                        custom_id="siyada:refresh_kingdom_status", row=0)
    async def refresh_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            _check_cooldown(user_id)
            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)
            troops = await db.get_troops(user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture, troops.mercenary_power)
            await db.touch_status_update(user_id)
            await interaction.response.send_message(
                embed=embeds.kingdom_status_embed(player, buildings, troops, power), ephemeral=True)
        except (PlayerNotFound, OnCooldown) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @discord.ui.button(label="📖 كيف ألعب؟", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:open_guide", row=0)
    async def open_guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        from guide_view import build_guide_pages, GuidePaginatorView
        pages = build_guide_pages()
        view = GuidePaginatorView(pages)
        view._sync_buttons()
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @discord.ui.button(label="🏆 لوحة الصدارة", style=discord.ButtonStyle.primary,
                        custom_id="siyada:leaderboard", row=1)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = await db.get_leaderboard_by_power(10)
        await interaction.response.send_message(embed=embeds.leaderboard_embed(rows), ephemeral=True)

    @discord.ui.button(label="🎫 فتح تذكرة دعم", style=discord.ButtonStyle.gray,
                        custom_id="siyada:open_ticket", row=1)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        interaction.client.dispatch("ticket_requested", interaction)

    @discord.ui.button(label="📜 مهامي اليومية", style=discord.ButtonStyle.success,
                        custom_id="siyada:daily_quests", row=1)
    async def daily_quests(self, interaction: discord.Interaction, button: discord.ui.Button):
        from quests import QuestsView
        quests = await db.get_today_quests(interaction.user.id)
        await interaction.response.send_message(embed=embeds.daily_quests_embed(quests), view=QuestsView(),
                                                  ephemeral=True)
