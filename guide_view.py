"""ui/guide_view.py — شرح اللعبة الكامل عبر صفحات تفاعلية (بدل قراءة ملف الدليل يدوياً)."""
import discord


def build_guide_pages() -> list[discord.Embed]:
    pages = []

    pages.append(discord.Embed(
        title="⚔️ سيادة الأمم — دليل اللاعب (1/6) — البداية",
        description=(
            "**كيف تبدأ؟**\n"
            "اذهب لقناة الدليل واضغط 🚀 **ابدأ إمبراطوريتك**.\n\n"
            "ستختار ثقافة **نهائية**:\n"
            "⚔️ قائد عسكري: +15% قوة قتالية، -10% تكلفة تدريب\n"
            "💰 بارون التجارة: +20% إنتاج ذهب، -10% رسوم سوق\n"
            "🔨 كبير البنّائين: -15% تكلفة بناء، +20% سرعة تطوير\n\n"
            "بعد الاختيار تحصل على 4 قنوات خاصة ودرع حماية **48 ساعة**."
        ), color=0x2C3E50))

    pages.append(discord.Embed(
        title="🏰 دليل اللاعب (2/6) — قنواتك ومواردك",
        description=(
            "**قنواتك الأربع:**\n"
            "🏰 قاعة العرش — التحكم بمبانيك، تتحدث تلقائياً كل ساعة\n"
            "⚔️ ديوان الحرب — تدريب، غارات، تجسس، علاج\n"
            "🔮 المذبح السحري — استدعاء السحرة والمخلوقات\n"
            "📜 صندوق البريد — سجل كل ما يحدث لك\n\n"
            "**الموارد الخمسة:** 🪙 ذهب، 🪵 خشب، ⛓️ حديد، 🌾 طعام، 🔮 سحر\n"
            "⚠️ نفاد الطعام = موت الجنود تدريجياً | نفاد الذهب = إنتاج أقل | نفاد السحر = مغادرة الكيانات"
        ), color=0x27AE60))

    pages.append(discord.Embed(
        title="🏗️ دليل اللاعب (3/6) — المباني",
        description=(
            "رقّي مبانيك بأزرار قاعة العرش مباشرة (بدون أوامر):\n\n"
            "🌾 المزرعة: +50 طعام/مستوى (حتى مستوى 5)\n"
            "⛏️ المنجم: +40 حديد +20 ذهب/مستوى\n"
            "🪓 المنشرة: +50 خشب/مستوى\n"
            "🏰 القلعة: +500 دفاع للحصن/مستوى\n"
            "🔮 المذبح: +10 جوهر سحر/مستوى\n\n"
            "💡 تكلفة كل ترقية = تكلفة المستوى السابق × 1.6"
        ), color=0x8E44AD))

    pages.append(discord.Embed(
        title="⚔️ دليل اللاعب (4/6) — الجيش والقتال",
        description=(
            "**مثلث القوة:** مشاة يتفوق على رماة ← فرسان يتفوق على مشاة ← رماة يتفوق على فرسان (+25% قوة)\n\n"
            "درّب جنودك بزر 🪖 في ديوان الحرب.\n"
            "قبل الهجوم، استخدم 🔎 **تجسس** (200 ذهب، نجاح 70%).\n"
            "اضغط 🗺️ **شنّ غارة** وأدخل آيدي الهدف وعدد كل نوع جندي.\n\n"
            "**شروط الغارة:** الهدف بلا درع، قوتكما متقاربة (80%-120%)، لم تهاجمه أكثر من 3 مرات خلال 24 ساعة.\n"
            "بعد الخسائر يمكنك علاج جرحاك بزر 🏥 (30 ذهب + 15 طعام لكل جريح)."
        ), color=0xC0392B))

    pages.append(discord.Embed(
        title="🔮 دليل اللاعب (5/6) — السحر والتحالفات والسوق",
        description=(
            "**السحر:** في المذبح السحري اختر ساحراً أو مخلوقاً من القوائم المنسدلة لاستدعائه (7 أيام)، "
            "أو جرّب بعثة محفوفة بالمخاطر بنصف التكلفة ونسبة نجاح منخفضة.\n\n"
            "**التحالفات:** أسّس تحالفاً (50,000 ذهب) أو انضم لواحد من القناة المركزية. "
            "في مقر التحالف تقدر تودع موارد أو تطلب دعماً طارئاً.\n\n"
            "**السوق الحرة:** اعرض مواردك للبيع أو اشترِ من عروض الآخرين — كلها بأزرار."
        ), color=0xF1C40F))

    pages.append(discord.Embed(
        title="🏆 دليل اللاعب (6/6) — الفوز ونصائح",
        description=(
            "الموسم يستمر **شهرين**. الفائز من يستولي على عاصمة الخادم!\n\n"
            "**نصائح سريعة:**\n"
            "1. رقّ المزرعة أولاً\n"
            "2. لا تبني جيشاً قبل تأمين الطعام\n"
            "3. استغل درعك الأول لتطوير اقتصادك\n"
            "4. تجسس قبل أي هجوم\n"
            "5. انضم لتحالف مبكراً\n"
            "6. راقب صندوق البريد دائماً\n\n"
            "بالتوفيق في بناء إمبراطوريتك! 👑"
        ), color=0x2980B9))

    return pages


class GuidePaginatorView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0

    def _sync_buttons(self):
        self.prev_btn.disabled = self.index == 0
        self.next_btn.disabled = self.index == len(self.pages) - 1

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)
