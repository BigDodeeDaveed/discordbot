import discord
from discord.ext import commands
from discord.commands import slash_command
import wikipedia

class wikisearch(commands.Cog): 

    def __init__(self, bot): 
        self.bot = bot
        
    @slash_command(name='wikisearch', description="Searches wikipedia.")
    @commands.cooldown(1, 5, commands.BucketType.user) 
    async def wikisearch(self, ctx, query: str):
        print(f"Hold on! Searching...")
        try:
            page = wikipedia.page(query)
            snippet = page.summary[:1900] + "..." if len(page.summary) > 1900 else page.summary
            wikipedia_embed = discord.Embed(
                title=page.title,
                description=snippet,
            )

            wikipedia_embed.set_footer(text=page.url)  
            await ctx.respond(embed=wikipedia_embed)
        except wikipedia.exceptions.DisambiguationError as e:
            await ctx.respond(f"Multiple results found. Please be more specific with your query")
        except wikipedia.exceptions.PageError as e:
            await ctx.respond(f"No results found for '{query}'")
        except Exception as e:
            await ctx.respond(f"An error occurred while fetching the Wikipedia page: {e}")

def setup(bot): 
    bot.add_cog(wikisearch(bot))