"""
mangakatana.com API
Compliant with the website up until at least 2022-07-23
"""
from datetime import datetime
from io import BytesIO
import requests as r
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from PIL import Image
import asyncio, aiohttp
import re

import settings, util

from requests_html import HTMLSession

stop_search = False

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
    author = soup.find("a", {"class": "author"})
    if author is None: author = "Unknown"
    else: author = author.text.strip()
    genres = [a.text.strip() for a in soup.find("div", {"class": "genres"})]
    genres = list(filter(lambda item: len(item) > 0, genres))
    status = soup.find("div", {"class": re.compile("d-cell-small value status .+")}).text.strip()
    desc = soup.find("div", {"class": "summary"}).find("p").text.strip()

    chapters = []
    srvr = ("" if settings.settings["server"]["source"] == "1" else "?sv=mk" if settings.settings["server"]["source"] == "2" else "?sv=3" if settings.settings["server"]["source"] == "3" else "")
    for tr in soup.find("div", {"class": "chapters"}).find("table").find("tbody").find_all("tr"):
        a = tr.find("div", {"class": "chapter"}).find("a")
        chapters.append(
            {
                "name": a.text.strip(),
                "url": a.get("href") + srvr,
                "date": datetime.strptime(tr.find("div", {"class": "update_time"}).text.strip(), "%b-%d-%Y")
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

def search2(query: str, search_by: int = 0) -> list:
    query = quote_plus(query)
    template_url = "https://mangakatana.com/page/{}?search={}&search_by={}".format("{}", query, "book_name" if search_by == 0 else "author")
    pages = []
    soups = [None]
    max_page = 1
    
    resp = r.get(template_url.format(1))
    pages.append(resp.text)

    soups[0] = BeautifulSoup(resp.text, "lxml")

    nresults = soups[0].find("div", {"class": "widget-title"}).find("span").text.strip()
    if not nresults.startswith("Search"): nresults = 1
    else: nresults = int(nresults.removeprefix("Search results (").removesuffix(")"))

    max_page = (nresults // 20) + 1

    if nresults == 1:
        cover_url = soups[0].find("div", {"class": "cover"}).find("img").get("src")
        title = soups[0].find("h1", {"class": "heading"}).text.strip()
        link = soups[0].find("link", {"rel": "canonical"}).get("href")
        return [{"title": title, "url": link, "cover_url": cover_url}]

    for i in range(2, max_page + 1):
        resp = r.get(template_url.format(i))
        if resp.status_code != 200: break
        soups.append(BeautifulSoup(resp.text, "lxml"))

    for soup in soups:
        print(len(soup.prettify()))
    


def search(query: str, search_by: int = 0) -> list:
    query = quote_plus(query)
    template_url = "https://mangakatana.com/page/{}?search={}&search_by={}"
    page = 1
    url = template_url.format(page, query, "book_name" if search_by == 0 else "author")
    resp = r.get(url, headers={"User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"})
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
        if stop_search: return None
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
        
        resp = r.get(url, headers={"User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"})
        if resp.status_code != 200: return None
        while len(resp.text) == 0:
            resp = r.get(url, headers={"User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"})
            if resp.status_code != 200: return None

        soup = BeautifulSoup(resp.text, "lxml")
        book_list = soup.find("div", {"id": "book_list"})
        if book_list is None:
            cover_url = soup.find("div", {"class": "cover"}).find("img").get("src")
            title = soup.find("h1", {"class": "heading"}).text.strip()
            link = soup.find("link", {"rel": "canonical"}).get("href")
            results.append({"title": title, "url": link, "cover_url": cover_url})
            return results
        else:
            books = book_list.find_all("div", {"class": "item"})
    
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
        return ([{"title": title, "url": link, "cover_url": cover_url}], 1)
    
    books = book_list.find_all("div", {"class": "item"})
    results = []
    
    for book in books:
        title = book.find("h3", {"class": "title"}).find("a").text.strip()
        a = book.find("div", {"class": "wrap_img"}).find("a")
        link = a.get("href")
        cover_url = a.find("img", {"alt": "[Cover]"}).get("src")
        results.append({"title": title, "url": link, "cover_url": cover_url})
    
    return (results, nresults)

def get_manga_chapter_images(url: str, s: HTMLSession) -> list:
    links = []
    
    resp = s.get(url)
    resp.html.render(timeout=60)
    
    page_divs = resp.html.find("div[id^=\"page\"]")
    for page_div in page_divs:
        img = page_div.find("img", first=True)
        #print(img.attrs)
        if img.attrs["src"] == "about:blank":
            links.append(img.attrs["data-src"])
        else: links.append(img.attrs["src"])
    
    for link in links:
        print(link)
    return links

def download_images(urls: list) -> list:
    sem = asyncio.BoundedSemaphore(20)
    results = [None] * len(urls)
    async def fetch(url: str, i: int):
        if url is None: return None
        try:
            async with sem, aiohttp.ClientSession() as sesh:
                async with sesh.get(url) as resp:
                    try:
                        results[i] = util.pngify(await resp.read())
                        resp.close()
                        print(f"{i} done", len(results[i]))
                    except Exception as e:
                        print(f"{i} failed ({e})")
            await sesh.close()
        except: pass
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [loop.create_task(fetch(url, i)) for i, url in enumerate(urls)]
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close() #???
    return results

import util

def download_images2(urls):
    results = [None] * len(urls)
    for url in urls:
        resp = r.get(url)
