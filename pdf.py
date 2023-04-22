from io import BytesIO
from fpdf import FPDF
from PIL import Image
import library

def make_pdf(chapters: list[str], outfile: str):
    pdf = FPDF()
    for chapter in chapters:
        pages = library.get_pages(chapter)
        for page in pages:
            buffer = BytesIO()
            pdf.add_page()
            im = Image.open(BytesIO(page))
            if im.width > im.height:
                rim = im.rotate(-90.0, Image.Resampling.BICUBIC, expand=True)
                rim.save(buffer, "png")
            else:
                im.save(buffer, "png")
            pdf.image(buffer, type="png", w=210, x=0, y=0)
            im.close()
            del buffer
    pdf.output(outfile, "f")
    return