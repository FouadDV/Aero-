import discord
from discord import app_commands
from discord.ext import commands
from helpers import (
    aero_embed, success_embed, error_embed, info_embed,
    format_aero, AERO_EMOJI, DIV, rank_badge, wealth_tier
)
import database as db


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="دليل أوامر AeroBot الكامل")
    async def help_command(self, interaction: discord.Interaction):
        embed = aero_embed(
            "📖  دليل AeroBot",
            f"مرحباً بك في **AeroBot** — منصة عملة Aero الافتراضية داخل Discord.\n{DIV}"
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(
            name="💼  الرصيد والملف الشخصي",
            value=(
                "`/balance` — عرض محفظتك أو محفظة أي عضو\n"
                "`/profile` — ملفك الشخصي مع المستوى والـ XP\n"
                "`/transactions` — سجل معاملاتك مع تصفح\n"
                "`/leaderboard` — قائمة أثرى الأعضاء"
            ),
            inline=False
        )
        embed.add_field(
            name="🎁  طرق كسب Aero",
            value=(
                "`/daily` — مكافأة يومية 🌅\n"
                "`/weekly` — مكافأة أسبوعية 📆\n"
                "`/referral <كود>` — استخدام كود إحالة صديق 🔗"
            ),
            inline=False
        )
        embed.add_field(
            name="💸  العمليات المالية",
            value=(
                "`/pay @عضو كمية` — تحويل Aero مع ضريبة\n"
                "`/gift @عضو كمية` — هدية بدون ضريبة 🎁\n"
                "`/trade @عضو give receive` — مقايضة مباشرة 🔄"
            ),
            inline=False
        )
        embed.add_field(
            name="ℹ️  معلومات عامة",
            value=(
                "`/info` — معلومات عن عملة Aero\n"
                "`/ping` — سرعة استجابة البوت"
            ),
            inline=False
        )
        embed.add_field(
            name=f"{DIV}\n📜  القوانين الأساسية",
            value=(
                "• Aero عملة **افتراضية** داخل Discord حصراً\n"
                "• لا يُسمح بتحويلها لأموال حقيقية أو استخدامها خارج البوت\n"
                "• جميع العمليات مسجلة ومراقبة\n"
                "• البوت غير مسؤول عن أي نزاع بين الأعضاء\n"
                "• كل عملية مالية تستلزم تأكيداً صريحاً منك"
            ),
            inline=False
        )
        embed.set_footer(text=f"✦ AeroBot  •  1 Aero = 0.018 (مقياس داخلي) ✦")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="قائمة أثرى الأعضاء في السيرفر")
    async def leaderboard(self, interaction: discord.Interaction):
        if await db.is_blacklisted(interaction.user.id):
            await interaction.response.send_message(embed=error_embed("الوصول محظور", "أنت في اللائحة السوداء."), ephemeral=True)
            return

        leaders = await db.get_leaderboard(10)
        if not leaders:
            await interaction.response.send_message(
                embed=info_embed("قائمة المتصدرين", f"{DIV}\nلا يوجد أعضاء بعد.\nكن أول المتصدرين عبر `/daily`! 🚀")
            )
            return

        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, u in enumerate(leaders):
            bal   = float(u["balance"])
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            badge = rank_badge(u["level"])
            lines.append(
                f"{medal}  <@{u['id']}>\n"
                f"    └ {format_aero(bal)}  •  مستوى {u['level']} {badge}"
            )

        embed = aero_embed(
            "🏆  قائمة المتصدرين",
            f"{DIV}\n" + "\n".join(lines) + f"\n{DIV}"
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="معلومات عن عملة Aero")
    async def info(self, interaction: discord.Interaction):
        val      = await db.get_setting("aero_value")   or "0.018"
        daily    = await db.get_setting("daily_reward")  or "5"
        weekly   = await db.get_setting("weekly_reward") or "10"
        referral = await db.get_setting("referral_reward") or "5"
        tax      = await db.get_setting("tax_rate")      or "0"

        embed = aero_embed(
            "💹  معلومات عملة Aero",
            f"{DIV}\n"
            f"**القيمة المرجعية**\n"
            f"## 1 {AERO_EMOJI} = {val}\n"
            f"> *(للمقياس الداخلي فقط — لا تعكس قيمة حقيقية)*\n"
            f"{DIV}"
        )
        embed.add_field(name="🌅 مكافأة يومية",    value=f"**{daily} Aero**", inline=True)
        embed.add_field(name="📆 مكافأة أسبوعية",  value=f"**{weekly} Aero**", inline=True)
        embed.add_field(name="🔗 مكافأة الإحالة",  value=f"**{referral} Aero**", inline=True)
        embed.add_field(name="💸 ضريبة التحويل",   value=f"**{tax}%**", inline=True)
        embed.add_field(
            name=f"{DIV}\n📜  القوانين الرسمية",
            value=(
                "• Aero عملة **افتراضية** داخل Discord حصراً\n"
                "• لا يُسمح بتحويلها لأموال حقيقية أو خارج البوت\n"
                "• البوت غير مسؤول عن أي خسارة أو نزاع\n"
                "• جميع العمليات مسجلة وشفافة\n"
                "• التأكيد إلزامي قبل كل عملية مالية"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="فحص سرعة استجابة البوت")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        if latency < 80:
            status = "ممتازة 🟢"
        elif latency < 150:
            status = "جيدة 🟡"
        else:
            status = "بطيئة 🔴"
        embed = aero_embed(
            "🏓  Pong!",
            f"{DIV}\n"
            f"⚡ **زمن الاستجابة:** `{latency} ms`\n"
            f"📶 **الحالة:** {status}\n"
            f"{DIV}"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
