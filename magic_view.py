"""ui/magic_view.py — أزرار المذبح السحري (استدعاء / بعثة / تحديث). تحل محل أوامر السحر السابقة."""
import discord
import time
from datetime import datetime, timedelta, timezone

import database as db
from exceptions import PlayerNotFound, NotEnoughResources, OnCooldown
import embeds
from constants import WIZARDS, BEASTS, SUMMON_DURATION_DAYS, EXPEDITION_COST_RATIO
from config import MANUAL_REFRESH_COOLDOWN_SECONDS

_last_refresh: dict[int, float] = {}


def _check_cooldown(user_id: int):
    now = time.time()
    last = _last_refresh.get(user_id, 0)
    if now - last < MANUAL_REFRESH_COOLDOWN_SECONDS:
        raise OnCooldown(int(MANUAL_REFRESH_COOLDOWN_SECONDS - (now - last)))
    _last_refresh[user_id] = now


class SummonWizardSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=w["name"], value=key, description=w["effect"][:100])
                   for key, w in WIZARDS.items()]
        super().__init__(placeholder="اختر ساحراً لاستدعائه...", options=options,
                          custom_id="siyada:select_wizard")

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        interaction.client.dispatch("summon_requested", interaction, "wizard", key)


class SummonBeastSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=b["name"], value=key, description=b["effect"][:100])
                   for key, b in BEASTS.items()]
        super().__init__(placeholder="اختر مخلوقاً لاستدعائه...", options=options,
                          custom_id="siyada:select_beast")

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        interaction.client.dispatch("summon_requested", interaction, "beast", key)


class ExpeditionSelect(discord.ui.Select):
    def __init__(self):
        options = (
            [discord.SelectOption(label=f"🧙 {w['name']}", value=f"wizard:{k}") for k, w in WIZARDS.items()]
            + [discord.SelectOption(label=f"🐲 {b['name']}", value=f"beast:{k}") for k, b in BEASTS.items()]
        )
        super().__init__(placeholder="اختر بعثة سحرية محفوفة بالمخاطر...", options=options,
                          custom_id="siyada:select_expedition")

    async def callback(self, interaction: discord.Interaction):
        kind, key = self.values[0].split(":")
        interaction.client.dispatch("expedition_requested", interaction, kind, key)


class MagicView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SummonWizardSelect())
        self.add_item(SummonBeastSelect())
        self.add_item(ExpeditionSelect())

    @discord.ui.button(label="🔄 تحديث الآن", style=discord.ButtonStyle.gray,
                        custom_id="siyada:refresh_magic", row=3)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            _check_cooldown(user_id)
            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)
            troops = await db.get_troops(user_id)
            await db.touch_status_update(user_id)
            await interaction.response.edit_message(
                embed=embeds.magic_altar_embed(player, buildings, troops), view=self)
        except (PlayerNotFound, OnCooldown) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
