import discord
from discord import app_commands
from discord.ext import commands

from once_human import database
from once_human.bot.checks import is_user
from once_human.bot.cogs.base import BaseCog
from once_human.bot.ui.view import UserView

from once_human.bot.utils import response


class SpecializationCog(BaseCog, name="specialization"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(description="Add/Modify your in-game specializations")
    @is_user()
    async def spec(self, interaction: discord.Interaction):
        await response(interaction).defer(ephemeral=True)
        async with database.AsyncSessionFactory() as session:
            view = await UserView.create(interaction, session, interaction.user)
            await view.refresh()
            await view.wait()


async def setup(bot: commands.Bot):
    await bot.add_cog(SpecializationCog(bot))
