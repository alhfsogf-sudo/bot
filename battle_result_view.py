"""ui/battle_result_view.py — أزرار 'انتقام' و'استنجد بالتحالف' تحت نتائج المعارك في الأخبار العالمية."""
import discord

import database as db
import embeds


class BattleResultView(discord.ui.View):
    def __init__(self, loser_id: int, winner_id: int):
        super().__init__(timeout=None)
        self.loser_id = loser_id
        self.winner_id = winner_id

    @discord.ui.button(label="🔄 انتقام", style=discord.ButtonStyle.danger, custom_id="siyada:revenge")
    async def revenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.loser_id:
            await interaction.response.send_message(
                embed=embeds.error_embed("هذا الزر مخصص للاعب المهزوم فقط."), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=embeds.mail_log_embed(
                "🔄 فرصة انتقام",
                f"توجه إلى ديوان حربك واضغط 🗺️ شنّ غارة على الآيدي `{self.winner_id}`",
                0xE67E22,
            ), ephemeral=True)

    @discord.ui.button(label="🛡️ استنجد بالتحالف", style=discord.ButtonStyle.primary,
                        custom_id="siyada:alliance_help")
    async def alliance_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.loser_id:
            await interaction.response.send_message(
                embed=embeds.error_embed("هذا الزر مخصص للاعب المهزوم فقط."), ephemeral=True)
            return
        player = await db.try_get_player(interaction.user.id)
        if not player or not player.alliance_id:
            await interaction.response.send_message(embed=embeds.error_embed("لست عضواً في تحالف."),
                                                      ephemeral=True)
            return
        alliance = await db.get_alliance(player.alliance_id)
        role_mention = f"<@&{alliance.role_id}>" if alliance and alliance.role_id else ""
        await interaction.response.send_message(
            content=f"🚨 {role_mention} {interaction.user.mention} يحتاج دعماً فورياً بعد هزيمته!",
            allowed_mentions=discord.AllowedMentions(roles=True))
