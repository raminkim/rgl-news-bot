import discord
import pytz
from typing import List, Dict, Any, Callable

from discord.ext import commands, tasks
from datetime import date, datetime

from crawlers.news_crawling import lol_news_articles, valorant_news_articles, overwatch_news_articles

class NewsCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_games = {}  # 채널과 게임 이름 매칭

    def create_news_embed(self, article: Dict[str, Any]):
        """
        뉴스 기사를 위한 디스코드 Embed 객체를 생성합니다.

        Args:
            article (Dict[str, Any]): 네이버 e스포츠 뉴스 API에서 가져온 기사 데이터.
                필수 키:
                    - title (str): 기사 제목
                    - subContent (str): 요약 내용
                    - linkUrl (str): 기사 URL
                    - thumbnail (str): 썸네일 이미지 URL
                    - createdAt (int): 생성 시각 (밀리초 단위 타임스탬프)
                    - officeName (str): 언론사 이름
                    - rank (int): 순위
                    - hitCount (int): 조회수

        Returns:
            discord.Embed: 제목, 설명, URL, 타임스탬프, 썸네일, 푸터(언론사·순위) 등이 설정된 Embed 객체
        """

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

        # 1) 원본 밀리초를 초 단위로 변환
        ts_seconds = article['createdAt'] / 1000
        # 2) KST 기준 datetime 객체 생성
        kst = pytz.timezone("Asia/Seoul")
        dt = datetime.fromtimestamp(ts_seconds, tz=kst)

        # 예: "2025-06-22 14:45:10"
        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        embed.add_field(
            name="⏰ 발행시간", 
            value=formatted,
            inline=False
        )

        return embed
    
    @tasks.loop(seconds=1200)
    async def news_loop(self):
        """
        20분마다 자동으로 새로운 기사를 확인하고,
        설정된 채널로 Embed 메시지를 전송합니다.
        """

        formatted_date = date.today().strftime('%Y-%m-%d')
        
        fetch_lol_articles = await self.safe_fetch_news(lol_news_articles, formatted_date, "롤")
        fetch_valorant_articles = await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트")
        fetch_overwatch_articles = await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치")
            
        for channel_id, game in self.channel_games.items():
            articles_to_send = []
            
            if "lol" in game:
                articles_to_send.extend(fetch_lol_articles)
            if "valorant" in game:
                articles_to_send.extend(fetch_valorant_articles)
            if "overwatch" in game:
                articles_to_send.extend(fetch_overwatch_articles)

            # 채널에 뉴스 설정이 되어 있지 않으면 넘어간다.
            if not articles_to_send:
                continue
            
            articles_to_send.sort(key=lambda x: x['createdAt'])

            channel = self.bot.get_channel(channel_id)
            if channel:
                for article in articles_to_send:
                    embed = self.create_news_embed(article)
                    await channel.send(embed=embed)

        now_done = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
        print(f"✅ [{now_done}] 뉴스 전송 완료")

    @commands.command(name='뉴스확인', help='현재 채널에 설정된 게임의 최신 뉴스를 가져옵니다.')
    async def check_news_now(self, ctx: commands.Context):
        """수동으로 뉴스를 확인합니다."""

        # 1. 현재 채널 설정 확인
        channel_games = self.channel_games.get(ctx.channel.id, [])

        if not channel_games:
            await ctx.send("❌ 이 채널은 뉴스 설정이 되어 있지 않습니다.\n`/뉴스채널설정 롤 발로란트 오버워치`로 설정해주세요!")
            return
        
        # 2. 설정된 게임별 뉴스 확인
        game_names = {"lol": "리그오브레전드", "valorant": "발로란트", "overwatch": "오버워치"}
        selected_names = [game_names[game] for game in channel_games]

        await ctx.send(f"🔍 현재 채널에 설정된 뉴스 채널: {ctx.channel.name} -> {', '.join(selected_names)}")

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
                await ctx.send("❌ 현재 새로운 뉴스가 없습니다.")
                return
            
            articles_to_send.sort(key=lambda x: x['createdAt'])

            await ctx.send(f"📢 새로운 뉴스 {len(articles_to_send)}개를 발견했습니다!")
            for article in articles_to_send[:10]:
                try:
                    embed = self.create_news_embed(article)
                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"❌ 뉴스 전송 중 오류: {e}")
                    continue
            
            if len(articles_to_send) > 10:
                await ctx.send(f"📋 총 {len(articles_to_send)}개 중 최신 10개만 표시했습니다.")
            
        except Exception as e:
            await ctx.send(f"❌ 뉴스 확인 중 오류가 발생했습니다: {e}")
            print(f"뉴스확인 명령어 오류: {e}")

    @commands.command(name='뉴스채널설정', help='채널별 게임 뉴스 설정. 매개변수 없이 입력하면 현재 설정 확인, 게임명 입력하면 설정 변경 (예: 롤 발로란트 오버워치)')
    @commands.has_guild_permissions(manage_channels=True)
    async def set_news_channel(self, ctx: commands.Context, *games: str):
        """
        채널 별 게임 뉴스 설정
        사용법: /뉴스채널설정 롤 발로란트 오버워치
        """

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
            "전체": ["lol", "valorant", "overwatch"]
        }

        game_names = {"lol": "리그오브레전드", "valorant": "발로란트", "overwatch": "오버워치"}

        # 게임이 지정되지 않았을 때 현재 설정 표시
        if not games:
            current_games = self.channel_games.get(ctx.channel.id, [])
            if current_games:
                current_names = [game_names[game] for game in current_games]
                await ctx.send(f"현재 설정된 뉴스 채널: {ctx.channel.name} -> {', '.join(current_names)}")
            else:
                await ctx.send("현재 설정된 뉴스 채널이 없습니다.")
            return

        # 입력된 게임들을 영어 코드로 변환
        selected_games = []

        for game in games:
            game_lower = game.lower()
            if game_lower in game_mapping:
                mapped = game_mapping[game_lower]
                if isinstance(mapped, list):
                    selected_games.extend(mapped)
                else:
                    selected_games.append(mapped)
            else:
                await ctx.send(f"❌ '{game}'는 지원하지 않는 게임명입니다.\n💡 **사용 가능한 게임:** 롤, 발로란트, 오버워치, 모든게임")
                return
            
        if not selected_games:
            return

        # 입력된 게임 중 중복 제거
        selected_games = list(set(selected_games))

        self.channel_games[ctx.channel.id] = selected_games
        selected_names = [game_names[game] for game in selected_games]

        print(f"📡 뉴스 채널 설정: {ctx.channel.name} -> {selected_names}")

        embed = discord.Embed(
            title="✅ 뉴스 채널 설정 완료",
            description=f"이제 {ctx.channel.mention}에서 **{', '.join(selected_names)}** 뉴스를 받습니다!",
            color=0x00ff56,
            timestamp=datetime.now(pytz.timezone("Asia/Seoul"))
        )

        await ctx.send(embed=embed)

        formatted_date = date.today().strftime('%Y-%m-%d')
        articles_to_send = []

        if "lol" in selected_games:
            articles_to_send.extend(await self.safe_fetch_news(lol_news_articles, formatted_date, "롤"))
        if "valorant" in selected_games:
            articles_to_send.extend(await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트"))
        if "overwatch" in selected_games:
            articles_to_send.extend(await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치"))
            
        if articles_to_send:
            articles_to_send.sort(key=lambda x: x['createdAt'])
            await ctx.send(f"📢 설정 완료! 최신 뉴스 {len(articles_to_send)}개를 확인했습니다:")
            for art in articles_to_send[:3]:
                embed = self.create_news_embed(art)
                await ctx.send(embed=embed)

        else:
            await ctx.send("📰 현재 새로운 뉴스가 없습니다.")

    async def safe_fetch_news(self, game_func: Callable, formatted_date: str, game_name: str):
        """안전하게 뉴스를 가져오는 헬퍼 함수"""
        try:
            articles = await game_func(formatted_date)
            print(f"✅ {game_name} 뉴스 {len(articles)}개 가져오기 성공")
            return articles
        except Exception as e:
            print(f"❌ {game_name} 뉴스 API 실패: {e}")
            return []

async def setup(bot: commands.Bot):
    await bot.add_cog(NewsCommand(bot))