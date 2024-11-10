import discord
from discord import app_commands
from discord.ext import commands
from once_human.bot.checks import is_admin
from once_human.bot.cogs.base import BaseCog
from once_human.bot.utils import response


class AdminCog(BaseCog, name="admin"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command()
    @is_admin()
    async def oh(self, interaction: discord.Interaction):
        await response(interaction).send_message("admin commands", ephemeral=True, delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
