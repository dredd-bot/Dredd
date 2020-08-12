import discord
import asyncio
from discord.ext import commands
from db import emotes
from utils.checks import is_booster

class Booster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:booster:686251890027266050>"
        self.big_icon = "https://cdn.discordapp.com/emojis/686251890027266050.png?v=1"

    @commands.command(brief='Set your custom prefix', aliases=['cprefix', 'cpref'])
    @is_booster()
    async def customprefix(self, ctx, prefix: str):
        """ Set a custom prefix you'll be able to use in any guild """
        await self.bot.db.execute("UPDATE vip SET prefix = $1 WHERE user_id = $2", prefix, ctx.author.id)
        self.bot.vip_prefixes[ctx.author.id] = prefix
        await ctx.send(f"{emotes.white_mark} Set your new custom prefix to {prefix}")

    @commands.group(brief='Manage your media', invoke_without_command=True)
    @is_booster()
    async def media(self, ctx):
        await ctx.send_help(ctx.command)

    @media.command(brief='Add media', name='add')
    @is_booster()
    async def media_add(self, ctx, media: str, *, url: str):
        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2", ctx.author.id, media.lower())\

        if len(media) > 32:
            return await ctx.send(f"{emotes.warning} Sorry! I can't have you have media longer than 32 characters. If you wish this number to be updated, please contact my developer(s)")
        if check:
            return await ctx.send(f"{emotes.warning} You already have {media.lower()} linked in your medias.")
        else:
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link) VALUES($1, $2, $3)", ctx.author.id, str(media.lower()), str(url))
            await ctx.send(f"{emotes.white_mark} Added {media.lower()} (<{url}>) to your medias.")
    
    @media.command(brief='Edit media', name='edit')
    @is_booster()
    async def media_edit(self, ctx, media: str, *, newurl: str):
        check = await self.bot.db.fetchval("SELECT media_link FROM media WHERE user_id = $1 AND media_type = $2", ctx.author.id, media.lower())

        if not check:
            return await ctx.send(f"{emotes.warning} You don't have {media.lower()} linked in your medias.")
        else:
            await self.bot.db.execute("UPDATE media SET media_link = $1 WHERE media_type = $2 AND user_id = $3", str(newurl), str(media.lower()), ctx.author.id)
            await ctx.send(f"{emotes.white_mark} Changed {media.lower()} link from <{check}> to <{newurl}>.")
    
    @media.command(brief="Remove media", name="remove")
    @is_booster()
    async def media_remove(self, ctx, media: str):
        check = await self.bot.db.fetchval("SELECT media_link FROM media WHERE user_id = $1 AND media_type = $2", ctx.author.id, media.lower())
        if not check:
            return await ctx.send(f"{emotes.warning} You don't have {media.lower()} linked in your medias.")
        else:
            await self.bot.db.execute("DELETE FROM media WHERE media_type = $1 AND user_id = $2", str(media.lower()), ctx.author.id)
            await ctx.send(f"{emotes.white_mark} Removed {media.lower()} from your medias")

    @media.command(brief='Clear medias', name='clear')
    @is_booster()
    async def media_clear(self, ctx):
        check = await self.bot.db.fetchval("SELECT * FROM media WHERE user_id = $1", ctx.author.id)
        num = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if not check:
            return await ctx.send(f"{emotes.warning} You don't have anything linked in your medias.")

        def check(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id
            
        try:
            checkmsg = await ctx.send(f"Are you sure you want to unlink all **{num}** medias?")
            await checkmsg.add_reaction(f"{emotes.white_mark}")
            await checkmsg.add_reaction(f"{emotes.red_mark}")
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)    
            
            if str(react) == f"{emotes.white_mark}":
                try:
                    await checkmsg.clear_reactions()
                except:
                    pass
                await checkmsg.edit(content=f"{emotes.white_mark} Unlinked {num} medias from your media list", delete_after=15)
                await self.bot.db.execute("DELETE FROM media WHERE user_id = $1", ctx.author.id)
                
            if str(react) == f"{emotes.red_mark}":
                try:
                    await checkmsg.clear_reactions()
                except:
                    pass
                await checkmsg.edit(content=f"{emotes.white_mark} I'm not deleting any medias from your media list.", delete_after=15)

        except asyncio.TimeoutError:
            try:
                await checkmsg.clear_reactions()
            except:
                pass
            await checkmsg.edit(content="Cancelling...", delete_after=15)


def setup(bot):
    bot.add_cog(Booster(bot))