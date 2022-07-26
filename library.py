import PySimpleGUI as sg
import sqlite3 as sql
from io import BytesIO
from PIL import Image

import mangakatana

def init_db():
    conn = sql.connect("a.db")
    cur = conn.cursor()
    return (conn, cur)

def add(url):
    conn, cur = init_db()
    cur.execute("INSERT INTO reading_list VALUES(?, 1, 0);", (url,))
    conn.commit()

def update(url, ch, p):
    conn, cur = init_db()
    cur.execute("UPDATE reading_list SET chapter = ?, page = ? WHERE url = ?", (ch, p, url))
    conn.commit()

def is_in_lib(url):
    conn, cur = init_db()
    cur.execute("SELECT * FROM reading_list WHERE url=?", (url,))
    rows = cur.fetchall()
    return (len(rows) > 0, rows[0] if len(rows) > 0 else None)

def make_window():
    _, cur = init_db()
    cur.execute("SELECT * FROM reading_list;")
    rows = cur.fetchall()
    thumbnail_urls = []
    layout = []
    infos = []

    treedata = sg.TreeData()
    
    for row in rows:
        info = mangakatana.get_manga_info(row[0])
        thumbnail_urls.append(info["cover_url"])
        infos.append(info)

    thumbnails = mangakatana.download_images(thumbnail_urls)

    for i, row in enumerate(rows):
        buf = BytesIO(thumbnails[i])
        outbuf = BytesIO()
        im = Image.open(buf)
        im.thumbnail((50, 50), resample=Image.BICUBIC)
        im.save(outbuf, "png")
        treedata.insert("", i,
            "",
            [infos[i]["title"], "{}/{}".format(str(row[1]).zfill(2), "??" if infos[i]["status"] == "Ongoing" else str(len(infos[i]["chapters"])).zfill(2)), infos[i]["chapters"][-1]["date"]],
            outbuf.getvalue()
            )
        buf.close()
        outbuf.close()
    title_max_len = max([len(a["title"]) for a in infos]) + 20
    col0_width = 50
    layout = [
        [
            sg.Menu([["Library", ["Search"]]], key="lib_menu")
        ],
        [
            sg.Tree(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="",
                key="lib_tree", row_height=50, num_rows=5, enable_events=True,
                max_col_width=title_max_len, justification="l"
            )
        ]
    ]
    
    w = sg.Window("Reading list", layout=layout, finalize=True)
    return w