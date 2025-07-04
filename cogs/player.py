from discord.ext import commands
from crawlers.player_crawling import search_valorant_players

import discord
import re

GAME_NAME = {
    "롤": "leagueofLegends",
    "LOL": "leagueofLegends",
    "lol": "leagueofLegends",
    "발로란트": "valorant",
    "VALORANT": "valorant",
    "valorant": "valorant",
    "오버워치": "overwatch",
    "OVERWATCH": "overwatch",
    "overwatch": "overwatch",
}

def extract_korean(text):
    """문장에서 한글(이름) 부분만 추출, 없으면 None 반환"""
    m = re.search(r'[(（](.*?)[)）]', text)
    if m:
        korean = m.group(1).strip()

        if re.search(r'[가-힣]', korean):
            return korean

    return None

class PlayerView(discord.ui.View):
    def __init__(self, player_results: list[dict], page: int = 0, per_page: int = 5):
        super().__init__(timeout=300)
        self.player_results = player_results
        self.page = page
        self.per_page = per_page

        start = page * per_page
        end = start + per_page
        current_page_players = player_results[start:end]
        total_pages = (len(player_results) + per_page - 1) // per_page

 
        for idx, player in enumerate(current_page_players, start=start + 1):
            real_name = player.get('real_name')
            label = f"{idx}. {player['player_name']}"
            if real_name:
                korean_name = extract_korean(real_name)
                if korean_name:
                    label = f"{idx}. {player['player_name']} ({korean_name})"
                else:
                    label = f"{idx}. {player['player_name']} ({real_name})"
            row_num = (idx - start - 1) // 5
            self.add_item(
                discord.ui.Button(
                    label=label,
                    url=player['player_link'],
                    emoji='🔍',
                    style=discord.ButtonStyle.primary,
                    row=row_num
                )
            )


        nav_row = 4
        nav_buttons = [None] * 5

        if page > 0:
            nav_buttons[0] = PrevPageButton(page - 1, player_results, per_page, row=nav_row)
        if end < len(player_results):
            nav_buttons[4] = NextPageButton(page + 1, player_results, per_page, row=nav_row)

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
    def __init__(self, page, player_results, per_page, row=4):
        super().__init__(label='⬅️ 이전', style=discord.ButtonStyle.secondary, row=row)
        self.page = page
        self.player_results = player_results
        self.per_page = per_page

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=PlayerView(self.player_results, self.page, self.per_page)
        )

class NextPageButton(discord.ui.Button):
    def __init__(self, page, player_results, per_page, row=4):
        super().__init__(label='다음 ➡️', style=discord.ButtonStyle.secondary, row=row)
        self.page = page
        self.player_results = player_results
        self.per_page = per_page

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=PlayerView(self.player_results, self.page, self.per_page)
        )

class PlayerCommand(commands.Cog):    
    @commands.command(name='선수', help='선수 정보 확인 (ex) /선수 발로란트 k1ng')
    async def show_player_info(self, ctx: commands.Context, game_name: str, player_name: str):
        if game_name not in GAME_NAME:
            await ctx.send(f"지원하지 않는 게임입니다. 지원 게임: {', '.join(GAME_NAME.keys())}")
            return
        
        player_results = search_valorant_players(player_name)
        if not player_results:
            await ctx.send("❌ 선수 검색 결과가 존재하지 않습니다!")
            return
        
        embed = discord.Embed(
            title=f"🔍 '{player_name}' 닉네임 검색 결과",
            description="동명이인 또는 유사 닉네임이 여러 명 검색되었습니다. 아래에서 확인하세요."
        )

        await ctx.send(embed=embed, view=PlayerView(player_results))


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCommand(bot))