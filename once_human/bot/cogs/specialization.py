import discord
from discord import app_commands
from discord.ext import commands

from once_human.bot.checks import is_user


class SpecializationCog(commands.Cog, name="specialization"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(description="Add/Modify your in-game specializations")
    @is_user()
    async def spec(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "change specs", ephemeral=True, delete_after=3
        )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await interaction.response.send_message(error)


async def setup(bot: commands.Bot):
    await bot.add_cog(SpecializationCog(bot))
