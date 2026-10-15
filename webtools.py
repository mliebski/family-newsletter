"""Web search (DuckDuckGo via ddgs) and page reading, shared by the newsletter agent.

Same logic as the Open WebUI "Web Search & Reader" tool, in a plain synchronous form.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests

try:
    from ddgs import DDGS
except ImportError:  # older package name
    from duckduckgo_search import DDGS

try:
    import trafilatura
except ImportError:
    trafilatura = None

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)


class WebTools:
    def __init__(self, region="ca-en", max_results=6, timelimit="w",
                 max_page_chars=5000, timeout=20, block_private=True):
        self.region = region
        self.max_results = max_results
        self.timelimit = timelimit or None
        self.max_page_chars = max_page_chars
        self.timeout = timeout
        self.block_private = block_private

    # ------------------------------------------------------------- search
    def search(self, query, mode="web"):
        """Return a list of {title, url, snippet, date, source}."""
        with DDGS() as ddgs:
            if mode == "news":
                raw = ddgs.news(query, region=self.region, safesearch="moderate",
                                timelimit=self.timelimit, max_results=self.max_results)
            else:
                raw = ddgs.text(query, region=self.region, safesearch="moderate",
                                timelimit=self.timelimit, max_results=self.max_results)
        results = []
        for r in raw or []:
            url = r.get("url") or r.get("href") or ""
            if not url:
                continue
            results.append({
                "title": (r.get("title") or "").strip(),
                "url": url,
                "snippet": (r.get("body") or "").strip(),
                "date": r.get("date", ""),
                "source": r.get("source", ""),
            })
        return results

    # --------------------------------------------------------------- read
    def read(self, url):
        """Return {url, title, text}; raises on failure."""
        final_url, content_type, body = self._fetch(url)
        if "html" in content_type:
            title, text = self._extract_html(body, final_url)
        elif content_type.startswith("text/"):
            title, text = "", body
        else:
            raise ValueError(f"unsupported content type '{content_type}'")
        text = (text or "").strip()
        if not text:
            raise ValueError("no readable text (page may need JavaScript or a login)")
        if len(text) > self.max_page_chars:
            text = text[: self.max_page_chars].rsplit(" ", 1)[0] + " …"
        return {"url": final_url, "title": title, "text": text}

    def _fetch(self, url, max_redirects=5):
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-CA,en;q=0.9",
        }
        current = url.strip()
        for _ in range(max_redirects + 1):
            self._check_url(current)
            resp = requests.get(current, headers=headers, timeout=self.timeout,
                                allow_redirects=False, stream=True)
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                resp.close()
                if not location:
                    raise ValueError("redirect without Location header")
                current = urljoin(current, location)
                continue
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
            raw = resp.raw.read(5_000_000, decode_content=True)
            resp.close()
            encoding = resp.encoding or "utf-8"
            return current, content_type, raw.decode(encoding, errors="replace")
        raise ValueError("too many redirects")

    def _check_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("only http(s) URLs are allowed")
        if not parsed.hostname:
            raise ValueError("URL has no host")
        if not self.block_private:
            return
        try:
            infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        except socket.gaierror:
            raise ValueError(f"cannot resolve {parsed.hostname}")
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError(f"{parsed.hostname} is a private/local address; blocked")

    @staticmethod
    def _extract_html(html, url):
        title, text = "", ""
        if trafilatura is not None:
            text = trafilatura.extract(html, url=url, include_comments=False,
                                       include_tables=True, favor_recall=True) or ""
            meta = trafilatura.extract_metadata(html)
            if meta and meta.title:
                title = meta.title
        if not text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
                tag.decompose()
            if soup.title and soup.title.string:
                title = title or soup.title.string.strip()
            lines = (ln.strip() for ln in soup.get_text("\n").splitlines())
            text = "\n".join(ln for ln in lines if ln)
        return title, text
