"""
Discord Bot
-----------
Listens for listener song requests and commands in a Discord server.
Injects approved requests into the playlist engine queue.
Optionally responds to users in Doctor Gonzo's voice.

Commands:
  !request <artist> - <title>   Request a song
    !nowplaying                    Show what's on air
      !queue                         Show upcoming tracks
        !skip                          (Admin only) Skip current track

        Setup:
          - Set DISCORD_BOT_TOKEN env var
            - Invite bot to your server with message/send permissions
              - Set DISCORD_REQUEST_CHANNEL env var (channel name or ID)
              """

from __future__ import annotations

import logging
import os
from typing import Optional

import discord
from discord.ext import commands

from services.playlist_engine import get_engine, Track
from services.dj_script_generator import get_generator
from orchestration.state_manager import get_state_manager

logger = logging.getLogger(__name__)

COMMAND_PREFIX = "!"
REQUEST_CHANNEL = os.getenv("DISCORD_REQUEST_CHANNEL", "song-requests")
ADMIN_ROLE      = os.getenv("DISCORD_ADMIN_ROLE", "DJ Admin")


def create_bot() -> commands.Bot:
      intents = discord.Intents.default()
      intents.message_content = True

    bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

    # ── EVENTS ────────────────────────────────────────────────────────────────

    @bot.event
    async def on_ready():
              logger.info("Discord bot online as %s (ID: %s)", bot.user, bot.user.id)
              await bot.change_presence(
                  activity=discord.Activity(
                      type=discord.ActivityType.listening,
                      name="Radio Free Gonzo"
                  )
              )

    @bot.event
    async def on_command_error(ctx, error):
              if isinstance(error, commands.CommandNotFound):
                            return
                        logger.error("Discord command error: %s", error)
        await ctx.send(f"Something broke: `{error}`")

    # ── COMMANDS ──────────────────────────────────────────────────────────────

    @bot.command(name="request", aliases=["req", "r"])
    async def request_song(ctx, *, song_query: str):
              """Request a song: !request Artist - Title"""
        # Must be in the right channel
        if ctx.channel.name != REQUEST_CHANNEL and str(ctx.channel.id) != REQUEST_CHANNEL:
                      await ctx.send(
                                        f"Requests go in #{REQUEST_CHANNEL}, friend. "
                                        f"Doctor Gonzo is watching all channels."
                      )
                      return

        # Parse "Artist - Title" format
        if " - " in song_query:
                      parts  = song_query.split(" - ", 1)
                      artist = parts[0].strip()
                      title  = parts[1].strip()
else:
            artist = song_query.strip()
            title  = ""

        if not artist:
                      await ctx.send("Format: `!request Artist - Title`  (title optional)")
                      return

        # Inject into playlist
        engine = get_engine()
        track  = Track(
                      title=title or "[Requested]",
                      artist=artist,
                      youtube_query=f"{artist} {title} official audio".strip(),
                      requested_by=ctx.author.display_name,
        )
        engine.inject_request(track, position=1)

        # Generate a Gonzo acknowledgment
        try:
                      gen  = get_generator()
                      ack  = gen.request_acknowledgment(
                          requester=ctx.author.display_name,
                          artist=artist,
                          title=title or "something",
                      )
except Exception:
            ack = f"Got it. {artist} is locked and loaded."

        embed = discord.Embed(
                      title="Request Queued",
                      description=f"**{artist}**{f' — {title}' if title else ''}\n\n_{ack}_",
                      color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)
        logger.info(
                      "Request queued: %s - %s by %s", artist, title, ctx.author.display_name
        )

    @bot.command(name="nowplaying", aliases=["np", "now"])
    async def now_playing(ctx):
              """Show the currently playing track."""
              sm    = get_state_manager()
              track = sm.now_playing
              if not track:
                            await ctx.send("Nothing on air right now. Stand by.")
                            return
                        embed = discord.Embed(
                                      title="Now Playing",
                                      description=f"**{track.get('artist','?')}** — *{track.get('title','?')}*",
                                      color=discord.Color.green(),
                        )
        if track.get("album"):
                      embed.add_field(name="Album", value=track["album"], inline=True)
                  if track.get("genre"):
                                embed.add_field(name="Genre", value=track["genre"], inline=True)
                            if track.get("requested_by"):
                                          embed.add_field(
                                                            name="Requested by", value=track["requested_by"], inline=True
                                          )
                                      await ctx.send(embed=embed)

    @bot.command(name="queue", aliases=["q", "upcoming"])
    async def show_queue(ctx):
              """Show the next few tracks in queue."""
        engine = get_engine()
        queue  = engine.state.queue[:5]
        if not queue:
                      await ctx.send("Queue is empty — the AI is thinking...")
                      return
                  lines = [
                                f"`{i+1}.` **{t.artist}** — *{t.title or 'TBD'}*"
                                + (f" _(req: {t.requested_by})_" if t.requested_by else "")
                                for i, t in enumerate(queue)
                  ]
        embed = discord.Embed(
                      title="Coming Up on Radio Free Gonzo",
                      description="\n".join(lines),
                      color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @bot.command(name="skip")
    @commands.has_role(ADMIN_ROLE)
    async def skip_track(ctx):
              """(Admin) Skip the current track."""
        sm = get_state_manager()
        sm.request_skip()
        await ctx.send("Skipping... brace yourself.")

    @bot.command(name="help_radio", aliases=["commands"])
    async def help_radio(ctx):
              embed = discord.Embed(
                  title="Radio Free Gonzo — Bot Commands",
                  color=discord.Color.dark_gold(),
    )
        embed.add_field(
                      name="!request Artist - Title",
                      value="Queue a song request",
                      inline=False,
        )
        embed.add_field(name="!nowplaying", value="See what's on air", inline=False)
        embed.add_field(name="!queue", value="See upcoming tracks", inline=False)
        embed.add_field(
                      name="!skip (Admin only)", value="Skip current track", inline=False
        )
        await ctx.send(embed=embed)

    return bot


def run_bot():
      token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
              logger.error("DISCORD_BOT_TOKEN not set — Discord bot will not start")
        return
    bot = create_bot()
    bot.run(token)
