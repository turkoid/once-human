import discord
from discord import app_commands
from once_human.config import config


def is_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == interaction.guild.owner_id

    if config.discord.admin_role:
        return app_commands.checks.has_role(config.discord.admin_role)
    else:
        return app_commands.check(predicate)


def is_user():
    def predicate(interaction: discord.Interaction) -> bool:
        return True

    if config.discord.user_role:
        return app_commands.checks.has_role(config.discord.user_role)
    else:
        return app_commands.check(predicate)
