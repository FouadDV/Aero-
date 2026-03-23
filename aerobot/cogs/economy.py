import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from helpers import (
    aero_embed, success_embed, error_embed, warning_embed, info_embed,
    format_aero, format_time_remaining, ConfirmView, send_dm,
    AERO_EMOJI, DIV, xp_for_level, level_progress_bar, rank_badge, wealth_tier
)
import database as db


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_blacklist(self, interaction: discord.Interaction) -> bool:
        if await db.is_blacklisted(interaction.user.id):
            embed = error_embed(
                "الوصول محظور",
                f"{DIV}\n"
                "أنت مُدرج في اللائحة السوداء ولا يمكنك استخدام البوت.\n\n"
                "إذا كنت تعتقد أن هذا خطأ، تواصل مع الإدارة مباشرةً."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await send_dm(interaction.user, embed)
            return False
        return True

    @app_commands.command(name="balance", description="اعرض رصيدك أو رصيد أي عضو")
    @app_commands.describe(user="العضو المراد الاستعلام عن رصيده")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        if not await self.check_blacklist(interaction):
            return
        target = user or interaction.user
        u      = await db.ensure_user(target.id)
        bal    = float(u["balance"])
        rank   = await db.get_user_rank(target.id)
        tier   = wealth_tier(bal)
        badge  = rank_badge(u["level"])

        embed = aero_embed(f"💼  محفظة  {target.display_name}")
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.description = (
            f"{DIV}\n"
            f"**الرصيد الحالي**\n"
            f"## {format_aero(bal)}\n"
            f"{DIV}"
        )
        embed.add_field(name="🏆 الترتيب", value=f"**# {rank}**", inline=True)
        embed.add_field(name="⭐ المستوى", value=f"**{u['level']}**  {badge}", inline=True)
        embed.add_field(name="💎 الفئة",   value=tier, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="عرض ملفك الشخصي الكامل")
    @app_commands.describe(user="العضو المراد عرض ملفه")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        if not await self.check_blacklist(interaction):
            return
        target   = user or interaction.user
        u        = await db.ensure_user(target.id)
        bal      = float(u["balance"])
        rank     = await db.get_user_rank(target.id)
        xp       = u["xp"]
        level    = u["level"]
        xp_need  = xp_for_level(level)
        bar      = level_progress_bar(xp, level)
        badge    = rank_badge(level)
        tier     = wealth_tier(bal)

        embed = aero_embed(f"🪪  الملف الشخصي  —  {target.display_name}")
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.description = (
            f"{DIV}\n"
            f"**الرصيد الكلي**\n"
            f"## {format_aero(bal)}\n"
            f"{DIV}"
        )
        embed.add_field(name="🏆 الترتيب",  value=f"# {rank}", inline=True)
        embed.add_field(name="⭐ المستوى",  value=f"{level}  {badge}", inline=True)
        embed.add_field(name="💎 الفئة",    value=tier, inline=True)
        embed.add_field(
            name="📊 تقدم المستوى",
            value=f"`{bar}`\n> **{xp}** / **{xp_need}** XP",
            inline=False
        )
        embed.add_field(name="🔗 كود الإحالة", value=f"```{u['referral_code']}```", inline=True)
        if u["join_date"]:
            embed.add_field(name="📅 عضو منذ", value=f"<t:{int(u['join_date'].timestamp())}:D>", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="استلم مكافأتك اليومية")
    async def daily(self, interaction: discord.Interaction):
        if not await self.check_blacklist(interaction):
            return
        u    = await db.ensure_user(interaction.user.id)
        last = u["last_daily"]
        now  = datetime.utcnow()

        if last and now < last + timedelta(hours=24):
            remaining = format_time_remaining(last + timedelta(hours=24))
            embed = warning_embed(
                "المكافأة اليومية غير متاحة بعد",
                f"{DIV}\n"
                f"لا يزال عليك الانتظار قليلاً قبل استلام مكافأتك القادمة.\n\n"
                f"⏱️ **الوقت المتبقي:** {remaining}\n"
                f"{DIV}\n"
                f"عُد لاحقاً ولا تفوّت يومك! 🎯"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        reward = float(await db.get_setting("daily_reward") or "5")
        embed = aero_embed(
            "🌅  المكافأة اليومية",
            f"{DIV}\n"
            f"**تذكير:** Aero عملة افتراضية داخل البوت حصراً،\n"
            f"ولا يمكن استخدامها خارج Discord.\n"
            f"{DIV}\n"
            f"🪙 **ستستلم:** {format_aero(reward)}\n\n"
            f"اضغط **تأكيد** للمتابعة."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(
                embed=warning_embed("تم الإلغاء", "ألغيت العملية. يمكنك المحاولة مرة أخرى في أي وقت."),
                view=view
            )
            return

        await db.update_balance(interaction.user.id, reward, add_xp=10)
        await db.update_last_daily(interaction.user.id)
        await db.add_transaction(None, interaction.user.id, reward, "daily", "مكافأة يومية")
        level_up = await db.check_level_up(interaction.user.id)

        new_bal = float(u["balance"]) + reward
        result = success_embed(
            "استلمت مكافأتك اليومية!",
            f"{DIV}\n"
            f"🪙 **المبلغ المضاف:** {format_aero(reward)}\n"
            f"💼 **رصيدك الآن:** {format_aero(new_bal)}\n"
            f"{DIV}\n"
            f"عُد غداً لاستلام مكافأة جديدة! 🌟"
        )
        await interaction.edit_original_response(embed=result, view=view)

        await send_dm(interaction.user, info_embed(
            "إشعار — مكافأتك اليومية",
            f"{DIV}\n"
            f"تم إضافة **{format_aero(reward)}** إلى محفظتك.\n"
            f"💼 رصيدك الحالي: **{format_aero(new_bal)}**\n"
            f"🕐 وقت الاستلام: <t:{int(now.timestamp())}:F>\n"
            f"{DIV}"
        ))

        if level_up:
            new_level, lv_reward = level_up
            lv_embed = success_embed(
                "ترقية مستوى! 🎉",
                f"{DIV}\n"
                f"مبروك! انتقلت إلى **المستوى {new_level}** {rank_badge(new_level)}\n"
                f"🎁 **مكافأة الترقية:** {format_aero(lv_reward)}\n"
                f"{DIV}\n"
                f"واصل النشاط للوصول إلى المستوى التالي!"
            )
            await interaction.followup.send(embed=lv_embed)
            await send_dm(interaction.user, lv_embed)

    @app_commands.command(name="weekly", description="استلم مكافأتك الأسبوعية")
    async def weekly(self, interaction: discord.Interaction):
        if not await self.check_blacklist(interaction):
            return
        u    = await db.ensure_user(interaction.user.id)
        last = u["last_weekly"]
        now  = datetime.utcnow()

        if last and now < last + timedelta(days=7):
            remaining = format_time_remaining(last + timedelta(days=7))
            embed = warning_embed(
                "المكافأة الأسبوعية غير متاحة بعد",
                f"{DIV}\n"
                f"لم تمر 7 أيام منذ آخر استلام بعد.\n\n"
                f"⏱️ **الوقت المتبقي:** {remaining}\n"
                f"{DIV}\n"
                f"ضع تذكيراً ولا تفوّت هذه المكافأة! 📆"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        reward = float(await db.get_setting("weekly_reward") or "10")
        embed = aero_embed(
            "📆  المكافأة الأسبوعية",
            f"{DIV}\n"
            f"**تذكير:** Aero عملة افتراضية داخل البوت حصراً.\n"
            f"{DIV}\n"
            f"🪙 **ستستلم:** {format_aero(reward)}\n\n"
            f"اضغط **تأكيد** للمتابعة."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(
                embed=warning_embed("تم الإلغاء", "ألغيت العملية. يمكنك المحاولة في أي وقت."),
                view=view
            )
            return

        await db.update_balance(interaction.user.id, reward, add_xp=30)
        await db.update_last_weekly(interaction.user.id)
        await db.add_transaction(None, interaction.user.id, reward, "weekly", "مكافأة أسبوعية")
        level_up = await db.check_level_up(interaction.user.id)

        new_bal = float(u["balance"]) + reward
        result = success_embed(
            "استلمت مكافأتك الأسبوعية!",
            f"{DIV}\n"
            f"🪙 **المبلغ المضاف:** {format_aero(reward)}\n"
            f"💼 **رصيدك الآن:** {format_aero(new_bal)}\n"
            f"{DIV}\n"
            f"أحسنت! عُد الأسبوع القادم 🗓️"
        )
        await interaction.edit_original_response(embed=result, view=view)

        await send_dm(interaction.user, info_embed(
            "إشعار — مكافأتك الأسبوعية",
            f"{DIV}\n"
            f"تم إضافة **{format_aero(reward)}** إلى محفظتك.\n"
            f"💼 رصيدك الحالي: **{format_aero(new_bal)}**\n"
            f"🕐 وقت الاستلام: <t:{int(now.timestamp())}:F>\n"
            f"{DIV}"
        ))

        if level_up:
            new_level, lv_reward = level_up
            lv_embed = success_embed(
                "ترقية مستوى! 🎉",
                f"{DIV}\n"
                f"مبروك! انتقلت إلى **المستوى {new_level}** {rank_badge(new_level)}\n"
                f"🎁 **مكافأة الترقية:** {format_aero(lv_reward)}\n"
                f"{DIV}"
            )
            await interaction.followup.send(embed=lv_embed)
            await send_dm(interaction.user, lv_embed)

    @app_commands.command(name="pay", description="أرسل Aero إلى عضو آخر")
    @app_commands.describe(user="العضو المستلم", amount="الكمية المراد إرسالها")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        if not await self.check_blacklist(interaction):
            return
        if user.bot:
            await interaction.response.send_message(embed=error_embed("عملية غير مسموحة", "لا يمكنك إرسال Aero إلى بوت."), ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("عملية غير مسموحة", "لا يمكنك إرسال Aero إلى نفسك."), ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message(embed=error_embed("كمية غير صحيحة", "يجب أن تكون الكمية أكبر من الصفر."), ephemeral=True)
            return

        sender     = await db.ensure_user(interaction.user.id)
        sender_bal = float(sender["balance"])
        tax_rate   = float(await db.get_setting("tax_rate") or "0") / 100
        tax        = round(amount * tax_rate, 4)
        total      = amount + tax

        if sender_bal < total:
            await interaction.response.send_message(
                embed=error_embed(
                    "رصيد غير كافٍ",
                    f"{DIV}\n"
                    f"رصيدك الحالي: **{format_aero(sender_bal)}**\n"
                    f"المبلغ المطلوب: **{format_aero(total)}**\n"
                    f"{DIV}\n"
                    f"الفرق: **{format_aero(total - sender_bal)}**"
                ),
                ephemeral=True
            )
            return

        await db.ensure_user(user.id)
        embed = aero_embed(
            "💸  تأكيد التحويل",
            f"{DIV}\n"
            f"**تذكير:** Aero عملة افتراضية داخل البوت حصراً.\n"
            f"{DIV}\n"
            f"👤 **المستلم:** {user.mention}\n"
            f"💰 **المبلغ:** {format_aero(amount)}\n"
            f"📊 **الضريبة ({int(tax_rate*100)}%):** {format_aero(tax)}\n"
            f"💳 **إجمالي الخصم:** {format_aero(total)}\n"
            f"{DIV}\n"
            f"اضغط **تأكيد** للمتابعة."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=warning_embed("تم الإلغاء", "لم يتم إجراء أي تحويل."), view=view)
            return

        await db.update_balance(interaction.user.id, -total, add_xp=5)
        await db.update_balance(user.id, amount, add_xp=3)
        await db.add_transaction(interaction.user.id, user.id, amount, "pay", f"تحويل إلى {user.display_name}")

        await interaction.edit_original_response(
            embed=success_embed(
                "تم التحويل بنجاح!",
                f"{DIV}\n"
                f"💸 أرسلت **{format_aero(amount)}** إلى {user.mention}\n"
                f"💼 رصيدك الجديد: **{format_aero(sender_bal - total)}**\n"
                f"{DIV}"
            ),
            view=view
        )
        await send_dm(interaction.user, info_embed(
            "إشعار — تحويل صادر",
            f"{DIV}\n"
            f"أرسلت **{format_aero(amount)}** إلى **{user.display_name}**\n"
            f"💼 رصيدك الحالي: **{format_aero(sender_bal - total)}**\n"
            f"🕐 <t:{int(datetime.utcnow().timestamp())}:F>\n{DIV}"
        ))
        await send_dm(user, info_embed(
            "إشعار — تحويل وارد 🎉",
            f"{DIV}\n"
            f"استلمت **{format_aero(amount)}** من **{interaction.user.display_name}**\n"
            f"🕐 <t:{int(datetime.utcnow().timestamp())}:F>\n{DIV}"
        ))

        for uid in [interaction.user.id, user.id]:
            lv = await db.check_level_up(uid)
            if lv:
                new_level, lv_reward = lv
                tgt = interaction.user if uid == interaction.user.id else user
                await send_dm(tgt, success_embed(
                    "ترقية مستوى! 🎉",
                    f"وصلت إلى **المستوى {new_level}** {rank_badge(new_level)}\n"
                    f"🎁 مكافأة: **{format_aero(lv_reward)}**"
                ))

    @app_commands.command(name="gift", description="أرسل هدية Aero بدون ضريبة")
    @app_commands.describe(user="المستلم", amount="كمية الهدية")
    async def gift(self, interaction: discord.Interaction, user: discord.Member, amount: float):
        if not await self.check_blacklist(interaction):
            return
        if user.bot:
            await interaction.response.send_message(embed=error_embed("عملية غير مسموحة", "لا يمكنك إرسال هدية إلى بوت."), ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("عملية غير مسموحة", "لا يمكنك إرسال هدية لنفسك."), ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message(embed=error_embed("كمية غير صحيحة", "يجب أن تكون الكمية أكبر من الصفر."), ephemeral=True)
            return

        sender = await db.ensure_user(interaction.user.id)
        bal    = float(sender["balance"])

        if bal < amount:
            await interaction.response.send_message(
                embed=error_embed("رصيد غير كافٍ", f"رصيدك: **{format_aero(bal)}**\nالمطلوب: **{format_aero(amount)}**"),
                ephemeral=True
            )
            return

        await db.ensure_user(user.id)
        embed = aero_embed(
            "🎁  تأكيد الهدية",
            f"{DIV}\n"
            f"**تذكير:** Aero عملة افتراضية داخل البوت حصراً.\n"
            f"{DIV}\n"
            f"👤 **المستلم:** {user.mention}\n"
            f"🎁 **قيمة الهدية:** {format_aero(amount)}\n"
            f"✨ **الضريبة:** معفاة\n"
            f"{DIV}\n"
            f"اضغط **تأكيد** للمتابعة."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=warning_embed("تم الإلغاء", "لم يتم إرسال الهدية."), view=view)
            return

        await db.update_balance(interaction.user.id, -amount, add_xp=5)
        await db.update_balance(user.id, amount, add_xp=3)
        await db.add_transaction(interaction.user.id, user.id, amount, "gift", f"هدية إلى {user.display_name}")

        await interaction.edit_original_response(
            embed=success_embed(
                "تم إرسال الهدية! 🎁",
                f"{DIV}\n"
                f"أرسلت هدية **{format_aero(amount)}** إلى {user.mention}\n"
                f"💼 رصيدك الجديد: **{format_aero(bal - amount)}**\n"
                f"{DIV}"
            ),
            view=view
        )
        await send_dm(interaction.user, info_embed(
            "إشعار — هدية مُرسَلة",
            f"{DIV}\nأرسلت هدية **{format_aero(amount)}** إلى **{user.display_name}** 🎁\n{DIV}"
        ))
        await send_dm(user, success_embed(
            "استلمت هدية! 🎁",
            f"{DIV}\n"
            f"أرسل لك **{interaction.user.display_name}** هدية قيمتها **{format_aero(amount)}**\n"
            f"🕐 <t:{int(datetime.utcnow().timestamp())}:R>\n"
            f"{DIV}"
        ))

    @app_commands.command(name="trade", description="قايض Aero مع عضو آخر")
    @app_commands.describe(user="العضو الآخر", give="ما ستُعطيه", receive="ما ستستلمه")
    async def trade(self, interaction: discord.Interaction, user: discord.Member, give: float, receive: float):
        if not await self.check_blacklist(interaction):
            return
        if user.bot or user.id == interaction.user.id:
            await interaction.response.send_message(embed=error_embed("عملية غير مسموحة", "لا يمكن إجراء المقايضة مع هذا المستخدم."), ephemeral=True)
            return
        if give <= 0 or receive <= 0:
            await interaction.response.send_message(embed=error_embed("كميات غير صحيحة", "جميع الكميات يجب أن تكون أكبر من الصفر."), ephemeral=True)
            return

        sender   = await db.ensure_user(interaction.user.id)
        receiver = await db.ensure_user(user.id)

        if float(sender["balance"]) < give:
            await interaction.response.send_message(embed=error_embed("رصيد غير كافٍ", f"رصيدك: **{format_aero(float(sender['balance']))}**"), ephemeral=True)
            return
        if float(receiver["balance"]) < receive:
            await interaction.response.send_message(embed=error_embed("رصيد غير كافٍ", f"رصيد {user.display_name} غير كافٍ لهذه المقايضة."), ephemeral=True)
            return

        embed = aero_embed(
            "🔄  تأكيد المقايضة",
            f"{DIV}\n"
            f"**تذكير:** Aero عملة افتراضية داخل البوت حصراً.\n"
            f"{DIV}\n"
            f"📤 **ستُعطي:** {format_aero(give)} → {user.mention}\n"
            f"📥 **ستستلم:** {format_aero(receive)} ← {user.mention}\n"
            f"{DIV}\n"
            f"⚠️ سيطلب من {user.mention} موافقته أيضاً.\n"
            f"اضغط **تأكيد** للمتابعة."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=warning_embed("تم الإلغاء", "لم تُجرَ أي مقايضة."), view=view)
            return

        r_embed = info_embed(
            "طلب مقايضة وارد 🔄",
            f"{DIV}\n"
            f"**{interaction.user.display_name}** يطلب مقايضة معك:\n\n"
            f"📤 **سيُعطيك:** {format_aero(give)}\n"
            f"📥 **يريد منك:** {format_aero(receive)}\n"
            f"{DIV}\n"
            f"هل توافق على هذه المقايضة؟"
        )
        r_view = ConfirmView(user.id)
        await interaction.followup.send(content=user.mention, embed=r_embed, view=r_view)
        await r_view.wait()

        if not r_view.confirmed:
            await interaction.followup.send(
                embed=error_embed("المقايضة مرفوضة", f"رفض {user.mention} المقايضة.")
            )
            return

        await db.update_balance(interaction.user.id, -give + receive, add_xp=10)
        await db.update_balance(user.id, give - receive, add_xp=10)
        await db.add_transaction(interaction.user.id, user.id, give,    "trade_out", f"مقايضة مع {user.display_name}")
        await db.add_transaction(user.id, interaction.user.id, receive, "trade_in",  f"مقايضة مع {interaction.user.display_name}")

        await interaction.followup.send(
            embed=success_embed(
                "اكتملت المقايضة! 🤝",
                f"{DIV}\n"
                f"تبادل **{interaction.user.mention}** و **{user.mention}** بنجاح.\n"
                f"{DIV}"
            )
        )
        await send_dm(interaction.user, success_embed("تأكيد — مقايضة مكتملة", f"اكتملت مقايضتك مع **{user.display_name}** بنجاح. 🤝"))
        await send_dm(user, success_embed("تأكيد — مقايضة مكتملة", f"اكتملت مقايضتك مع **{interaction.user.display_name}** بنجاح. 🤝"))

    @app_commands.command(name="transactions", description="عرض سجل معاملاتك")
    async def transactions(self, interaction: discord.Interaction):
        if not await self.check_blacklist(interaction):
            return

        await db.ensure_user(interaction.user.id)
        total = await db.count_transactions(interaction.user.id)
        if total == 0:
            await interaction.response.send_message(
                embed=info_embed("سجل المعاملات", f"{DIV}\nلا توجد معاملات مسجلة بعد.\nابدأ بـ `/daily` لكسب أول Aero! 🚀"),
                ephemeral=True
            )
            return

        tx_list  = await db.get_transactions(interaction.user.id, limit=50)
        per_page = 5
        pages    = []

        type_icons = {
            "daily":        ("🌅", "مكافأة يومية"),
            "weekly":       ("📆", "مكافأة أسبوعية"),
            "referral":     ("🔗", "مكافأة إحالة"),
            "pay":          ("💸", "تحويل"),
            "gift":         ("🎁", "هدية"),
            "trade_out":    ("🔄", "مقايضة — صادر"),
            "trade_in":     ("🔄", "مقايضة — وارد"),
            "admin_add":    ("➕", "إضافة إدارية"),
            "admin_remove": ("➖", "خصم إداري"),
            "admin_reset":  ("♻️", "إعادة تعيين"),
        }

        for i in range(0, len(tx_list), per_page):
            chunk    = tx_list[i:i + per_page]
            page_num = i // per_page + 1
            total_pages = (len(tx_list) + per_page - 1) // per_page
            embed = aero_embed(f"📋  سجل المعاملات  —  صفحة {page_num}/{total_pages}")
            embed.description = DIV

            for tx in chunk:
                t_type  = tx["type"]
                amount  = float(tx["amount"])
                sent_by = tx["sender_id"]
                ts      = int(tx["created_at"].timestamp())

                icon, label = type_icons.get(t_type, ("🔁", t_type))

                is_incoming = (
                    t_type in ("daily", "weekly", "referral", "admin_add", "trade_in") or
                    (t_type in ("pay", "gift") and sent_by != interaction.user.id)
                )
                sign  = "+  " if is_incoming else "−  "
                color_hint = "🟢" if is_incoming else "🔴"

                embed.add_field(
                    name=f"{icon}  {label}",
                    value=(
                        f"{color_hint} **{sign}{format_aero(amount)}**\n"
                        f"🕐 <t:{ts}:R>"
                    ),
                    inline=True
                )

            embed.set_footer(text=f"✦ AeroBot  •  {len(tx_list)} معاملة إجمالاً  •  صفحة {page_num}/{total_pages} ✦")
            pages.append(embed)

        from helpers import PaginationView
        view = PaginationView(interaction.user.id, pages)
        await interaction.response.send_message(embed=pages[0], view=view)

    @app_commands.command(name="referral", description="استخدم كود إحالة واحصل على مكافأة")
    @app_commands.describe(code="كود الإحالة")
    async def referral(self, interaction: discord.Interaction, code: str):
        if not await self.check_blacklist(interaction):
            return
        u = await db.ensure_user(interaction.user.id)

        if u["referred_by"]:
            await interaction.response.send_message(
                embed=error_embed("مستخدم من قبل", "لقد سبق أن استخدمت كود إحالة. لا يُسمح بأكثر من إحالة واحدة."),
                ephemeral=True
            )
            return

        referrer = await db.get_referral_by_code(code.upper().strip())
        if not referrer:
            await interaction.response.send_message(
                embed=error_embed("كود غير صحيح", f"{DIV}\nالكود الذي أدخلته **غير موجود** في النظام.\nتأكد من الكود وحاول مجدداً."),
                ephemeral=True
            )
            return
        if referrer["id"] == interaction.user.id:
            await interaction.response.send_message(
                embed=error_embed("غير مسموح", "لا يمكنك استخدام كودك الشخصي."),
                ephemeral=True
            )
            return

        reward = float(await db.get_setting("referral_reward") or "5")
        embed = aero_embed(
            "🔗  تأكيد الإحالة",
            f"{DIV}\n"
            f"**تذكير:** Aero عملة افتراضية داخل البوت حصراً.\n"
            f"{DIV}\n"
            f"🎁 **مكافأتك:** {format_aero(reward)}\n"
            f"🎁 **مكافأة صاحب الكود:** {format_aero(reward)}\n"
            f"{DIV}\n"
            f"اضغط **تأكيد** للمتابعة."
        )
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()

        if not view.confirmed:
            await interaction.edit_original_response(embed=warning_embed("تم الإلغاء", "لم يتم تفعيل الإحالة."), view=view)
            return

        await db.set_referred_by(interaction.user.id, referrer["id"])
        await db.update_balance(interaction.user.id, reward, add_xp=15)
        await db.update_balance(referrer["id"],     reward, add_xp=15)
        await db.add_transaction(None, interaction.user.id, reward, "referral", "مكافأة إحالة — مستخدم جديد")
        await db.add_transaction(None, referrer["id"],      reward, "referral", "مكافأة إحالة ناجحة")

        await interaction.edit_original_response(
            embed=success_embed(
                "تم تفعيل الإحالة! 🎉",
                f"{DIV}\n"
                f"🪙 حصلت على **{format_aero(reward)}** مكافأة ترحيب!\n"
                f"شكراً لانضمامك إلى مجتمع Aero.\n"
                f"{DIV}"
            ),
            view=view
        )
        try:
            ref_user = await interaction.client.fetch_user(referrer["id"])
            await send_dm(ref_user, success_embed(
                "إحالة ناجحة! 🔗",
                f"{DIV}\n"
                f"انضم **{interaction.user.display_name}** عبر كودك!\n"
                f"🪙 حصلت على **{format_aero(reward)}** مكافأة إحالة.\n"
                f"{DIV}"
            ))
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Economy(bot))
