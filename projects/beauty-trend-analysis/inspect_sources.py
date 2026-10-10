"""수집기 개발용: 공개 페이지의 본문·날짜 구조 확인."""
import requests
from bs4 import BeautifulSoup

for url in [
    'https://www.cosinkorea.com/news/article.html?no=58472',
    'https://business.hwahae.co.kr/insight/trendreport-26-3q-trend-snap/',
]:
    response = requests.get(url, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    print('\nURL:', url)
    print(soup.get_text(' ', strip=True)[:6500])
    for node in soup.find_all(['div', 'section', 'span', 'li', 'time']):
        own = ' '.join(node.find_all(string=True, recursive=False)).strip()
        if ('2026' in own and len(own) < 150) or 'post-content' in str(node.get('class')):
            print('NODE', node.name, node.attrs, own[:150])
    for node in soup.find_all('script', type='application/ld+json'):
        print('JSONLD', node.get_text()[:1500])
    for node in soup.find_all('p')[:8]:
        print('PARENT', [(p.name, p.get('id'), p.get('class')) for p in list(node.parents)[:3]])
