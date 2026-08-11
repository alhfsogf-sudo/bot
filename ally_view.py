"""
ui/ally_view.py — قناة 'ally' الخاصة بكل لاعب.
قبل الانضمام لتحالف: تعرض زري تأسيس/انضمام (نفس فكرة AllianceHubView لكن خاصة وسرّية لصاحبها فقط).
بعد الانضمام: تعرض حالة التحالف الحالية وزر مغادرة.
هذا يغني عن الحاجة لقناة تحالفات مركزية عامة لكل لاعب على حدة.
"""
import discord

import database as db
from exceptions import PlayerNotFound
import embeds
from nickname import strip_alliance_tag
from alliance_view import CreateAllianceModal, JoinAllianceModal


def personal_ally_embed_sync(alliance_name: str = None, alliance_tag: str = None) -> discord.Embed:
    if alliance_name:
        return discord.Embed(
            title="🤝 حالة تحالفي",
            description=f"أنت عضو في **{alliance_name} [{alliance_tag}]**.\nيمكنك التنسيق في قناة التحالف المخصصة.",
            color=0x3498DB,
        )
    return discord.Embed(
        title="🤝 التحالفات",
        description="لست عضواً في أي تحالف بعد.\nأسّس تحالفك الخاص أو انضم لتحالف موجود بأحد الزرين أدناه.",
        color=0x95A5A6,
    )


class PersonalAllyView(discord.ui.View):
    """View ديناميكي: تُبنى أزراره حسب كون اللاعب في تحالف أم لا."""

    def __init__(self, in_alliance: bool):
        super().__init__(timeout=None)
        if in_alliance:
            self.add_item(LeaveAllianceButton())
        else:
            self.add_item(CreateAllianceButton())
            self.add_item(JoinAllianceButton())


class CreateAllianceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛡️ أسّس تحالفاً", style=discord.ButtonStyle.primary,
                          custom_id="siyada:ally_create")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateAllianceModal())


class JoinAllianceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🤝 انضم لتحالف", style=discord.ButtonStyle.secondary,
                          custom_id="siyada:ally_join")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JoinAllianceModal())


class LeaveAllianceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚪 غادر التحالف", style=discord.ButtonStyle.danger,
                          custom_id="siyada:ally_leave")

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            if not player.alliance_id:
                await interaction.response.send_message(embed=embeds.error_embed("لست عضواً في تحالف."),
                                                          ephemeral=True)
                return
            alliance = await db.get_alliance(player.alliance_id)
            guild = interaction.guild

            if alliance and alliance.leader_id == user_id:
                # القائد يغادر = حل التحالف بالكامل
                members = await db.get_alliance_members(alliance.alliance_id)
                for m in members:
                    await db.set_alliance_id(m.user_id, None)
                if alliance.role_id:
                    role = guild.get_role(alliance.role_id)
                    if role:
                        await role.delete(reason="حل التحالف")
                for ch_id in (alliance.hq_channel_id, alliance.war_room_channel_id):
                    ch = guild.get_channel(ch_id) if ch_id else None
                    if ch:
                        await ch.delete(reason="حل التحالف")
                await db.delete_alliance(alliance.alliance_id)
                await interaction.response.edit_message(
                    embed=personal_ally_embed_sync(), view=PersonalAllyView(in_alliance=False))
                await interaction.followup.send(
                    embed=embeds.mail_log_embed("🛡️ تم حل التحالف", "غادر القائد فانحلّ التحالف بالكامل.", 0xE74C3C),
                    ephemeral=True)
            else:
                await db.set_alliance_id(user_id, None)
                if alliance and alliance.role_id:
                    role = guild.get_role(alliance.role_id)
                    if role:
                        await interaction.user.remove_roles(role, reason="مغادرة تحالف")
                await strip_alliance_tag(interaction.user)
                await interaction.response.edit_message(
                    embed=personal_ally_embed_sync(), view=PersonalAllyView(in_alliance=False))
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
