"""
Dredd, discord bot
Copyright (C) 2021 Moksej
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.
You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import discord

from discord.ext import commands
from utils.checks import is_booster
from utils.i18n import locale_doc


class Boosters(commands.Cog, aliases=['Donators']):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = '<:n_:747399776231882812>'
        self.big_icon = 'https://cdn.discordapp.com/emojis/747399776231882812.png?v=1'

    @commands.command(brief=_("Set your own custom prefix"))
    @is_booster()
    @locale_doc
    async def customprefix(self, ctx, prefix: str):
        _(""" Set your own custom prefix which you'll be able to access everywhere """)

        if len(prefix) >= 7:
            return await ctx.send(_("{0} Custom prefix can't be longer than 7 characters.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        await self.bot.db.execute("UPDATE boosters SET prefix = $1 WHERE user_id = $2", prefix, ctx.author.id)
        self.bot.boosters[ctx.author.id] = prefix
        await ctx.send(_("{0} Set your custom prefix to `{1}`.").format(
            self.bot.settings['emojis']['misc']['white-mark'], prefix
        ))

    @commands.group(brief=_("Manage your social medias"), name='social-media',
                    aliases=['socmedias', 'media', 'socialmedia', 'socialmedias', 'social'], invoke_without_command=True)
    @is_booster()
    @locale_doc
    async def socialmedia(self, ctx):
        _(""" Base command for managing your social medias """)
        await ctx.send_help(ctx.command)

    @socialmedia.command(name='add', brief=_("Link a social media"))
    @is_booster()
    @locale_doc
    async def socialmedia_add(self, ctx, name: str, url: str):
        _(""" Add social media to your medias list """)

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2", ctx.author.id, name.lower())
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if len(name) > 32:
            return await ctx.send(_("{0} Sorry! I can't have you have media longer than 32 characters."
                                    "If you wish this number to be updated, please contact my developer(s)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if check:
            return await ctx.send(_("{0} You already have {name.lower()} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if not (url.startswith('https://') or url.startswith('http://')):
            return await ctx.send(_("{0} URL must start with either a http:// or https://").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        else:
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link) VALUES($1, $2, $3)", ctx.author.id, str(name.lower()), str(url))
            await ctx.send(_("{0} Added {1} (<{2}>) to your medias.").format(
                self.bot.settings['emojis']['misc']['white-mark'], name.lower(), url
            ))

    @socialmedia.command(name='discord', brief=_("Link your Discord server"))
    @is_booster()
    @locale_doc
    async def socialmedia_discord(self, ctx, invite: str, name: str = None):
        _(""" Add Discord to your social medias list, when not providing the name, server name will be used""")

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2", ctx.author.id, name)
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if invite.startswith('https://') or invite.startswith('http://'):
            return await ctx.send(_("{0} Invite must not be a full link, only the code (PMZXUwdr)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if name and len(name) > 32:
            return await ctx.send(_("{0} Sorry! I can't have you have media longer than 32 characters."
                                    "If you wish this number to be updated, please contact my developer(s)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if check:
            return await ctx.send(_("{0} You already have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], name
            ))
        else:
            try:
                invite = await self.bot.fetch_invite(str(invite))
                name = name or invite.guild.name
            except Exception as e:
                raise commands.BadArgument(_("Can't seem to find that invite, please make sure you're only sending the code (PMZXUwdr) else it won't work."))
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link, type) VALUES($1, $2, $3, $4)", ctx.author.id, name, invite.url, 1)
            await ctx.send(_("{0} Added Discord ({1} - <{2}>) to your medias list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], name, invite.url
            ))

    @socialmedia.command(name='instagram', brief=_("Link your Instagram account"))
    @is_booster()
    @locale_doc
    async def socialmedia_instagram(self, ctx, account_name: str):
        _(""" Add Instagram to your social medias list """)

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2 AND type = $3", ctx.author.id, account_name, 2)
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if account_name.startswith('https://') or account_name.startswith('http://'):
            return await ctx.send(_("{0} Account name must not be a full link, only the name (TheMoksej)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if len(account_name) > 30:
            return await ctx.send(_("{0} Instagram account limit is 30, you're over 30, you sure it's the correct account name?").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if check:
            return await ctx.send(_("{0} You already have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], account_name
            ))
        else:
            link = 'https://instagram.com/{0}'.format(account_name)
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link, type) VALUES($1, $2, $3, $4)", ctx.author.id, account_name, link, 2)
            await ctx.send(_("{0} Added Instagram ({1} - <{2}>) to your medias list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], account_name, link
            ))

    @socialmedia.command(name='twitch', brief=_("Link your Twitch account"))
    @is_booster()
    @locale_doc
    async def socialmedia_twitch(self, ctx, account_name: str):
        _(""" Add Twitch to your social medias list """)

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2 AND type = $3", ctx.author.id, account_name, 3)
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if account_name.startswith('https://') or account_name.startswith('http://'):
            return await ctx.send(_("{0} Account name must not be a full link, only the name (TheMoksej)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if len(account_name) > 30:
            return await ctx.send(_("{0} Twitch account limit is 30, you're over 30, you sure it's the correct account name?").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if check:
            return await ctx.send(_("{0} You already have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], account_name
            ))
        else:
            link = 'https://twitch.tv/{0}'.format(account_name)
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link, type) VALUES($1, $2, $3, $4)", ctx.author.id, account_name, link, 3)
            await ctx.send(_("{0} Added Twitch ({1} - <{2}>) to your medias list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], account_name, link
            ))

    @socialmedia.command(name='twitter', brief=_("Link your Twitter account"))
    @is_booster()
    @locale_doc
    async def socialmedia_twitter(self, ctx, account_name: str):
        _(""" Add Twitter to your social medias list """)

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2 AND type = $3", ctx.author.id, account_name, 4)
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if account_name.startswith('https://') or account_name.startswith('http://'):
            return await ctx.send(_("{0} Account name must not be a full link, only the name (TheMoksej)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if len(account_name) > 30:
            return await ctx.send(_("{0} Twitter account limit is 30, you're over 30, you sure it's the correct account name?").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if check:
            return await ctx.send(_("{0} You already have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], account_name
            ))
        else:
            link = 'https://twitter.com/{0}'.format(account_name)
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link, type) VALUES($1, $2, $3, $4)", ctx.author.id, account_name, link, 4)
            await ctx.send(_("{0} Added Twitter ({1} - <{2}>) to your medias list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], account_name, link
            ))

    @socialmedia.command(name='github', brief=_("Link your GitHub account"))
    @is_booster()
    @locale_doc
    async def socialmedia_github(self, ctx, account_name: str):
        _(""" Add Github to your social medias list """)

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2 AND type = $3", ctx.author.id, account_name, 5)
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if account_name.startswith('https://') or account_name.startswith('http://'):
            return await ctx.send(_("{0} Account name must not be a full link, only the name (TheMoksej)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if len(account_name) > 30:
            return await ctx.send(_("{0} GitHub account limit is 30, you're over 30, you sure it's the correct account name?").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        if check:
            return await ctx.send(_("{0} You already have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], account_name
            ))
        else:
            link = 'https://github.com/{0}'.format(account_name)
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link, type) VALUES($1, $2, $3, $4)", ctx.author.id, account_name, link, 5)
            await ctx.send(_("{0} Added GitHub ({1} - <{2}>) to your medias list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], account_name, link
            ))

    @socialmedia.command(name='youtube', brief=_("Link your youtube account"))
    @is_booster()
    @locale_doc
    async def socialmedia_youtube(self, ctx, account_name: str, overwrite_name: str):
        _(""" Add YouTube to your social medias list """)

        check = await self.bot.db.fetchval("SELECT media_type FROM media WHERE user_id = $1 AND media_type = $2 AND type = $3", ctx.author.id, account_name, 7)
        tot_medias = await self.bot.db.fetchval("SELECT count(*) FROM media WHERE user_id = $1", ctx.author.id)
        if tot_medias >= 10:
            raise commands.BadArgument(_("You've reached the max limit of social medias available. (10)"))

        if account_name.startswith('https://') or account_name.startswith('http://'):
            return await ctx.send(_("{0} Account name must not be a full link, only the name (UCyFCSJXJ6cGWae2DBg3J2zg)").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if len(account_name) > 60:
            return await ctx.send(_("{0} Youtube account name limit is 60, you're over 60, you sure it's the correct account name?").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        elif len(overwrite_name) > 32:
            return await ctx.send(_("{0} Overwrite name must be shorter than 32 characters.").format(self.bot.settings['emojis']['misc']['warn']))
        if check:
            return await ctx.send(_("{0} You already have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], account_name
            ))
        else:
            link = 'https://youtube.com/channel/{0}'.format(account_name)
            await self.bot.db.execute("INSERT INTO media(user_id, media_type, media_link, type) VALUES($1, $2, $3, $4)", ctx.author.id, overwrite_name, link, 7)
            await ctx.send(_("{0} Added YouTube ({1} - <{2}>) to your medias list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], overwrite_name, link
            ))

    @socialmedia.command(name='remove', brief=_("Remove linked social media"))
    @is_booster()
    @locale_doc
    async def socialmedia_remove(self, ctx, name: str, social_type: int = None):
        _(""" Remove media from your medias list

        Social types:
        1 - Discord
        2 - Instagram
        3 - Twitch
        4 - Twitter
        5 - Github
        6 - Spotify
        7 - Youtube """)

        if social_type:
            query = f'SELECT media_link FROM media WHERE user_id = $1 AND media_type = $2 AND type = {social_type}'
            query2 = f'DELETE FROM media WHERE media_type = $1 AND user_id = $2 AND type = {social_type}'
        else:
            query = "SELECT media_link FROM media WHERE user_id = $1 AND media_type = $2"
            query2 = 'DELETE FROM media WHERE media_type = $1 AND user_id = $2'
        check = await self.bot.db.fetch(query, ctx.author.id, name)
        if not check:
            return await ctx.send(_("{0} You don't have {1} linked in your medias.").format(
                self.bot.settings['emojis']['misc']['warn'], name
            ))
        elif len(check) >= 2:
            while True:
                try:
                    msg = await ctx.channel.send(_("{0} You're about to delete all the social medias named {1}. Are you sure you want to do that? If no, please add a social type *(`{2}help socialmedia remove`)*").format(self.bot.settings['emojis']['misc']['warn'], name, ctx.prefix), delete_after=60)
                    await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                    await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                    verify_response, user = await self.bot.wait_for('reaction_add', check=lambda r, m: r.message.id == msg.id and m.id == ctx.author.id, timeout=60.0)

                    if str(verify_response) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                        await self.bot.db.execute('DELETE FROM media WHERE media_type = $1 AND user_id = $2', name, ctx.author.id)
                        await ctx.send(_("{0} Deleted all the social medias named {1} from your account.").format(self.bot.settings['emojis']['misc']['white-mark'], name))
                        break
                    elif str(verify_response) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                        await ctx.channel.send(_("Alright, I will not be removing your social medias."))
                        break
                    else:
                        pass
                except asyncio.TimeoutError:
                    await ctx.send(_("{0} You've waited for too long, canceling the command.").format(self.bot.settings['emojis']['misc']['warn']))
                    break
        else:
            await self.bot.db.execute(query2, str(name), ctx.author.id)
            await ctx.send(_("{0} Removed {1} from your linked social medias").format(
                self.bot.settings['emojis']['misc']['white-mark'], name
            ))


def setup(bot):
    bot.add_cog(Boosters(bot))
