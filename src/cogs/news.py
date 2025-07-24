import discord
import pytz
import asyncio
from typing import List, Dict, Any, Callable

from discord.ext import commands, tasks
from datetime import date, datetime, timedelta

from crawlers.news_crawling import lol_news_articles, valorant_news_articles, overwatch_news_articles
from db import load_all_channel_state, load_channel_state, save_channel_state, delete_channel_state, load_state, update_state

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
    

class NewsView(discord.ui.View):
    def __init__(self, info_embed, articles_to_send: List[Dict[str, Any]], page: int = 0, per_page: int = 4):
        super().__init__(timeout=300)
        self.info_embed = info_embed
        self.articles_to_send = articles_to_send
        self.page = page
        self.per_page = per_page
        self.total_pages = (len(articles_to_send) + per_page - 1) // per_page

        # 페이지네이션 버튼만 추가 (이전, 페이지, 다음 순서)
        self.prev_btn = self.PrevPageButton(self)
        self.page_info_btn = self.PageInfoButton(self)
        self.next_btn = self.NextPageButton(self)
        self.add_item(self.prev_btn)
        self.add_item(self.page_info_btn)
        self.add_item(self.next_btn)

    def get_page_articles(self):
        start = self.page * self.per_page
        end = start + self.per_page
        return self.articles_to_send[start:end]

    def get_embeds(self):
        embeds = [self.info_embed]
        for article in self.get_page_articles():
            embed = discord.Embed(
                title=article.get('title'),
                url=article.get('linkUrl'),
                color=0x1E90FF
            )
            if article.get('thumbnail'):
                embed.set_thumbnail(url=article['thumbnail'])
            ts = article.get('createdAt')
            if ts:
                dt = datetime.fromtimestamp(ts / 1000)
                # 한국식 시간 포맷
                kst = pytz.timezone("Asia/Seoul")
                dt_kst = dt.astimezone(kst)
                hour = dt_kst.hour
                minute = dt_kst.minute
                ampm = "오전" if hour < 12 else "오후"
                hour12 = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
                formatted = f"{dt_kst.strftime('%Y-%m-%d')} {ampm} {hour12}:{minute:02d}"
            else:
                formatted = "-"
            embed.add_field(
                name="⏰ 발행시간",
                value=formatted,
                inline=False
            )
            embeds.append(embed)
        return embeds

    class PrevPageButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(label="⬅️ 이전", style=discord.ButtonStyle.secondary, disabled=view.page == 0)
            self.view_ref = view
        async def callback(self, interaction: discord.Interaction):
            if self.view_ref.page > 0:
                self.view_ref.page -= 1
                await self.view_ref.update_message(interaction)

    class NextPageButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(label="다음 ➡️", style=discord.ButtonStyle.secondary, disabled=view.page == view.total_pages - 1)
            self.view_ref = view
        async def callback(self, interaction: discord.Interaction):
            if self.view_ref.page < self.view_ref.total_pages - 1:
                self.view_ref.page += 1
                await self.view_ref.update_message(interaction)

    class PageInfoButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(
                label=f"{view.page+1} / {view.total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )

    async def update_message(self, interaction: discord.Interaction):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page == self.total_pages - 1
        self.page_info_btn.label = f"{self.page+1} / {self.total_pages}"
        await interaction.response.edit_message(embeds=self.get_embeds(), view=self)
            
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

            state = await load_state()
            lol_last = state.get("lol", 0)
            valorant_last = state.get("valorant", 0)
            overwatch_last = state.get("overwatch", 0)

            # 1. 각 게임별로 lastProcessedAt 이후의 기사만 추출
            fetch_lol_articles = [article for article in await self.safe_fetch_news(lol_news_articles, formatted_date, "롤") if article["createdAt"] > lol_last]
            fetch_valorant_articles = [article for article in await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트") if article["createdAt"] > valorant_last]
            fetch_overwatch_articles = [article for article in await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치") if article["createdAt"] > overwatch_last]
            
            # 2. 뉴스가 없으면 종료
            if not (fetch_lol_articles or fetch_valorant_articles or fetch_overwatch_articles):
                return
            
            # 3. 뉴스 전송
            for channel_id, game_states in (await load_all_channel_state()).items():
                articles_to_send = []
                
                if game_states.get("lol", False):
                    articles_to_send.extend(fetch_lol_articles)
                if game_states.get("valorant", False):
                    articles_to_send.extend(fetch_valorant_articles)
                if game_states.get("overwatch", False):
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

            # 4. 각 게임별로 전송한 뉴스가 있다면, 가장 최신 createdAt만 update_state로 갱신
            if fetch_lol_articles:
                await update_state("lol", [max(fetch_lol_articles, key=lambda x: x["createdAt"])])
            if fetch_valorant_articles:
                await update_state("valorant", [max(fetch_valorant_articles, key=lambda x: x["createdAt"])])
            if fetch_overwatch_articles:
                await update_state("overwatch", [max(fetch_overwatch_articles, key=lambda x: x["createdAt"])])

            now_done = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
            print(f"✅ [{now_done}] 뉴스 전송 완료")
            
        except Exception as e:
            now_error = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
            print(f"❌ [{now_error}] 뉴스 루프 실행 중 오류: {e}")

    @commands.command(
    name='뉴스확인',
    help=(
        "원하는 날짜의 이스포츠 뉴스를 한눈에 확인할 수 있습니다.\n\n"
        "**▶️ 기본 사용법**\n"
        "└ `/뉴스확인` 또는 `/뉴스확인 오늘` : 오늘의 뉴스를 확인합니다.\n"
        "└ `/뉴스확인 어제` : 어제 뉴스를 확인합니다.\n\n"
        "**📅 날짜로 검색**\n"
        "└ `/뉴스확인 2025-07-14` : 해당 날짜의 뉴스를 확인합니다.\n"
        "└ `/뉴스확인 2025.07.14` 또는 `/뉴스확인 2025/07/14` 형식도 지원합니다.\n\n"
        "**ℹ️ 안내**\n"
        "- 오늘 이후의 날짜를 입력하거나, 잘못된 날짜 형식 입력 시 안내 메시지가 출력됩니다.\n"
        "- 뉴스가 없을 경우에도 안내 메시지가 출력됩니다.\n"
        "- 뉴스가 여러 개일 경우, 한 페이지에 4개씩 페이지네이션으로 보여집니다."
    )
)
    async def check_news_now(self, ctx: commands.Context, date_str: str = None):
        if not date_str:
            target_date = date.today()
        elif date_str.lower() == "오늘":
            target_date = date.today()
        elif date_str.lower() == "어제":
            target_date = date.today() - timedelta(days=1)
        else:
            for format in ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]:
                try:
                    target_date = datetime.strptime(date_str, format).date()
                    if target_date > date.today():
                        await safe_send(ctx, "❌ 날짜가 오늘 이후일 수 없습니다.\n\n자세한 사용법은 `/뉴스확인` 명령어를 참고해주세요!")
                        return
                    break
                except ValueError:
                    continue

        if not target_date:
            await safe_send(ctx, "❌ 날짜 형식이 올바르지 않습니다. \n 예시: `/뉴스확인 2025-07-14`\n\n자세한 사용법은 `/뉴스확인` 명령어를 참고해주세요!")
            return

        try:
            articles_to_send = []
            formatted_date = target_date.strftime('%Y-%m-%d')

            articles_to_send.extend(await self.safe_fetch_news(lol_news_articles, formatted_date, "롤"))
            articles_to_send.extend(await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트"))
            articles_to_send.extend(await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치"))

            articles_to_send.sort(key=lambda x: x['createdAt'], reverse=True)

            # 1. 뉴스 목록 embed (상단 안내)
            info_embed = discord.Embed(
                title=f"🔎 {formatted_date} 뉴스 검색 결과",
                description=f"총 {len(articles_to_send)}건의 뉴스가 검색되었습니다.\n아래에서 페이지를 넘겨 뉴스를 확인하세요.",
                color=0x1E90FF
            )

            # 뉴스가 없을 때 안내
            if not articles_to_send:
                info_embed.description = f"❌ 해당 {formatted_date} 날짜의 뉴스가 없습니다.\n\n자세한 사용법은 `/뉴스확인` 명령어를 참고해주세요!"
                await ctx.send(embed=info_embed)
                return
            else:
                await safe_send(ctx, f"{formatted_date} 날짜의 이스포츠 뉴스 찾는 중... 잠시만 기다려주세요! 🙏")
                await safe_send(ctx, f"📢 해당 {formatted_date} 날짜의 새로운 뉴스 {len(articles_to_send)}개를 발견했습니다!")

            # 2. NewsView
            view = NewsView(info_embed, articles_to_send, page=0, per_page=4)
            await ctx.send(embeds=view.get_embeds(), view=view)
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
        """
        뉴스 크롤링 함수를 실행하고, 뉴스 데이터를 반환합니다.
        뉴스 데이터가 없으면 빈 리스트를 반환합니다.

        Args:
            game_func: 뉴스 크롤링 함수
            formatted_date: 뉴스 크롤링 함수에 전달할 날짜 문자열
            game_name: 뉴스 크롤링 함수에 전달할 게임 이름

        Returns:
            list: 뉴스 데이터 리스트
        """
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