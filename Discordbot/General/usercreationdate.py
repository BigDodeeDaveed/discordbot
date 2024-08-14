import discord
from discord.ext import commands
from discord.commands import slash_command

class userinfo(commands.Cog):     

    def __init__(self, bot): 
        self.bot = bot

    @slash_command(name="accountdate", description="Shows when your account was created.",)
    @commands.cooldown(1,5,commands.BucketType.user)
    async def usercreationdate(self, ctx, member: discord.Member):
        user_embed = discord.Embed(
            title="User Info",
            description=f"{member}'s account was created on  {member.created_at.strftime("%d/%m/%Y %H:%M:%S")}."
        )
        await ctx.respond(embed=user_embed)

def setup(bot): 
   bot.add_cog(userinfo(bot))

