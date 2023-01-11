from io import BytesIO
from fpdf import FPDF
import library

def make_pdf(chapters: list[str], info: dict, outfile: str):
    """`info` is the dict returned by `get_book_info`"""
    pdf = FPDF()
    for chapter in chapters:
        pages = library.get_pages(chapter)
        for page in pages:
            pdf.add_page()
            pdf.image(BytesIO(page), type="png", w=210, x=0, y=0)
    pdf.output(outfile, "f")
    return