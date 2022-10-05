import re

def parse(text: str):
    lines = text.splitlines()
    parsed = []
    h = re.compile("^#{1,6}\s+.*") # header
    bq = re.compile("^(?:>\s)*\s*.*") # blockquote
    ul = re.compile("^[\*+-]\s+.*") # unordered list
    ol = re.compile("^[0-9]+\.\s+.*") # ordered list

    for line in lines:
        print(re.findall(h, line))
        print(re.findall(bq, line))

parse("> > ## Hello world~")