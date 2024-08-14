import discord
from discord.ext import commands

class OnMessageCooldown(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            cooldown_embed = discord.Embed(
                description=f"This command is currently on cooldown. Please try again in **{int(error.retry_after):.2f} seconds**.",
                color=0xFF0000
            )
            try:
                await ctx.respond(embed=cooldown_embed, ephemeral=True)  # ephemeral makes it visible only to the user
            except discord.HTTPException as e:
                print(f"Error sending cooldown embed: {e}")
        else:
            raise error


def setup(bot):
    bot.add_cog(OnMessageCooldown(bot))
