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

CHANGE_LOG = {
    'V0.1.0': "Unlogged",
    'V0.1.5': "Added `deposit`, `withdraw`, `unregister`, `job`, `changelog`, `shop`, `buy` commands.\nImproved `account`, `balance`, `leaderboard`, `help` commands and logging system.",
    'V0.2.0': 'Added `meme`, `bankrob` command\nChanged `user`, `server`, `credits`, `eightball`, `roast`, `job` commands visual look.\nRenamed `profile` to `account`, `boxes` to `crates`.\nNerfed medium and supreme boxes.\nRemoved `lock` and `unlock` commands.',
    'V0.2.5': 'Added `dehoist` and `unbanall`\nImproved moderation commands\nChanged how work `help`, `bugreport`, `about` commands.',
    'V0.5.0': 'Added `pressf`, `supreme`, `roles`, `servermods` commands\nImproved `help` command',
    'V0.5.5': 'Added `serveremotes` commands.\nStarted logging nickname changes\nImproved `help` command\nRemoved `feedback`, `changelog` commands',
    'V0.6.0': 'Released updated `automod`\nImplemented warning system\nImproved functionality',
    'V0.6.5': 'Updated error handler\nVote locked `pussy`, `spank`, `setafk` commands\nMessage deletes now inform who deleted the message\nYou can now have AFK state.\nStatus reports won\'t be sent from the bot anymore.',
    'V0.7.0': '`translate` was disabled until further notice.\nAdded `permissions` command.\n`userinfo` used to shit it self if you had nitro custom emoji. Not anymore.',
    'V0.7.5': 'Initiated rewrite v2',
    'V0.8.0 Rewrite': "Removed `lolice`, `whowouldwin` commands.\n`permissions` now show what permissions you don't have as well.\nCompletely got rid of economy cog\nAutomod is now better and more simple to setup\nAdded todo list\nImproved commands structure\nAdded more management commands for bot's staff.",
    'V0.9.0 Rewrite': "Logs now have case numebrs (bans, unbans, mutes, kicks)\nRoles/channels create/edit/delete logs do not exist anymore\n`userinfo` command was changed a little bit. (design and emotes) also it was glitching out sometimes by showing incorrect status, especially when streaming.\nMessage deletes are now getting logged if you have `moderation` logging enabled.\nJoin role for bots is here!\nAdded char limit for afk and nick commands\nAdded discord's allowed_mentions feature\nYou can invoke commands by editing the message",
    'V1.0.0 Final Rewrite': "You can now follow suggestions and bugs\nPrefix command now has a char limit\nAdded temp mute\nIf user was muted before and rejoined the server, he'll be muted.\nAdded char limit for some of the fun commands\nFixed some stuff\nYou can disable join messages for bots",
    'V1.0.1': "Fixed a typo in setafk command\nHelp command shows clean prefix now instead of <@id> when you invoke commands using @mention\nGetting bot badges isn't automated anymore, and stored in json file.\nYou can invoke commands by editing your messages now.",
    'V1.0.2': "Roles are now reversed in userinfo\nRoles char limit fixed in userinfo\nServers can now have badges\nHelp command has a cooldown now\nAutomod now is changed a little bit, mostly database requests\nUpdated database requests with logs (case numbers are now cached)",
    'V1.0.3': "1. Leaving and welcoming messages are now visible in serversettings\n2. Changelog command is here\n3. If there are no disabled commands, bot will return that there are none.\n4. Lockdown and unlockdown commands are here!\n5. Mentioning an AFK user will now show his username in clean content, for ex: ***Example*** will be **\*Example\***\n6. Raidmode is now here!",
    'V1.0.4': "1. More management commands for bot staff\n2. You can now opt-out yourself from nicknames logging by doing `<serverprefix>nicks opt-out`\n3. Updated Privacy Policy.\n4. Voting unlocks the vote-locked commands instantly",
    'V1.0.5': "1. Removed bugreport command\n2. Added alias `ui` to `userinfo` command.\n3. Switched up how user roles look like in `userinfo` command if they have too many of them.\n4. When joining support server you'll receive early supporter badge now yet again.\n5. If you have any badges and you join the support server, you'll get special roles for those badges.\n6. Logs like kicks, bans and unbans now show the reason. Keep in mind it might still be buggy.\n7. Hackban will now check if user was previously banned.\n8. If someone will mention you while you're afk, they'll now see how long ago did you go afk.\n9. Deleted message logs now show how many messages were deleted.\n10. From now on blacklisted users will have ⚠️ badge.\n11. Added more logging stuff for support server only.\n12. Previously if you had moderation logs turned on you'd get deleted messages history. Those will show if you'll have delete messages logs enabled now.",
    'V1.1.0 Beta': "1. Blacklisted users will have ⛔ badge instead now.\n2. Bot logs your activity status now\n3. Help command look has a little bit changed and also disabled commands won't show up anymore (it is still being redesigned, so you might see design change in the coming days)\n4. Prefixes are now cached.\n5. Cases used to repeat time to time, fixed now",
    'V1.1.0': "1. You also need to be opted in to see someone's status that bot has logged\n2. Removed `trap` command\n3. Reduced fun commands cooldowns\n4. Switched up how disabled commands work\n5. There's now `todo info` command which will show when you added your todo and the jump to the message\n6. Lockdown command is now made owner only\n7. dehoist command is now more advanced.\n8. Added snipe command\n9. Reduced cooldowns\n10. Removed changelog command\n11. Added booster perks\n12. Fixed commands not working in DMs\n13. Changed help command design",
    'V1.2.0': "1. Maintenance mode was added for bot developer(s)\n2. tempmute was fully rewritten\n3. Changed welcoming and leaving messages formatting\n4. Bot acknowledgements now have a new locaton in userinfo and serverinfo commands. No more confussion I guess.\n5. Changed cache related stuff\n6. Changed permission checks for togglelog and logchannel commands\n7. Added partners command\n8. If guild icon is animated, it'll be shown as gif in serverinfo command\n9. Added reactions to main help command that you can use to navigate\n10. Changed the look of join message that people see when bot join their server\n11. Hopefully fixed logs showing wrong moderator\n12. You'll be able to see how long you were AFK after coming back",
    'V1.3.0': '1. lockchannel and unlockchannel will take the current channel as default. They are also kinda rewritten\n2. Removed wallpaper command\n3. Rewrote command briefs you see in `-help <category>`\n4. Suggestion embeds now have brand new design\n5. Welcoming and leaving messages can now be embedded\n6. Suggestions can now be longer by 3 times (384 characters)\n7. User badges are now being cached so JSON file wouldn\'t get opened every time user invokes `userinfo` and possibly corrupted\n8. Uptime is now more advanced\n9. Partner badges are now <:partner:748833273383485440> instead of <:partners:683288926940823598>\n10. If you are blacklisted bot will not respond to you anymore at all since we changed the system a bit.\n11. Improved purge command\n12. Members can now be automatically dehoisted when you enable antidehoist logs. They\'ll get dehoisted 60 seconds after they change their nick or join the server\n12. Rewrote cache\n13. Snipes are now being logged in cache.\n14. Updated privacy policy\n15. Deleted images are now being properly logged\n16. Added temp ban\n17. Instead of `togglemsg bots` there are now 2 separate commands: `togglemsg joinbots` and `togglemsg leavebots`\n18. Added a members limit for ban, kick commands',
    'V1.4.0': '1. users that don\'t share servers with a bot will be fetched now.\n2. Welcoming and leaving messages now have ability to display user\'s tag and id\n3. Changed how todo list ids are displayed`\n4. Updated character limits for todo lists.\n5. Fixed logging not logging deleted/edited messages over 1024 characters\n6. Moderation commands have a new format\n7. Added owner-exclusive features\n8. Changed error handler format',
    'V1.4.1': '1. Fixed issue where you couldn\'t edit your todo if it was shorter than 150 characters.',
    'V1.5.0': '1. Fixed where bot wouldn\'t react with ⏹️ when paginating 1 page only\n2. Added more roasts.\n3. Added competing activity status to `userinfo` command\n4. Fixed fun commands opening a new session each time.\n5. You can now use roast outside NSFW channels',
    'V1.5.1': '1. Imported aiohttp module where I should\'ve had it',
    'V3.0.0': 'https://canary.discord.com/channels/671078170874740756/699741816685330462/827950602225975307',
    'V3.0.1': 'https://canary.discord.com/channels/671078170874740756/699741816685330462/829011633061363762',
    'V3.0.2': 'https://canary.discord.com/channels/671078170874740756/699741816685330462/829531198639571036',
    'V3.0.3': 'https://canary.discord.com/channels/671078170874740756/699741816685330462/832997273733562408',
    'V3.1.0': ''
}

version = '3.1.0'
most_recent = CHANGE_LOG["V" + version]


def setup(bot):
    bot.changelog = CHANGE_LOG
    bot.most_recent_change = most_recent
    bot.version = version
    bot.help_icon = ''
