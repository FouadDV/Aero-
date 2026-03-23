import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from helpers import (
    aero_embed, success_embed, error_embed, warning_embed, info_embed,
    format_aero, format_time_remaining, ConfirmView, send_dm, AERO_EMOJI
)
import database as db


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_blacklist(self, interaction: discord.Interaction) -> bool:
        if await db.is_blacklisted(interaction.user.id):
            embed = error_embed(
                "محظور من البوت",
                "أنت في اللائحة السوداء ولا يمكنك استخدام أوامر البوت.\n"
                "تواصل مع الإدارة إذا كنت تعتقد أن هذا خطأ."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await send_dm(interaction.user, embed)
            return False
        return True

    @app_commands.command(name="balance", description="عرض رصيد Aero الخاص بك أو بعضو آخر")
    @app_commands.describe(user="العضو المراد عرض رصيده (اختياري)")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        if not await self.check_blacklist(interaction):
            return
        target = user or interaction.user
        u = await db.ensure_user(target.id)
        bal = float(u["balance"])
        rank = await db.get_user_rank(target.id)
        embed = aero_embed(
            f"💰 رصيد {target.display_name}",
            f"الرصيد الحالي: **{format_aero(bal)}**\n"
            f"المستوى: **{u['level']}** | XP: **{u['xp']}**\n"
            f"الترتيب: **#{rank}**"
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="عرض ملفك الشخصي الكامل")
    @app_commands.describe(user="العضو المراد عرض ملفه (اختياري)")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        if not await self.check_blacklist(interaction):
            return
        target = user or interaction.user
        u = await db.ensure_user(target.id)
        bal = float(u["balance"])
        rank = await db.get_user_rank(target.id)
        from helpers import xp_for_level, level_progress_bar
        xp = u["xp"]
        level = u["level"]
        xp_needed = xp_for_level(level)
        bar = level_progress_bar(xp, level)
        embed = aero_embed(f"👤 ملف {target.display_name}")
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💰 الرصيد", value=format_aero(bal), inline=True)
        embed.add_field(name="🏆 الترتيب", value=f"#{rank}", inline=True)
        embed.add_field(name="⭐ المستوى", value=str(level), inline=True)
        embed.add_field(name="📊 تقدم XP", value=f"`{bar}`\n{xp}/{xp_needed} XP", inline=False)
        embed.add_field(name="🔗 كود الإحالة", value=f"`{u['referral_code']}`", inline=True)
        join_date = u["join_date"]
        if join_date:
            embed.add_field(name="📅 تاريخ الانضمام", value=f"<t:{int(join_date.timestamp())}:D>", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="احصل على مكافأتك اليومية")
    async def daily(self, interaction: discord.Interaction):
        if not await self.check_blacklist(interaction):
            return
        u = await db.ensure_user(interaction.user.id)
        last = u["last_daily"]
        now = datetime.utcnow()
        if last and now < last + timedelta(hours=24):
            next_time = last + timedelta(hours=24)
            remaining = format_time_remaining(next_time)
            embed = warning_embed(
                "المكافأة اليومية غير متاحة",
                f"يمكنك الحصول على مكافأتك اليومية بعد **{remaining}**"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        daily_reward = float(await db.get_setting("daily_reward") or "5")
        embed = aero_embed(
            "🌟 مكافأة يومية",
            f"حسابك يستخدم Aero داخل البوت فقط.\n"
            f"ستحصل على **{format_aero(daily_reward)}**\n\n"
            f"اضغط موافق للاستمرار."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            embed = error_embed("تم الإلغاء", "تم إلغاء عملية المكافأة اليومية.")
            await interaction.edit_original_response(embed=embed, view=view)
            return

        await db.update_balance(interaction.user.id, daily_reward, add_xp=10)
        await db.update_last_daily(interaction.user.id)
        await db.add_transaction(None, interaction.user.id, daily_reward, "daily", "مكافأة يومية")

        level_up = await db.check_level_up(interaction.user.id)
        result_embed = success_embed(
            "تم استلام المكافأة اليومية!",
            f"حصلت على **{format_aero(daily_reward)}** {AERO_EMOJI}\n"
            f"رصيدك الجديد: **{format_aero(float(u['balance']) + daily_reward)}**"
        )
        await interaction.edit_original_response(embed=result_embed, view=view)

        dm_embed = success_embed(
            "مكافأتك اليومية",
            f"تم إضافة **{format_aero(daily_reward)}** إلى رصيدك!\n"
            f"تاريخ الاستلام: <t:{int(now.timestamp())}:F>"
        )
        await send_dm(interaction.user, dm_embed)

        if level_up:
            new_level, reward = level_up
            level_embed = success_embed(
                "🎉 ترقية مستوى!",
                f"مبروك! وصلت إلى **المستوى {new_level}**!\n"
                f"مكافأة الترقية: **{format_aero(reward)}**"
            )
            await interaction.followup.send(embed=level_embed)
            await send_dm(interaction.user, level_embed)

    @app_commands.command(name="weekly", description="احصل على مكافأتك الأسبوعية")
    async def weekly(self, interaction: discord.Interaction):
        if not await self.check_blacklist(interaction):
            return
        u = await db.ensure_user(interaction.user.id)
        last = u["last_weekly"]
        now = datetime.utcnow()
        if last and now < last + timedelta(days=7):
            next_time = last + timedelta(days=7)
            remaining = format_time_remaining(next_time)
            embed = warning_embed(
                "المكافأة الأسبوعية غير متاحة",
                f"يمكنك الحصول على مكافأتك الأسبوعية بعد **{remaining}**"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        weekly_reward = float(await db.get_setting("weekly_reward") or "10")
        embed = aero_embed(
            "✨ مكافأة أسبوعية",
            f"حسابك يستخدم Aero داخل البوت فقط.\n"
            f"ستحصل على **{format_aero(weekly_reward)}**\n\n"
            f"اضغط موافق للاستمرار."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            embed = error_embed("تم الإلغاء", "تم إلغاء عملية المكافأة الأسبوعية.")
            await interaction.edit_original_response(embed=embed, view=view)
            return

        await db.update_balance(interaction.user.id, weekly_reward, add_xp=30)
        await db.update_last_weekly(interaction.user.id)
        await db.add_transaction(None, interaction.user.id, weekly_reward, "weekly", "مكافأة أسبوعية")

        level_up = await db.check_level_up(interaction.user.id)
        result_embed = success_embed(
            "تم استلام المكافأة الأسبوعية!",
            f"حصلت على **{format_aero(weekly_reward)}** {AERO_EMOJI}\n"
            f"رصيدك الجديد: **{format_aero(float(u['balance']) + weekly_reward)}**"
        )
        await interaction.edit_original_response(embed=result_embed, view=view)

        dm_embed = success_embed(
            "مكافأتك الأسبوعية",
            f"تم إضافة **{format_aero(weekly_reward)}** إلى رصيدك!\n"
            f"تاريخ الاستلام: <t:{int(now.timestamp())}:F>"
        )
        await send_dm(interaction.user, dm_embed)

        if level_up:
            new_level, reward = level_up
            level_embed = success_embed(
                "🎉 ترقية مستوى!",
                f"مبروك! وصلت إلى **المستوى {new_level}**!\n"
                f"مكافأة الترقية: **{format_aero(reward)}**"
            )
            await interaction.followup.send(embed=level_embed)
            await send_dm(interaction.user, level_embed)

    @app_commands.command(name="pay", description="إرسال Aero إلى عضو آخر")
    @app_commands.describe(user="العضو المستلم", amount="كمية Aero المراد إرسالها")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        if not await self.check_blacklist(interaction):
            return
        if user.bot:
            await interaction.response.send_message(embed=error_embed("خطأ", "لا يمكنك الإرسال إلى بوت."), ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("خطأ", "لا يمكنك الإرسال لنفسك."), ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message(embed=error_embed("خطأ", "يجب أن تكون الكمية أكبر من صفر."), ephemeral=True)
            return

        sender = await db.ensure_user(interaction.user.id)
        sender_bal = float(sender["balance"])
        tax_rate = float(await db.get_setting("tax_rate") or "0") / 100
        tax = round(amount * tax_rate, 4)
        total_deducted = amount + tax

        if sender_bal < total_deducted:
            await interaction.response.send_message(
                embed=error_embed("رصيد غير كافٍ", f"رصيدك: **{format_aero(sender_bal)}**\nالمبلغ المطلوب: **{format_aero(total_deducted)}**"),
                ephemeral=True
            )
            return

        await db.ensure_user(user.id)

        embed = aero_embed(
            "💸 تأكيد التحويل",
            f"حسابك يستخدم Aero داخل البوت فقط.\n\n"
            f"المستلم: {user.mention}\n"
            f"المبلغ: **{format_aero(amount)}**\n"
            f"الضريبة: **{format_aero(tax)}**\n"
            f"إجمالي الخصم: **{format_aero(total_deducted)}**\n\n"
            f"اضغط موافق للاستمرار."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء عملية التحويل."), view=view)
            return

        await db.update_balance(interaction.user.id, -total_deducted, add_xp=5)
        await db.update_balance(user.id, amount, add_xp=3)
        await db.add_transaction(interaction.user.id, user.id, amount, "pay", f"تحويل من {interaction.user.name}")

        result_embed = success_embed(
            "تم التحويل بنجاح!",
            f"أرسلت **{format_aero(amount)}** إلى {user.mention}\n"
            f"رصيدك الجديد: **{format_aero(sender_bal - total_deducted)}**"
        )
        await interaction.edit_original_response(embed=result_embed, view=view)

        sender_dm = success_embed("تأكيد التحويل", f"أرسلت **{format_aero(amount)}** إلى **{user.display_name}**")
        receiver_dm = info_embed("استلمت Aero!", f"استلمت **{format_aero(amount)}** من **{interaction.user.display_name}**")
        await send_dm(interaction.user, sender_dm)
        await send_dm(user, receiver_dm)

        for uid in [interaction.user.id, user.id]:
            level_up = await db.check_level_up(uid)
            if level_up:
                new_level, reward = level_up
                target_user = interaction.user if uid == interaction.user.id else user
                level_embed = success_embed("🎉 ترقية مستوى!", f"وصلت إلى **المستوى {new_level}**! مكافأة: **{format_aero(reward)}**")
                await send_dm(target_user, level_embed)

    @app_commands.command(name="gift", description="إرسال هدية Aero بدون ضريبة")
    @app_commands.describe(user="المستلم", amount="كمية الهدية")
    async def gift(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        if not await self.check_blacklist(interaction):
            return
        if user.bot:
            await interaction.response.send_message(embed=error_embed("خطأ", "لا يمكنك الإرسال إلى بوت."), ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("خطأ", "لا يمكنك إرسال هدية لنفسك."), ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message(embed=error_embed("خطأ", "يجب أن تكون الكمية أكبر من صفر."), ephemeral=True)
            return

        sender = await db.ensure_user(interaction.user.id)
        sender_bal = float(sender["balance"])

        if sender_bal < amount:
            await interaction.response.send_message(
                embed=error_embed("رصيد غير كافٍ", f"رصيدك: **{format_aero(sender_bal)}**"),
                ephemeral=True
            )
            return

        await db.ensure_user(user.id)

        embed = aero_embed(
            "🎁 تأكيد الهدية",
            f"حسابك يستخدم Aero داخل البوت فقط.\n\n"
            f"المستلم: {user.mention}\n"
            f"الهدية: **{format_aero(amount)}** (بدون ضريبة)\n\n"
            f"اضغط موافق للاستمرار."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء إرسال الهدية."), view=view)
            return

        await db.update_balance(interaction.user.id, -amount, add_xp=5)
        await db.update_balance(user.id, amount, add_xp=3)
        await db.add_transaction(interaction.user.id, user.id, amount, "gift", f"هدية من {interaction.user.name}")

        result_embed = success_embed("تم إرسال الهدية!", f"أرسلت هدية **{format_aero(amount)}** إلى {user.mention} 🎁")
        await interaction.edit_original_response(embed=result_embed, view=view)

        await send_dm(interaction.user, success_embed("تأكيد الهدية", f"أرسلت هدية **{format_aero(amount)}** إلى **{user.display_name}** 🎁"))
        await send_dm(user, info_embed("استلمت هدية!", f"استلمت هدية **{format_aero(amount)}** من **{interaction.user.display_name}** 🎁"))

    @app_commands.command(name="trade", description="مقايضة Aero مع عضو آخر")
    @app_commands.describe(user="العضو الآخر", give="كمية Aero التي ستعطيها", receive="كمية Aero التي ستستلمها")
    async def trade(self, interaction: discord.Interaction, user: discord.Member, give: float, receive: float):
        if not await self.check_blacklist(interaction):
            return
        if user.bot or user.id == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("خطأ", "لا يمكن إجراء مقايضة مع هذا المستخدم."), ephemeral=True)
            return
        if give <= 0 or receive <= 0:
            await interaction.response.send_message(embed=error_embed("خطأ", "يجب أن تكون الكميات أكبر من صفر."), ephemeral=True)
            return

        sender = await db.ensure_user(interaction.user.id)
        receiver = await db.ensure_user(user.id)

        if float(sender["balance"]) < give:
            await interaction.response.send_message(embed=error_embed("رصيد غير كافٍ", f"رصيدك: **{format_aero(float(sender['balance']))}**"), ephemeral=True)
            return
        if float(receiver["balance"]) < receive:
            await interaction.response.send_message(embed=error_embed("رصيد غير كافٍ", f"رصيد {user.display_name} غير كافٍ للمقايضة."), ephemeral=True)
            return

        embed = aero_embed(
            "🔄 تأكيد المقايضة",
            f"حسابك يستخدم Aero داخل البوت فقط.\n\n"
            f"ستعطي: **{format_aero(give)}** لـ {user.mention}\n"
            f"ستستلم: **{format_aero(receive)}** من {user.mention}\n\n"
            f"⚠️ يحتاج {user.mention} أيضاً للموافقة.\n"
            f"اضغط موافق للاستمرار."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء المقايضة."), view=view)
            return

        confirm_embed = info_embed(
            "طلب مقايضة",
            f"{interaction.user.mention} يريد مقايضة:\n"
            f"يعطيك: **{format_aero(give)}**\n"
            f"يأخذ منك: **{format_aero(receive)}**\n\n"
            f"هل توافق؟"
        )
        receiver_view = ConfirmView(user.id)
        await interaction.followup.send(content=user.mention, embed=confirm_embed, view=receiver_view)
        await receiver_view.wait()

        if not receiver_view.confirmed:
            await interaction.followup.send(embed=error_embed("المقايضة مرفوضة", f"رفض {user.mention} المقايضة."))
            return

        await db.update_balance(interaction.user.id, -give + receive, add_xp=10)
        await db.update_balance(user.id, give - receive, add_xp=10)
        await db.add_transaction(interaction.user.id, user.id, give, "trade_out", f"مقايضة مع {user.name}")
        await db.add_transaction(user.id, interaction.user.id, receive, "trade_in", f"مقايضة مع {interaction.user.name}")

        await interaction.followup.send(embed=success_embed("تمت المقايضة!", f"اكتملت المقايضة بين {interaction.user.mention} و {user.mention}"))
        await send_dm(interaction.user, success_embed("تأكيد المقايضة", f"تمت المقايضة مع **{user.display_name}** بنجاح."))
        await send_dm(user, success_embed("تأكيد المقايضة", f"تمت المقايضة مع **{interaction.user.display_name}** بنجاح."))

    @app_commands.command(name="transactions", description="عرض آخر معاملاتك")
    async def transactions(self, interaction: discord.Interaction):
        if not await self.check_blacklist(interaction):
            return
        await db.ensure_user(interaction.user.id)
        total = await db.count_transactions(interaction.user.id)
        if total == 0:
            await interaction.response.send_message(embed=info_embed("المعاملات", "لا توجد معاملات بعد."), ephemeral=True)
            return

        tx_list = await db.get_transactions(interaction.user.id, limit=50)
        pages = []
        per_page = 5
        for i in range(0, len(tx_list), per_page):
            chunk = tx_list[i:i + per_page]
            embed = aero_embed(f"📋 معاملاتك ({i + 1}-{min(i + per_page, len(tx_list))} من {len(tx_list)})")
            for tx in chunk:
                tx_type = tx["type"]
                amount = float(tx["amount"])
                sender_id = tx["sender_id"]
                receiver_id = tx["receiver_id"]
                ts = int(tx["created_at"].timestamp())

                if tx_type in ("daily", "weekly", "referral", "admin_add"):
                    icon = "➕"
                    direction = "استلمت"
                elif tx_type in ("pay", "gift", "trade_out", "admin_remove"):
                    if sender_id == interaction.user.id:
                        icon = "➖"
                        direction = "أرسلت"
                    else:
                        icon = "➕"
                        direction = "استلمت"
                else:
                    icon = "🔄"
                    direction = tx_type

                desc = tx.get("description") or direction
                embed.add_field(
                    name=f"{icon} {desc}",
                    value=f"**{format_aero(amount)}** • <t:{ts}:R>",
                    inline=False
                )
            embed.set_footer(text=f"AeroBot • صفحة {i // per_page + 1} من {(len(tx_list) + per_page - 1) // per_page}")
            pages.append(embed)

        from helpers import PaginationView
        view = PaginationView(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=view)

    @app_commands.command(name="referral", description="استخدام كود إحالة للحصول على مكافأة")
    @app_commands.describe(code="كود الإحالة")
    async def referral(self, interaction: discord.Interaction, code: str):
        if not await self.check_blacklist(interaction):
            return
        u = await db.ensure_user(interaction.user.id)
        if u["referred_by"]:
            await interaction.response.send_message(embed=error_embed("خطأ", "لقد استخدمت كود إحالة من قبل."), ephemeral=True)
            return

        referrer = await db.get_referral_by_code(code.upper())
        if not referrer:
            await interaction.response.send_message(embed=error_embed("كود غير صحيح", "الكود الذي أدخلته غير موجود."), ephemeral=True)
            return
        if referrer["id"] == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("خطأ", "لا يمكنك استخدام كودك الخاص."), ephemeral=True)
            return

        referral_reward = float(await db.get_setting("referral_reward") or "5")

        embed = aero_embed("🔗 تأكيد كود الإحالة",
            f"حسابك يستخدم Aero داخل البوت فقط.\n"
            f"ستحصل على **{format_aero(referral_reward)}** مكافأة إحالة!\n\n"
            f"اضغط موافق للاستمرار.")
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=error_embed("تم الإلغاء", "تم إلغاء العملية."), view=view)
            return

        await db.set_referred_by(interaction.user.id, referrer["id"])
        await db.update_balance(interaction.user.id, referral_reward, add_xp=15)
        await db.update_balance(referrer["id"], referral_reward, add_xp=15)
        await db.add_transaction(None, interaction.user.id, referral_reward, "referral", "مكافأة إحالة")
        await db.add_transaction(None, referrer["id"], referral_reward, "referral", "مكافأة إحالة ناجحة")

        await interaction.edit_original_response(
            embed=success_embed("مكافأة الإحالة!", f"حصلت على **{format_aero(referral_reward)}**! 🎉"),
            view=view
        )

        try:
            referrer_user = await interaction.client.fetch_user(referrer["id"])
            await send_dm(referrer_user, info_embed("إحالة ناجحة!", f"قام **{interaction.user.display_name}** باستخدام كود إحالتك! حصلت على **{format_aero(referral_reward)}**"))
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Economy(bot))
