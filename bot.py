import discord
import os
import asyncio
import logging
import signal
import random

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

class RateLimitHandler:
    """Discord Rate Limit 지수 백오프 처리"""
    
    def __init__(self):
        self.retry_count = 0
        self.base_delay = 1  # 기본 대기 시간 (초)
        self.max_retries = 3
        self.max_delay = 60
    
    async def handle_rate_limit(self, retry_after: float = None) -> bool:
        """
        Rate Limit 처리 with 지수 백오프
        Returns: True if should continue, False if should stop
        """
        self.retry_count += 1
        
        if self.retry_count > self.max_retries:
            print(f"🚨 최대 재시도 횟수({self.max_retries}) 초과")
            return False
        
        if retry_after:
            # Discord가 명시한 대기 시간 준수
            if retry_after > 3600:  # 60분 초과 시 포기
                print(f"🚨 심각한 Rate Limit: {retry_after}초 ({retry_after/60:.1f}분)")
                print("🛑 60분을 초과하므로 봇을 종료합니다. 토큰 재생성을 고려해주세요.")
                return False
            
            # 60분 이내면 Discord가 지정한 시간 그대로 대기
            wait_time = retry_after
            if retry_after > 300:  # 5분 초과 시 추가 정보 제공
                print(f"⚠️ 긴 Rate Limit: {retry_after}초 ({retry_after/60:.1f}분)")
                print("📋 가능한 원인:")
                print("   • Invalid Request Limit (Cloudflare 차단)")
                print("   • 글로벌 Rate Limit 초과")
                print("   • 토큰 남용 감지")
            print(f"⏰ Discord 지정 대기: {wait_time}초 ({wait_time/60:.1f}분)")
        else:
            # 지수 백오프 계산 (Discord 권장)
            exponential_delay = self.base_delay * (2 ** (self.retry_count - 1))
            jitter = random.uniform(0, 1)  # 지터 추가 (동시 요청 방지)
            wait_time = min(exponential_delay + jitter, self.max_delay)
            
            print(f"📈 지수 백오프 대기: {wait_time:.1f}초 (재시도 {self.retry_count}/{self.max_retries})")
        
        print(f"⏳ {wait_time:.0f}초 대기 시작...")
        await asyncio.sleep(wait_time)
        print(f"✅ {wait_time:.0f}초 대기 완료, 재시도합니다")
        return True
    
    def reset(self):
        """성공 시 카운터 리셋"""
        self.retry_count = 0

    def is_rate_limit_error(self, error) -> tuple[bool, float]:
        """
        Rate Limit 에러인지 확인하고 대기시간 반환
        Returns: (is_rate_limit, retry_after)
        """
        retry_after = 0
        
        if isinstance(error, discord.HTTPException):
            if error.status == 429:  # 디스코드 레이트 리밋
                # Discord 공식 정책: retry_after 필드 또는 Retry-After 헤더 사용
                if hasattr(error, 'retry_after') and error.retry_after:
                    retry_after = float(error.retry_after)
                else:
                    retry_after = float(error.response.headers.get("Retry-After", 0))
                
                # 글로벌 Rate Limit 확인
                is_global = error.response.headers.get("X-RateLimit-Global") == "true"
                scope = error.response.headers.get("X-RateLimit-Scope", "unknown")
                
                print(f"🔍 Rate Limit 정보: scope={scope}, global={is_global}, retry_after={retry_after}")
                return True, retry_after
            elif error.status == 503:  # 서비스 불가
                return True, 30
        
        # Cloudflare Rate Limit 감지
        error_str = str(error).lower()
        if any(phrase in error_str for phrase in [
            "rate limit", "too many requests", "error 1015", 
            "cloudflare", "being rate limited"
        ]):
            print("🚨 Cloudflare Rate Limit 감지 - Invalid Request Limit 가능성")
            return True, 60
        
        return False, 0

async def safe_send(ctx_or_channel, content=None, **kwargs):
    """
    Rate Limit 안전한 메시지 전송
    Discord 정책을 완전히 준수하는 중앙집중식 전송 함수
    """
    max_attempts = 3
    local_handler = RateLimitHandler()
    
    for attempt in range(max_attempts):
        try:
            if hasattr(ctx_or_channel, 'send'):
                # Context 또는 Channel 객체
                return await ctx_or_channel.send(content, **kwargs)
            else:
                # 기타 경우
                return await ctx_or_channel.send(content, **kwargs)
                
        except Exception as e:
            is_rate_limit, retry_after = local_handler.is_rate_limit_error(e)
            
            if is_rate_limit:
                if attempt < max_attempts - 1:  # 마지막 시도가 아니면
                    should_continue = await local_handler.handle_rate_limit(retry_after)
                    if should_continue:
                        continue
                

                logging.warning(f"메시지 전송 Rate Limit: {e}")
                return None
            else:
                # Rate Limit이 아닌 다른 에러
                print(f"❌ 메시지 전송 실패: {type(e).__name__}: {e}")
                if hasattr(ctx_or_channel, 'channel'):
                    print(f"📍 채널: {ctx_or_channel.channel.name}")
                elif hasattr(ctx_or_channel, 'name'):
                    print(f"📍 채널: {ctx_or_channel.name}")
                print(f"📝 전송 실패한 메시지: {str(content)[:100]}...")
                return None
    
    return None

# 글로벌 Rate Limit 핸들러
rate_limit_handler = RateLimitHandler()

# on_ready 이벤트
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📡 봇이 {len(bot.guilds)}개의 서버에 연결되어 있습니다.')
    print('Commands:', [cmd.name for cmd in bot.commands])
    print('='*50)
    
    # 성공적 연결 시 Rate Limit 카운터 리셋
    rate_limit_handler.reset()

# 오류 처리
@bot.event
async def on_command_error(ctx, error):
    # HTTPException (429 등)이 발생한 경우 Discord로 메시지를 보내지 않음
    if isinstance(error, discord.HTTPException):
        if error.status == 429:
            # Rate Limit 발생 시 안전하게 처리
            retry_after = float(error.response.headers.get("Retry-After", 0))
            logging.warning(f"명령어 실행 중 Rate Limit 발생: {retry_after}초")
        print(f"Discord HTTP 오류 발생 (메시지 전송 안함): {error}")
        return
    
    # 사용자 경험을 위한 안전한 에러 메시지 전송 (safe_send 사용)
    if isinstance(error, commands.CommandNotFound):
        await safe_send(ctx, f"❌ '{ctx.message.content}' 명령어를 찾을 수 없습니다. `/도움`을 입력해보세요.")
    elif isinstance(error, commands.MissingPermissions):
        await safe_send(ctx, "❌ 이 명령어를 사용할 권한이 없습니다.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await safe_send(ctx, f"❌ 필수 인수가 누락되었습니다. `/도움 {ctx.command}`을(를) 확인해보세요.")
    elif isinstance(error, commands.CommandOnCooldown):
        await safe_send(ctx, f"⏰ 잠시만요! {error.retry_after:.0f}초 후에 다시 시도해주세요.")
    else:
        await safe_send(ctx, f"❌ 명령어 실행 중 오류가 발생했습니다.")
        print(f"기타 오류 상세: {error}")
        
    # 전송 실패 시 콘솔 로그만 기록 (safe_send에서 이미 처리)

async def load_cogs():
    """모든 cog를 로드합니다."""
    cogs_to_load = [
        'cogs.hello',
        'cogs.help',  # 안전한 cog들을 먼저 로드
        'cogs.news',
        'cogs.player',
        'cogs.schedule'  # 이미지 처리가 있는 cog를 마지막에
    ]    
    
    successful_cogs = []
    failed_cogs = []
    
    for cog in cogs_to_load:
        try:
            print(f'🔄 {cog} 로드 시작...')
            await bot.load_extension(cog)
            print(f'✅ {cog} 로드 완료')
            successful_cogs.append(cog)
        except Exception as e:
            print(f'❌ {cog} 로드 실패: {e}')
            print(f'❌ 상세 오류: {type(e).__name__}: {e}')
            failed_cogs.append(cog)
            import traceback
            traceback.print_exc()
            
    print(f"\n📊 Cog 로드 결과:")
    print(f"✅ 성공: {len(successful_cogs)}개 - {', '.join(successful_cogs)}")
    if failed_cogs:
        print(f"❌ 실패: {len(failed_cogs)}개 - {', '.join(failed_cogs)}")
        print(f"⚠️ 실패한 기능들은 사용할 수 없지만, 봇은 정상 작동합니다.")
    else:
        print(f"🎉 모든 Cog가 성공적으로 로드되었습니다!")

async def shutdown(signal_received, loop):
    """종료 신호를 처리하는 함수"""
    print(f"🛑 종료 신호 {signal_received.name} 수신됨...")
    print("📡 Discord 연결을 종료하는 중...")
    if not bot.is_closed():
        await bot.close()
    print("✅ 봇이 안전하게 종료되었습니다.")
    loop.stop()

async def start_bot():
    """봇을 시작하고 429 에러 시 지수 백오프로 재시도합니다."""
    token = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        print("❌ DISCORD_BOT_TOKEN이 설정되지 않았습니다.")
        print("💡 .env 파일에 'DISCORD_BOT_TOKEN=your_token_here' 를 추가해주세요.")
        return

    print("🔑 토큰 확인 완료")
    
    max_startup_attempts = 3  # 시작 시도 횟수 제한
    attempt = 0
    
    while attempt < max_startup_attempts:
        attempt += 1
        try:
            print(f"🚀 Discord 서버 연결 시도 중... ({attempt}/{max_startup_attempts})")
            await bot.start(token)
            break  # 성공 시 루프 종료
            
        except discord.LoginFailure as e:
            print("❌ 잘못된 토큰입니다. 봇을 종료합니다.")
            print("💡 Discord Developer Portal에서 토큰을 확인해주세요.")
            return
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get("Retry-After", 0))
                
                print(f"⏰ Discord Rate Limit 발생!")
                print(f"📊 상태 코드: {e.status}")
                print(f"⏱️ 대기 시간: {retry_after}초 ({retry_after/60:.1f}분)")
                
                # Rate Limit 처리
                should_continue = await rate_limit_handler.handle_rate_limit(retry_after)
                if not should_continue:
                    print("🛑 Rate Limit 처리 실패. 봇을 종료합니다.")
                    print("💡 토큰 재생성 후 1-2시간 뒤 다시 시도해주세요.")
                    return
                continue
            elif e.status == 401:
                print("❌ 인증 실패: 토큰이 유효하지 않습니다.")
                print("💡 .env 파일의 DISCORD_BOT_TOKEN을 확인해주세요.")
                return
            elif e.status == 403:
                print("❌ 권한 없음: 봇이 해당 서버에 접근할 권한이 없습니다.")
                return
            else:
                print(f"❌ Discord HTTP 에러: {e.status} - {e}")
                if attempt >= max_startup_attempts:
                    print("🛑 최대 시도 횟수 초과. 봇을 종료합니다.")
                    return
                await asyncio.sleep(5)  # 5초 대기 후 재시도
                continue
                
        except Exception as e:
            error_str = str(e)
            print(f"❌ 봇 시작 중 에러: {error_str}")
            
            # 네트워크 연결 문제 등 일반적인 에러 처리
            if attempt >= max_startup_attempts:
                print("🛑 최대 시도 횟수 초과. 봇을 종료합니다.")
                return
            
            print(f"🔄 5초 후 재시도...")
            await asyncio.sleep(5)
            continue

async def main():
    """메인 실행 함수"""
    print("🚀 이스포츠 뉴스 봇을 시작합니다...")

    # 봇의 이벤트 루프 가져오기
    loop = asyncio.get_event_loop()
    
    # Windows에서는 signal handler 사용 불가, try-except로 처리
    try:
        # Render가 보내는 SIGTERM 신호를 받았을 때 shutdown 함수를 실행하도록 등록
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))
        print("✅ Signal handlers 등록 완료")
    except NotImplementedError:
        # Windows에서는 signal handler가 지원되지 않음
        print("⚠️ Windows 환경: Signal handlers 건너뜀")
    
    # Cog 로드
    print("📂 Cog 로드 시작...")
    await load_cogs()

    # 봇 시작
    print("🔗 Discord 연결 시작...")
    await start_bot()

if __name__ == '__main__':
    # 서버 핑용 웹페이지(keep-alive) 기동
    keep_alive()

    asyncio.run(main())