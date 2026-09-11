import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from cuti.fetch import fetch_text

url = "https://www.catawiki.com/en/l/106255624-rolex-explorer-ii-216570-men-2010-2020"
html = fetch_text(url, 15.0)

data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL).group(1))
imgs = data["props"]["pageProps"]["lotDetailsData"]["images"]
print("Total images in lotDetailsData:", len(imgs))
for i, img in enumerate(imgs):
    print(f"[{i:02d}] large: {img.get('large')}")
    print(f"     medium: {img.get('medium')}")
    print(f"     thumb : {img.get('thumbnail')}")
