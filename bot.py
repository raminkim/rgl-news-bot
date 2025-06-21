import discord
import os
import asyncio

from discord.ext import commands
from dotenv import load_dotenv

from cogs.hello import HelloCommand

# env 로드
load_dotenv()

# Intents 및 Bot 인스턴스 생성
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# on_ready 이벤트
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print('Commands:', [cmd.name for cmd in bot.commands])

async def main():
    await bot.load_extension('cogs.hello')
    await bot.start(os.getenv('DISCORD_BOT_TOKEN'))

if __name__ == '__main__':
    asyncio.run(main())