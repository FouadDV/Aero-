import discord
from discord import app_commands
from discord.ext import commands
from helpers import aero_embed, success_embed, error_embed, info_embed, format_aero, AERO_EMOJI
import database as db


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="عرض جميع أوامر AeroBot")
    async def help_command(self, interaction: discord.Interaction):
        embed = aero_embed("📖 دليل AeroBot", "البوت العربي الاحترافي لإدارة عملة Aero الافتراضية")
        embed.add_field(
            name="💰 أوامر الرصيد",
            value=(
                "`/balance` — عرض رصيدك\n"
                "`/profile` — ملفك الشخصي\n"
                "`/transactions` — سجل معاملاتك"
            ),
            inline=False
        )
        embed.add_field(
            name="🎁 طرق كسب Aero",
            value=(
                "`/daily` — مكافأة يومية\n"
                "`/weekly` — مكافأة أسبوعية\n"
                "`/referral` — استخدام كود إحالة"
            ),
            inline=False
        )
        embed.add_field(
            name="💸 العمليات المالية",
            value=(
                "`/pay @user amount` — إرسال Aero\n"
                "`/gift @user amount` — إرسال هدية بدون ضريبة\n"
                "`/trade @user give receive` — مقايضة"
            ),
            inline=False
        )
        embed.add_field(
            name="📋 قوانين AeroBot",
            value=(
                "• Aero عملة افتراضية داخل Discord فقط\n"
                "• لا يمكن تحويلها مقابل أموال حقيقية\n"
                "• جميع العمليات مسجلة\n"
                "• أي تعامل بين الأعضاء على مسؤوليتهم الشخصية"
            ),
            inline=False
        )
        embed.set_footer(text="AeroBot • 1 Aero = 0.018 (مقياس داخلي فقط)")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="عرض أعلى الأرصدة في السيرفر")
    async def leaderboard(self, interaction: discord.Interaction):
        if await db.is_blacklisted(interaction.user.id):
            await interaction.response.send_message(embed=error_embed("محظور", "أنت في اللائحة السوداء."), ephemeral=True)
            return

        leaders = await db.get_leaderboard(10)
        if not leaders:
            await interaction.response.send_message(embed=info_embed("المتصدرون", "لا يوجد مستخدمون بعد."))
            return

        embed = aero_embed("🏆 قائمة المتصدرين")
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, u in enumerate(leaders):
            medal = medals[i] if i < 3 else f"**#{i+1}**"
            bal = float(u["balance"])
            lines.append(f"{medal} <@{u['id']}> — {format_aero(bal)} | مستوى {u['level']}")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="معلومات عن عملة Aero والقيمة المرجعية")
    async def info(self, interaction: discord.Interaction):
        aero_value = await db.get_setting("aero_value") or "0.018"
        daily = await db.get_setting("daily_reward") or "5"
        weekly = await db.get_setting("weekly_reward") or "10"
        referral = await db.get_setting("referral_reward") or "5"
        tax = await db.get_setting("tax_rate") or "0"

        embed = aero_embed("ℹ️ معلومات عملة Aero")
        embed.add_field(name="💹 القيمة المرجعية", value=f"1 Aero = **{aero_value}** (مقياس داخلي)", inline=False)
        embed.add_field(name="📅 المكافأة اليومية", value=f"**{daily} Aero**", inline=True)
        embed.add_field(name="📆 المكافأة الأسبوعية", value=f"**{weekly} Aero**", inline=True)
        embed.add_field(name="🔗 مكافأة الإحالة", value=f"**{referral} Aero**", inline=True)
        embed.add_field(name="💸 الضريبة على التحويل", value=f"**{tax}%**", inline=True)
        embed.add_field(
            name="📜 القوانين الرسمية",
            value=(
                "• Aero عملة افتراضية داخل Discord فقط\n"
                "• لا يُسمح باستخدامها خارج البوت أو تحويلها لأموال حقيقية\n"
                "• البوت غير مسؤول عن أي خسارة أو نزاع\n"
                "• جميع العمليات مسجلة ومراقبة\n"
                "• يجب الموافقة قبل كل عملية مالية"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="فحص سرعة استجابة البوت")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = aero_embed("🏓 Pong!", f"سرعة الاستجابة: **{latency}ms**")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
