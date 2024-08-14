import discord
from discord.ext import commands
from discord.commands import slash_command

class latencychecker(commands.Cog):
    def __init__ (self,bot):
        self.bot = bot

    @slash_command(name="ping", description="Checks the bot's latency")
    @commands.cooldown(1,5, commands.BucketType.user)
    async def latency(self, ctx):
        latency_ms = round(self.bot.latency * 1000)  
        await ctx.respond(f"Latency is: {latency_ms}ms")


def setup(bot):
    bot.add_cog(latencychecker(bot)) 
