"""core/exceptions.py — أخطاء مخصصة لأحداث اللعبة."""


class GameError(Exception):
    def __init__(self, message: str = "حدث خطأ غير متوقع في اللعبة"):
        self.message = message
        super().__init__(message)


class PlayerNotFound(GameError):
    def __init__(self):
        super().__init__("❌ لست مسجّلاً بعد. اذهب إلى قناة الدليل واضغط «ابدأ إمبراطوريتك».")


class PlayerAlreadyExists(GameError):
    def __init__(self):
        super().__init__("❌ لديك إمبراطورية مسجّلة بالفعل.")


class AccountTooNew(GameError):
    def __init__(self, days_left: int):
        super().__init__(f"❌ حسابك حديث جداً. يجب الانتظار {days_left} يوم إضافي قبل التسجيل.")


class NotEnoughResources(GameError):
    def __init__(self, missing: dict):
        details = ", ".join(f"{v} {k}" for k, v in missing.items())
        super().__init__(f"❌ مواردك غير كافية. تحتاج إضافياً: {details}")


class ShieldActive(GameError):
    def __init__(self):
        super().__init__("🛡️ هذا اللاعب محمي بدرع المبتدئين ولا يمكن مهاجمته حالياً.")


class OutOfPowerRange(GameError):
    def __init__(self):
        super().__init__("⚖️ فرق القوة كبير جداً. يمكنك فقط مهاجمة من قوته بين 80% و 120% من قوتك.")


class RaidLimitReached(GameError):
    def __init__(self):
        super().__init__("🚫 وصلت للحد الأقصى (3 غارات) على هذا الهدف خلال 24 ساعة.")


class BuildingMaxLevel(GameError):
    def __init__(self):
        super().__init__("🏆 هذا المبنى وصل للمستوى الأقصى (5).")


class MagicEssenceDepleted(GameError):
    def __init__(self):
        super().__init__("🔮 جوهر السحر نفد — غادرك ساحرك/مخلوقك.")


class OnCooldown(GameError):
    def __init__(self, seconds_left: int):
        super().__init__(f"⏳ الرجاء الانتظار {seconds_left} ثانية قبل التحديث مرة أخرى.")
