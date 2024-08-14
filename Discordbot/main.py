import discord 
import os 
from dotenv import load_dotenv

load_dotenv() 
bot = discord.Bot(help_command=None)

intents = discord.Intents.all()
intents=intents


for fn in os.listdir("./Events"):
    if fn.endswith(".py"):
        bot.load_extension(f"Events.{fn[:-3]}")

for fn in os.listdir("./General"): 
    if fn.endswith(".py"):
        bot.load_extension(f"General.{fn[: -3]}")


bot.run(os.getenv('TOKEN')) 