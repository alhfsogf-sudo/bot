"""ui/market_view.py — واجهة السوق الحرة بالكامل بأزرار (بدون أوامر).
تم نقل حالة العروض من الذاكرة إلى قاعدة البيانات (#1) — تبقى العروض سليمة حتى بعد إعادة تشغيل البوت."""
import discord

import database as db
from exceptions import PlayerNotFound, NotEnoughResources
import embeds
from constants import MARKET_PRICE_LIMITS, EMOJI


class ListResourceModal(discord.ui.Modal, title="📦 عرض مورد للبيع"):
    resource = discord.ui.TextInput(label="المورد (wood/iron/food/essence)", placeholder="wood")
    amount = discord.ui.TextInput(label="الكمية", placeholder="100")
    price = discord.ui.TextInput(label="السعر لكل وحدة (ذهب)", placeholder="5")

    async def on_submit(self, interaction: discord.Interaction):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return

        res = self.resource.value.strip().lower()
        if res not in MARKET_PRICE_LIMITS:
            await interaction.response.send_message(
                embed=embeds.error_embed("مورد غير مدعوم. استخدم: wood / iron / food / essence"), ephemeral=True)
            return
        try:
            amt = int(self.amount.value)
            price = int(self.price.value)
            if amt <= 0 or price <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=embeds.error_embed("قيم غير صحيحة."), ephemeral=True)
            return

        lo, hi = MARKET_PRICE_LIMITS[res]
        if not (lo <= price <= hi):
            await interaction.response.send_message(
                embed=embeds.error_embed(f"السعر يجب أن يكون بين {lo} و {hi} ذهب."), ephemeral=True)
            return

        user_id = interaction.user.id
        try:
            player = await db.get_player(user_id)
            if getattr(player, res) < amt:
                raise NotEnoughResources({res: amt - getattr(player, res)})

            await db.update_player_resources(user_id, **{res: -amt})
            listing_id = await db.create_market_listing(user_id, res, amt, price)

            e = discord.Embed(
                title="🤝 عرض جديد في السوق",
                description=(
                    f"البائع: {interaction.user.mention}\n"
                    f"المورد: {EMOJI[res]} **{amt:,}**\n"
                    f"السعر: **{price}** 🪙 / وحدة\n"
                    f"الإجمالي: **{amt * price:,}** 🪙"
                ),
                color=0xF1C40F,
            )
            view = BuyListingView(listing_id)
            msg = await interaction.channel.send(embed=e, view=view)
            await db.set_market_listing_message(listing_id, interaction.channel.id, msg.id)
            interaction.client.add_view(view, message_id=msg.id)  # يبقى فعّالاً بعد إعادة تشغيل البوت
            await interaction.response.send_message(embed=embeds.success_embed("تم نشر عرضك في السوق."),
                                                      ephemeral=True)
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)


class BuyListingView(discord.ui.View):
    def __init__(self, listing_id: int):
        super().__init__(timeout=None)  # دائم — العرض يبقى حتى يُشترى أو يُلغى، مثبّت عبر message_id
        self.listing_id = listing_id

    @discord.ui.button(label="💰 شراء الآن", style=discord.ButtonStyle.success, custom_id="siyada:market_buy")
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        listing = await db.get_market_listing(self.listing_id)
        if not listing:
            await interaction.response.send_message(embed=embeds.error_embed("هذا العرض لم يعد متاحاً."),
                                                      ephemeral=True)
            return
        buyer_id = interaction.user.id
        if buyer_id == listing["seller_id"]:
            await interaction.response.send_message(embed=embeds.error_embed("لا يمكنك شراء عرضك الخاص."),
                                                      ephemeral=True)
            return
        total_cost = listing["amount"] * listing["price"]
        try:
            buyer = await db.get_player(buyer_id)
            if buyer.gold < total_cost:
                raise NotEnoughResources({"gold": total_cost - buyer.gold})

            await db.update_player_resources(buyer_id, gold=-total_cost, **{listing["resource"]: listing["amount"]})
            await db.update_player_resources(listing["seller_id"], gold=total_cost)
            await db.close_market_listing(self.listing_id)

            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                embed=embeds.success_embed(f"تم البيع لـ {interaction.user.mention}"), view=self)
        except (PlayerNotFound, NotEnoughResources) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @discord.ui.button(label="🚫 إلغاء", style=discord.ButtonStyle.danger, custom_id="siyada:market_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        listing = await db.get_market_listing(self.listing_id)
        if not listing:
            await interaction.response.send_message(embed=embeds.error_embed("هذا العرض لم يعد متاحاً."),
                                                      ephemeral=True)
            return
        if interaction.user.id != listing["seller_id"]:
            await interaction.response.send_message(embed=embeds.error_embed("هذا العرض ليس لك."), ephemeral=True)
            return

        await db.update_player_resources(listing["seller_id"], **{listing["resource"]: listing["amount"]})
        await db.close_market_listing(self.listing_id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embeds.mail_log_embed("🚫 أُلغي العرض", "", 0x95A5A6), view=self)


class MarketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 عرض مورد للبيع", style=discord.ButtonStyle.primary,
                        custom_id="siyada:list_resource")
    async def list_resource(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await db.is_maintenance_mode():
            await interaction.response.send_message(embed=embeds.maintenance_embed(), ephemeral=True)
            return
        await interaction.response.send_modal(ListResourceModal())
