"""ui/titan_view.py — زر مهاجمة التيتان في حدث غارة التيتان (PvE).
حالة التيتان أصبحت دائمة في قاعدة البيانات (#1) — الضرر لا يُفقد عند إعادة تشغيل البوت."""
import discord

import database as db
from exceptions import PlayerNotFound
import embeds
from game_math import military_power


class TitanAttackView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚔️ هاجم التيتان", style=discord.ButtonStyle.danger, custom_id="siyada:attack_titan")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = await db.get_player(interaction.user.id)
            troops = await db.get_troops(interaction.user.id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture,
                                    troops.mercenary_power)
            damage = max(1, round(power))

            titan = await db.get_world_state("titan")
            if not titan or titan.get("hp", 0) <= 0:
                await interaction.response.send_message(embed=embeds.error_embed("لا توجد غارة تيتان نشطة حالياً."),
                                                          ephemeral=True)
                return

            titan["hp"] = max(0, titan["hp"] - damage)
            await db.set_world_state("titan", titan)

            remaining_pct = (titan["hp"] / titan["max_hp"]) * 100
            e = interaction.message.embeds[0]
            e.description = f"❤️ الصحة المتبقية: **{titan['hp']:,} / {titan['max_hp']:,}** ({remaining_pct:.1f}%)"
            await interaction.response.edit_message(embed=e, view=self)
            await interaction.followup.send(
                embed=embeds.success_embed(f"ألحقت **{damage:,}** ضرر بالتيتان!"), ephemeral=True)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
