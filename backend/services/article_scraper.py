import trafilatura
from bs4 import BeautifulSoup

import requests

def scrape_full_article(url: str, is_aggregator: bool = False) -> tuple[str, str]:
    """
    Скачивает и извлекает чистый текст статьи по URL, а также прямую ссылку на источник, если она есть.
    Возвращает (text, source_url)
    """
    try:
        final_url = url
        if is_aggregator:
            try:
                # Resolve aggregator redirects
                response = requests.get(url, allow_redirects=True, timeout=15)
                final_url = response.url
                
                if "yandex" in final_url or "dzen.ru" in final_url or "google.com/news" in final_url:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
                    if meta_refresh and 'url=' in meta_refresh.get('content', '').lower():
                        content = meta_refresh.get('content', '')
                        final_url = content.split('url=')[-1].strip("'\" ")
            except Exception as e:
                print(f"Error resolving aggregator URL: {e}")

        downloaded = trafilatura.fetch_url(final_url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            
            # Попытка найти ссылку на источник
            source_url = final_url if is_aggregator else ""
            try:
                soup = BeautifulSoup(downloaded, 'html.parser')
                # Ищем td с классом topic_footer, внутри которого есть ссылка
                footer_td = soup.find('td', class_='topic_footer')
                if footer_td:
                    a_tag = footer_td.find('a', class_='a_topic_info')
                    if a_tag and a_tag.has_attr('href'):
                        source_url = a_tag['href']
            except Exception as e:
                print(f"Ошибка при извлечении ссылки источника: {e}")
                
            return text, source_url
        return None, ""
    except Exception as e:
        print(f"Ошибка при парсинге {url}: {e}")
        return None
