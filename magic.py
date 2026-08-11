"""cogs/magic.py — Module 6: نظام السحر. يستمع لأحداث القوائم المنسدلة في المذبح
بدل أوامر /summon_wizard /summon_beast /expedition."""
import discord
import random
from datetime import datetime, timedelta, timezone
from discord.ext import commands

import database as db
from exceptions import PlayerNotFound, NotEnoughResources
import embeds
from constants import WIZARDS, BEASTS, SUMMON_DURATION_DAYS, EXPEDITION_COST_RATIO, \
    EXPEDITION_SUCCESS_RATE, EXPEDITION_SUCCESS_RATE_ECLIPSE


class Magic(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        from magic_view import MagicView
        self.bot.add_view(MagicView())

    async def _refresh_magic_panel(self, guild: discord.Guild, user_id: int):
        from magic_view import MagicView
        from economy import _find_and_update_panel
        p = await db.try_get_player(user_id)
        if not p or not p.magic_channel_id:
            return
        b = await db.get_buildings(user_id)
        t = await db.get_troops(user_id)
        ch = guild.get_channel(p.magic_channel_id)
        if ch:
            await _find_and_update_panel(ch, embeds.magic_altar_embed(p, b, t), MagicView(), title_prefix="🔮")

    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_summon_requested(self, interaction: discord.Interaction, kind: str, key: str):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)
            troops = await db.get_troops(user_id)

            if buildings.altar < 5:
                await interaction.response.send_message(
                    embed=embeds.error_embed("🔮 يلزم ترقية المذبح للمستوى 5 أولاً."), ephemeral=True)
                return

            catalog = WIZARDS if kind == "wizard" else BEASTS
            data = catalog[key]

            if kind == "wizard" and troops.wizard:
                await interaction.response.send_message(
                    embed=embeds.error_embed("لديك ساحر بالفعل — لا يمكن استدعاء أكثر من واحد."), ephemeral=True)
                return
            if kind == "beast" and troops.beast:
                await interaction.response.send_message(
                    embed=embeds.error_embed("لديك مخلوق بالفعل — لا يمكن استدعاء أكثر من واحد."), ephemeral=True)
                return

            missing = {res: amt - getattr(player, res) for res, amt in data["cost"].items()
                       if getattr(player, res) < amt}
            if missing:
                raise NotEnoughResources(missing)

            await db.update_player_resources(user_id, **{k: -v for k, v in data["cost"].items()})
            expires = datetime.now(timezone.utc) + timedelta(days=SUMMON_DURATION_DAYS)
            if kind == "wizard":
                await db.set_wizard(user_id, data["name"], expires)
            else:
                await db.set_beast(user_id, data["name"], expires)

            await interaction.response.send_message(
                embed=embeds.success_embed(f"تم استدعاء {data['name']}! ({data['effect']})"), ephemeral=True)
            if interaction.guild:
                await self._refresh_magic_panel(interaction.guild, user_id)
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_expedition_requested(self, interaction: discord.Interaction, kind: str, key: str):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            troops = await db.get_troops(user_id)
            catalog = WIZARDS if kind == "wizard" else BEASTS
            data = catalog[key]

            if kind == "wizard" and troops.wizard:
                await interaction.response.send_message(
                    embed=embeds.error_embed("لديك ساحر بالفعل."), ephemeral=True)
                return
            if kind == "beast" and troops.beast:
                await interaction.response.send_message(
                    embed=embeds.error_embed("لديك مخلوق بالفعل."), ephemeral=True)
                return

            cost = {res: round(amt * EXPEDITION_COST_RATIO) for res, amt in data["cost"].items()}
            missing = {res: amt - getattr(player, res) for res, amt in cost.items()
                       if getattr(player, res) < amt}
            if missing:
                raise NotEnoughResources(missing)

            await db.update_player_resources(user_id, **{k: -v for k, v in cost.items()})

            success_rate = EXPEDITION_SUCCESS_RATE_ECLIPSE if await db.get_world_state("eclipse_active", False) \
                else EXPEDITION_SUCCESS_RATE
            if random.random() <= success_rate:
                expires = datetime.now(timezone.utc) + timedelta(days=SUMMON_DURATION_DAYS)
                if kind == "wizard":
                    await db.set_wizard(user_id, data["name"], expires)
                else:
                    await db.set_beast(user_id, data["name"], expires)
                await interaction.response.send_message(
                    embed=embeds.success_embed(f"🎉 نجحت البعثة! حصلت على {data['name']}"), ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=embeds.error_embed("💀 فشلت البعثة وضاعت الموارد."), ephemeral=True)

            if interaction.guild:
                await self._refresh_magic_panel(interaction.guild, user_id)
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Magic(bot))
