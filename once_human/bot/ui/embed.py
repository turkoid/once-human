import discord


class TimedEmbed:
    def __init__(self, embed: discord.Embed, duration: float):
        self.embed = embed
        self.duration = duration


class Error(discord.Embed):
    def __init__(self, error_message: str) -> None:
        super().__init__(title="ERROR", description=error_message, color=discord.Color.from_rgb(255, 0, 0))
