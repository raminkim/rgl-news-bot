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
        self.max_retries = 5  # 최대 재시도 횟수
        self.max_delay = 300  # 최대 대기 시간 (5분)
    
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
            if retry_after > 3600:  # 1시간 초과 시 포기
                print(f"🚨 심각한 Rate Limit: {retry_after}초 ({retry_after/60:.1f}분)")
                print("🛑 봇을 종료합니다. 토큰 재생성을 고려해주세요.")
                return False
            
            wait_time = retry_after
            print(f"⏰ Discord 지정 대기: {wait_time}초 ({wait_time/60:.1f}분)")
        else:
            # 지수 백오프 계산 (Discord 권장)
            exponential_delay = self.base_delay * (2 ** (self.retry_count - 1))
            jitter = random.uniform(0, 1)  # 지터 추가 (동시 요청 방지)
            wait_time = min(exponential_delay + jitter, self.max_delay)
            
            print(f"📈 지수 백오프 대기: {wait_time:.1f}초 (재시도 {self.retry_count}/{self.max_retries})")
        
        print(f"⏳ {wait_time:.0f}초 대기 시작...")
        start_time = asyncio.get_event_loop().time()
        await asyncio.sleep(wait_time)
        end_time = asyncio.get_event_loop().time()
        actual_wait = end_time - start_time
        print(f"✅ {actual_wait:.1f}초 대기 완료 (예상: {wait_time:.0f}초), 재시도합니다")
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
                retry_after = float(error.response.headers.get("Retry-After", 0))
                return True, retry_after
            elif error.status == 503:  # 서비스 불가
                return True, 60
        
        # Cloudflare Rate Limit 감지
        error_str = str(error).lower()
        if any(phrase in error_str for phrase in [
            "rate limit", "too many requests", "error 1015", 
            "cloudflare", "being rate limited"
        ]):
            return True, 120
        
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
                
                # Rate Limit 처리 실패 시 콘솔에만 기록
                logging.warning(f"메시지 전송 Rate Limit: {e}")
                return None
            else:
                # Rate Limit이 아닌 다른 에러
                logging.error(f"메시지 전송 실패: {e}")
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
    
    # 뉴스 루프 시작 (봇 연결 완료 후)
    try:
        news_cog = bot.get_cog('NewsCommand')
        if news_cog:
            # 이미 실행 중인 루프가 있다면 중지
            if news_cog.news_loop.is_running():
                news_cog.news_loop.cancel()
                print("🔄 기존 뉴스 루프 중지됨")
                
            # 새로운 루프 시작
            news_cog.news_loop.start()
            print("✅ 뉴스 자동 전송 루프 시작됨")
        else:
            print("⚠️ NewsCommand Cog를 찾을 수 없습니다")
    except Exception as e:
        print(f"⚠️ 뉴스 루프 시작 실패: {e}")
        print("⚠️ 뉴스 자동 전송은 비활성화됩니다. 수동 명령어는 여전히 사용 가능합니다.")

@bot.event
async def on_disconnect():
    """게이트웨이 연결 끊김 시 뉴스 루프를 일시 중단합니다."""
    news_cog = bot.get_cog('NewsCommand')
    if news_cog and news_cog.news_loop.is_running():
        news_cog.news_loop.cancel()
        print("🔌 연결 끊김 → 뉴스 루프 일시 중단")

@bot.event
async def on_resumed():
    """세션 재개 시 뉴스 루프를 다시 시작합니다."""
    news_cog = bot.get_cog('NewsCommand')
    if news_cog and not news_cog.news_loop.is_running():
        news_cog.news_loop.start()
        print("🔄 세션 재개 → 뉴스 루프 재시작")

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
    
    while True:
        try:
            print("🚀 Discord 서버 연결 시도 중...")
            await bot.start(token)
            break  # 성공 시 루프 종료
            
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get("Retry-After", 0))
                
                print(f"⏰ Discord Rate Limit 발생!")
                print(f"📊 상태 코드: {e.status}")
                print(f"⏱️ 대기 시간: {retry_after}초 ({retry_after/60:.1f}분)")
                
                # 지수 백오프로 Rate Limit 처리
                should_continue = await rate_limit_handler.handle_rate_limit(retry_after)
                if not should_continue:
                    print("🛑 Rate Limit 처리 실패. 봇을 종료합니다.")
                    print("💡 토큰 재생성 후 1-2시간 뒤 다시 시도해주세요.")
                    return
                continue
            else:
                print(f"❌ Discord HTTP 에러: {e.status} - {e}")
                should_continue = await rate_limit_handler.handle_rate_limit()
                if not should_continue:
                    return
                continue
                
        except Exception as e:
            error_str = str(e)
            print(f"❌ 봇 시작 중 에러: {error_str}")
            
            if "429" in error_str or "Too Many Requests" in error_str or "rate limit" in error_str.lower():
                print("🔍 Rate Limit 에러로 감지됨")
                # 문자열에서 Rate Limit 감지
                should_continue = await rate_limit_handler.handle_rate_limit()
                if not should_continue:
                    print("🛑 Rate Limit 처리 실패. 봇을 종료합니다.")
                    return
                continue
            else:
                print("🔍 일반 에러로 판단, 재시도")
                should_continue = await rate_limit_handler.handle_rate_limit()
                if not should_continue:
                    return
                continue

async def main():
    """메인 실행 함수"""
    print("🚀 이스포츠 뉴스 봇을 시작합니다...")

    # 봇의 이벤트 루프 가져오기
    loop = asyncio.get_event_loop()
    
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))
        print("✅ Signal handlers 등록 완료")
    except NotImplementedError:
        print("⚠️ Windows 환경: Signal handlers 건너뜀")
    
    # Cog 로드
    print("📂 Cog 로드 시작...")
    await load_cogs()

    # 봇 시작
    print("🔗 Discord 연결 시작...")
    await start_bot()

if __name__ == '__main__':
    keep_alive()

    asyncio.run(main())