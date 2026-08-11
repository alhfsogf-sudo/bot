"""ui/alliance_view.py — أزرار مقر التحالف (إيداع / طلب دعم) + إنشاء/انضمام بأزرار عامة."""
import discord

import database as db
from exceptions import PlayerNotFound, NotEnoughResources
import embeds
from constants import ALLIANCE_CREATION_COST, EMOJI
from nickname import apply_alliance_tag


class CreateAllianceModal(discord.ui.Modal, title="🛡️ تأسيس تحالف"):
    name = discord.ui.TextInput(label="اسم التحالف", max_length=50)
    tag = discord.ui.TextInput(label="الرمز (TAG)", max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            if player.alliance_id:
                await interaction.response.send_message(
                    embed=embeds.error_embed("أنت بالفعل عضو في تحالف."), ephemeral=True)
                return
            if player.gold < ALLIANCE_CREATION_COST:
                raise NotEnoughResources({"gold": ALLIANCE_CREATION_COST - player.gold})

            await db.update_player_resources(user_id, gold=-ALLIANCE_CREATION_COST)
            alliance = await db.create_alliance(self.name.value, self.tag.value.upper(), user_id)

            guild = interaction.guild
            role = await guild.create_role(name=f"[{alliance.tag}] {alliance.name}",
                                            reason="تأسيس تحالف")
            await interaction.user.add_roles(role)
            await apply_alliance_tag(interaction.user, alliance.tag)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            }
            category = await guild.create_category(f"🛡️┃{alliance.tag}", overwrites=overwrites,
                                                     reason="تأسيس تحالف")
            hq_channel = await guild.create_text_channel(f"🛡️┃hq", category=category, overwrites=overwrites)
            war_room_channel = await guild.create_text_channel(f"⚔️┃war-room", category=category, overwrites=overwrites)

            await db.set_alliance_channel_role(alliance.alliance_id, hq_channel.id, war_room_channel.id, role.id)
            await db.set_alliance_id(user_id, alliance.alliance_id)

            from siege_view import SiegeStartView
            await hq_channel.send(
                embed=embeds.mail_log_embed(
                    f"🛡️ مقر تحالف {alliance.name} [{alliance.tag}]",
                    f"القائد: {interaction.user.mention}\nرقم التحالف: **{alliance.alliance_id}**",
                    0x3498DB,
                ),
                view=AllianceHQView(),
            )
            await war_room_channel.send(embed=embeds.mail_log_embed(
                "⚔️ غرفة الحرب",
                "نسّقوا هجماتكم ودفاعاتكم هنا بعيداً عن بقية أعضاء الخادم.\n"
                "اضغط 🛡️ لبدء حصار جماعي منسّق على أي هدف — كل الأعضاء يقدرون ينضمون بجنودهم.",
                0xC0392B), view=SiegeStartView())

            await interaction.response.send_message(
                embed=embeds.success_embed(f"تأسس تحالفك! رقمه: **{alliance.alliance_id}** — {hq_channel.mention}"),
                ephemeral=True)

            await _refresh_personal_ally_channel(guild, user_id)
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class JoinAllianceModal(discord.ui.Modal, title="🤝 الانضمام لتحالف"):
    alliance_id = discord.ui.TextInput(label="رقم التحالف", placeholder="1")

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            aid = int(self.alliance_id.value.strip())
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("رقم غير صحيح."), ephemeral=True)
            return
        try:
            player = await db.get_player(user_id)
            if player.alliance_id:
                await interaction.response.send_message(embed=embeds.error_embed("أنت بالفعل عضو في تحالف."),
                                                          ephemeral=True)
                return
            alliance = await db.get_alliance(aid)
            if not alliance:
                await interaction.response.send_message(embed=embeds.error_embed("لا يوجد تحالف بهذا الرقم."),
                                                          ephemeral=True)
                return
            await db.set_alliance_id(user_id, aid)
            guild = interaction.guild
            if alliance.role_id:
                role = guild.get_role(alliance.role_id)
                if role:
                    await interaction.user.add_roles(role)
                    await apply_alliance_tag(interaction.user, alliance.tag)
            await interaction.response.send_message(
                embed=embeds.success_embed(f"انضممت إلى **{alliance.name} [{alliance.tag}]**"), ephemeral=True)

            await _refresh_personal_ally_channel(guild, user_id)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


async def _refresh_personal_ally_channel(guild: discord.Guild, user_id: int):
    """يحدّث قناة 'ally' الخاصة بلاعب بعد تأسيس/انضمام/مغادرة تحالف — تحوّل أزرارها تلقائياً."""
    from ally_view import PersonalAllyView, personal_ally_embed_sync
    player = await db.try_get_player(user_id)
    if not player or not player.ally_channel_id:
        return
    ch = guild.get_channel(player.ally_channel_id)
    if not ch:
        return
    alliance = await db.get_alliance(player.alliance_id) if player.alliance_id else None
    embed = personal_ally_embed_sync(alliance.name, alliance.tag) if alliance else personal_ally_embed_sync()
    view = PersonalAllyView(in_alliance=bool(alliance))
    async for msg in ch.history(limit=10):
        if msg.author.id == guild.me.id and msg.embeds:
            await msg.edit(embed=embed, view=view)
            return
    await ch.send(embed=embed, view=view)


class DepositModal(discord.ui.Modal, title="💰 إيداع في بنك التحالف"):
    resource = discord.ui.TextInput(label="المورد (gold/wood/iron/food)", placeholder="gold")
    amount = discord.ui.TextInput(label="الكمية", placeholder="1000")

    async def on_submit(self, interaction: discord.Interaction):
        res = self.resource.value.strip().lower()
        if res not in {"gold", "wood", "iron", "food"}:
            await interaction.response.send_message(embed=embeds.error_embed("مورد غير مدعوم."), ephemeral=True)
            return
        try:
            amt = int(self.amount.value)
            if amt <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("كمية غير صحيحة."), ephemeral=True)
            return

        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            if not player.alliance_id:
                await interaction.response.send_message(embed=embeds.error_embed("لست عضواً في تحالف."),
                                                          ephemeral=True)
                return
            if getattr(player, res) < amt:
                raise NotEnoughResources({res: amt - getattr(player, res)})

            await db.update_player_resources(user_id, **{res: -amt})
            await db.update_alliance_bank(player.alliance_id, **{f"bank_{res}": amt})

            await interaction.response.send_message(
                embed=embeds.success_embed(f"تم إيداع {amt} {EMOJI.get(res, res)} في بنك التحالف."), ephemeral=True)
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class AllianceHQView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 إيداع في البنك", style=discord.ButtonStyle.success,
                        custom_id="siyada:alliance_deposit")
    async def deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DepositModal())

    @discord.ui.button(label="🛡️ طلب دعم حصار", style=discord.ButtonStyle.danger,
                        custom_id="siyada:alliance_support")
    async def request_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = await db.get_player(interaction.user.id)
            if not player.alliance_id:
                await interaction.response.send_message(embed=embeds.error_embed("لست عضواً في تحالف."),
                                                          ephemeral=True)
                return
            alliance = await db.get_alliance(player.alliance_id)
            role_mention = f"<@&{alliance.role_id}>" if alliance.role_id else ""
            await interaction.response.send_message(
                content=f"🚨 {role_mention} نداء استغاثة من {interaction.user.mention}! يحتاج دعماً فورياً!",
                allowed_mentions=discord.AllowedMentions(roles=True))
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class AllianceHubView(discord.ui.View):
    """View عام يُنشر في قناة التحالفات المركزية — لتأسيس تحالف أو الانضمام لواحد."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🛡️ أسّس تحالفاً", style=discord.ButtonStyle.primary,
                        custom_id="siyada:create_alliance")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateAllianceModal())

    @discord.ui.button(label="🤝 انضم لتحالف", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:join_alliance")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(JoinAllianceModal())
