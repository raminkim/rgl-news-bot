from bs4 import BeautifulSoup
from urllib.parse import urljoin

import aiohttp
import requests
import asyncio

def search_valorant_players(player_name: str) -> list:
    """
    VLR 플레이어 검색 결과에서 플레이어 정보를 추출한다.
    
    Args:
        player_name (str): 검색할 플레이어 이름
    """
    url = f'https://www.vlr.gg/search/?q={player_name}&type=players'

    params = {
        'q': player_name,
        'type': 'players'
    }

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.22 Safari/537.36',
    }
    

    response = requests.get(url=url, params=params, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []

        for a in soup.select('div.wf-card a'):
            # a 태그 내부에서 닉네임 추출
            nickname_element = a.select_one('.search-item-title')
            if not nickname_element:
                continue

            nickname = nickname_element.get_text(strip=True)

            # 실명(또는 팀/추가 정보) 추출
            desc_el = a.select_one('.search-item-desc')
            real_name = desc_el.get_text(strip=True) if desc_el else ''

            player_link = urljoin(url, a['href'])

            results.append({
                'player_name': nickname,
                'real_name': real_name,
                'player_link': player_link
            })

        return results
    
    else:
        return None
    

async def fetch_valorant_player_info(player_name: str, real_name: str, player_link: str) -> dict:
    """
    VLR 플레이어 프로필 페이지에서 플레이어 정보를 추출한다.

    Args:
        player_name (str): 플레이어 닉네임
        real_name (str): 플레이어 실명
        player_link (str): 플레이어 프로필 페이지 링크

    Returns:
        dict: 플레이어 정보
    """

    player_info = {
        'player_name': player_name,
        'real_name': real_name,
        'player_link': player_link
    }

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.22 Safari/537.36',
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url=player_link, headers=headers) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), 'html.parser')

                # 플레이어 이미지 추출
                player_image_url = None
                meta_image_tag = soup.find('meta', property='og:image')
                if meta_image_tag and meta_image_tag.get('content'):
                    raw_url = meta_image_tag['content'].strip()
                    if raw_url:
                        player_image_url = raw_url
                
                player_info['player_image'] = player_image_url

                # 플레이어 현재 팀 이력 추출
                current_team_heading = soup.find('h2', string=lambda text: text and 'Current Teams' in text)
                current_teams_list = []

                if current_team_heading:
                    current_team_container = current_team_heading.find_next_sibling('div', class_='wf-card')
                    if current_team_container:
                        current_team_tag = current_team_container.find('a', class_='wf-module-item mod-first')

                        if current_team_tag:
                            # 현재 팀 로고 추출
                            current_team_logo_url = None
                            current_team_logo_tag = current_team_tag.find('div')
                            if current_team_logo_tag:
                                img_tag = current_team_logo_tag.find('img')
                                if img_tag and img_tag.get('src'):
                                    src = img_tag['src'].strip()
                                    if src:
                                        current_team_logo_url = "https:" + src if src.startswith('//') else src

                        current_team_container = current_team_container.find('div', style=lambda x: 'flex: 1; padding-left: 20px; line-height: 1.45' in x if x else False)

                        # 현재 팀 이력 추출
                        current_team_name_tag = current_team_container.find('div', style=lambda x: 'font-weight: 500' in x if x else False)
                        current_team_name = current_team_name_tag.get_text(strip=True)

                        # 현재 팀 기간 추출
                        current_team_period_tag = current_team_container.find_all('div', class_='ge-text-light')
                        current_team_period = current_team_period_tag[1].get_text(strip=True) if len(current_team_period_tag) > 1 else ""

                        current_teams_list.append({
                            'team_logo': current_team_logo_url,
                            'team_name': current_team_name,
                            'team_period': current_team_period
                        })

                    player_info['current_teams'] = current_teams_list


                # 선수 과거 팀 이력 추출
                past_teams_heading = soup.find('h2', string=lambda text: text and 'Past Teams' in text)
                past_teams_list = []

                if past_teams_heading:
                    team_list_container = past_teams_heading.find_next_sibling('div', class_='wf-card')
                    if team_list_container:
                        team_tags = team_list_container.find_all('a', class_='wf-module-item')

                        for team_tag in team_tags:
                            # 과거 팀 로고 추출
                            log_tag = team_tag.find('div')
                            team_logo_url = "https:" + log_tag.find('img')['src']

                            team_container = team_tag.find('div', style=lambda x: 'flex: 1; padding-left: 20px; line-height: 1.45' in x if x else False)
                            
                            # 과거 팀 이름 추출
                            team_name_tag = team_container.find('div', style=lambda x: 'font-weight: 500' in x if x else False)
                            team_name = team_name_tag.get_text(strip=True)

                            # 과거 팀 기간 추출
                            team_period_tags = team_container.find_all('div', class_='ge-text-light')
                            team_period = team_period_tags[1].get_text(strip=True) if len(team_period_tags) > 1 else ""

                            past_teams_list.append({
                                'team_logo': team_logo_url,
                                'team_name': team_name,
                                'team_period': team_period
                            })

                    player_info['past_teams'] = past_teams_list
                    
                else:
                    print("'Past Teams' 섹션을 찾을 수 없습니다.")
                                
                return player_info


if __name__ == "__main__":
    print(search_valorant_players("mako"))
    asyncio.run(fetch_valorant_player_info("mako", "김명관", "https://www.vlr.gg/player/4462/mako"))