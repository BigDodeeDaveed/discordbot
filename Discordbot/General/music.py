import discord
import os
from discord.ext import commands
from discord.commands import slash_command, Option
import yt_dlp as youtube_dl
import asyncio
from googleapiclient.discovery import build
from dotenv import load_dotenv
from collections import deque
import re

class MusicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.queues = {}
        self.inactivity_tasks = {}
        self.loop = {}
        self.current_song = {}
        
        load_dotenv()
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        if not youtube_api_key:
            raise ValueError("YOUTUBE_API_KEY not found in environment variables")
        
        self.youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        
        
        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'nocheckcertificate': True,
            'default_search': 'ytsearch',
            'extract_flat': False,
        }
        
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

    @slash_command(name="play", description="Plays music or videos from YouTube")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def play(self, ctx, query: str = Option(description="Song name or YouTube URL")):
        await ctx.defer()
        
        # Check if user is in voice channel
        if ctx.author.voice is None:
            await ctx.followup.send("❌ You need to be in a voice channel to use this command.")
            return

        # Connect to voice channel if not already connected
        if ctx.voice_client is None:
            try:
                vc = await ctx.author.voice.channel.connect()
                await ctx.followup.send(f"✅ Joined **{vc.channel.name}**")
            except Exception as e:
                await ctx.followup.send(f"❌ Failed to join voice channel: {str(e)}")
                return
        else:
            vc = ctx.voice_client

        # Initialize queue for this guild
        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = deque()
        
        self.players[ctx.guild.id] = vc

        youtube_url_pattern = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )

        try:
            # Determine if query is URL or search term
            if youtube_url_pattern.match(query):
                video_url = query
            else:
                # Search YouTube
                request = self.youtube.search().list(
                    q=query,
                    part='snippet',
                    type='video',
                    maxResults=1
                )
                response = request.execute()
                
                if not response.get('items'):
                    await ctx.followup.send("❌ No results found on YouTube.")
                    return
                
                video_id = response['items'][0]['id']['videoId']
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            # Extract video info
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                lambda: youtube_dl.YoutubeDL(self.YDL_OPTIONS).extract_info(video_url, download=False)
            )
            
            if not info:
                await ctx.followup.send("❌ Could not extract video information.")
                return
            
            # Handle playlist results
            if 'entries' in info:
                info = info['entries'][0]
            
            # Get audio URL with multiple fallback methods
            audio_url = None
            
            
            if 'url' in info:
                audio_url = info['url']
            
            
            elif 'formats' in info and info['formats']:
                formats = info['formats']
                
               
                audio_formats = [f for f in formats 
                               if f.get('acodec') != 'none' 
                               and f.get('vcodec') == 'none'
                               and f.get('url')]
                
                if audio_formats:
                    # Pick best audio quality
                    audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)
                    audio_url = audio_formats[0]['url']
                else:
                    # Fallback: any format with audio
                    formats_with_audio = [f for f in formats 
                                        if f.get('acodec') != 'none' 
                                        and f.get('url')]
                    
                    if formats_with_audio:
                        audio_url = formats_with_audio[0]['url']
            
            
            if not audio_url and 'requested_formats' in info:
                for fmt in info['requested_formats']:
                    if fmt.get('url'):
                        audio_url = fmt['url']
                        break
            
            if not audio_url:
                await ctx.followup.send(
                    "❌ Could not extract audio URL. The video may not have audio or is unavailable.\n"
                    "**Tip:** Try updating yt-dlp: `pip install --upgrade yt-dlp`"
                )
                return
            
            song_info = {
                'url': audio_url,
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0),
                'requester': ctx.author.name,
                'webpage_url': info.get('webpage_url', video_url)
            }
            
            self.queues[ctx.guild.id].append(song_info)
            
            # Start playing if nothing is currently playing
            if not vc.is_playing() and not vc.is_paused():
                await self.play_next(ctx)
            else:
                duration_str = self._format_duration(song_info['duration'])
                await ctx.followup.send(
                    f"➕ Added to queue: **{song_info['title']}** `[{duration_str}]`\n"
                    f"Position: #{len(self.queues[ctx.guild.id])}"
                )

        except youtube_dl.utils.DownloadError as e:
            error_msg = str(e).lower()
            
            if 'requested format is not available' in error_msg:
                await ctx.followup.send(
                    "❌ The requested format is not available for this video.\n"
                    "**Solution:** Run `pip install --upgrade yt-dlp` and restart the bot."
                )
            elif 'sign in' in error_msg or 'login' in error_msg:
                await ctx.followup.send("❌ This video requires authentication. Try a different video.")
            elif 'not available' in error_msg or 'private' in error_msg:
                await ctx.followup.send("❌ This video is not available (may be region-locked or private).")
            else:
                await ctx.followup.send(f"❌ Could not download video: {str(e)}")
            
            print(f"DownloadError: {e}")
            
        except KeyError as e:
            await ctx.followup.send(f"❌ Missing video data: {str(e)}. The video format may not be supported.")
            print(f"KeyError in play command: {str(e)}")
            
        except Exception as e:
            await ctx.followup.send(f"❌ An unexpected error occurred. Please try again or use a different video.")
            print(f"Play command error: {type(e).__name__}: {str(e)}")

    @slash_command(name="join", description="Joins your voice channel")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def join(self, ctx):
        await ctx.defer()

        if ctx.author.voice is None:
            await ctx.followup.send("❌ You need to be in a voice channel to use this command.")
            return
        
        voice_channel = ctx.author.voice.channel
        
        if ctx.voice_client is None:
            try:
                vc = await voice_channel.connect()
                await ctx.followup.send(f"✅ Joined **{voice_channel.name}**")
                self.players[ctx.guild.id] = vc
                await self.start_inactivity_check(ctx.guild.id)
            except Exception as e:
                await ctx.followup.send(f"❌ Failed to join: {str(e)}")
        else:
            await ctx.followup.send(f"ℹ️ Already connected to **{ctx.voice_client.channel.name}**")

    @slash_command(name="leave", description="Leaves the voice channel")
    async def leave(self, ctx):
        if ctx.voice_client is None:
            await ctx.respond("❌ I'm not in a voice channel!")
            return
        
        guild_id = ctx.guild.id
        
        # Clear queue and stop playback
        if guild_id in self.queues:
            self.queues[guild_id].clear()
        if guild_id in self.loop:
            self.loop[guild_id] = False
        if guild_id in self.current_song:
            del self.current_song[guild_id]
        
        await ctx.voice_client.disconnect()
        await self.stop_inactivity_check(guild_id)
        
        if guild_id in self.players:
            del self.players[guild_id]
        
        await ctx.respond("👋 Left the voice channel")

    @slash_command(name="loop", description="Toggles looping of the current song")
    async def loop(self, ctx):
        guild_id = ctx.guild.id

        if guild_id not in self.loop:
            self.loop[guild_id] = False

        self.loop[guild_id] = not self.loop[guild_id]

        if self.loop[guild_id]:
            await ctx.respond("🔁 Looping enabled")
        else:
            await ctx.respond("🔁 Looping disabled")

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        vc = ctx.voice_client

       
        if not vc or not vc.is_connected():
            self.current_song.pop(guild_id, None)
            return
        
        if not self.queues.get(guild_id):
            self.current_song.pop(guild_id, None)
            await self.start_inactivity_check(guild_id)
            return

        song_info = self.queues[guild_id].popleft()
        self.current_song[guild_id] = song_info

        try:
            audio_source = discord.FFmpegPCMAudio(song_info['url'], **self.FFMPEG_OPTIONS)
            
            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                
                # Schedule the next song
                future = asyncio.run_coroutine_threadsafe(
                    self.after_song(ctx), 
                    self.bot.loop
                )
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in after_playing: {e}")
            
            vc.play(audio_source, after=after_playing)
            
            duration_str = self._format_duration(song_info['duration'])
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{song_info['title']}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Duration", value=duration_str, inline=True)
            embed.add_field(name="Requested by", value=song_info['requester'], inline=True)
            embed.add_field(name="Loop", value="🔁 Enabled" if self.loop.get(guild_id, False) else "➡️ Disabled", inline=True)
            
            await ctx.followup.send(embed=embed)
            
            await self.start_inactivity_check(guild_id)
            
        except Exception as e:
            print(f"Error playing song: {str(e)}")
            self.current_song.pop(guild_id, None)
            
            await ctx.followup.send(f"❌ Failed to play: {song_info['title']}")
            
            # Try to play next song
            if self.queues.get(guild_id):
                await self.play_next(ctx)

    async def play_song(self, ctx, song_info):
        """Helper function for looping songs"""
        vc = ctx.voice_client
        guild_id = ctx.guild.id

        if not vc or not vc.is_connected():
            return

        try:
            audio_source = discord.FFmpegPCMAudio(song_info['url'], **self.FFMPEG_OPTIONS)
            
            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                future = asyncio.run_coroutine_threadsafe(
                    self.after_song(ctx), 
                    self.bot.loop
                )
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in after_playing (loop): {e}")
            
            vc.play(audio_source, after=after_playing)
            
        except Exception as e:
            print(f"Error in play_song: {str(e)}")
            await ctx.followup.send(f"❌ Error looping song: {str(e)}")

    async def after_song(self, ctx):
        """Called after a song finishes playing"""
        vc = ctx.voice_client
        guild_id = ctx.guild.id

        # Check if looping is enabled
        if vc and guild_id in self.loop and self.loop[guild_id] and guild_id in self.current_song:
            await self.play_song(ctx, self.current_song[guild_id])
        # Check if there are more songs in queue
        elif vc and self.queues.get(guild_id):
            await self.play_next(ctx)
        # Start inactivity timer if queue is empty
        elif vc and not self.queues.get(guild_id):
            await self.start_inactivity_check(guild_id)

    @slash_command(name="pause", description="Pauses the current song")
    async def pause(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("❌ You need to be in a voice channel to use this command.")
            return

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.respond("❌ Nothing is playing!")
            return

        ctx.voice_client.pause()
        await ctx.respond("⏸️ Paused")

    @slash_command(name="resume", description="Resumes the paused song")
    async def resume(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("❌ You need to be in a voice channel to use this command.")
            return

        if not ctx.voice_client or not ctx.voice_client.is_paused():
            await ctx.respond("❌ Nothing is paused!")
            return

        ctx.voice_client.resume()
        await ctx.respond("▶️ Resumed")
    
    @slash_command(name="skip", description="Skips to the next song in queue")
    async def skipsong(self, ctx):
        if ctx.author.voice is None:
            await ctx.respond("❌ You need to be in a voice channel to use this command.")
            return
        
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.respond("❌ Nothing is playing right now.")
            return
        
        # Disable loop for this skip
        guild_id = ctx.guild.id
        was_looping = self.loop.get(guild_id, False)
        if was_looping:
            self.loop[guild_id] = False
        
        ctx.voice_client.stop()
        await ctx.respond("⏭️ Skipped to next song")
        
        # Re-enable loop if it was on
        if was_looping:
            self.loop[guild_id] = True

    @slash_command(name="stop", description="Stops the music and clears the queue")
    async def stop(self, ctx):
        guild_id = ctx.guild.id
        
        if ctx.author.voice is None:
            await ctx.respond("❌ You need to be in a voice channel to use this command.")
            return

        if not ctx.voice_client:
            await ctx.respond("❌ I'm not in a voice channel!")
            return
        
        # Clear everything
        if guild_id in self.queues:
            self.queues[guild_id].clear()
        if guild_id in self.loop:
            self.loop[guild_id] = False
        if guild_id in self.current_song:
            del self.current_song[guild_id]
        
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
        
        await ctx.respond("⏹️ Stopped playing and cleared the queue")

    @slash_command(name="queue", description="Shows the current music queue")
    async def show_queue(self, ctx):
        guild_id = ctx.guild.id

        # Check if there's a current song or queue
        has_current = guild_id in self.current_song
        has_queue = guild_id in self.queues and self.queues[guild_id]
        
        if not has_current and not has_queue:
            await ctx.respond("📭 The queue is empty")
            return
        
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue()
        )
        
        # Show currently playing song
        if has_current:
            current = self.current_song[guild_id]
            duration_str = self._format_duration(current['duration'])
            loop_status = " 🔁" if self.loop.get(guild_id, False) else ""
            embed.add_field(
                name="Now Playing",
                value=f"**{current['title']}** `[{duration_str}]`{loop_status}\nRequested by: {current['requester']}",
                inline=False
            )
        
        # Show queue
        if has_queue:
            queue_list = list(self.queues[guild_id])
            queue_text = ""
            
            for i, song in enumerate(queue_list[:10]):  # Show first 10 songs
                duration_str = self._format_duration(song['duration'])
                queue_text += f"`{i + 1}.` **{song['title']}** `[{duration_str}]`\n"
            
            if len(queue_list) > 10:
                queue_text += f"\n*...and {len(queue_list) - 10} more*"
            
            embed.add_field(
                name=f"Up Next ({len(queue_list)} songs)",
                value=queue_text,
                inline=False
            )
        
        await ctx.respond(embed=embed)

    @slash_command(name="nowplaying", description="Shows the currently playing song")
    async def nowplaying(self, ctx):
        guild_id = ctx.guild.id
        
        if guild_id not in self.current_song:
            await ctx.respond("❌ Nothing is currently playing")
            return
        
        song = self.current_song[guild_id]
        duration_str = self._format_duration(song['duration'])
        
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{song['title']}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Duration", value=duration_str, inline=True)
        embed.add_field(name="Requested by", value=song['requester'], inline=True)
        embed.add_field(name="Loop", value="🔁 Enabled" if self.loop.get(guild_id, False) else "➡️ Disabled", inline=True)
        embed.add_field(name="URL", value=f"[Click here]({song['webpage_url']})", inline=False)
        
        await ctx.respond(embed=embed)

    @slash_command(name="clear", description="Clears the entire queue")
    async def clear(self, ctx):
        guild_id = ctx.guild.id
        
        if guild_id not in self.queues or not self.queues[guild_id]:
            await ctx.respond("❌ The queue is already empty")
            return
        
        queue_length = len(self.queues[guild_id])
        self.queues[guild_id].clear()
        
        await ctx.respond(f"🗑️ Cleared {queue_length} song(s) from the queue")

    def _format_duration(self, seconds):
        """Format duration in seconds to MM:SS or HH:MM:SS"""
        if not seconds:
            return "Unknown"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    async def check_inactivity(self, guild_id, timeout=300):
        """Disconnect bot after 5 minutes of inactivity"""
        try:
            await asyncio.sleep(timeout)

            player = self.players.get(guild_id)
            if player and player.is_connected() and not player.is_playing() and not player.is_paused():
                await player.disconnect()
                
                if guild_id in self.players:
                    del self.players[guild_id]
                if guild_id in self.queues:
                    self.queues[guild_id].clear()
                if guild_id in self.current_song:
                    del self.current_song[guild_id]
                
                guild = self.bot.get_guild(guild_id)
                if guild and guild.system_channel:
                    await guild.system_channel.send("👋 Disconnected due to 5 minutes of inactivity")
                
                await self.stop_inactivity_check(guild_id)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in inactivity check for guild {guild_id}: {e}")

    async def start_inactivity_check(self, guild_id):
        """Start or restart the inactivity timer"""
        # Cancel existing task
        if guild_id in self.inactivity_tasks:
            self.inactivity_tasks[guild_id].cancel()
            try:
                await self.inactivity_tasks[guild_id]
            except asyncio.CancelledError:
                pass

        # Create new task
        self.inactivity_tasks[guild_id] = asyncio.create_task(
            self.check_inactivity(guild_id)
        )

    async def stop_inactivity_check(self, guild_id):
        """Stop the inactivity timer"""
        if guild_id in self.inactivity_tasks:
            self.inactivity_tasks[guild_id].cancel()
            try:
                await self.inactivity_tasks[guild_id]
            except asyncio.CancelledError:
                pass
            del self.inactivity_tasks[guild_id]

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        for task in self.inactivity_tasks.values():
            task.cancel()

def setup(bot):
    bot.add_cog(MusicPlayer(bot))
