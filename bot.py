import discord
import os
import asyncio

from discord.ext import commands
from dotenv import load_dotenv

from server.keep_alive import keep_alive

# env 로드
load_dotenv()

# Intents 및 Bot 인스턴스 생성
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# on_ready 이벤트
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📡 봇이 {len(bot.guilds)}개의 서버에 연결되어 있습니다.')
    print('Commands:', [cmd.name for cmd in bot.commands])
    print('='*50)

# 오류 처리
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ '{ctx.message.content}' 명령어를 찾을 수 없습니다. `/도움`을 입력해보세요.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ 이 명령어를 사용할 권한이 없습니다.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 필수 인수가 누락되었습니다. `/도움 {ctx.command}`을(를) 확인해보세요.")
    else:
        print(f"오류 발생: {error}")
        await ctx.send(f"❌ 명령어 실행 중 오류가 발생했습니다: {error}")

async def load_cogs():
    """모든 cog를 로드합니다."""
    cogs_to_load = [
        'cogs.hello',
        'cogs.news',
        'cogs.help'
    ]    
    
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f'✅ {cog} 로드 완료')
        except Exception as e:
            print(f'❌ {cog} 로드 실패: {e}')

async def main():
    """메인 실행 함수"""
    token = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        print("❌ DISCORD_BOT_TOKEN이 설정되지 않았습니다.")
        print("💡 .env 파일에 'DISCORD_BOT_TOKEN=your_token_here' 를 추가해주세요.")
        return

    print("🚀 이스포츠 뉴스 봇을 시작합니다...")
    
    # Cog 로드
    await load_cogs()

    # 봇 시작
    try:
        await bot.start(token)
    except Exception as e:
        print(f"❌ 봇 시작 실패: {e}")

if __name__ == '__main__':
    # 서버 핑용 웹페이지(keep-alive) 기동
    keep_alive()

    asyncio.run(main())