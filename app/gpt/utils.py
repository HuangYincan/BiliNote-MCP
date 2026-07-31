import codecs

def fix_markdown(markdown: str) -> str:
    return codecs.decode(markdown, 'unicode_escape')