import discord
from discord import app_commands

from once_human.config import config


def is_admin():
    def is_guild_owner(interaction: discord.Interaction) -> bool:
        return interaction.user.id == interaction.guild.owner_id

    if config.discord.admin_role:
        return app_commands.checks.has_role(config.discord.admin_role)
    else:
        return app_commands.check(is_guild_owner)


def is_user():
    def always_true(interaction: discord.Interaction) -> bool:
        return True

    if config.discord.user_role:
        return app_commands.checks.has_role(config.discord.user_role)
    else:
        return app_commands.check(always_true)
