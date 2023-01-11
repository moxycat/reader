import zipfile as zf
import library

def make_archive(chapters: list[str], outfile) -> None:
    archive = zf.ZipFile(outfile, "w", zf.ZIP_DEFLATED, True, 5)
    for i, chapter in enumerate(chapters):
        cid = chapter.split("/")[-1]
        pages = library.get_pages(chapter)
        for j, page in enumerate(pages):
            archive.writestr("%s/%d.png" % (cid, j), page)
    archive.close()