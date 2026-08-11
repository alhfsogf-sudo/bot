"""cogs/tickets.py — Module 11: نظام تذاكر الدعم/الشكاوى (#13)."""
import discord
from discord import app_commands
from discord.ext import commands

from config import ADMIN_LOG_CHANNEL_ID
import database as db
from exceptions import PlayerNotFound
import embeds
from logger import get_logger

log = get_logger("tickets")


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="siyada:close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.close_ticket(interaction.channel.id)
        await interaction.response.send_message("سيتم إغلاق هذه التذكرة خلال 10 ثوانٍ...")
        import asyncio
        await asyncio.sleep(10)
        try:
            await interaction.channel.delete(reason="إغلاق تذكرة")
        except discord.HTTPException:
            pass


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketCloseView())

    @commands.Cog.listener()
    async def on_ticket_requested(self, interaction: discord.Interaction):
        try:
            player = await db.get_player(interaction.user.id)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
            return

        if await db.has_open_ticket(interaction.user.id):
            await interaction.response.send_message(
                embed=embeds.error_embed("لديك تذكرة مفتوحة بالفعل — راجعها قبل فتح تذكرة جديدة."), ephemeral=True)
            return

        guild = interaction.guild
        admin_log_ch = guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        admin_role = discord.utils.get(guild.roles, permissions=discord.Permissions(administrator=True))
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        ticket_ch = await guild.create_text_channel(
            f"🎫┃ticket-{interaction.user.name}"[:95], overwrites=overwrites,
            reason="فتح تذكرة دعم",
        )
        await db.create_ticket(interaction.user.id, ticket_ch.id)

        await ticket_ch.send(
            content=f"{interaction.user.mention}",
            embed=embeds.mail_log_embed(
                "🎫 تذكرة دعم جديدة",
                "اشرح مشكلتك أو استفسارك هنا وسيتواصل معك أحد المشرفين قريباً.\n"
                "اضغط 🔒 لإغلاق التذكرة عند الانتهاء.",
                0x3498DB,
            ),
            view=TicketCloseView(),
        )
        if admin_log_ch:
            await admin_log_ch.send(embed=embeds.mail_log_embed(
                "🎫 تذكرة جديدة", f"{interaction.user.mention} فتح تذكرة: {ticket_ch.mention}", 0xF39C12))

        await interaction.response.send_message(
            embed=embeds.success_embed(f"تم فتح تذكرتك: {ticket_ch.mention}"), ephemeral=True)
        log.info(f"تذكرة جديدة من {interaction.user.id} في {ticket_ch.id}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
