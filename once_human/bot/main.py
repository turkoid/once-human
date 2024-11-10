import discord
from discord import app_commands, Interaction
from discord.ext import commands

from once_human.bot.utils import response
from once_human.config import config


class OnceHumanBotTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction: Interaction[discord.Client],
        error: app_commands.AppCommandError | Exception,
    ) -> None:
        await response(interaction).send_message(error)


class OnceHumanBot(commands.Bot):
    def __init__(self, ask: bool = False) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="", intents=intents)
        self.guild_id = discord.Object(id=config.discord.guild)
        self.ask = ask

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def setup_hook(self) -> None:
        for ext in ["admin", "specialization"]:
            await self.load_extension(f"cogs.{ext}")

        self.tree.copy_global_to(guild=self.guild_id)
        if self.ask and input("sync?") == "y":
            await self.tree.sync(guild=self.guild_id)
            print("synced")


if __name__ == "__main__":
    bot = OnceHumanBot()
    bot.run(config.discord.token)
