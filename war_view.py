"""ui/war_view.py — أزرار ديوان الحرب (تدريب / غارة / تجسس / علاج / تحديث)."""
import discord
import time
from datetime import datetime, timedelta, timezone

import database as db
from exceptions import PlayerNotFound, NotEnoughResources, OnCooldown
import embeds
from constants import TROOP_TYPES, HEAL_COST_GOLD_PER_UNIT, HEAL_COST_FOOD_PER_UNIT
from game_math import training_cost, military_power
from config import MANUAL_REFRESH_COOLDOWN_SECONDS

_last_refresh: dict[int, float] = {}


def _check_cooldown(user_id: int):
    now = time.time()
    last = _last_refresh.get(user_id, 0)
    if now - last < MANUAL_REFRESH_COOLDOWN_SECONDS:
        raise OnCooldown(int(MANUAL_REFRESH_COOLDOWN_SECONDS - (now - last)))
    _last_refresh[user_id] = now


class TrainTroopsModal(discord.ui.Modal, title="🪖 تدريب جنود"):
    troop_type = discord.ui.TextInput(
        label="النوع (infantry / archers / cavalry)", placeholder="infantry", max_length=20
    )
    amount = discord.ui.TextInput(label="العدد", placeholder="100", max_length=10)

    async def on_submit(self, interaction: discord.Interaction):
        ttype = self.troop_type.value.strip().lower()
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        if ttype not in TROOP_TYPES:
            await interaction.response.send_message(
                embed=embeds.error_embed("نوع غير معروف. استخدم: infantry / archers / cavalry"),
                ephemeral=True)
            return
        try:
            amt = int(self.amount.value.strip())
            if amt <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("العدد يجب أن يكون رقماً موجباً."),
                                                      ephemeral=True)
            return

        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            cost = training_cost(ttype, amt, player.culture)
            missing = {res: c - getattr(player, res) for res, c in cost.items() if getattr(player, res) < c}
            if missing:
                raise NotEnoughResources(missing)

            deltas = {res: -c for res, c in cost.items()}
            await db.update_player_resources(user_id, **deltas)
            await db.update_troops(user_id, **{ttype: amt})
            await db.increment_quest_progress(user_id, "train", amt)

            player = await db.get_player(user_id)
            troops = await db.get_troops(user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture, troops.mercenary_power)

            await interaction.response.send_message(
                embed=embeds.success_embed(f"تم تدريب {amt} {TROOP_TYPES[ttype]['name']} {TROOP_TYPES[ttype]['emoji']}"),
                ephemeral=True)

            war_ch = interaction.guild.get_channel(player.war_channel_id)
            if war_ch:
                async for msg in war_ch.history(limit=20):
                    if msg.author == interaction.client.user and msg.embeds:
                        await msg.edit(embed=embeds.war_divan_embed(player, troops, power), view=WarView())
                        break
            mail_ch = interaction.guild.get_channel(player.king_channel_id)
            if mail_ch:
                await mail_ch.send(embed=embeds.mail_log_embed(
                    "🪖 تدريب جنود", f"تم تدريب {amt} {TROOP_TYPES[ttype]['name']}", 0x2ECC71))
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class RaidTargetModal(discord.ui.Modal, title="🗺️ شنّ غارة"):
    target_id = discord.ui.TextInput(label="آيدي اللاعب الهدف", placeholder="123456789012345678")
    infantry = discord.ui.TextInput(label="عدد المشاة", default="0", required=False)
    cavalry = discord.ui.TextInput(label="عدد الفرسان", default="0", required=False)
    archers = discord.ui.TextInput(label="عدد الرماة", default="0", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        try:
            target_id = int(self.target_id.value.strip())
            inf = int(self.infantry.value or 0)
            cav = int(self.cavalry.value or 0)
            arc = int(self.archers.value or 0)
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("أرقام غير صحيحة."), ephemeral=True)
            return

        if inf + cav + arc <= 0:
            await interaction.response.send_message(embed=embeds.error_embed("يجب إرسال جندي واحد على الأقل."),
                                                      ephemeral=True)
            return

        interaction.client.dispatch(
            "raid_initiated", interaction, target_id, {"infantry": inf, "cavalry": cav, "archers": arc}
        )
        await interaction.response.send_message(embed=embeds.mail_log_embed(
            "🗺️ الغارة قيد التنفيذ", "جارٍ حساب نتيجة المعركة...", 0xF39C12), ephemeral=True)


class ScoutModal(discord.ui.Modal, title="🔎 تجسس على هدف"):
    target_id = discord.ui.TextInput(label="آيدي اللاعب الهدف", placeholder="123456789012345678")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_id = int(self.target_id.value.strip())
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("آيدي غير صحيح."), ephemeral=True)
            return
        interaction.client.dispatch("scout_initiated", interaction, target_id)


class HireMercenariesModal(discord.ui.Modal, title="💰 استئجار مرتزقة (#19)"):
    """مرتزقة: قوة قتالية فورية مؤقتة بدون تدريب — تنتهي صلاحيتها تلقائياً بعد المدة المحددة."""
    gold_amount = discord.ui.TextInput(label="كمية الذهب للإنفاق", placeholder="2000")
    hours = discord.ui.TextInput(label="مدة الاستئجار بالساعات (حد أقصى 48)", placeholder="24")

    MERCENARY_POWER_PER_GOLD = 0.5  # كل 1 ذهب = 0.5 قوة قتالية مؤقتة

    async def on_submit(self, interaction: discord.Interaction):
        try:
            gold = int(self.gold_amount.value)
            hrs = int(self.hours.value)
            if gold <= 0 or hrs <= 0:
                raise ValueError
            hrs = min(hrs, 48)
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("قيم غير صحيحة."), ephemeral=True)
            return

        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            if player.gold < gold:
                raise NotEnoughResources({"gold": gold - player.gold})

            await db.update_player_resources(user_id, gold=-gold)
            power_gained = round(gold * self.MERCENARY_POWER_PER_GOLD)
            expires = datetime.now(timezone.utc) + timedelta(hours=hrs)
            await db.set_mercenaries(user_id, power_gained, expires)

            player = await db.get_player(user_id)
            troops = await db.get_troops(user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture,
                                    troops.mercenary_power)
            await interaction.response.send_message(
                embed=embeds.success_embed(
                    f"استأجرت مرتزقة بقوة **{power_gained:,}** لمدة **{hrs}** ساعة."), ephemeral=True)

            from economy import _find_and_update_panel
            war_ch = interaction.guild.get_channel(player.war_channel_id)
            await _find_and_update_panel(war_ch, embeds.war_divan_embed(player, troops, power), WarView(),
                                          title_prefix="⚔️")
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class WarView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🪖 تدريب جنود", style=discord.ButtonStyle.success,
                        custom_id="siyada:train_troops", row=0)
    async def train(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TrainTroopsModal())

    @discord.ui.button(label="🗺️ شنّ غارة", style=discord.ButtonStyle.danger,
                        custom_id="siyada:raid_target", row=0)
    async def raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RaidTargetModal())

    @discord.ui.button(label="🔎 تجسس", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:scout_target", row=0)
    async def scout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScoutModal())

    @discord.ui.button(label="🏥 علاج الجرحى", style=discord.ButtonStyle.primary,
                        custom_id="siyada:heal_wounded", row=1)
    async def heal(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            troops = await db.get_troops(user_id)
            if troops.wounded <= 0:
                await interaction.response.send_message(embed=embeds.error_embed("لا يوجد جرحى لعلاجهم."),
                                                          ephemeral=True)
                return
            gold_needed = troops.wounded * HEAL_COST_GOLD_PER_UNIT
            food_needed = troops.wounded * HEAL_COST_FOOD_PER_UNIT
            missing = {}
            if player.gold < gold_needed:
                missing["gold"] = gold_needed - player.gold
            if player.food < food_needed:
                missing["food"] = food_needed - player.food
            if missing:
                raise NotEnoughResources(missing)

            healed = troops.wounded
            await db.update_player_resources(user_id, gold=-gold_needed, food=-food_needed)
            await db.update_troops(user_id, wounded=-healed)
            # (#3) إعادتهم بنفس نسب توزيع جيشه الحي الحالي بدل تحويلهم جميعاً مشاة
            alive_total = troops.infantry + troops.cavalry + troops.archers
            if alive_total > 0:
                inf_back = round(healed * (troops.infantry / alive_total))
                cav_back = round(healed * (troops.cavalry / alive_total))
                arc_back = max(0, healed - inf_back - cav_back)
            else:
                inf_back, cav_back, arc_back = healed, 0, 0
            await db.update_troops(user_id, infantry=inf_back, cavalry=cav_back, archers=arc_back)

            player = await db.get_player(user_id)
            troops = await db.get_troops(user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture, troops.mercenary_power)
            await interaction.response.edit_message(embed=embeds.war_divan_embed(player, troops, power), view=self)

            mail_ch = interaction.guild.get_channel(player.king_channel_id)
            if mail_ch:
                await mail_ch.send(embed=embeds.mail_log_embed("🏥 علاج", f"تم علاج {healed} جندي جريح", 0x2ECC71))
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @discord.ui.button(label="🔄 تحديث الآن", style=discord.ButtonStyle.gray,
                        custom_id="siyada:refresh_war", row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            _check_cooldown(user_id)
            player = await db.get_player(user_id)
            troops = await db.get_troops(user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture, troops.mercenary_power)
            await db.touch_status_update(user_id)
            await interaction.response.edit_message(embed=embeds.war_divan_embed(player, troops, power), view=self)
        except (PlayerNotFound, OnCooldown) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @discord.ui.button(label="📜 سجل معاركي", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:battle_history", row=2)
    async def battle_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await db.get_player(interaction.user.id)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
            return
        rows = await db.get_battle_history(interaction.user.id, limit=10)
        await interaction.response.send_message(embed=embeds.battle_history_embed(interaction.user.id, rows),
                                                  ephemeral=True)

    @discord.ui.button(label="🕵️ من تجسّس عليّ؟", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:counter_espionage", row=2)
    async def counter_espionage(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await db.get_player(interaction.user.id)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
            return
        rows = await db.get_recent_scouts_on(interaction.user.id, limit=5)
        await interaction.response.send_message(embed=embeds.scout_defense_embed(rows), ephemeral=True)

    @discord.ui.button(label="💰 استئجار مرتزقة", style=discord.ButtonStyle.success,
                        custom_id="siyada:hire_mercenaries", row=2)
    async def hire_mercenaries(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HireMercenariesModal())
