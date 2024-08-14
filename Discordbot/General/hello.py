import os 
import discord
from discord.ext import commands
from discord.commands import slash_command

class helloCog(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

    @slash_command(name="hello", description="Says hello.")
    @commands.cooldown(1,5,commands.BucketType.user)
    async def hello(self, ctx: discord.ApplicationContext):
        await ctx.respond(f"Hello {ctx.author.mention}!")



def setup(bot):
    bot.add_cog(helloCog(bot)) 

