import os
from discord.ext import commands
from discord.commands import slash_command
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

class geminiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="askbot", description="Asks the bot any question")
    async def askbot(self, ctx, * ,question):
        if not question:
            await ctx.respond("Please provide a query")
            return

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(question)
            if response and hasattr(response, 'text'):
                response_text = response.text
                for chunk in [response_text[i:i + 1900] for i in range(0, len(response_text), 1900)]:
                    await ctx.defer()
                    await ctx.respond(chunk)
        except Exception as e:
            await ctx.respond(f"an error occured whilst processing your request: {e}")

def setup(bot):
    bot.add_cog(geminiCog(bot))