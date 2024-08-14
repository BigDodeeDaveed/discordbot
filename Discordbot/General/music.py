import discord
import os
from discord.ext import commands
from discord.commands import slash_command
import yt_dlp as youtube_dl
import asyncio
from googleapiclient.discovery import build
from dotenv import load_dotenv
from collections import deque

load_dotenv()

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

class MusicPlayer(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.players = {}  # To keep track of voice clients per guild
        self.queues = {}  # To manage song queues for each guild

    @slash_command(name="play", description="Plays music or videos from Youtube.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def play(self, ctx, *, query):
        
        await ctx.defer()  
        if ctx.author.voice is None:
            await ctx.respond("You need to be in a Voice Channel to use this command.")
            return

        vc = ctx.voice_client

        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = deque()
        
        YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': 'True',
            'quiet': True,
            'extract_flat': 'in_playlist',
            'no_warnings': True,
            'source_address': '0.0.0.0',
            'cachedir': False,
            'skip_download': True,
        }

        try:
            request = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                maxResults=1
            )
            response = request.execute()
            video_id = response['items'][0]['id']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(video_url, download=False)
                url2 = info['url']
                song_info = {
                    'url': url2,
                    'title': info['title'],
                    'requester': ctx.author.name
                }
                
                self.queues[ctx.guild.id].append(song_info)
            await ctx.respond(f"Added to queue: {song_info['title']}")

            if not vc or not vc.is_playing():
                await self.play_next(ctx)

        except Exception as e:
            await ctx.respond(f"An error occurred: {str(e)}")
            print(f"An error occurred: {str(e)}")

    @slash_command(name="join", description="Joins VC")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def join(self, ctx):

        if ctx.author.voice is None:
            await ctx.respond("You need to be in a Voice Channel to use this command.")
            return
        
        voice_channel = ctx.author.voice.channel
        
        if ctx.voice_client is None:
            vc = await voice_channel.connect()
            await ctx.respond(f"Joined {voice_channel}.")
        else:
            vc = ctx.voice_client
            await ctx.respond(f"Already connected to {vc.channel}.")
        
        self.players[ctx.guild.id] = vc
        asyncio.create_task(self.check_inactivity(ctx.guild.id))

    async def play_next(self, ctx):
        vc = ctx.voice_client
        if not vc or not self.queues[ctx.guild.id]:
            return

        song_info = self.queues[ctx.guild.id].popleft()

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        try:
            vc.play(discord.FFmpegPCMAudio(song_info['url'], **FFMPEG_OPTIONS),
                    after=lambda e: asyncio.run_coroutine_threadsafe(self.after_song(ctx), self.bot.loop).result())

            await ctx.send(f"Now playing: {song_info['title']} requested by {song_info['requester']}")
            asyncio.create_task(self.check_inactivity(ctx.guild.id))  # Restart inactivity check when a new song plays
        except Exception as e:
            await ctx.send(f"An error occurred while playing the next song: {str(e)}")
            print(f"An error occurred while playing the next song: {str(e)}")

    async def after_song(self, ctx):
        vc = ctx.voice_client

        if not vc or not self.queues[ctx.guild.id]:  # If the queue is empty
            await asyncio.sleep(60)  # Wait 1 minute before disconnecting
            if not vc.is_playing() and not self.queues[ctx.guild.id]:  # Ensure nothing else is queued or playing
                await vc.disconnect()
                await ctx.send("Disconnected due to inactivity.")

    @slash_command(name="pause", description="Pauses the bot.")
    async def pause(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("You need to be in a Voice Channel to use this command.")
            return

        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.respond("Paused ⏸️")
        else:
            await ctx.respond("Nothing is playing!")

    @slash_command(name="resume", description="Resumes the bot.")
    async def resume(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("You need to be in a Voice Channel to use this command.")
            return

        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.respond("Resumed ⏯️")
        else:
            await ctx.respond("Nothing is playing!")
    
    @slash_command(name="skip", description="Skips to the next song in queue.")
    async def skipsong(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("You need to be in a Voice Channel to use this command.")
            return

        ctx.voice_client.stop()
        await ctx.respond("Skipped to next song in queue.")

    @slash_command(name="stop", description="Stops the music.")
    async def stop(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("You need to be in a Voice Channel to use this command.")
            return
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            self.queues[ctx.guild.id].clear()
            await ctx.respond("Stopped playing music.")
        else:
            await ctx.respond("Nothing is playing!")

    async def check_inactivity(self, guild_id, timeout=60):  # 1 minute timeout by default
        await asyncio.sleep(timeout)  # Wait for the specified timeout period

        player = self.players.get(guild_id)  # Get the voice client associated with the guild
        if not player:
            return  # If no player is found, exit the function

        try:
            if player.is_connected() and not player.is_playing() and not player.is_paused():
                await player.disconnect()  # Disconnect the bot if it's not playing or paused
                del self.players[guild_id]  # Remove the player from the tracking dictionary
                guild = self.bot.get_guild(guild_id)
                if guild and guild.system_channel:
                    await guild.system_channel.send("Disconnected due to inactivity.")
        except Exception as e:
            print(f"Error in inactivity check for guild {guild_id}: {e}")

def setup(bot):
    bot.add_cog(MusicPlayer(bot))
