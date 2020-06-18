import discord
from db import emotes

from discord.ext import commands

class owner_only(commands.CommandError):
    pass

def has_voted():
    async def predicate(ctx):
        check = await ctx.bot.dblpy.get_user_vote(ctx.author.id)
        if check == True:
            return True
        elif check == False:
            e = discord.Embed(color=ctx.bot.logging_color, description="This command is vote locked. to use this command, please [vote here](https://top.gg/bot/667117267405766696/vote).")
            await ctx.send(embed=e)
            return False
        return True
    return commands.check(predicate)

def is_guild(ID):
    async def predicate(ctx):
        if ctx.guild.id == ID:
            return True
        else:
            if await ctx.bot.is_admin(ctx.author):
                return True
            else:
                return False
            return False
    return commands.check(predicate)

