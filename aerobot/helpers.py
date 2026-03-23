import discord
from discord import Embed, Color
from datetime import datetime, timedelta
import re


AERO_EMOJI = "🪙"
BOT_COLOR = 0x5865F2


def aero_embed(title: str, description: str = "", color=BOT_COLOR) -> Embed:
    embed = Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.utcnow()
    embed.set_footer(text="AeroBot • عملة Aero الافتراضية")
    return embed


def success_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"✅ {title}", description, color=0x57F287)


def error_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"❌ {title}", description, color=0xED4245)


def warning_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"⚠️ {title}", description, color=0xFEE75C)


def info_embed(title: str, description: str = "") -> Embed:
    return aero_embed(f"ℹ️ {title}", description, color=0x5865F2)


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
    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)
    seconds = int(diff.total_seconds() % 60)
    if hours > 0:
        return f"{hours} ساعة و {minutes} دقيقة"
    elif minutes > 0:
        return f"{minutes} دقيقة و {seconds} ثانية"
    else:
        return f"{seconds} ثانية"


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2)


def level_progress_bar(xp: int, level: int) -> str:
    needed = xp_for_level(level)
    if needed == 0:
        return "████████████████████ 100%"
    filled = int((xp / needed) * 20)
    filled = min(filled, 20)
    empty = 20 - filled
    pct = min(int((xp / needed) * 100), 100)
    return f"{'█' * filled}{'░' * empty} {pct}%"


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
        self.user_id = user_id
        self.confirmed = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("ليس لك صلاحية", "هذه الرسالة مخصصة لشخص آخر."),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ موافق", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="❌ إلغاء", style=discord.ButtonStyle.danger)
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
        self.pages = pages
        self.current = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current == 0
        self.next_button.disabled = self.current >= len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("ليس لك صلاحية", "هذه الرسالة مخصصة لشخص آخر."),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="▶️ التالي", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)
