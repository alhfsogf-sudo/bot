"""utils/nickname.py — إضافة/إزالة رمز التحالف [TAG] من اسم اللاعب الظاهر تلقائياً (#17)."""
import re
import discord

_TAG_PATTERN = re.compile(r"^\[[^\]]{1,6}\]\s*")


async def apply_alliance_tag(member: discord.Member, tag: str):
    try:
        base_name = _TAG_PATTERN.sub("", member.display_name)
        new_nick = f"[{tag}] {base_name}"[:32]
        await member.edit(nick=new_nick, reason="انضمام لتحالف")
    except discord.Forbidden:
        pass  # صلاحيات غير كافية (مثلاً اللاعب أعلى رتبة من البوت) — يُتجاهل بأمان
    except discord.HTTPException:
        pass


async def strip_alliance_tag(member: discord.Member):
    try:
        base_name = _TAG_PATTERN.sub("", member.display_name)
        await member.edit(nick=base_name, reason="مغادرة تحالف")
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass
