from ebooklib import epub as ep
import library

def make_book_from_chapters(chapters: list[str], info: dict, outfile: str):
    """`info` dict is the one obtained through `library.get_book_info`"""
    chapter_names = []
    for ch in info["chapters"]:
        if ch["url"] in chapters:
            chapter_names.append(ch["name"])

    book = ep.EpubBook()
    book.set_title(info["title"])
    book.add_author(info["author"])
    book.set_language("en")

    book.set_cover(file_name="cover.png", content=info["cover"])

    book.spine = ["nav"]

    css_styling = ".wrapper {padding: 0; margin: 0;} .page {width: 100%; height: auto; margin: 0; padding: 0;} h1 {text-decoration: underline;}"
    book_css = ep.EpubItem(uid="book_style", file_name="style.css", media_type="text/css", content=css_styling)
    book.add_item(book_css)

    for url, name in zip(chapters, chapter_names):
        cid = url.split("/")[-1] # chapter id e.g. `c18` for chapter 18
        content = "<body><h1>%s</h1>" % name
        pages: list[bytes] = library.get_pages(url)
        for i, page in enumerate(pages):
            item = ep.EpubImage(
                uid="%s_%d" % (cid, i),
                file_name="%s/%d.png" % (cid, i),
                media_type="image/png", content=page)
            book.add_item(item)
            content += "<div class=\"wrapper\"><img class=\"page\" src=\"%s/%d.png\"></div>" % (cid, i)
        content += "</body>"
        filename = cid + ".xhtml"
        ch = ep.EpubHtml(uid=cid, file_name=filename, content=content, title=cid)
        ch.add_item(book_css)
        book.spine.append(cid)
        book.add_item(ch)
        book.toc.append(ep.Link(filename, name, cid))
    
    book.add_item(ep.EpubNcx())
    book.add_item(ep.EpubNav())

    ep.write_epub(outfile, book, {})