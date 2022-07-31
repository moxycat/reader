"""
mangakatana.com API
Compliant with the website up until at least 2022-07-23
"""
from concurrent.futures import ThreadPoolExecutor
from email.mime import image
from io import BytesIO
from multiprocessing.dummy import current_process
import threading
import requests as r
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from PIL import Image
import asyncio, aiohttp
import re
import multiprocessing

def get_manga_info(url: str) -> dict:
    resp = r.get(url)
    if resp.status_code != 200: return {}
    soup = BeautifulSoup(resp.text, "lxml")
    
    link = soup.find("link", {"rel": "canonical"}).get("href")
    cover_url = soup.find("div", {"class": "cover"}).find("img").get("src")
    title = soup.find("h1", {"class": "heading"}).text.strip()
    
    alt_names_div = soup.find("div", {"class": "alt_name"})
    if alt_names_div is None: alt_names = [""]
    else: alt_names = [name.strip() for name in alt_names_div.text.split(" ; ")]
    author = soup.find("a", {"class": "author"}).text.strip()
    genres = [a.text.strip() for a in soup.find("div", {"class": "genres"})]
    genres = list(filter(lambda item: len(item) > 0, genres))
    status = soup.find("div", {"class": re.compile("d-cell-small value status .+")}).text.strip()
    desc = soup.find("div", {"class": "summary"}).find("p").text.strip()

    chapters = []
    for tr in soup.find("div", {"class": "chapters"}).find("table").find("tbody").find_all("tr"):
        a = tr.find("div", {"class": "chapter"}).find("a")
        chapters.append(
            {
                "name": a.text.strip(),
                "url": a.get("href"),
                "date": tr.find("div", {"class": "update_time"}).text.strip()
            }
        )
    
    chapters.reverse()
    return {
        "url": link,
        "cover_url": cover_url,
        "title": title,
        "alt_names": alt_names,
        "author": author,
        "genres": genres,
        "status": status,
        "description": desc,
        "chapters": chapters
        }

def search(query: str, search_by: int = 0) -> list:
    query = quote_plus(query)
    template_url = "https://mangakatana.com/page/{}?search={}&search_by={}"
    page = 1
    url = template_url.format(page, query, "book_name" if search_by == 0 else "author")
    resp = r.get(url)
    if resp.status_code != 200: return []
    soup = BeautifulSoup(resp.text, "lxml")

    nresults = soup.find("div", {"class": "widget-title"}).find("span").text.strip()
    if not nresults.startswith("Search"): nresults = 1
    else: nresults = int(nresults.removeprefix("Search results (").removesuffix(")"))
    added = 0

    book_list = soup.find("div", {"id": "book_list"})
    if book_list is None:
        cover_url = soup.find("div", {"class": "cover"}).find("img").get("src")
        title = soup.find("h1", {"class": "heading"}).text.strip()
        link = soup.find("link", {"rel": "canonical"}).get("href")
        return [{"title": title, "url": link, "cover_url": cover_url}]
    
    books = book_list.find_all("div", {"class": "item"})
    results = []
    
    while added != nresults:
        for book in books:
            title = book.find("h3", {"class": "title"}).find("a").text.strip()
            a = book.find("div", {"class": "wrap_img"}).find("a")
            link = a.get("href")
            cover_url = a.find("img", {"alt": "[Cover]"}).get("src")
            results.append({"title": title, "url": link, "cover_url": cover_url})
            added += 1
        if added != nresults: page += 1
        else: break
        url = template_url.format(page, query, "book_name" if search_by == 0 else "author")
        resp = r.get(url)
        if resp.status_code != 200: return None
        soup = BeautifulSoup(resp.text, "lxml")
        books = soup.find("div", {"id": "book_list"}).find_all("div", {"class": "item"})
    
    return results

def search_page_count(query: str, search_by: int = 0) -> int:
    query = quote_plus(query)
    template_url = "https://mangakatana.com/page/{}?search={}&search_by={}"
    current_page = 1
    while True:
        url = template_url.format(current_page, query, "book_name" if search_by == 0 else "author")
        resp = r.get(url)
        if resp.status_code == 404: break
        else: current_page += 1
    return current_page - 1

def search_page(query: str, page: int = 1, search_by: int = 0) -> tuple:
    query = quote_plus(query)
    template_url = "https://mangakatana.com/page/{}?search={}&search_by={}"
    url = template_url.format(page, query, "book_name" if search_by == 0 else "author")
    resp = r.get(url)
    if resp.status_code != 200: return ([], 0)
    soup = BeautifulSoup(resp.text, "lxml")

    nresults = soup.find("div", {"class": "widget-title"}).find("span").text.strip()
    if not nresults.startswith("Search"): nresults = 1
    else: nresults = int(nresults.removeprefix("Search results (").removesuffix(")"))
    added = 0

    book_list = soup.find("div", {"id": "book_list"})
    if book_list is None:
        cover_url = soup.find("div", {"class": "cover"}).find("img").get("src")
        title = soup.find("h1", {"class": "heading"}).text.strip()
        link = soup.find("link", {"rel": "canonical"}).get("href")
        return [{"title": title, "url": link, "cover_url": cover_url}]
    
    books = book_list.find_all("div", {"class": "item"})
    results = []
    
    for book in books:
        title = book.find("h3", {"class": "title"}).find("a").text.strip()
        a = book.find("div", {"class": "wrap_img"}).find("a")
        link = a.get("href")
        cover_url = a.find("img", {"alt": "[Cover]"}).get("src")
        results.append({"title": title, "url": link, "cover_url": cover_url})
    
    return (results, nresults)


def count_chapters(chapters: list) -> int:
    count = 0
    for ch in chapters:
        ret = re.match(".*[Cc]hapter (.+)\s*:.+")
        print(ret)

def get_manga_chapter_images(url: str) -> list:
    resp = r.get(url)
    if resp.status_code != 200: return None
    images = re.findall("var ytaw=\[('.+'),\];", resp.text)
    images = images[0].replace("'", "").split(",")
    images = list(filter(lambda item: item is not None, images))
    return images

def download_images(urls: list) -> list:
    sem = asyncio.BoundedSemaphore(20)
    results = [None] * len(urls)
    async def fetch(url: str, i: int):
        async with sem, aiohttp.ClientSession() as sesh:
            async with sesh.get(url) as resp:
                buf = BytesIO()
                outbuf = BytesIO()
                buf.write(await resp.read())
                im = Image.open(buf)
                im.save(outbuf, "png")
                results[i] = outbuf.getvalue()
                im.close()
                buf.close()
                outbuf.close()
                print(f"{i} done")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [loop.create_task(fetch(url, i)) for i, url in enumerate(urls)]
    loop.run_until_complete(asyncio.wait(tasks))
    return results