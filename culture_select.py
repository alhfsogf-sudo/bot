"""ui/culture_select.py — أزرار اختيار الثقافة عند التسجيل + زر بدء التسجيل نفسه."""
import discord
from datetime import datetime, timezone, timedelta

from config import GUILD_ID, ACCOUNT_AGE_DAYS, NEWS_CHANNEL_ID, WORLD_LOG_CHANNEL_ID
import database as db
from exceptions import PlayerAlreadyExists, AccountTooNew
from constants import CULTURES, STARTING_RESOURCES, CHANNEL_KING, CHANNEL_WAR, CHANNEL_MAGIC, \
    CHANNEL_GUIDE, CHANNEL_ALLY
import embeds


class StartRegistrationView(discord.ui.View):
    """الزر الوحيد الدائم في قناة الدليل — يبدأ عملية التسجيل بدل أمر /start."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚀 ابدأ إمبراطوريتك", style=discord.ButtonStyle.success,
                        custom_id="siyada:start_registration")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        account_age = datetime.now(timezone.utc) - member.created_at
        if account_age < timedelta(days=ACCOUNT_AGE_DAYS):
            days_left = ACCOUNT_AGE_DAYS - account_age.days
            await interaction.response.send_message(
                embed=embeds.error_embed(AccountTooNew(days_left).message), ephemeral=True
            )
            return

        if await db.player_exists(member.id):
            await interaction.response.send_message(
                embed=embeds.error_embed(PlayerAlreadyExists().message), ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=embeds.culture_select_embed(), view=CultureSelectView(), ephemeral=True
        )

    @discord.ui.button(label="📖 اشرح لي اللعبة", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:explain_game")
    async def explain(self, interaction: discord.Interaction, button: discord.ui.Button):
        from guide_view import build_guide_pages
        pages = build_guide_pages()
        await interaction.response.send_message(embed=pages[0], view=None, ephemeral=True)


class EmpireNameModal(discord.ui.Modal, title="👑 اسمِّ إمبراطوريتك"):
    empire_name = discord.ui.TextInput(label="اسم الإمبراطورية", max_length=32,
                                        placeholder="مثال: مملكة الفجر الذهبي")

    def __init__(self, culture_key: str, parent_view: "CultureSelectView"):
        super().__init__()
        self.culture_key = culture_key
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        name = self.empire_name.value.strip() or interaction.user.display_name
        await self.parent_view._handle_culture(interaction, self.culture_key, name)


class CultureSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="⚔️ قائد عسكري", style=discord.ButtonStyle.danger)
    async def military(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmpireNameModal("military", self))

    @discord.ui.button(label="💰 بارون التجارة", style=discord.ButtonStyle.success)
    async def trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmpireNameModal("trade", self))

    @discord.ui.button(label="🔨 كبير البنّائين", style=discord.ButtonStyle.primary)
    async def industrial(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmpireNameModal("industrial", self))

    async def _handle_culture(self, interaction: discord.Interaction, culture_key: str, empire_name: str):
        member = interaction.user
        guild = interaction.guild or interaction.client.get_guild(GUILD_ID)
        if await db.player_exists(member.id):
            await interaction.followup.send(embed=embeds.error_embed(PlayerAlreadyExists().message))
            return

        culture = CULTURES[culture_key]

        role_name = f"{culture.emoji} {culture.name}"
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            role = await guild.create_role(name=role_name, color=discord.Color(culture.color),
                                            reason="ثقافة لاعب جديد")
        await member.add_roles(role, reason="اختيار ثقافة")

        overwrites = self._build_overwrites(guild, member, role)

        category = await guild.create_category(f"👑┃{empire_name}", overwrites=overwrites,
                                                 reason="إمبراطورية جديدة")
        king_ch = await guild.create_text_channel(CHANNEL_KING, category=category, overwrites=overwrites)
        war_ch = await guild.create_text_channel(CHANNEL_WAR, category=category, overwrites=overwrites)
        magic_ch = await guild.create_text_channel(CHANNEL_MAGIC, category=category, overwrites=overwrites)
        guide_ch = await guild.create_text_channel(CHANNEL_GUIDE, category=category, overwrites=overwrites)
        ally_ch = await guild.create_text_channel(CHANNEL_ALLY, category=category, overwrites=overwrites)

        player = await db.create_player(
            user_id=member.id,
            guild_id=guild.id,
            culture=culture_key,
            starting_resources=STARTING_RESOURCES[culture_key],
            category_id=category.id,
            king_channel_id=king_ch.id,
            war_channel_id=war_ch.id,
            magic_channel_id=magic_ch.id,
            guide_channel_id=guide_ch.id,
            ally_channel_id=ally_ch.id,
        )
        await db.set_empire_name(member.id, empire_name)
        player = await db.get_player(member.id)

        from quests import assign_quests_to_player
        await assign_quests_to_player(member.id)

        # نشر لوحات التحكم الأولية (بالأزرار فقط، بدون أوامر) — كل قناة تظهر للاعب نفسه حصرياً
        from dashboard_view import DashboardView
        from war_view import WarView
        from magic_view import MagicView
        from main_menu import MainStatusView
        from guide_view import build_guide_pages, GuidePaginatorView
        from ally_view import PersonalAllyView, personal_ally_embed_sync
        from database import get_buildings, get_troops
        from game_math import military_power

        buildings = await get_buildings(member.id)
        troops = await get_troops(member.id)
        power = military_power(troops.infantry, troops.cavalry, troops.archers, culture_key)

        # 👑 king — لوحة المبنى + رسالة ترحيب + وصول سريع لتحديث الحالة الشامل
        await king_ch.send(embed=embeds.welcome_embed(player, culture.name))
        await king_ch.send(embed=embeds.throne_hall_embed(player, buildings), view=DashboardView())
        await king_ch.send(embed=embeds.mail_log_embed(
            "🔄 وصول سريع", "اضغط الزر أدناه في أي وقت لعرض حالتك الكاملة فوراً.", 0x2C3E50),
            view=MainStatusView())

        # ⚔️ war — ديوان الحرب
        await war_ch.send(embed=embeds.war_divan_embed(player, troops, power), view=WarView())

        # 🔮 magic — المذبح السحري
        await magic_ch.send(embed=embeds.magic_altar_embed(player, buildings, troops), view=MagicView())

        # 📖 guide — شرح اللعبة الكامل مثبّتاً وخاصاً باللاعب
        guide_pages = build_guide_pages()
        guide_view = GuidePaginatorView(guide_pages)
        guide_view._sync_buttons()
        guide_msg = await guide_ch.send(embed=guide_pages[0], view=guide_view)
        try:
            await guide_msg.pin(reason="دليل اللعبة الدائم")
        except discord.HTTPException:
            pass

        # 🤝 ally — تأسيس/انضمام لتحالف، خاص باللاعب فقط
        await ally_ch.send(embed=personal_ally_embed_sync(), view=PersonalAllyView(in_alliance=False))

        await interaction.followup.send(embed=embeds.success_embed(
            f"تأسست إمبراطوريتك بنجاح! توجه إلى {king_ch.mention} للبدء."
        ))

        news_ch = guild.get_channel(NEWS_CHANNEL_ID)
        if news_ch:
            await news_ch.send(embed=embeds.mail_log_embed(
                "👑 إمبراطورية جديدة!",
                f"{member.mention} أسّس إمبراطورية **{empire_name}** بثقافة **{culture.name}** {culture.emoji}",
                culture.color,
            ))

        world_log_ch = guild.get_channel(WORLD_LOG_CHANNEL_ID)
        if world_log_ch and (not news_ch or world_log_ch.id != news_ch.id):
            await world_log_ch.send(embed=embeds.mail_log_embed(
                "📰 سجل عالمي", f"تأسست إمبراطورية جديدة: **{empire_name}** ({member.mention})", 0x95A5A6
            ))

    def _build_overwrites(self, guild: discord.Guild, member: discord.Member, role: discord.Role):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        admin_role = discord.utils.get(guild.roles, permissions=discord.Permissions(administrator=True))
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        return overwrites
