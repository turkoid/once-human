import discord
from discord import app_commands
from discord.ext import commands
from once_human.bot.checks import is_admin


class OnceHumanCog(commands.Cog, name="base"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command()
    @is_admin()
    async def oh(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "admin commands", ephemeral=True, delete_after=5
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(OnceHumanCog(bot))
