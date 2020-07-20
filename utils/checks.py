import discord
import aiohttp
from db import emotes

from discord.ext import commands

class owner_only(commands.CommandError):
    pass

def has_voted():
    async def predicate(ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://discord.boats/api/bot/667117267405766696/voted?id={ctx.author.id}') as r:
                js = await r.json()
                if js['error'] == True and js['message'] == "User wasn't found":
                    e = discord.Embed(color=ctx.bot.logging_color, description="Please [vote here](https://discord.boats/bot/667117267405766696/vote) to be able to use this command.")
                    await ctx.send(embed=e)
                    return False
                elif js['error'] == False and js['voted'] == False:
                    e = discord.Embed(color=ctx.bot.logging_color, description="Please [vote here](https://discord.boats/bot/667117267405766696/vote) to be able to use this command.")
                    await ctx.send(embed=e)
                    return False
                elif js['error'] == False and js['voted'] == True:
                    return True
                elif js['error'] == True:
                    e = discord.Embed(color=ctx.bot.logging_color, description=f"Error while fetching your vote: {js['message']}")
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

