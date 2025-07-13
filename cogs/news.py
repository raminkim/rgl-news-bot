import discord
import pytz
import asyncio
from typing import List, Dict, Any, Callable

from discord.ext import commands, tasks
from datetime import date, datetime

from crawlers.news_crawling import lol_news_articles, valorant_news_articles, overwatch_news_articles
from db import load_all_channel_state, load_channel_state, save_channel_state, delete_channel_state

async def safe_send(ctx_or_channel, content=None, **kwargs):
    """Rate Limit 안전한 메시지 전송"""
    try:
        if hasattr(ctx_or_channel, 'send'):
            return await ctx_or_channel.send(content, **kwargs)
        else:
            return await ctx_or_channel.send(content, **kwargs)
    except Exception as e:
        print(f"메시지 전송 실패: {e}")
        return None

class NewsCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_games = {}

    async def cog_load(self):
        # 뉴스 루프는 봇 연결 완료 후 on_ready에서 시작
        print("📰 뉴스 시스템 로드 완료 (루프는 봇 연결 후 시작)")
        pass

    async def cog_unload(self):
        if self.news_loop.is_running():
            self.news_loop.cancel()
            print("❌ 뉴스 자동 전송 루프 중지됨")

    def create_news_embed(self, article: Dict[str, Any]):
        embed = discord.Embed(
            title=article.get('title'),
            description=article.get('subContent'),
            url=article.get('linkUrl'),
            timestamp=datetime.fromtimestamp(article["createdAt"] / 1000, tz=pytz.UTC),
            color=0x1E90FF
        )

        if article['thumbnail']:
            embed.set_thumbnail(url=article['thumbnail'])
        
        embed.add_field(
            name="🏆 순위", 
            value=f"#{article['rank']}", 
            inline=True
        )

        ts_seconds = article['createdAt'] / 1000
        kst = pytz.timezone("Asia/Seoul")
        dt = datetime.fromtimestamp(ts_seconds, tz=kst)

        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        embed.add_field(
            name="⏰ 발행시간", 
            value=formatted,
            inline=False
        )

        return embed
    
    @tasks.loop(seconds=1200)
    async def news_loop(self):
        if not self.bot.is_ready():
            return
        try:
            formatted_date = date.today().strftime('%Y-%m-%d')
            
            fetch_lol_articles = await self.safe_fetch_news(lol_news_articles, formatted_date, "롤")
            fetch_valorant_articles = await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트")
            fetch_overwatch_articles = await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치")
            
            for channel_id, game_states in (await load_all_channel_state()).items():
                articles_to_send = []
                
                if "lol" in game_states:
                    articles_to_send.extend(fetch_lol_articles)
                if "valorant" in game_states:
                    articles_to_send.extend(fetch_valorant_articles)
                if "overwatch" in game_states:
                    articles_to_send.extend(fetch_overwatch_articles)

                if not articles_to_send:
                    continue
                
                articles_to_send.sort(key=lambda x: x['createdAt'])

                channel = self.bot.get_channel(channel_id)
                if channel:
                    for i, article in enumerate(articles_to_send):
                        embed = self.create_news_embed(article)
                        await safe_send(channel, embed=embed)
                        
                        # 마지막 뉴스가 아니면 5초 대기
                        if i < len(articles_to_send) - 1:
                            await asyncio.sleep(5)

            now_done = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
            print(f"✅ [{now_done}] 뉴스 전송 완료")
            
        except Exception as e:
            now_error = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
            print(f"❌ [{now_error}] 뉴스 루프 실행 중 오류: {e}")

    @commands.command(name='뉴스확인', help='최근 뉴스를 조회합니다.')
    async def check_news_now(self, ctx: commands.Context):
        game_names = {"lol": "리그오브레전드", "valorant": "발로란트", "overwatch": "오버워치"}
        channel_games = [game_names[game] for game, enabled in (await load_channel_state(ctx.channel.id)).items() if enabled]

        if not channel_games:
            await safe_send(ctx, "❌ 이 채널은 뉴스 설정이 되어 있지 않습니다.\n`/뉴스채널설정 롤 발로란트 오버워치`로 설정해주세요!")
            return

        await safe_send(ctx, f"🔍 현재 채널에 설정된 뉴스 채널: {ctx.channel.name} -> {', '.join(channel_games)}")

        try:
            formatted_date = date.today().strftime('%Y-%m-%d')
            articles_to_send = []

            if "lol" in channel_games:
                articles_to_send.extend(await self.safe_fetch_news(lol_news_articles, formatted_date, "롤"))
            if "valorant" in channel_games:
                articles_to_send.extend(await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트"))
            if "overwatch" in channel_games:
                articles_to_send.extend(await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치"))

            if not articles_to_send:
                await safe_send(ctx, "❌ 현재 새로운 뉴스가 없습니다.")
                return
            
            articles_to_send.sort(key=lambda x: x['createdAt'])

            await safe_send(ctx, f"📢 새로운 뉴스 {len(articles_to_send)}개를 발견했습니다!")
            for i, article in enumerate(articles_to_send[-10:]):
                try:
                    embed = self.create_news_embed(article)
                    await safe_send(ctx, embed=embed)
                    
                    # 마지막 뉴스가 아니면 5초 대기
                    if i < min(len(articles_to_send), 10) - 1:
                        await asyncio.sleep(5)

                except Exception as e:
                    await safe_send(ctx, f"❌ 뉴스 전송 중 오류: {e}")
                    continue
            
            if len(articles_to_send) > 10:
                await safe_send(ctx, f"📋 총 {len(articles_to_send)}개 중 최신 10개만 표시했습니다.")
            
        except Exception as e:
            await safe_send(ctx, f"❌ 뉴스 확인 중 오류가 발생했습니다: {e}")
            print(f"뉴스확인 명령어 오류: {e}")

    @commands.command(
        name='뉴스채널설정',
        help=(
            '채널별 게임 뉴스 설정\n\n'
            '**게임별 설정:** `/뉴스채널설정 롤 발로란트 오버워치`\n'
            '**전체 설정:** `/뉴스채널설정 모든게임` 또는 `/뉴스채널설정 모두`\n'
            '**설정 해제:** `/뉴스채널설정 해제` 또는 `/뉴스채널설정 삭제`\n'
            '**설정 확인:** `/뉴스채널설정` (인자 없이)\n\n'
            '💡 **전체 설정 키워드:** 모든게임, 모두, 전체, ON, on\n'
            '💡 **해제 키워드:** 해제, 삭제, off, OFF'
        )
    )
    @commands.has_guild_permissions(manage_channels=True)
    async def set_news_channel(self, ctx: commands.Context, *games: str):
        # 한국어 게임명 매칭
        game_mapping = {
            "롤": "lol",
            "리그오브레전드": "lol", 
            "lol": "lol",
            "발로란트": "valorant",
            "발로": "valorant",
            "valorant": "valorant",
            "오버워치": "overwatch", 
            "오버": "overwatch",
            "overwatch": "overwatch",
            "모든게임": ["lol", "valorant", "overwatch"],
            "모두": ["lol", "valorant", "overwatch"],
            "전체": ["lol", "valorant", "overwatch"],
            "ON": ["lol", "valorant", "overwatch"],
            "on": ["lol", "valorant", "overwatch"],
        }

        game_names = {"lol": "리그오브레전드", "valorant": "발로란트", "overwatch": "오버워치"}

        if not games:
            loaded_games = await load_channel_state(ctx.channel.id)
            
            current_games = [game_names[game] for game, enabled in loaded_games.items() if enabled]
            if current_games:
                await safe_send(ctx, f"현재 '{ctx.channel.name}' 채널에 설정된 뉴스 설정값: -> {', '.join(current_games)}")
            else:
                await safe_send(ctx, "현재 채널은 뉴스 설정이 되어 있지 않습니다.\n`/뉴스채널설정 롤 발로란트 오버워치`과 같은 명령어로 설정해주세요!")
            return
        
        if len(games) == 1 and games[0] in ("해제", "삭제", "off", "OFF"):
            deleted = await delete_channel_state(ctx.channel.id)
            if deleted:
                await safe_send(ctx, f"✅ '{ctx.channel.name}' 채널의 뉴스 알림 설정이 해제되었습니다.")
            else:
                await safe_send(ctx, f"ℹ️ '{ctx.channel.name}' 채널은 이미 뉴스 알림 설정이 되어 있지 않습니다.")
            return

        selected_games = []
        for game in games:
            mapped = game_mapping.get(game.lower())
            if mapped is None:
                await safe_send(ctx, f"❌ '{game}'는 지원하지 않는 게임명입니다.\n💡 **사용 가능한 게임:** 롤, 발로란트, 오버워치\n💡 **전체 설정:** 모든게임, 모두, 전체, ON, on")
                return
            
            if isinstance(mapped, list):
                selected_games.extend(mapped)
            else:
                selected_games.append(mapped)

        # 채널 설정 저장
        channel_state = {game: True for game in list(set(selected_games))}
        for game in ["lol", "valorant", "overwatch"]:
            if game not in channel_state:
                channel_state[game] = False
                
        result: bool = await save_channel_state(ctx.channel.id, channel_state)

        # 채널 설정 저장 실패 시 오류 메시지 전송
        if not result:
            await safe_send(ctx, "❌ 뉴스 설정 저장 중 오류가 발생했습니다.\n봇 관리자에게 문의해주세요.")
            return

        if selected_games:
            selected_names = [game_names[game] for game in selected_games]
            
            embed = discord.Embed(
                title="📰 뉴스 채널 설정 완료",
                description=f"**채널:** {ctx.channel.name}\n**게임:** {', '.join(selected_names)}\n\n🔄 20분마다 자동으로 새로운 뉴스를 확인합니다.",
                color=0x00ff00
            )
            
            await safe_send(ctx, embed=embed)

    async def safe_fetch_news(self, game_func: Callable, formatted_date: str, game_name: str):
        try:
            news_data = await game_func(formatted_date)
            if news_data and isinstance(news_data, list):
                return news_data
            return []
        except Exception as e:
            print(f"{game_name} 뉴스 크롤링 오류: {e}")
            return []

async def setup(bot: commands.Bot):
    await bot.add_cog(NewsCommand(bot))