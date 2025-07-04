from bs4 import BeautifulSoup
from urllib.parse import urljoin

import requests

def search_valorant_players(player_name: str) -> list:
    """
    VLR 플레이어 검색 결과에서 플레이어 정보를 추출한다.
    
    Args:
        player_name (str): 검색할 플레이어 이름
    """
    url = f'https://www.vlr.gg/search/?q={player_name}&type=players'
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []

        for a in soup.select('div.wf-card a'):
            # a 태그 내부에서 닉네임(div.search-item-title) 추출
            nickname_element = a.select_one('.search-item-title')
            if not nickname_element:
                continue

            nickname = nickname_element.get_text(strip=True)

            # 실명(또는 팀/추가 정보) 추출
            desc_el = a.select_one('.search-item-desc')
            real_name = desc_el.get_text(strip=True) if desc_el else ''

            player_link = urljoin(url, a['href'])
            image_link = urljoin(url, a.select_one('img')['src'])

            results.append({
                'player_name': nickname,
                'real_name': real_name,
                'player_link': player_link,
                'image_link': image_link
            })

        return results
    
    else:
        return None
    


if __name__ == "__main__":
    results = search_valorant_players("k1ng")
    print(results)