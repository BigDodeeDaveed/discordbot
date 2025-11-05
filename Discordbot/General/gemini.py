import os
from discord.ext import commands
from discord.commands import slash_command, Option
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')


if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

class GeminiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    @slash_command(name="askbot", description="Ask the bot any question")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def askbot(
        self, 
        ctx, 
        question: str = Option(description="Your question for the bot")
    ):
       
        if len(question) > 500:
            await ctx.respond("Your question is too long. Please keep it under 500 characters.")
            return
        
        await ctx.defer()
        
        try:
            response = self.model.generate_content(question)
            
           
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                await ctx.respond("Your question was blocked due to safety filters.")
                return
            
          
            if not response or not hasattr(response, 'text'):
                await ctx.respond("Sorry, I couldn't generate a response.")
                return
            
            response_text = response.text
            
        
            if not response_text.strip():
                await ctx.respond("The response was empty. Try rephrasing your question.")
                return
            
            
            chunks = [response_text[i:i + 1900] for i in range(0, len(response_text), 1900)]
            
           
            await ctx.respond(chunks[0])
            
          
            for chunk in chunks[1:]:
                await ctx.followup.send(chunk)
                
        except Exception as e:
           
            print(f"Error in askbot command: {type(e).__name__}: {e}")
            await ctx.respond("An error occurred while processing your request. Please try again later.")
    
    @askbot.error
    async def askbot_error(self, ctx, error):
        """Handle command-specific errors"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(
                f"⏰ Please wait {error.retry_after:.1f} seconds before using this command again.",
                ephemeral=True
            )
        else:
           
            raise error

def setup(bot):
    bot.add_cog(GeminiCog(bot))
