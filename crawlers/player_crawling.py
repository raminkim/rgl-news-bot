from bs4 import BeautifulSoup
from urllib.parse import urljoin

import aiohttp
import requests
import re

def split_country_field(value: str):
    """
    KRKorea, CNChina, JPJapan 등에서 2글자 코드와 나머지 분리.
    단, 코드가 없거나 순수 국가명만 있을 때도 대응.
    """
    m = re.match(r'^([A-Z]{2})(.+)', value)
    if m:
        return {"code": m.group(1), "name": m.group(2).strip()}
    else:
        return {"code": "", "name": value.strip()}

def search_lol_players(player_name: str) -> dict:
    url = f'https://lol.fandom.com/wiki/{player_name}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.22 Safari/537.36',
    }

    try:
        response = requests.get(url=url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    result = {
        "player_name": player_name,
        "real_name": None,
        "player_link": url,
        "player_image": None,
        "current_teams": [],
        "past_teams": []
    }

    # 인포박스에서 player_image 추출 (원본 이미지 링크 우선)
    infobox = soup.find('table', class_='infobox-player-narrow')
    if infobox:
        a_tag = infobox.find('a', class_='mw-file-description')
        if a_tag and a_tag.has_attr('href'):
            href = a_tag['href']
            if href.startswith('http'):
                result['player_image'] = href
            else:
                result['player_image'] = 'https://static.wikia.nocookie.net' + href
        else:
            img_tag = infobox.find('img', attrs={"data-src": True})
            if img_tag:
                result['player_image'] = img_tag['data-src']
            else:
                img_tag = infobox.find('img', attrs={"src": True})
                if img_tag:
                    result['player_image'] = img_tag['src']

    # 1. 플레이어 인포박스 크롤링
    infobox = soup.find('table', class_='infobox-player-narrow')
    temp_info = {}
    if infobox:
        player_info_label = [
            "Name", "Country of Birth", "Birthday", "Residency", "Role", "Team", "Contract Expires"
        ]
        rows = infobox.find_all('tr')
        for row in rows:
            label_tag = row.find('td', class_='infobox-label')
            value_tag = label_tag.find_next_sibling('td') if label_tag else None
            if label_tag and value_tag:
                label = " ".join(label_tag.get_text(strip=True).split())
                value = " ".join(value_tag.get_text(strip=True).split())
                if label in player_info_label:
                    temp_info[label] = value

    # Name에서 player_name, real_name 분리
    name_val = temp_info.get("Name", "")
    # 예: 'Yoon Sung-won (윤성원)' 또는 'Oner (문현준)'
    import re
    m = re.match(r'^(.*?)\s*\((.*?)\)$', name_val)
    if m:
        result["player_name"] = m.group(1).strip()
        result["real_name"] = m.group(2).strip()
    else:
        result["player_name"] = name_val.strip()
        result["real_name"] = None

    # 현재 팀, 계약 만료일 추출
    team = temp_info.get("Team")
    contract = temp_info.get("Contract Expires")
    if team:
        team_url = f'https://lol.fandom.com/wiki/{team.replace(" ", "_")}'
        result["current_teams"].append({
            "team_logo": None,
            "team_name": team,
            "team_period": f"Contract Expires: {contract}" if contract else ""
        })

    # 2. 팀 주요 경력 크롤링 (past_teams)
    def get_display_date(td):
        span = td.find('span', class_='ofl-toggle-2-1')
        return span.get_text(strip=True) if span else td.get_text(strip=True)

    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    def convert_month_year(text):
        parts = text.strip().split()
        if len(parts) == 2 and parts[0] in month_map:
            return f"{parts[1]}년 {month_map[parts[0]]}월"
        return text

    teamlist = soup.find('div', class_='player-history-teamlist')
    if teamlist:
        tables = teamlist.find_all('table', class_='player-team-history')
        for table in tables:
            for row in table.find_all('tr'):
                if row.find('th'):
                    continue
                cols = row.find_all('td')
                if len(cols) >= 6:
                    team_td = cols[1]
                    team_name_tag = team_td.find('span', class_='teamname')
                    team_name = team_name_tag.get_text(strip=True) if team_name_tag else ''
                    team_link_tag = team_name_tag.find('a') if team_name_tag else None
                    team_link = 'https://lol.fandom.com' + team_link_tag['href'] if team_link_tag and team_link_tag.has_attr('href') else None
                    team_img_tag = team_td.find('img', attrs={"data-src": True})
                    team_img_url = team_img_tag['data-src'] if team_img_tag else None
                    start = get_display_date(cols[3])
                    end = get_display_date(cols[4])
                    duration = cols[5].get_text(strip=True)
                    start_kor = convert_month_year(start)
                    end_kor = convert_month_year(end)
                    period = f"{start_kor} ~ {end_kor}"
                    if start_kor or end_kor:
                        entry = {
                            "team_logo": team_img_url,
                            "team_name": team_name,
                            "team_period": period
                        }
                        result["past_teams"].append(entry)
    # 중복 제거
    unique = []
    seen = set()
    for t in result["past_teams"]:
        key = (t["team_name"], t["team_period"])
        if key not in seen:
            unique.append(t)
            seen.add(key)
    # 가장 최근 종료일이 위로 오게 정렬
    import re
    from datetime import datetime
    def parse_end(period):
        # 예: '2023년 7월 ~ 2023년 8월' → 2023, 8
        m = re.match(r'.*~\s*(\d{4})년\s*(\d{1,2})월', period)
        if m:
            return int(m.group(1)), int(m.group(2))
        # '현재' 또는 'Present'가 포함된 경우 최상단
        if '현재' in period or 'Present' in period:
            return (9999, 12)
        return (0, 0)  # 파싱 실패시 맨 아래
    unique.sort(key=lambda t: parse_end(t["team_period"]), reverse=True)
    result["past_teams"] = unique
    return result


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

if __name__ == '__main__':
    player_data = search_lol_players('poby')
    import asyncio
    valorant_data = asyncio.run(fetch_valorant_player_info("mako", "김명관", "https://www.vlr.gg/player/4462/mako"))