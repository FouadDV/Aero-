import discord
from discord.ext import commands
import os
import asyncio
from helpers import aero_embed, success_embed, error_embed, BOT_COLOR
import database as db


intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class AeroBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        await db.init_db()
        cogs = ["cogs.economy", "cogs.admin", "cogs.general"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ تم تحميل: {cog}")
            except Exception as e:
                print(f"❌ فشل تحميل {cog}: {e}")

        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"✅ تم مزامنة الأوامر للسيرفر: {guild_id}")
        else:
            await self.tree.sync()
            print("✅ تم مزامنة الأوامر عالمياً")

    async def on_ready(self):
        print(f"\n{'=' * 50}")
        print(f"🤖 AeroBot يعمل الآن!")
        print(f"📛 الاسم: {self.user.name}#{self.user.discriminator}")
        print(f"🆔 المعرّف: {self.user.id}")
        print(f"🌐 عدد السيرفرات: {len(self.guilds)}")
        print(f"{'=' * 50}\n")
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="عملة Aero 🪙"
        )
        await self.change_presence(activity=activity, status=discord.Status.online)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.CheckFailure):
            return
        embed = error_embed("خطأ غير متوقع", "حدث خطأ أثناء تنفيذ الأمر. الرجاء المحاولة مرة أخرى.")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            pass
        print(f"خطأ في أمر /{interaction.command.name if interaction.command else '?'}: {error}")

    async def on_member_join(self, member: discord.Member):
        await db.ensure_user(member.id)


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ خطأ: لم يتم تعيين DISCORD_TOKEN")
        return

    bot = AeroBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
