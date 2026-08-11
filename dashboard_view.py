"""ui/dashboard_view.py — أزرار ترقية المباني في قاعة العرش + زر تحديث فوري."""
import discord
import time

import database as db
from exceptions import PlayerNotFound, BuildingMaxLevel, NotEnoughResources, OnCooldown
import embeds
from game_math import building_upgrade_cost, military_power
from config import MANUAL_REFRESH_COOLDOWN_SECONDS

BUILDING_LABELS = {
    "farm": ("🌾 ترقية المزرعة", "farm"),
    "mine": ("⛏️ ترقية المنجم", "mine"),
    "lumber": ("🪓 ترقية المنشرة", "lumber"),
    "castle": ("🏰 ترقية القلعة", "castle"),
    "altar": ("🔮 ترقية المذبح", "altar"),
}

_last_refresh: dict[int, float] = {}  # user_id -> unix ts، لتبريد زر التحديث اليدوي


def _check_cooldown(user_id: int):
    now = time.time()
    last = _last_refresh.get(user_id, 0)
    if now - last < MANUAL_REFRESH_COOLDOWN_SECONDS:
        raise OnCooldown(int(MANUAL_REFRESH_COOLDOWN_SECONDS - (now - last)))
    _last_refresh[user_id] = now


class DashboardView(discord.ui.View):
    """View مستمر (timeout=None) — يشتغل حتى بعد إعادة تشغيل البوت عبر custom_id ثابت."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _upgrade(self, interaction: discord.Interaction, building: str, label: str):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)
            current_level = getattr(buildings, building)

            if current_level >= 5:
                raise BuildingMaxLevel()

            cost = building_upgrade_cost(building, current_level, player.culture)
            missing = {res: amt - getattr(player, res) for res, amt in cost.items()
                       if getattr(player, res) < amt}
            if missing:
                raise NotEnoughResources(missing)

            deltas = {res: -amt for res, amt in cost.items()}
            await db.update_player_resources(user_id, **deltas)
            await db.upgrade_building(user_id, building)
            await db.increment_quest_progress(user_id, "upgrade", 1)

            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)

            await interaction.response.edit_message(embed=embeds.throne_hall_embed(player, buildings), view=self)

            mail_ch = interaction.guild.get_channel(player.king_channel_id)
            if mail_ch:
                await mail_ch.send(embed=embeds.mail_log_embed(
                    "🏗️ ترقية ناجحة",
                    f"{label} إلى المستوى **{getattr(buildings, building)}**",
                    0x2ECC71,
                ))
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
        except (BuildingMaxLevel, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @discord.ui.button(label="🌾 ترقية المزرعة", style=discord.ButtonStyle.success,
                        custom_id="siyada:upgrade_farm", row=0)
    async def upgrade_farm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "farm", "🌾 المزرعة")

    @discord.ui.button(label="⛏️ ترقية المنجم", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:upgrade_mine", row=0)
    async def upgrade_mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "mine", "⛏️ المنجم")

    @discord.ui.button(label="🪓 ترقية المنشرة", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:upgrade_lumber", row=0)
    async def upgrade_lumber(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "lumber", "🪓 المنشرة")

    @discord.ui.button(label="🏰 ترقية القلعة", style=discord.ButtonStyle.primary,
                        custom_id="siyada:upgrade_castle", row=1)
    async def upgrade_castle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "castle", "🏰 القلعة")

    @discord.ui.button(label="🔮 ترقية المذبح", style=discord.ButtonStyle.primary,
                        custom_id="siyada:upgrade_altar", row=1)
    async def upgrade_altar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "altar", "🔮 المذبح")

    @discord.ui.button(label="🔄 تحديث الآن", style=discord.ButtonStyle.gray,
                        custom_id="siyada:refresh_throne", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            _check_cooldown(user_id)
            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)
            await db.touch_status_update(user_id)
            await interaction.response.edit_message(embed=embeds.throne_hall_embed(player, buildings), view=self)
        except (PlayerNotFound, OnCooldown) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
