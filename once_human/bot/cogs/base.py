import traceback

import discord
from discord import app_commands
from discord.ext import commands

from once_human.bot.utils import response


class BaseCog(commands.Cog):
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        print(tb)
        await response(interaction).send_message(error)
