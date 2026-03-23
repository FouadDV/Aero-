import discord
from discord import Embed, Color
from datetime import datetime, timedelta


AERO_EMOJI = "🪙"
BOT_COLOR   = 0x5865F2
DIV         = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def aero_embed(title: str, description: str = "", color=BOT_COLOR) -> Embed:
    embed = Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.utcnow()
    embed.set_footer(text="✦ AeroBot  •  عملة Aero الافتراضية ✦")
    return embed


def success_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"✅  {title}", description, color=0x2ECC71)


def error_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"🚫  {title}", description, color=0xE74C3C)


def warning_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"⚠️  {title}", description, color=0xF39C12)


def info_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"💡  {title}", description, color=0x3498DB)


def format_aero(amount: float) -> str:
    if amount == int(amount):
        return f"{int(amount):,} {AERO_EMOJI}"
    return f"{amount:,.4f} {AERO_EMOJI}"


def format_time_remaining(target_time) -> str:
    if target_time is None:
        return "متاح الآن"
    now = datetime.utcnow()
    if now >= target_time:
        return "متاح الآن"
    diff = target_time - now
    hours   = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)
    seconds = int(diff.total_seconds() % 60)
    if hours > 0:
        return f"{hours} س و {minutes} د"
    elif minutes > 0:
        return f"{minutes} د و {seconds} ث"
    else:
        return f"{seconds} ثانية"


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2)


def level_progress_bar(xp: int, level: int, width: int = 18) -> str:
    needed = xp_for_level(level)
    if needed == 0:
        return f"{'█' * width}  100%"
    ratio  = min(xp / needed, 1.0)
    filled = round(ratio * width)
    empty  = width - filled
    pct    = int(ratio * 100)
    return f"{'█' * filled}{'░' * empty}  {pct}%"


def rank_badge(level: int) -> str:
    if level >= 50: return "👑 أسطوري"
    if level >= 30: return "💎 ماسي"
    if level >= 20: return "🏅 ذهبي"
    if level >= 10: return "🥈 فضي"
    if level >= 5:  return "🥉 برونزي"
    return "🌱 مبتدئ"


def wealth_tier(balance: float) -> str:
    if balance >= 1000: return "💎 ثري"
    if balance >= 500:  return "💰 ميسور"
    if balance >= 100:  return "🪙 مدّخر"
    if balance >= 10:   return "📈 ناشئ"
    return "🌱 مبتدئ"


async def send_dm(user: discord.User, embed: Embed):
    try:
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        return False
    except Exception:
        return False


class ConfirmView(discord.ui.View):
    def __init__(self, user_id: int, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.user_id   = user_id
        self.confirmed = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("ليس لك صلاحية", "هذه الرسالة مخصصة لشخص آخر فقط."),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="تأكيد", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="إلغاء", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class PaginationView(discord.ui.View):
    def __init__(self, user_id: int, pages: list, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.pages   = pages
        self.current = 0
        self._update()

    def _update(self):
        self.prev_button.disabled = (self.current == 0)
        self.next_button.disabled = (self.current >= len(self.pages) - 1)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("ليس لك صلاحية", "هذه الرسالة مخصصة لشخص آخر فقط."),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="السابق", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="التالي", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)
