"""utils/embeds.py — مصنع كل الـ Embeds المرئية في البوت."""
import discord
from datetime import datetime, timezone

from constants import EMOJI, CULTURES
from models import Player, Buildings, Troops


def _now_str() -> str:
    return f"<t:{int(datetime.now(timezone.utc).timestamp())}:R>"


def _next_refresh_str(hours: int = 1) -> str:
    from datetime import timedelta
    nxt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return f"<t:{int(nxt.timestamp())}:R>"


def _progress_bar(level: int, max_level: int = 5, length: int = 5) -> str:
    filled = round((level / max_level) * length)
    return "▰" * filled + "▱" * (length - filled)


# ------------------------------------------------------------------
# قناة الدليل
# ------------------------------------------------------------------
def guide_embed() -> discord.Embed:
    e = discord.Embed(
        title="⚔️ سيادة الأمم — Empires of Discord",
        description=(
            "مرحباً بك في عالم **سيادة الأمم**!\n"
            "ابنِ إمبراطوريتك، درّب جيشك، تحالف أو احارب — "
            "والفائز من يستولي على عاصمة الخادم!\n\n"
            "اضغط الزر أدناه لتبدأ رحلتك. اختيار الثقافة **نهائي** فاختر بحكمة."
        ),
        color=0x2C3E50,
    )
    for c in CULTURES.values():
        e.add_field(name=f"{c.emoji} {c.name}", value=c.description, inline=False)
    e.set_footer(text="اضغط 📖 لشرح اللعبة الكامل في أي وقت")
    return e


def culture_select_embed() -> discord.Embed:
    e = discord.Embed(
        title="🎭 اختر ثقافتك",
        description="هذا القرار **نهائي ولا رجعة فيه**. اختر بما يناسب أسلوب لعبك.",
        color=0x8E44AD,
    )
    for c in CULTURES.values():
        e.add_field(name=f"{c.emoji} {c.name}", value=c.description, inline=False)
    return e


def welcome_embed(player: Player, culture_name: str) -> discord.Embed:
    e = discord.Embed(
        title="👑 تأسست إمبراطوريتك!",
        description=(
            f"ثقافتك: **{culture_name}**\n"
            f"🛡️ لديك درع حماية **48 ساعة** — لا أحد يقدر يهاجمك خلالها."
        ),
        color=0x27AE60,
    )
    e.add_field(name="مواردك الابتدائية", value=_resources_line(player.resources), inline=False)
    e.set_footer(text="راجع صندوق البريد لكل التحديثات، وقاعة العرش للتحكم في مبانيك")
    return e


# ------------------------------------------------------------------
# لوحات التحكم (تتحدث كل ساعة تلقائياً + عند الطلب)
# ------------------------------------------------------------------
def _resources_line(resources: dict) -> str:
    return (
        f"{EMOJI['gold']} {resources['gold']:,}  "
        f"{EMOJI['wood']} {resources['wood']:,}  "
        f"{EMOJI['iron']} {resources['iron']:,}  "
        f"{EMOJI['food']} {resources['food']:,}  "
        f"{EMOJI['essence']} {resources['essence']:,}"
    )


def throne_hall_embed(player: Player, buildings: Buildings) -> discord.Embed:
    culture = CULTURES[player.culture]
    shield_txt = "🛡️ **نشط**" if player.shield_active else "❌ منتهي"
    if player.shield_active and player.shield_time_left:
        hrs = int(player.shield_time_left.total_seconds() // 3600)
        mins = int((player.shield_time_left.total_seconds() % 3600) // 60)
        shield_txt += f" ({hrs} س {mins} د متبقية)"

    title_name = player.empire_name or culture.name
    e = discord.Embed(
        title=f"🏰 قاعة العرش — {culture.emoji} {title_name}",
        color=culture.color,
    )
    e.add_field(name="💰 الموارد", value=_resources_line(player.resources), inline=False)
    e.add_field(
        name="🏗️ المباني",
        value=(
            f"🌾 المزرعة: {_progress_bar(buildings.farm)} مستوى **{buildings.farm}**\n"
            f"⛏️ المنجم: {_progress_bar(buildings.mine)} مستوى **{buildings.mine}**\n"
            f"🪓 المنشرة: {_progress_bar(buildings.lumber)} مستوى **{buildings.lumber}**\n"
            f"🏰 القلعة: {_progress_bar(buildings.castle)} مستوى **{buildings.castle}**\n"
            f"🔮 المذبح: {_progress_bar(buildings.altar)} مستوى **{buildings.altar}**"
        ),
        inline=False,
    )
    e.add_field(name="🛡️ الدرع", value=shield_txt, inline=False)
    e.set_footer(text=f"🔄 آخر تحديث: الآن  •  تحديث تلقائي تالٍ: {_next_refresh_str()}")
    e.timestamp = datetime.now(timezone.utc)
    return e


def war_divan_embed(player: Player, troops: Troops, power: float) -> discord.Embed:
    culture = CULTURES[player.culture]
    e = discord.Embed(title=f"⚔️ ديوان الحرب — {culture.name}", color=0xC0392B)
    e.add_field(
        name="🪖 الجيش",
        value=(
            f"⚔️ مشاة: **{troops.infantry:,}**\n"
            f"🐎 فرسان: **{troops.cavalry:,}**\n"
            f"🏹 رماة: **{troops.archers:,}**\n"
            f"🩹 جرحى: **{troops.wounded:,}**"
        ),
        inline=False,
    )
    e.add_field(name="💥 القوة العسكرية الكلية", value=f"**{power:,.0f}**", inline=False)
    wizard_txt = f"🧙 {troops.wizard}" if troops.wizard else "لا يوجد"
    beast_txt = f"🐲 {troops.beast}" if troops.beast else "لا يوجد"
    e.add_field(name="🔮 الكيانات السحرية", value=f"{wizard_txt}\n{beast_txt}", inline=False)
    e.set_footer(text=f"🔄 آخر تحديث: الآن  •  تحديث تلقائي تالٍ: {_next_refresh_str()}")
    e.timestamp = datetime.now(timezone.utc)
    return e


def magic_altar_embed(player: Player, buildings: Buildings, troops: Troops) -> discord.Embed:
    e = discord.Embed(title="🔮 المذبح السحري", color=0x8E44AD)
    e.add_field(name="جوهر السحر", value=f"{EMOJI['essence']} **{player.essence:,}**", inline=False)
    e.add_field(name="مستوى المذبح", value=f"**{buildings.altar}** / 5", inline=True)
    can_summon = "✅ نعم" if buildings.altar >= 5 else "❌ يلزم مستوى 5"
    e.add_field(name="استدعاء كامل متاح؟", value=can_summon, inline=True)
    wizard_txt = f"🧙 {troops.wizard}" if troops.wizard else "لا يوجد"
    beast_txt = f"🐲 {troops.beast}" if troops.beast else "لا يوجد"
    e.add_field(name="ساحرك الحالي", value=wizard_txt, inline=False)
    e.add_field(name="مخلوقك الحالي", value=beast_txt, inline=False)
    e.set_footer(text=f"🔄 آخر تحديث: الآن  •  تحديث تلقائي تالٍ: {_next_refresh_str()}")
    e.timestamp = datetime.now(timezone.utc)
    return e


def kingdom_status_embed(player: Player, buildings: Buildings, troops: Troops, power: float) -> discord.Embed:
    """لوحة حالة شاملة موحّدة — تُستخدم في زر 'تحديث حالتي' العام."""
    culture = CULTURES[player.culture]
    shield_txt = "🛡️ نشط" if player.shield_active else "❌ منتهي"
    e = discord.Embed(
        title=f"👑 حالة إمبراطوريتك — {culture.emoji} {culture.name}",
        color=culture.color,
    )
    e.add_field(name="💰 الموارد", value=_resources_line(player.resources), inline=False)
    e.add_field(
        name="🏗️ المباني",
        value=f"🌾{buildings.farm} ⛏️{buildings.mine} 🪓{buildings.lumber} 🏰{buildings.castle} 🔮{buildings.altar}",
        inline=True,
    )
    e.add_field(
        name="🪖 الجيش",
        value=f"⚔️{troops.infantry} 🐎{troops.cavalry} 🏹{troops.archers} 🩹{troops.wounded}",
        inline=True,
    )
    e.add_field(name="💥 القوة", value=f"{power:,.0f}", inline=True)
    e.add_field(name="🛡️ الدرع", value=shield_txt, inline=True)
    e.set_footer(text="تُحدَّث هذه اللوحة تلقائياً كل ساعة، أو اضغط الزر لتحديث فوري")
    e.timestamp = datetime.now(timezone.utc)
    return e


def mail_log_embed(title: str, description: str, color: int = 0x95A5A6) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.timestamp = datetime.now(timezone.utc)
    return e


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(title="❌ خطأ", description=message, color=0xE74C3C)


def maintenance_embed() -> discord.Embed:
    return discord.Embed(
        title="🚧 وضع الصيانة",
        description="البوت متوقف مؤقتاً لإجراء تحديثات. حاول مرة أخرى بعد قليل.",
        color=0x95A5A6,
    )


def success_embed(message: str) -> discord.Embed:
    return discord.Embed(title="✅ تم", description=message, color=0x2ECC71)


# ------------------------------------------------------------------
# لوحة الصدارة (#4)
# ------------------------------------------------------------------
def leaderboard_embed(rows: list[dict]) -> discord.Embed:
    e = discord.Embed(title="🏆 لوحة صدارة الإمبراطوريات", color=0xF1C40F)
    if not rows:
        e.description = "لا يوجد لاعبون مسجّلون بعد."
        return e
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        culture = CULTURES.get(r["culture"])
        name = r.get("empire_name") or (culture.name if culture else r["culture"])
        lines.append(f"{medal} <@{r['user_id']}> — **{name}** — 💥 {r['power']:,.0f}")
    e.description = "\n".join(lines)
    e.timestamp = datetime.now(timezone.utc)
    return e


# ------------------------------------------------------------------
# المهام اليومية (#9)
# ------------------------------------------------------------------
QUEST_LABELS = {
    "train": "🪖 درّب {target} جندي",
    "upgrade": "🏗️ رقِّ {target} مبنى",
    "raid_win": "⚔️ اربح {target} غارة",
}


def daily_quests_embed(quests: list[dict]) -> discord.Embed:
    e = discord.Embed(title="📜 مهامك اليومية", color=0x9B59B6)
    if not quests:
        e.description = "لا توجد مهام اليوم — راجع لاحقاً."
        return e
    for q in quests:
        label = QUEST_LABELS.get(q["quest_type"], q["quest_type"]).format(target=q["target"])
        status = "✅ مكتملة" if q["completed"] else f"{q['progress']}/{q['target']}"
        claimed = " (تم الاستلام)" if q["claimed"] else ""
        e.add_field(name=label, value=f"{status}{claimed} — 🎁 {q['reward_gold']} 🪙", inline=False)
    e.set_footer(text="تُجدَّد المهام يومياً عند منتصف الليل UTC")
    return e


# ------------------------------------------------------------------
# سجل المعارك (#6)
# ------------------------------------------------------------------
def battle_history_embed(user_id: int, rows: list[dict]) -> discord.Embed:
    e = discord.Embed(title="📜 سجل معاركي (آخر 10)", color=0x34495E)
    if not rows:
        e.description = "لا توجد معارك مسجّلة بعد."
        return e
    lines = []
    for r in rows:
        ts = f"<t:{int(r['created_at'].timestamp())}:R>"
        if r["attacker_id"] == user_id:
            role = "⚔️ هاجمت"
            other = r["defender_id"]
        else:
            role = "🛡️ هاجمك"
            other = r["attacker_id"]
        outcome = "🏆 فوز المهاجم" if r["result"] == "attacker_win" else "🛡️ صدّ الدفاع"
        lines.append(f"{role} <@{other}> — {outcome} — {ts}")
    e.description = "\n".join(lines)
    return e


# ------------------------------------------------------------------
# مكافحة التجسس (#10)
# ------------------------------------------------------------------
def scout_defense_embed(rows: list[dict]) -> discord.Embed:
    e = discord.Embed(title="🕵️ من تجسّس عليك مؤخراً؟", color=0x2C3E50)
    if not rows:
        e.description = "لا توجد محاولات تجسس مسجّلة عليك."
        return e
    lines = []
    for r in rows:
        ts = f"<t:{int(r['created_at'].timestamp())}:R>"
        result = "✅ نجح" if r["success"] else "❌ فشل"
        lines.append(f"<@{r['scout_id']}> — {result} — {ts}")
    e.description = "\n".join(lines)
    return e
