import discord
import aiohttp
from db import emotes

from discord.ext import commands
from utils.default import color_picker

class owner_only(commands.CommandError):
    pass

def has_voted():
    async def predicate(ctx):
        if await ctx.bot.is_booster(ctx.author):
            return True
        if 100 <= len(ctx.bot.guilds) <= 110:
            return True
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://discord.boats/api/bot/667117267405766696/voted?id={ctx.author.id}') as r:
                js = await r.json()
                color = color_picker('colors')
                if js['error'] == True and js['message'] == "User wasn't found":
                    e = discord.Embed(color=color['logging_color'], description="Please [vote here](https://discord.boats/bot/667117267405766696/vote) to be able to use this command.")
                    await ctx.send(embed=e)
                    return False
                elif js['error'] == False and js['voted'] == False:
                    e = discord.Embed(color=color['logging_color'], description="Please [vote here](https://discord.boats/bot/667117267405766696/vote) to be able to use this command.")
                    await ctx.send(embed=e)
                    return False
                elif js['error'] == False and js['voted'] == True:
                    return True
                elif js['error'] == True:
                    e = discord.Embed(color=color['logging_color'], description=f"Error while fetching your vote: {js['message']}")
                    await ctx.send(embed=e)
                    return False
    return commands.check(predicate)

# def has_voted():
#     async def predicate(ctx):
#         check = await ctx.bot.dblpy.get_user_vote(ctx.author.id)
#         if check == True:
#             return True
#         elif check == False:
#             e = discord.Embed(color=ctx.bot.logging_color, description="Please [vote here](https://top.gg/bot/667117267405766696/vote) to be able to use this command.")
#             await ctx.send(embed=e)
#             return False
#         return True
#     return commands.check(predicate)

def is_guild(ID):
    async def predicate(ctx):
        if ctx.guild.id == ID:
            return True
        else:
            if await ctx.bot.is_admin(ctx.author):
                return True
            elif not await ctx.bot.is_admin(ctx.author):
                return False
            return False
    return commands.check(predicate)

def is_booster():
    async def predicate(ctx):
        if await ctx.bot.is_booster(ctx.author):
            return True
        await ctx.send(f"{emotes.bot_booster} This command is booster-locked")
        return False
    return commands.check(predicate)

def test_command():
    async def predicate(ctx):
        if await ctx.bot.is_admin(ctx.author):
            return True
        elif not await ctx.bot.is_admin(ctx.author):
            color = color_picker('colors')
            e = discord.Embed(color=color['logembed_color'], description=f"{emotes.warning} This command is in it's testing phase, please [join support server]({ctx.bot.support}) if you want to know when it'll be available.")
            await ctx.send(embed=e)
            return False
        return False
    return commands.check(predicate)

class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=member_id))
            except discord.NotFound:
                raise commands.BadArgument('This member has not been banned before.') from None

        elif not argument.isdigit():
            ban_list = await ctx.guild.bans()
            entity = discord.utils.find(lambda u: str(u.user.name) == argument, ban_list)
            if entity is None:
                raise commands.BadArgument('This member has not been banned before.')
            return entity

class MemberNotFound(Exception):
    pass

class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument("User needs to be an ID")
        elif argument.isdigit():
            member_id = int(argument, base=10)
            try:
                ban_check = await ctx.guild.fetch_ban(discord.Object(id=member_id))
                if ban_check:
                    raise commands.BadArgument('This user is already banned.') from None
            except discord.NotFound:
                return type('_Hackban', (), {'id': argument, '__str__': lambda s: s.id})()

