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
    'V1.0.5': "1. Removed bugreport command\n2. Added alias `ui` to `userinfo` command.\n3. Switched up how user roles look like in `userinfo` command if they have too many of them.\n4. When joining support server you'll receive early supporter badge now yet again.\n5. If you have any badges and you join the support server, you'll get special roles for those badges.\n6. Logs like kicks, bans and unbans now show the reason. Keep in mind it might still be buggy.\n7. Hackban will now check if user was previously banned.\n8. If someone will mention you while you're afk, they'll now see how long ago did you go afk.\n9. Deleted message logs now show how many messages were deleted.\n10. From now on blacklisted users will have ⚠️ badge.\n11. Added more logging stuff for support server only.\n12. Previously if you had moderation logs turned on you'd get deleted messages history. Those will show if you'll have delete messages logs enabled now."
    }

version = '1.0.5'
most_recent = CHANGE_LOG["V"+version]

def setup(bot):
    bot.changelog = CHANGE_LOG
    bot.most_recent_change = most_recent
    bot.version = version