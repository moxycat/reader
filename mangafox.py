from io import BytesIO
import requests as r
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
from PIL import Image
import asyncio, aiohttp
import re
from datetime import datetime


def get_manga_info(url: str) -> dict:
    resp = r.get(url)
    if resp.status_code != 200: return {}
    soup = BeautifulSoup(resp.text, "lxml")

    title = soup.find("span", {"class": "detail-info-right-title-font"}).text.strip()
    status = soup.find("span", {"class": "detail-info-right-title-tip"}).text.strip()
    author = soup.find("p", {"class": "detail-info-right-say"}).find("a").text.strip()
    genres = [a.text.strip() for a in soup.find("p", {"class": "detail-info-right-tag-list"}).find_all("a")]
    desc = soup.find("p", {"class": "fullcontent"}).text.strip()
    cover_url = soup.find("img", {"class": "detail-info-cover-img"}).get("src")
    
    chapters = []

    chapterlist_div = soup.find("div", {"id": "chapterlist"})
    lists = chapterlist_div.find_all("ul", {"class": "detail-main-list"})
    for list in lists:
        lis = list.find_all("li")
        for li in lis:
            a = li.find("a")
            url = urljoin("http://fanfox.net/", a.get("href"))
            name = a.find("p", {"class": "title3"}).text.strip()
            date = a.find("p", {"class": "title2"}).text.strip()
            date = datetime.strptime(date, "%b %d,%Y")
            chapters.append({"url": url, "name": name, "date": date})

    chapters.reverse()
    return {
        "url": url,
        "cover_url": cover_url,
        "title": title,
        "alt_names": [], # compat entry
        "author": author,
        "genres": genres,
        "status": status,
        "description": desc,
        "chapters": chapters
        }

def search(query: str):
    query = quote_plus(query)
    template = "https://fanfox.net/search?page={}&title={}"
    page = 1
    url = template.format(page, query)
    resp = r.get(url)
    if resp.status_code != 200: return []
    soup = BeautifulSoup(resp.text, "lxml")

    results = []

    while resp.status_code == 200:
        list = soup.find("ul", {"class": "manga-list-4-list line"})
        if list is None: break
        lis = list.find_all("li")
        for li in lis:
            anchor = li.find("a")
            url = urljoin("http://fanfox.net/", anchor.get("href"))
            title = li.find("p", {"class": "manga-list-4-item-title"}).text.strip()
            cover_url = anchor.find("img").get("src")
            results.append({"title": title, "url": url, "cover_url": cover_url})
        page += 1
        url = template.format(page, query)
        resp = r.get(url)
        soup = BeautifulSoup(resp.text, "lxml")
    
    return results

def get_manga_chapter_images(url: str) -> list:
    resp = r.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    return soup.prettify()

print(get_manga_chapter_images("https://fanfox.net/manga/komi_san_wa_komyushou_desu/c369/1.html"))