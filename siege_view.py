"""
ui/siege_view.py — نظام حصار حقيقي منسّق للتحالفات (#8).
عضو يبدأ حصاراً على هدف، وبقية أعضاء التحالف ينضمون بجنودهم خلال مهلة زمنية،
ثم تُحسم المعركة بجمع قوة كل المشاركين ضد قوة دفاع الهدف.
حالة الحصار في الذاكرة فقط (مدتها قصيرة — دقائق — على عكس التيتان/السوق التي تبقى أياماً،
لذلك لا حاجة لتخزينها في قاعدة البيانات بحسب طبيعتها المؤقتة جداً)."""
import discord
import asyncio
from datetime import datetime, timedelta, timezone

import database as db
from exceptions import PlayerNotFound
import embeds
from game_math import military_power
from logger import get_logger

log = get_logger("siege")

_active_sieges: dict[int, dict] = {}  # alliance_id -> siege state
DEFENDER_LOSS_RATIO_ON_SIEGE_WIN = 0.40
ATTACKERS_LOSS_RATIO_ON_SIEGE_WIN = 0.20
ATTACKERS_LOSS_RATIO_ON_SIEGE_LOSE = 0.60


class SiegeStartModal(discord.ui.Modal, title="🛡️ بدء حصار منسّق"):
    target_id = discord.ui.TextInput(label="آيدي الهدف", placeholder="123456789012345678")
    minutes = discord.ui.TextInput(label="مهلة انضمام الأعضاء بالدقائق (5-30)", placeholder="10")

    def __init__(self, alliance_id: int):
        super().__init__()
        self.alliance_id = alliance_id

    async def on_submit(self, interaction: discord.Interaction):
        if self.alliance_id in _active_sieges:
            await interaction.response.send_message(
                embed=embeds.error_embed("يوجد حصار نشط بالفعل لتحالفكم — انتظروا انتهاءه."), ephemeral=True)
            return
        try:
            target_id = int(self.target_id.value.strip())
            minutes = max(5, min(30, int(self.minutes.value.strip())))
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("قيم غير صحيحة."), ephemeral=True)
            return

        target = await db.try_get_player(target_id)
        if not target:
            await interaction.response.send_message(embed=embeds.error_embed("لا يوجد لاعب بهذا الآيدي."),
                                                      ephemeral=True)
            return
        if target.shield_active:
            await interaction.response.send_message(embed=embeds.error_embed("🛡️ الهدف محمي بدرع حالياً."),
                                                      ephemeral=True)
            return

        ends_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        _active_sieges[self.alliance_id] = {
            "target_id": target_id, "initiator_id": interaction.user.id,
            "participants": {}, "ends_at": ends_at,
        }

        e = discord.Embed(
            title="🛡️ بدأ حصار منسّق!",
            description=(
                f"الهدف: <@{target_id}>\n"
                f"بدأه: {interaction.user.mention}\n"
                f"⏳ ينتهي التجميع: <t:{int(ends_at.timestamp())}:R>\n\n"
                "اضغط 🤝 انضم بجنودك للمساهمة بقوتك في الهجوم الجماعي."
            ),
            color=0x922B21,
        )
        await interaction.response.send_message(embed=e, view=SiegeJoinView(self.alliance_id))

        await asyncio.sleep(minutes * 60)
        await _resolve_siege(interaction.client, interaction.guild, self.alliance_id)


class SiegeJoinModal(discord.ui.Modal, title="🤝 انضمام للحصار بجنودك"):
    infantry = discord.ui.TextInput(label="عدد المشاة", default="0", required=False)
    cavalry = discord.ui.TextInput(label="عدد الفرسان", default="0", required=False)
    archers = discord.ui.TextInput(label="عدد الرماة", default="0", required=False)

    def __init__(self, alliance_id: int):
        super().__init__()
        self.alliance_id = alliance_id

    async def on_submit(self, interaction: discord.Interaction):
        siege = _active_sieges.get(self.alliance_id)
        if not siege:
            await interaction.response.send_message(embed=embeds.error_embed("لا يوجد حصار نشط حالياً."),
                                                      ephemeral=True)
            return
        try:
            inf = int(self.infantry.value or 0)
            cav = int(self.cavalry.value or 0)
            arc = int(self.archers.value or 0)
            if inf + cav + arc <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("أرسل جندياً واحداً على الأقل."),
                                                      ephemeral=True)
            return

        user_id = interaction.user.id
        try:
            troops = await db.get_troops(user_id)
            if inf > troops.infantry or cav > troops.cavalry or arc > troops.archers:
                await interaction.response.send_message(embed=embeds.error_embed("لا تملك هذا العدد من الجنود."),
                                                          ephemeral=True)
                return
            await db.update_troops(user_id, infantry=-inf, cavalry=-cav, archers=-arc)
            prev = siege["participants"].get(user_id, {"infantry": 0, "cavalry": 0, "archers": 0})
            siege["participants"][user_id] = {
                "infantry": prev["infantry"] + inf, "cavalry": prev["cavalry"] + cav, "archers": prev["archers"] + arc,
            }
            await interaction.response.send_message(
                embed=embeds.success_embed("انضممت للحصار بنجاح! جنودك سُحبوا مؤقتاً من جيشك حتى الحسم."),
                ephemeral=True)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class SiegeJoinView(discord.ui.View):
    def __init__(self, alliance_id: int):
        super().__init__(timeout=1800)
        self.alliance_id = alliance_id

    @discord.ui.button(label="🤝 انضم بجنودك", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SiegeJoinModal(self.alliance_id))


class SiegeStartView(discord.ui.View):
    """يُنشر بشكل دائم في غرفة حرب التحالف."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🛡️ بدء حصار منسّق", style=discord.ButtonStyle.danger,
                        custom_id="siyada:start_siege")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = await db.get_player(interaction.user.id)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
            return
        if not player.alliance_id:
            await interaction.response.send_message(embed=embeds.error_embed("لست عضواً في تحالف."), ephemeral=True)
            return
        await interaction.response.send_modal(SiegeStartModal(player.alliance_id))


async def _resolve_siege(bot, guild: discord.Guild, alliance_id: int):
    siege = _active_sieges.pop(alliance_id, None)
    if not siege or not siege["participants"]:
        if siege:
            log.info(f"حصار التحالف {alliance_id} انتهى بلا أي مشاركين.")
        return

    target_id = siege["target_id"]
    defender = await db.try_get_player(target_id)
    if not defender:
        return
    def_troops = await db.get_troops(target_id)
    def_power = military_power(def_troops.infantry, def_troops.cavalry, def_troops.archers,
                                defender.culture, def_troops.mercenary_power)

    total_atk_power = 0
    for uid, sent in siege["participants"].items():
        p = await db.try_get_player(uid)
        culture = p.culture if p else None
        total_atk_power += military_power(sent["infantry"], sent["cavalry"], sent["archers"], culture)

    attackers_win = total_atk_power >= def_power

    if attackers_win:
        loot = {res: round(getattr(defender, res) * 0.15) for res in ("gold", "wood", "iron", "food")}
        await db.update_player_resources(target_id, **{k: -v for k, v in loot.items()})
        n = len(siege["participants"])
        share = {k: v // n for k, v in loot.items()}
        loss_ratio = ATTACKERS_LOSS_RATIO_ON_SIEGE_WIN
        # دفاع الهدف يخسر جزءاً من جيشه
        d_inf = round(def_troops.infantry * DEFENDER_LOSS_RATIO_ON_SIEGE_WIN)
        d_cav = round(def_troops.cavalry * DEFENDER_LOSS_RATIO_ON_SIEGE_WIN)
        d_arc = round(def_troops.archers * DEFENDER_LOSS_RATIO_ON_SIEGE_WIN)
        await db.update_troops(target_id, infantry=-d_inf, cavalry=-d_cav, archers=-d_arc)
        result_text = f"🏆 نجح الحصار! نُهب من الهدف: " + ", ".join(f"{v} {k}" for k, v in loot.items() if v)
    else:
        loss_ratio = ATTACKERS_LOSS_RATIO_ON_SIEGE_LOSE
        share = {}
        result_text = "🛡️ صمد المدافع أمام الحصار الجماعي!"

    for uid, sent in siege["participants"].items():
        lost = {t: round(amt * loss_ratio) for t, amt in sent.items()}
        survived = {t: sent[t] - lost[t] for t in sent}
        wounded_total = sum(lost.values())
        await db.update_troops(uid, infantry=survived["infantry"], cavalry=survived["cavalry"],
                                archers=survived["archers"], wounded=wounded_total)
        if share:
            await db.update_player_resources(uid, **share)

    alliance = await db.get_alliance(alliance_id)
    war_room = guild.get_channel(alliance.war_room_channel_id) if alliance else None
    if war_room:
        await war_room.send(embed=embeds.mail_log_embed(
            "🛡️ نتيجة الحصار المنسّق",
            f"الهدف: <@{target_id}>\nالمشاركون: {len(siege['participants'])}\n{result_text}",
            0x922B21 if attackers_win else 0x2ECC71,
        ))
    log.info(f"حصار تحالف {alliance_id} على {target_id}: {'نجاح' if attackers_win else 'فشل'}")
