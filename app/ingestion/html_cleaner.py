from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

NOISY_SELECTORS = (
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "noscript",
    "iframe",
)


def clean_html(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select(",".join(NOISY_SELECTORS)):
        element.decompose()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if isinstance(href, str):
            anchor["href"] = urljoin(base_url, href)

    for image in soup.find_all("img", src=True):
        src = image.get("src")
        if isinstance(src, str):
            image["src"] = urljoin(base_url, src)

    return str(soup).strip()
