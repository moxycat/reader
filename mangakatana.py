"""
mangakatana.com API
Compliant with the website up until at least 2022-07-23
"""
from datetime import datetime
import requests as r
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re
import concurrent.futures

import settings, util

import requests_html
from requests_html import HTMLSession

stop_search = False

def get_manga_info(url: str) -> dict:
    try:
        resp = r.get(url)
    except: return {}
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
    #srvr = ("" if settings.settings["server"]["source"] == "1" else "?sv=mk" if settings.settings["server"]["source"] == "2" else "?sv=3" if settings.settings["server"]["source"] == "3" else "")
    chaptersoup = soup.find("div", {"class": "chapters"}).find("table").find("tbody").find_all("tr")
    for i, tr in enumerate(reversed(chaptersoup)):
        a = tr.find("div", {"class": "chapter"}).find("a")
        chapters.append(
            {
                "index": i,
                "name": a.text.strip(),
                "url": a.get("href"),# + srvr,
                "date": datetime.strptime(
                    tr.find("div", {"class": "update_time"}).text.strip(),
                    "%b-%d-%Y")
            }
        )

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

def search(
    query:str, search_by:int, sesh:requests_html.HTMLSession,
    wind, _results:list[dict[str, str]] = [], _url=None):
    # stop if searching is manually cancelled by the user
    if stop_search: return _results
    # sanitize query string
    query = quote_plus(query)

    def fetcher(url):
        response = sesh.get(url)
        while len(response.text) == 0:
            response = sesh.get(url)
        return response
    
    # _url is None only on the first iteration of the function, thus we setup everyting here
    if _url is None:
        r = fetcher(
            f"""https://mangakatana.com/?search={query}&search_by={
                'book_name' if search_by == 0 else 'author'}""")
        _results.clear()
    else:
        r = fetcher(_url)

    # determine if page has only one book on it
    if r.html.find("div#single_book", first=True) is not None:
        url = r.html.find("meta[property=\"og:url\"]", first=True).attrs["content"] # grab url
        title = r.html.find("h1.heading", first=True).text # grab title
        _results.append({"title": title, "url": url}) # add to results
        return _results # single book pages are always last so we can exit early
    
    # all books are found in the div with id "book_list" with each book being in its own div with a class "item"
    items: list[requests_html.Element] = r.html.find("div#book_list>div.item")
    
    # iterate all books
    for item in items:
        # grab the anchor that contains the url to the book and it's title
        anchor = item.find("h3.title", first=True).find("a", first=True)
        url = anchor.attrs["href"] # grab the url
        title = anchor.text # grab the text
        _results.append({"title": title, "url": url}) # add to results

    # find the next page button
    next_page_anchor = r.html.find("a.next.page-numbers", first=True)
    # if it exists we call the search function on it otherwise return current results
    if next_page_anchor is not None:
        # write to window (signify search progress)
        wind.write_event_value("search_update_status", _results)
        # call search function recursively
        search(query, search_by, sesh, wind, _results, next_page_anchor.attrs["href"])
    return _results

def get_manga_chapter_images(url: str, s: HTMLSession) -> list:
    links = []
    try:
        resp: requests_html.HTMLResponse = s.get(url)
        resp.html.render(timeout=60, reload=False)
    except: return []
    
    page_divs = resp.html.find("div[id^=\"page\"]")
    for page_div in page_divs:
        img = page_div.find("img", first=True)
        if img.attrs["src"] == "about:blank":
            links.append(img.attrs["data-src"])
        else: links.append(img.attrs["src"])
    
    for link in links:
        print(link)
    return links

def fetch(url: str) -> bytes | None:
    try:
        resp = r.get(url)
        img = util.pngify(resp.content)
        print(len(resp.content))
        return img
    except:
        return None

def download_images(urls: list[str]):
    if urls == []: return [None]
    with concurrent.futures.ThreadPoolExecutor() as pool:
        results = pool.map(fetch, urls)
    return list(results)

def find_chapter_ordinal(chapter_urls: list, index: int):
    n = 0
    for i in range(0, index + 1):
        m = re.search(r".*c[0-9]+(\.[1234]?)?$", chapter_urls[i])
        if m is not None: n += 1
    return n