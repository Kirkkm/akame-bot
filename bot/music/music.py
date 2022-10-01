import discord
from discord.ext import commands

import asyncio

import validators

from math import ceil

import youtube_dl
from .aux_youtube import *

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

play = asyncio.Lock()
lock = asyncio.Lock()

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
                        
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
            
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot, token):
        self.bot = bot
        self.fetch = FetchYoutube(token)
        self.queue = []

        self.loop = False
        self.player = None
        self.playing = 0
    
    @commands.command(pass_context=True, aliases=['Skip'])
    async def skip(self, ctx):
        """Skip the current track"""

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        
        embedVar = discord.Embed(title="Skip", description="Skipped Song", color=0x0099ff)
        await ctx.send(embed=embedVar)

    @commands.command(pass_context=True)
    async def pause(self, ctx):
        """Pause the current song"""
        try:
            ctx.voice_client.pause()
            embedVar = discord.Embed(title="Pause", description="Paused current song", color=0x0099ff)
            await ctx.send(embed=embedVar)
        except:
            embedVar = discord.Embed(title="Error", description="Error on pause", color=0x0099ff)
            await ctx.send(embed=embedVar)


    #Resume music
    @commands.command(pass_context=True)
    async def resume(self, ctx):
        """Resume the current song"""
        try:
            ctx.voice_client.resume()
            embedVar = discord.Embed(title="Resume", description="Resume current song", color=0x0099ff)
            await ctx.send(embed=embedVar)
        except:
            embedVar = discord.Embed(title="Error", description="Error on resume", color=0x0099ff)
            await ctx.send(embed=embedVar)


    #Show the queue
    @commands.command(pass_context=True, aliases=['q'])
    async def queue(self, ctx, page=1):
        """Show the current songs in queue.
        !queue [page]"""
        if not self.queue:
            return

        string = f'```Playing Right Now: {self.fetch.parse_name(self.queue[0])}\n\n'
        start_in = 1 + 15*(page-1)
        go_to = 16 + 15*(page-1)
        if page > ceil(len(self.queue)/15):
            await ctx.send(
                f"Not too many songs in the queue! Wait! You can add more, and then you can acess page {page}"
            )

        else:
            while start_in < go_to and start_in < len(self.queue):
                number = f'{str(start_in)} ' if start_in < 10 else start_in
                string += f'{number} ->\t{self.fetch.parse_name(self.queue[start_in])} \n'
                start_in += 1
            string += f'\nPage {page}\{ceil(len(self.queue) / 15)}```'
            await ctx.send(string)


    #Enable and disable the queue loop
    @commands.command(pass_context=True, aliases=['qloop'])
    async def loop(self, ctx):
        """Enable/Disable Queue Loop"""

        self.loop = not self.loop
        if self.loop:
            embedVar = discord.Embed(title="Loop", description="Queue loop enabled", color=0x0099ff)
        else:
            embedVar = discord.Embed(title="Loop", description="Queue loop disabled", color=0x0099ff)

        await ctx.send(embed=embedVar)


    @commands.command(pass_context=True, aliases=['clean','cleanq'])
    async def clear(self, ctx):
        """Clean Queue"""
        self.queue = []

        ctx.voice_client.stop()

        embedVar = discord.Embed(title="Stop", description="Deleted all songs", color=0x0099ff)
        await ctx.send(embed=embedVar)

    @commands.command()
    async def play(self, ctx, *args):
        """Plays from a url or a search query (almost anything youtube_dl supports)"""

        content = "".join(f"{i} " for i in args)
        if content := content.split():
            pseudo_url = content[0]

            # Radio
            if validators.url(pseudo_url) and ("youtube" in pseudo_url) and ("radio" in pseudo_url):
                embedVar = discord.Embed(title="Error", description="Can't play youtube Radio playlist!", color=0xff0000)
            elif validators.url(pseudo_url) and ("youtube" in pseudo_url) and ("list" in pseudo_url):
                self.queue = self.fetch.parse_playlist(pseudo_url)

                embedVar = discord.Embed(title="Added Playlist", description="Added a new playlist!", color=0x0099ff)
            elif validators.url(pseudo_url) and ("youtube" in pseudo_url) and ("watch" in pseudo_url):
                self.queue += [content[0],]

                embedVar = discord.Embed(title="Added Song", description="Added the song!", color=0x0099ff)
            elif validators.url(pseudo_url) and ("spotify" in pseudo_url) and ("track" in pseudo_url):
                embedVar = discord.Embed(title="Error", description="Spotify songs not implemented", color=0xff0000)
            elif validators.url(pseudo_url) and ("spotify" in pseudo_url) and ("playlist" in pseudo_url):
                embedVar = discord.Embed(title="Error", description="Spotify playlist not implemented", color=0xff0000)
            elif validators.url(pseudo_url):
                embedVar = discord.Embed(title="Error", description="This is not a valid music video", color=0xff0000)
            else:
                video = ytdl.extract_info(f"ytsearch:{content}", download=False)['entries'][0]
                self.queue.append(video['webpage_url'])

                embedVar = discord.Embed(
                    title="Added Song",
                    description=f"Added the song **{video['title']}**!",
                    color=0x0099FF,
                )


            await ctx.send(embed=embedVar)

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        self.queue = []

        ctx.voice_client.stop()
        
        await ctx.voice_client.disconnect()
    
    @play.after_invoke
    async def ensure_play(self, ctx):
        if self.playing:
            return

        self.playing = 1
        while True:
            await lock.acquire()
            if not self.queue:
                break

            def release(error):
                if error:
                    print(f'Player error: {error}') 

                lock.release()

            self.player = await YTDLSource.from_url(self.queue[0], loop=self.bot.loop, stream=True)
            ctx.voice_client.play(self.player, after=lambda error: release(error))

            embedVar = discord.Embed(title="Start Playing", description='Now playing: {}'.format(self.player.title), color=0x0099ff)
            await ctx.send(embed=embedVar)

            if self.loop:
                last_played = self.queue[0]
                del self.queue[0]
                self.queue.append(last_played)
            else:
                del self.queue[0]


        lock.release()
        self.playing = 0   

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                embedVar = discord.Embed(title="Error", description="You're not connected to a voice channel", color=0xff0000)
                await ctx.send(embed=embedVar)
                raise commands.CommandError("Author not connected to a voice channel.")