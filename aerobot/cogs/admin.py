import discord
from discord import app_commands
from discord.ext import commands
from helpers import (
    aero_embed, success_embed, error_embed, warning_embed, info_embed,
    format_aero, ConfirmView, send_dm, AERO_EMOJI, BOT_COLOR
)
import database as db
import os


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

    @admin_group.command(name="stats", description="عرض إحصائيات البوت الكاملة")
    @is_admin()
    async def stats(self, interaction: discord.Interaction):
        stats = await db.get_stats()
        aero_value = float(await db.get_setting("aero_value") or "0.018")
        embed = aero_embed("📊 إحصائيات AeroBot")
        embed.add_field(name="👥 عدد المستخدمين", value=f"**{stats['user_count']}**", inline=True)
        embed.add_field(name="🔄 عدد المعاملات", value=f"**{stats['tx_count']}**", inline=True)
        embed.add_field(name="💰 إجمالي Aero المتداول", value=f"**{format_aero(stats['total_aero'])}**", inline=False)
        embed.add_field(name="📈 أعلى رصيد", value=f"**{format_aero(stats['max_balance'])}**", inline=True)
        embed.add_field(name="📉 أدنى رصيد (نشط)", value=f"**{format_aero(stats['min_balance'])}**", inline=True)
        embed.add_field(name="⚖️ متوسط الرصيد", value=f"**{format_aero(stats['avg_balance'])}**", inline=True)
        embed.add_field(name="💹 القيمة المرجعية", value=f"1 Aero = **{aero_value}**", inline=False)
        embed.add_field(
            name="🔍 ملاحظة تحليلية",
            value=(
                f"إجمالي القيمة الكلية: **{stats['total_aero'] * aero_value:.4f}**\n"
                f"متوسط معاملات/مستخدم: **{stats['tx_count'] / max(stats['user_count'], 1):.1f}**"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
