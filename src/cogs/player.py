from discord.ext import commands
from crawlers.player_crawling import search_lol_players, search_valorant_players, fetch_valorant_player_info, search_lol_players_individual

import discord
import re
from datetime import datetime
import aiohttp
import asyncio
from urllib.parse import urlparse

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

GAME_NAME = {
    "롤": "lol",
    "LOL": "lol",
    "lol": "lol",
    "발로란트": "valorant",
    "발로": "valorant",
    "VALORANT": "valorant",
    "valorant": "valorant",
    "오버워치": "overwatch",
    "OVERWATCH": "overwatch",
    "overwatch": "overwatch",
}

import discord
from datetime import datetime

def format_url(url: str) -> str | None:
    """URL을 안전하게 포맷하고 유효성을 검사하는 함수"""
    if not url or not isinstance(url, str):
        return None
    
    # 공백 제거
    url = url.strip()
    if not url:
        return None
    
    # // 로 시작하는 경우 https: 추가
    if url.startswith('//'):
        url = "https:" + url
    # http나 https로 시작하지 않는 경우 https:// 추가
    elif not url.startswith(('http://', 'https://')):
        url = "https://" + url
    
    # URL 유효성 검사
    try:
        parsed = urlparse(url)
        # 기본 검사: scheme과 netloc이 있는지
        if not parsed.netloc or parsed.scheme not in ('http', 'https'):
            return None
        
        # 특수문자나 공백 검사
        if any(char in url for char in [' ', '\n', '\r', '\t']):
            return None
        
        # 기본적인 이미지 확장자 검사 (선택사항)
        if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) and 'image' not in url.lower():
            # 이미지가 아닐 수도 있지만 일단 통과
            pass
            
        return url
    except Exception as e:
        print(f"URL 파싱 오류: {e}, URL: {url}")
        return None

def create_player_embed(player_info: dict, game_name: str = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎮 {player_info.get('player_name', 'N/A')}",
        url=player_info.get('player_link'),
        color=0xff4654,
        timestamp=datetime.now()
    )

    player_image_url = format_url(player_info.get('player_image'))
    if player_image_url:
        try:
            embed.set_thumbnail(url=player_image_url)
        except Exception as e:
            print(f"썸네일 설정 실패: {e}, URL: {player_image_url}")

    if current_teams := player_info.get('current_teams'):
        current_team = current_teams[0]
        team_logo_url = format_url(current_team.get('team_logo'))
        try:
            if team_logo_url:
                embed.set_author(
                    name=f"🏆 Current Team: {current_team.get('team_name', 'N/A')}",
                    icon_url=team_logo_url
                )
            else:
                embed.set_author(name=f"🏆 Current Team: {current_team.get('team_name', 'N/A')}")
        except Exception as e:
            print(f"Author 설정 실패: {e}, URL: {team_logo_url}")
            embed.set_author(name=f"🏆 Current Team: {current_team.get('team_name', 'N/A')}")

    if real_name := player_info.get('real_name'):
        embed.add_field(name="실명", value=real_name, inline=False)
    
    if current_teams:
        current_team = current_teams[0]

        team_period = current_team.get('team_period', '정보 없음')
        if not team_period.startswith('Contract Expires:'):
            embed.add_field(
                name="입단일",
                value=team_period,
                inline=False
            )
        # 롤일 때 계약 만료일 추가
        if game_name == "lol":
            contract_expires = None
            if current_team.get('team_period', '').startswith('Contract Expires: '):
                contract_expires = current_team['team_period'].replace('Contract Expires: ', '').strip()
            if contract_expires:
                try:
                    date_obj = datetime.strptime(contract_expires, "%Y-%m-%d")
                    contract_expires_str = date_obj.strftime("%Y.%m.%d")
                except Exception:
                    contract_expires_str = contract_expires
                embed.add_field(
                    name="계약 만료일",
                    value=contract_expires_str,
                    inline=False
                )

    if past_teams := player_info.get('past_teams'):
        past_teams_list = [
            f"• **{team.get('team_name', 'N/A')}** ({team.get('team_period', '')})" 
            for team in past_teams[:5]
        ]
        if len(past_teams) > 5:
            footer_text = f"\n\n*총 {len(past_teams)}개 팀 중 5개만 표시됩니다.*"
            past_teams_list.append(footer_text)
        past_teams_text = "\n".join(past_teams_list)
        embed.add_field(
            name="📚 과거 팀 이력",
            value=past_teams_text or "정보 없음",
            inline=False
        )
    return embed

def extract_korean(text):
    """문장에서 한글(이름) 부분만 추출, 없으면 None 반환"""
    m = re.search(r'[(（](.*?)[)）]', text)
    if m:
        korean = m.group(1).strip()

        if re.search(r'[가-힣]', korean):
            return korean

    return None

class PlayerButton(discord.ui.Button):
    def __init__(self, player_data: dict, label: str, row: int, game_type: str = "valorant"):
        super().__init__(label=label, emoji='🔍', style=discord.ButtonStyle.primary, row=row)
        self.player_data = player_data
        self.game_type = game_type
    
    async def callback(self, interaction: discord.Interaction):
        # 즉시 응답 - 3초 제한 때문에 빠르게 처리
        await interaction.response.send_message("선수 정보를 가져오는 중입니다... ⏳")
        
        try:
            if self.game_type == "valorant":
                player_name = self.player_data.get('player_name')
                real_name = self.player_data.get('real_name')
                player_link = self.player_data.get('player_link')
                
                # 선수 상세 정보 가져오기
                player_info = await fetch_valorant_player_info(player_name, real_name, player_link)
                
                # player_info가 비어있거나 None인 경우 처리
                if not player_info:
                    await interaction.edit_original_response(content="해당 선수의 정보를 찾을 수 없습니다.")
                    return
                
                # 분리된 함수를 호출하여 임베드 생성
                embed = create_player_embed(player_info, game_name="valorant")
                
            elif self.game_type == "lol":
                search_player_name = self.player_data.get('search_player_name')
                player_label = self.player_data.get('player_label')
                
                # 롤 선수 상세 정보 가져오기 (동기 함수를 비동기로 래핑)
                loop = asyncio.get_event_loop()
                player_info = await loop.run_in_executor(None, search_lol_players_individual, search_player_name)
                
                # player_info가 비어있거나 None인 경우 처리
                if not player_info:
                    await interaction.edit_original_response(content="해당 선수의 정보를 찾을 수 없습니다.")
                    return
                
                # 분리된 함수를 호출하여 임베드 생성
                embed = create_player_embed(player_info, game_name="lol")
            
            # 원래 메시지를 임베드로 교체
            await interaction.edit_original_response(content=None, embed=embed)

        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="⏰ 시간 초과: 서버 응답이 느려 정보를 가져올 수 없습니다.")
        except Exception as e:
            print(f"An error occurred in player info callback: {e}")
            await interaction.edit_original_response(content="정보를 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")

class PlayerView(discord.ui.View):
    def __init__(self, player_results: list[dict], page: int = 0, per_page: int = 5, game_type: str = "valorant"):
        super().__init__(timeout=300)
        self.player_results = player_results
        self.page = page
        self.per_page = per_page
        self.game_type = game_type

        start = page * per_page
        end = start + per_page
        current_page_players = player_results[start:end]
        total_pages = (len(player_results) + per_page - 1) // per_page

        for idx, player in enumerate(current_page_players, start=start + 1):
            if self.game_type == "valorant":
                real_name = player.get('real_name')
                label = f"{idx}. {player['player_name']}"
                if real_name:
                    korean_name = extract_korean(real_name)
                    if korean_name:
                        label = f"{idx}. {player['player_name']} ({korean_name})"
                    else:
                        label = f"{idx}. {player['player_name']} ({real_name})"
            elif self.game_type == "lol":
                player_label = player.get('player_label', player.get('search_player_name', ''))
                label = f"{idx}. {player_label}"
            
            row_num = (idx - start - 1) // 5
            self.add_item(
                PlayerButton(
                    player_data=player,
                    label=label,
                    row=row_num,
                    game_type=self.game_type
                )
            )

        nav_row = 4
        nav_buttons = [None] * 5

        if page > 0:
            nav_buttons[0] = PrevPageButton(page - 1, player_results, per_page, self.game_type, row=nav_row)
        if end < len(player_results):
            nav_buttons[4] = NextPageButton(page + 1, player_results, per_page, self.game_type, row=nav_row)

        nav_buttons[2] = discord.ui.Button(
            label=f"{page+1} / {total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=nav_row
        )

        for b in nav_buttons:
            if b is None:
                self.add_item(discord.ui.Button(label="·", disabled=True, style=discord.ButtonStyle.secondary, row=nav_row))
            else:
                self.add_item(b)

class PrevPageButton(discord.ui.Button):
    def __init__(self, page, player_results, per_page, game_type, row=4):
        super().__init__(label='⬅️ 이전', style=discord.ButtonStyle.secondary, row=row)
        self.page = page
        self.player_results = player_results
        self.per_page = per_page
        self.game_type = game_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=PlayerView(self.player_results, self.page, self.per_page, self.game_type)
        )

class NextPageButton(discord.ui.Button):
    def __init__(self, page, player_results, per_page, game_type, row=4):
        super().__init__(label='다음 ➡️', style=discord.ButtonStyle.secondary, row=row)
        self.page = page
        self.player_results = player_results
        self.per_page = per_page
        self.game_type = game_type

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=PlayerView(self.player_results, self.page, self.per_page, self.game_type)
        )

class PlayerCommand(commands.Cog):    
    @commands.command(name='선수', help='선수 정보 확인 (ex) /선수 발로란트 k1ng')
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def show_player_info(self, ctx: commands.Context, game_name: str, player_name: str):
        if game_name not in GAME_NAME:
            await safe_send(ctx, f"지원하지 않는 게임입니다. 지원 게임: {', '.join(GAME_NAME.keys())}")
            return
        
        game_name = GAME_NAME[game_name]
        player_name = player_name.lower().capitalize()
        
        try:
            if game_name == "lol":
                # 롤 선수 검색 (동기 함수를 비동기로 래핑)
                loop = asyncio.get_event_loop()
                player_results = await loop.run_in_executor(None, search_lol_players, player_name)

                if not player_results:
                    await safe_send(ctx, "❌ 롤 선수 검색 결과가 존재하지 않습니다!")
                    return

                embed = discord.Embed(
                    title=f"🔍 '{player_name}' 닉네임 검색 결과",
                    description=f"동명이인 또는 유사 닉네임이 {len(player_results)} 명 검색되었습니다. 아래에서 확인하세요."
                )
                
                await safe_send(ctx, embed=embed, view=PlayerView(player_results, game_type="lol"))
                
            elif game_name == "valorant":
                player_results = search_valorant_players(player_name)
                
                if not player_results:
                    await safe_send(ctx, "❌ 발로란트 선수 검색 결과가 존재하지 않습니다!")
                    return
                
                embed = discord.Embed(
                    title=f"🔍 '{player_name}' 닉네임 검색 결과",
                    description="동명이인 또는 유사 닉네임이 여러 명 검색되었습니다. 아래에서 확인하세요."
                )

                await safe_send(ctx, embed=embed, view=PlayerView(player_results, game_type="valorant"))
                
        except Exception as e:
            print(f"선수 검색 중 오류 발생: {e}")
            await safe_send(ctx, "❌ 선수 검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCommand(bot))