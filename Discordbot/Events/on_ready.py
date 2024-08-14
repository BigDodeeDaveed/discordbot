import discord
from discord.ext import commands
from main import bot


class on_ready(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_ready(self):
        await bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name='Server members.'))
        print(f'Logged in as: {self.bot.user.name}')



def setup(bot):
    bot.add_cog(on_ready(bot))