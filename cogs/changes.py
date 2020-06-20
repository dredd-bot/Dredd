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
    'V0.8.0 Rewrite': "Removed `lolice`, `whowouldwin` commands.\n`permissions` now show what permissions you don't have as well.\nCompletely got rid of economy cog\nAutomod is now better and more simple to setup\nAdded todo list commands\nImproved commands structure\nAdded more management commands for bot's staff.",
    'V0.9.0 Rewrite': "Logs now have case numebrs (bans, unbans, mutes, kicks)\nRoles/channels create/edit/delete does not exist anymore\n`userinfo` command was changed a little bit. (design and emotes) also it was glitching out sometimes by showing incorrect status, especially when streaming.\nMessage deletes are now getting logged if you have `moderation` logging enabled.\nJoin role for bots is here!\nAdded char limit for afk and nick commands",
    'V1.0.0 Final Rewrite': "You can now follow suggestions and bugs\nPrefix command now has a char limit\nAdded temp mute\nIf user was muted before and rejoined the server, he'll be muted."
}

version = '0.9.0 Rewrite'
most_recent = CHANGE_LOG["V"+version]

def setup(bot):
    bot.changelog = CHANGE_LOG
    bot.most_recent_change = most_recent
    bot.version = version