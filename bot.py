import discord
import os
import asyncio
import logging
import signal

from discord.ext import commands
from dotenv import load_dotenv

from server.keep_alive import keep_alive

# 로깅 설정
logging.basicConfig(level=logging.INFO)

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
    # HTTPException (429 등)이 발생한 경우 Discord로 메시지를 보내지 않음
    if isinstance(error, discord.HTTPException):
        print(f"Discord HTTP 오류 발생 (메시지 전송 안함): {error}")
        return
    
    # 사용자 경험을 위한 안전한 에러 메시지 전송
    try:
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"❌ '{ctx.message.content}' 명령어를 찾을 수 없습니다. `/도움`을 입력해보세요.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 이 명령어를 사용할 권한이 없습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ 필수 인수가 누락되었습니다. `/도움 {ctx.command}`을(를) 확인해보세요.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ 잠시만요! {error.retry_after:.0f}초 후에 다시 시도해주세요.")
        else:
            await ctx.send(f"❌ 명령어 실행 중 오류가 발생했습니다.")
            print(f"기타 오류 상세: {error}")
            
    except discord.HTTPException as send_error:
        # 에러 메시지 전송 중 429 에러 발생 시 콘솔에만 기록
        print(f"에러 메시지 전송 실패 (Rate Limit 방지): {send_error}")
        if isinstance(error, commands.CommandNotFound):
            print(f"명령어를 찾을 수 없음: {ctx.message.content}")
        elif isinstance(error, commands.CommandOnCooldown):
            print(f"쿨다운 중: {error}")
        else:
            print(f"원본 오류: {error}")
    except Exception as send_error:
        # 다른 예외 발생 시에도 안전하게 처리
        print(f"에러 메시지 전송 중 예외: {send_error}")
        print(f"원본 오류: {error}")

async def load_cogs():
    """모든 cog를 로드합니다."""
    cogs_to_load = [
        'cogs.hello',
        'cogs.news',
        'cogs.help',
        'cogs.schedule',
        'cogs.player'
    ]    
    
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f'✅ {cog} 로드 완료')
        except Exception as e:
            print(f'❌ {cog} 로드 실패: {e}')

async def shutdown(signal_received, loop):
    """종료 신호를 처리하는 함수"""
    print(f"🛑 종료 신호 {signal_received.name} 수신됨...")
    print("📡 Discord 연결을 종료하는 중...")
    if not bot.is_closed():
        await bot.close()
    print("✅ 봇이 안전하게 종료되었습니다.")
    loop.stop()

async def start_bot():
    """봇을 시작하고 429 에러 시 재시도합니다."""
    token = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        print("❌ DISCORD_BOT_TOKEN이 설정되지 않았습니다.")
        print("💡 .env 파일에 'DISCORD_BOT_TOKEN=your_token_here' 를 추가해주세요.")
        return

    max_retries = 3  # 최대 3번만 재시도
    retry_count = 0

    while retry_count < max_retries:
        try:
            await bot.start(token)
            break  # 성공 시 루프 종료
            
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get("Retry-After", 60))
                
                # 과도한 대기 시간 감지 시 봇 종료
                if retry_after > 1800:  # 30분 초과 시
                    logging.error(f"🚨 심각한 Rate Limit 감지: {retry_after}초 ({retry_after/60:.1f}분)")
                    logging.error("🛑 봇을 종료합니다. 토큰 재생성을 고려해주세요.")
                    logging.error("💡 1-2시간 후 다시 시도하거나 Discord 개발자 포털에서 토큰을 재생성하세요.")
                    return
                
                # 일반적인 Rate Limit 처리 (최대 30분)
                max_wait = 1800  # 30분
                if retry_after > max_wait:
                    logging.error(f"⚠️ 대기 시간 제한: {retry_after}초 → {max_wait}초로 제한")
                    retry_after = max_wait
                    
                logging.warning("Discord Rate Limit (429) — %s초 후 재시도", retry_after)
                await asyncio.sleep(retry_after)
                retry_count += 1
                continue
            else:
                logging.error(f"Discord HTTP 에러: {e}")
                retry_count += 1
                await asyncio.sleep(10)
                continue
                
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Too Many Requests" in error_str:
                retry_time = 60  # 60초 대기
                logging.warning("429 에러 감지 — %s초 후 재시도: %s", retry_time, error_str)
                await asyncio.sleep(retry_time)
                retry_count += 1
                continue
            else:
                logging.error(f"봇 시작 실패: {e}")
                retry_count += 1
                await asyncio.sleep(10)
                continue
    
    # 최대 재시도 횟수 초과
    logging.error("🚨 최대 재시도 횟수 초과. 봇을 종료합니다.")
    logging.error("💡 토큰 재생성 후 1-2시간 뒤 다시 시도해주세요.")

async def main():
    """메인 실행 함수"""
    print("🚀 이스포츠 뉴스 봇을 시작합니다...")

    # 봇의 이벤트 루프 가져오기
    loop = asyncio.get_event_loop()
    
    # Render가 보내는 SIGTERM 신호를 받았을 때 shutdown 함수를 실행하도록 등록
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))
    
    # Cog 로드
    await load_cogs()

    # 봇 시작
    await start_bot()

if __name__ == '__main__':
    # 서버 핑용 웹페이지(keep-alive) 기동
    keep_alive()

    asyncio.run(main())