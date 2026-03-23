import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from helpers import (
    aero_embed, success_embed, error_embed, warning_embed, info_embed,
    format_aero, ConfirmView, send_dm, AERO_EMOJI, BOT_COLOR
)
import database as db
import os


def build_stats_pages(s, aero_value: float) -> list:
    now_ts = int(datetime.utcnow().timestamp())
    total_val = s["total_aero"] * aero_value
    activity_rate = (s["active_users"] / max(s["user_count"], 1)) * 100
    tx_per_user = s["tx_count"] / max(s["user_count"], 1)
    dist_total = max(s["dist_0_10"] + s["dist_10_50"] + s["dist_50_100"] + s["dist_100_plus"], 1)

    def bar(count, total, width=10):
        filled = round((count / total) * width)
        return "█" * filled + "░" * (width - filled)

    type_labels = {
        "daily": "يومي", "weekly": "أسبوعي", "referral": "إحالة",
        "pay": "تحويل", "gift": "هدية", "trade_out": "مقايضة (خروج)",
        "trade_in": "مقايضة (دخول)", "admin_add": "إضافة إدارية",
        "admin_remove": "خصم إداري", "admin_reset": "إعادة تعيين",
    }

    p1 = aero_embed("📊 الإحصائيات العامة — الصفحة 1/3")
    p1.add_field(name="👥 المستخدمون", value=(
        f"الكل: **{s['user_count']}** | نشطون (7 أيام): **{s['active_users']}**\n"
        f"جدد اليوم: **{s['new_today']}** | جدد الأسبوع: **{s['new_week']}**\n"
        f"رصيد صفر: **{s['zero_balance']}** | محظورون: **{s['blacklist_count']}**\n"
        f"لديهم إحالات: **{s['referred_count']}**"
    ), inline=False)
    p1.add_field(name="💰 الأرصدة", value=(
        f"إجمالي Aero: **{format_aero(s['total_aero'])}**\n"
        f"القيمة الكلية: **{total_val:.4f}** (× {aero_value})\n"
        f"أعلى رصيد: **{format_aero(s['max_balance'])}**\n"
        f"أدنى رصيد: **{format_aero(s['min_balance'])}**\n"
        f"متوسط: **{format_aero(s['avg_balance'])}** | وسيط: **{format_aero(s['median_balance'])}**"
    ), inline=False)
    p1.add_field(name="⭐ المستويات", value=(
        f"متوسط المستوى: **{s['avg_level']:.1f}** | أعلى مستوى: **{s['max_level']}**\n"
        f"متوسط XP: **{s['avg_xp']:.0f}**"
    ), inline=False)
    p1.set_footer(text=f"آخر تحديث: <t:{now_ts}:R> • AeroBot")

    p2 = aero_embed("📊 تحليل المعاملات — الصفحة 2/3")
    p2.add_field(name="🔄 المعاملات", value=(
        f"الإجمالي: **{s['tx_count']}** | اليوم: **{s['tx_today']}** | الأسبوع: **{s['tx_week']}**\n"
        f"معدل/مستخدم: **{tx_per_user:.1f}**"
    ), inline=False)

    tx_lines = []
    for t in s["tx_by_type"][:8]:
        label = type_labels.get(t["type"], t["type"])
        tx_lines.append(f"• {label}: **{t['count']}** معاملة | **{format_aero(float(t['total']))}**")
    if tx_lines:
        p2.add_field(name="📋 تفصيل حسب النوع", value="\n".join(tx_lines), inline=False)

    p2.add_field(name="💸 مصادر Aero", value=(
        f"مكافآت (يومي/أسبوعي/إحالة): **{format_aero(s['aero_rewards'])}**\n"
        f"تحويلات بين الأعضاء: **{format_aero(s['aero_transferred'])}**\n"
        f"إضافات إدارية: **{format_aero(s['aero_admin'])}**"
    ), inline=False)
    p2.set_footer(text=f"آخر تحديث: <t:{now_ts}:R> • AeroBot")

    p3 = aero_embed("📊 التحليلات المتقدمة — الصفحة 3/3")
    p3.add_field(name="📈 توزيع الثروة", value=(
        f"0–10 Aero:   `{bar(s['dist_0_10'], dist_total)}` {s['dist_0_10']} مستخدم\n"
        f"10–50 Aero:  `{bar(s['dist_10_50'], dist_total)}` {s['dist_10_50']} مستخدم\n"
        f"50–100 Aero: `{bar(s['dist_50_100'], dist_total)}` {s['dist_50_100']} مستخدم\n"
        f"100+ Aero:   `{bar(s['dist_100_plus'], dist_total)}` {s['dist_100_plus']} مستخدم"
    ), inline=False)

    if s["top3"]:
        medals = ["🥇", "🥈", "🥉"]
        top_lines = [f"{medals[i]} <@{u['id']}> — {format_aero(float(u['balance']))} | مستوى {u['level']}" for i, u in enumerate(s["top3"])]
        p3.add_field(name="🏆 أثرى 3 أعضاء", value="\n".join(top_lines), inline=False)

    if s["most_active"]:
        active_lines = [f"**#{i+1}** <@{u['uid']}> — {u['cnt']} معاملة" for i, u in enumerate(s["most_active"])]
        p3.add_field(name="⚡ أكثر 3 أعضاء نشاطاً", value="\n".join(active_lines), inline=False)

    p3.add_field(name="🔍 مؤشرات صحة الاقتصاد", value=(
        f"معدل النشاط: **{activity_rate:.1f}%** من المستخدمين\n"
        f"نسبة الأثرياء (100+): **{(s['rich_users'] / max(s['user_count'], 1) * 100):.1f}%**\n"
        f"نسبة الأرصدة الصفرية: **{(s['zero_balance'] / max(s['user_count'], 1) * 100):.1f}%**\n"
        f"نسبة مشاركة الإحالات: **{(s['referred_count'] / max(s['user_count'], 1) * 100):.1f}%**"
    ), inline=False)
    p3.set_footer(text=f"آخر تحديث: <t:{now_ts}:R> • AeroBot")

    return [p1, p2, p3]


class StatsView(discord.ui.View):
    def __init__(self, admin_user_id: int, aero_value: float):
        super().__init__(timeout=300)
        self.admin_user_id = admin_user_id
        self.aero_value = aero_value
        self.current_page = 0
        self.pages = []
        self.update_nav_buttons()

    def update_nav_buttons(self):
        total = len(self.pages) if self.pages else 3
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page >= total - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.admin_user_id:
            await interaction.response.send_message(
                embed=error_embed("ليس لك صلاحية", "هذه اللوحة مخصصة للمسؤول فقط."),
                ephemeral=True
            )
            return False
        return True

    async def refresh_pages(self):
        s = await db.get_advanced_stats()
        self.aero_value = float(await db.get_setting("aero_value") or "0.018")
        self.pages = build_stats_pages(s, self.aero_value)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_nav_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_nav_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="🔄 تحديث", style=discord.ButtonStyle.primary, row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.refresh_pages()
        self.update_nav_buttons()
        await interaction.edit_original_response(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="♻️ إعادة تعيين الكل", style=discord.ButtonStyle.danger, row=1)
    async def reset_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_embed = warning_embed(
            "⚠️ تحذير — إعادة تعيين شاملة",
            "**هذا الإجراء سيقوم بـ:**\n"
            "• حذف جميع المعاملات\n"
            "• إعادة جميع أرصدة الأعضاء إلى صفر\n"
            "• إعادة جميع مستويات XP والمستويات إلى الأول\n\n"
            "**لا يمكن التراجع عن هذا الإجراء.**\n"
            "اضغط موافق للاستمرار."
        )
        confirm_view = ConfirmView(self.admin_user_id, timeout=30)
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        if not confirm_view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء إعادة التعيين."), view=confirm_view)
            return

        await db.reset_all_stats()
        await interaction.edit_original_response(
            embed=success_embed("تمت إعادة التعيين!", "تم إعادة تعيين جميع الإحصائيات والأرصدة والمعاملات من الصفر."),
            view=confirm_view
        )
        await send_dm(interaction.user, warning_embed(
            "إعادة تعيين شاملة",
            "قمت بإعادة تعيين جميع بيانات AeroBot من الصفر."
        ))
        await self.refresh_pages()
        self.current_page = 0
        self.update_nav_buttons()
        await interaction.followup.send(embed=self.pages[0], view=self, ephemeral=True)


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        owner_id = int(os.getenv("OWNER_ID", "0"))
        if interaction.user.id == owner_id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message(
            embed=error_embed("صلاحية مرفوضة", "هذا الأمر مخصص للمسؤولين فقط."),
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="لوحة الإدارة")

    @admin_group.command(name="panel", description="عرض لوحة الإدارة الكاملة")
    @is_admin()
    async def panel(self, interaction: discord.Interaction):
        settings = {}
        for key in ["daily_reward", "weekly_reward", "referral_reward", "tax_rate", "aero_value"]:
            settings[key] = await db.get_setting(key) or "—"

        embed = aero_embed("⚙️ لوحة إدارة AeroBot")
        embed.add_field(name="💰 الإعدادات الحالية", value=(
            f"• المكافأة اليومية: **{settings['daily_reward']} Aero**\n"
            f"• المكافأة الأسبوعية: **{settings['weekly_reward']} Aero**\n"
            f"• مكافأة الإحالة: **{settings['referral_reward']} Aero**\n"
            f"• نسبة الضريبة: **{settings['tax_rate']}%**\n"
            f"• قيمة Aero: **{settings['aero_value']}**"
        ), inline=False)
        embed.add_field(name="📋 الأوامر المتاحة", value=(
            "`/admin add` — إضافة رصيد\n"
            "`/admin remove` — خصم رصيد\n"
            "`/admin set` — تعديل الإعدادات\n"
            "`/admin stats` — إحصائيات عامة\n"
            "`/admin blacklist` — إدارة اللائحة السوداء\n"
            "`/admin reset` — إعادة تعيين رصيد عضو"
        ), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="add", description="إضافة رصيد Aero لعضو")
    @app_commands.describe(user="العضو", amount="الكمية المراد إضافتها")
    @is_admin()
    async def add_balance(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        if amount <= 0:
            await interaction.response.send_message(embed=error_embed("خطأ", "الكمية يجب أن تكون أكبر من صفر."), ephemeral=True)
            return

        await db.ensure_user(user.id)

        embed = aero_embed("➕ تأكيد إضافة رصيد",
            f"حسابك يستخدم Aero داخل البوت فقط.\n\n"
            f"العضو: {user.mention}\n"
            f"الإضافة: **{format_aero(amount)}**\n\n"
            f"اضغط موافق للاستمرار.")
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء العملية."), view=view)
            return

        await db.update_balance(user.id, amount)
        await db.add_transaction(interaction.user.id, user.id, amount, "admin_add", f"إضافة إدارية من {interaction.user.name}")

        await interaction.edit_original_response(
            embed=success_embed("تمت الإضافة!", f"تم إضافة **{format_aero(amount)}** إلى {user.mention}"),
            view=view
        )
        owner_dm = info_embed("إضافة رصيد", f"أضافت **{interaction.user.display_name}** **{format_aero(amount)}** إلى رصيد **{user.display_name}**")
        await send_dm(interaction.user, owner_dm)
        await send_dm(user, info_embed("تم إضافة رصيد!", f"تم إضافة **{format_aero(amount)}** إلى رصيدك من قِبل الإدارة."))

    @admin_group.command(name="remove", description="خصم رصيد Aero من عضو")
    @app_commands.describe(user="العضو", amount="الكمية المراد خصمها")
    @is_admin()
    async def remove_balance(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        if amount <= 0:
            await interaction.response.send_message(embed=error_embed("خطأ", "الكمية يجب أن تكون أكبر من صفر."), ephemeral=True)
            return

        u = await db.ensure_user(user.id)
        current = float(u["balance"])
        if current < amount:
            await interaction.response.send_message(
                embed=warning_embed("تحذير", f"رصيد {user.display_name} هو **{format_aero(current)}** فقط. سيصبح صفراً."),
                ephemeral=True
            )

        embed = aero_embed("➖ تأكيد خصم الرصيد",
            f"حسابك يستخدم Aero داخل البوت فقط.\n\n"
            f"العضو: {user.mention}\n"
            f"الخصم: **{format_aero(amount)}**\n\n"
            f"اضغط موافق للاستمرار.")
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء العملية."), view=view)
            return

        deduct = min(amount, current)
        await db.update_balance(user.id, -deduct)
        await db.add_transaction(interaction.user.id, user.id, deduct, "admin_remove", f"خصم إداري من {interaction.user.name}")

        await interaction.edit_original_response(
            embed=success_embed("تم الخصم!", f"تم خصم **{format_aero(deduct)}** من {user.mention}"),
            view=view
        )
        await send_dm(interaction.user, info_embed("خصم رصيد", f"تم خصم **{format_aero(deduct)}** من رصيد **{user.display_name}**"))
        await send_dm(user, warning_embed("تنبيه", f"تم خصم **{format_aero(deduct)}** من رصيدك من قِبل الإدارة."))

    @admin_group.command(name="set", description="تعديل إعدادات البوت")
    @app_commands.describe(
        setting="الإعداد المراد تعديله",
        value="القيمة الجديدة"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="المكافأة اليومية", value="daily_reward"),
        app_commands.Choice(name="المكافأة الأسبوعية", value="weekly_reward"),
        app_commands.Choice(name="مكافأة الإحالة", value="referral_reward"),
        app_commands.Choice(name="نسبة الضريبة (%)", value="tax_rate"),
        app_commands.Choice(name="قيمة Aero المرجعية", value="aero_value"),
    ])
    @is_admin()
    async def set_setting(self, interaction: discord.Interaction, setting: str, value: str):
        try:
            float_val = float(value)
            if float_val < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=error_embed("خطأ", "القيمة يجب أن تكون رقماً موجباً."), ephemeral=True)
            return

        setting_names = {
            "daily_reward": "المكافأة اليومية",
            "weekly_reward": "المكافأة الأسبوعية",
            "referral_reward": "مكافأة الإحالة",
            "tax_rate": "نسبة الضريبة",
            "aero_value": "قيمة Aero المرجعية",
        }

        embed = aero_embed("⚙️ تأكيد تغيير الإعداد",
            f"الإعداد: **{setting_names.get(setting, setting)}**\n"
            f"القيمة الجديدة: **{value}**\n\n"
            f"ملاحظة: تغيير القيمة يؤثر فقط على المكافآت المستقبلية.\n"
            f"اضغط موافق للاستمرار.")
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء التغيير."), view=view)
            return

        await db.set_setting(setting, value)
        await interaction.edit_original_response(
            embed=success_embed("تم التحديث!", f"تم تغيير **{setting_names.get(setting, setting)}** إلى **{value}**"),
            view=view
        )
        await send_dm(interaction.user, info_embed("تغيير إعداد", f"تم تغيير **{setting_names.get(setting, setting)}** إلى **{value}**"))

    @admin_group.command(name="reset", description="إعادة تعيين رصيد عضو إلى صفر")
    @app_commands.describe(user="العضو")
    @is_admin()
    async def reset_balance(self, interaction: discord.Interaction, user: discord.Member):
        await db.ensure_user(user.id)
        embed = aero_embed("🔄 تأكيد إعادة التعيين",
            f"ستقوم بإعادة تعيين رصيد {user.mention} إلى صفر.\n\n"
            f"اضغط موافق للاستمرار.")
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء العملية."), view=view)
            return

        await db.set_balance(user.id, 0)
        await db.add_transaction(interaction.user.id, user.id, 0, "admin_reset", "إعادة تعيين رصيد")
        await interaction.edit_original_response(embed=success_embed("تم!", f"تم إعادة تعيين رصيد {user.mention} إلى صفر."), view=view)
        await send_dm(user, warning_embed("تنبيه", "تم إعادة تعيين رصيدك إلى صفر من قِبل الإدارة."))

    @admin_group.command(name="stats", description="عرض إحصائيات البوت الكاملة مع تحليلات متقدمة")
    @is_admin()
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        aero_value = float(await db.get_setting("aero_value") or "0.018")
        s = await db.get_advanced_stats()
        view = StatsView(interaction.user.id, aero_value)
        view.pages = build_stats_pages(s, aero_value)
        view.update_nav_buttons()
        await interaction.followup.send(embed=view.pages[0], view=view, ephemeral=True)

    blacklist_group = app_commands.Group(name="blacklist", description="إدارة اللائحة السوداء", parent=admin_group)

    @blacklist_group.command(name="add", description="إضافة عضو إلى اللائحة السوداء")
    @app_commands.describe(user="العضو", reason="سبب الحظر")
    @is_admin()
    async def blacklist_add(self, interaction: discord.Interaction, user: discord.Member, reason: str = "لم يُذكر"):
        if await db.is_blacklisted(user.id):
            await interaction.response.send_message(embed=warning_embed("تنبيه", f"{user.mention} موجود بالفعل في اللائحة السوداء."), ephemeral=True)
            return

        await db.add_blacklist(user.id, reason, interaction.user.id)
        await interaction.response.send_message(
            embed=success_embed("تمت الإضافة!", f"تم إضافة {user.mention} إلى اللائحة السوداء.\nالسبب: {reason}"),
            ephemeral=True
        )
        await send_dm(user, error_embed(
            "تم حظرك من AeroBot",
            f"تم إضافتك إلى اللائحة السوداء.\n"
            f"السبب: **{reason}**\n"
            f"تواصل مع الإدارة إذا كنت تعتقد أن هذا خطأ."
        ))

    @blacklist_group.command(name="remove", description="إزالة عضو من اللائحة السوداء")
    @app_commands.describe(user="العضو")
    @is_admin()
    async def blacklist_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not await db.is_blacklisted(user.id):
            await interaction.response.send_message(embed=warning_embed("تنبيه", f"{user.mention} ليس في اللائحة السوداء."), ephemeral=True)
            return

        await db.remove_blacklist(user.id)
        await interaction.response.send_message(
            embed=success_embed("تمت الإزالة!", f"تم إزالة {user.mention} من اللائحة السوداء."),
            ephemeral=True
        )
        await send_dm(user, success_embed("رُفع الحظر", "تم إزالتك من اللائحة السوداء. يمكنك الآن استخدام AeroBot مرة أخرى."))

    @blacklist_group.command(name="list", description="عرض اللائحة السوداء")
    @is_admin()
    async def blacklist_list(self, interaction: discord.Interaction):
        bl = await db.get_blacklist()
        if not bl:
            await interaction.response.send_message(embed=info_embed("اللائحة السوداء", "اللائحة السوداء فارغة."), ephemeral=True)
            return

        embed = aero_embed(f"🚫 اللائحة السوداء ({len(bl)} عضو)")
        for entry in bl[:20]:
            uid = entry["user_id"]
            reason = entry["reason"] or "لم يُذكر"
            added_at = entry["added_at"]
            ts = int(added_at.timestamp()) if added_at else 0
            embed.add_field(
                name=f"<@{uid}>",
                value=f"السبب: {reason}\nتاريخ الإضافة: <t:{ts}:D>",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
