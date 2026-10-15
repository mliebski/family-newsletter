#!/usr/bin/env python3
"""Family Newsletter Agent.

For each topic in config.toml:
  1. RESEARCH - the local LLM (via Ollama) calls web_search / read_webpage tools.
  2. FALLBACK - if the model gathered too little, the seed queries are run directly.
  3. WRITE    - the model turns the gathered sources into structured JSON stories.
  4. VERIFY   - every story's source URL must be one the agent actually saw.
Then an editor's note is written and everything is rendered to static HTML.

The model never writes HTML: it only returns JSON, which is escaped and rendered by
render.py. That keeps pages safe and the layout consistent.

Usage:
  python newsletter_agent.py                       # full run with config.toml
  python newsletter_agent.py --model gpt-oss:20b   # override the model
  python newsletter_agent.py --topic "Tech & AI"   # one topic only (testing)
"""

import argparse
import datetime as dt
import json
import sys
import time
import tomllib
from pathlib import Path

import requests

from render import render_issue, render_index
from webtools import WebTools

HERE = Path(__file__).resolve().parent

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web. Returns titles, URLs and short snippets.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Read the main text of a web page found via web_search.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full http(s) URL"}},
                "required": ["url"],
            },
        },
    },
]

STORIES_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "summary": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "source_url": {"type": "string"},
                },
                "required": ["headline", "summary", "why_it_matters", "source_url"],
            },
        }
    },
    "required": ["stories"],
}

INTRO_SCHEMA = {
    "type": "object",
    "properties": {"intro": {"type": "string"}},
    "required": ["intro"],
}


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def norm(url):
    return url.strip().rstrip("/").lower()


# ---------------------------------------------------------------- Ollama client
class Ollama:
    def __init__(self, cfg):
        self.url = cfg["url"].rstrip("/") + "/api/chat"
        self.model = cfg["model"]
        self.timeout = cfg.get("timeout_seconds", 1200)
        self.think = cfg.get("think", False)
        self.options = {
            "num_ctx": cfg.get("num_ctx", 16384),
            "temperature": cfg.get("temperature", 0.4),
        }

    def chat(self, messages, tools=None, fmt=None):
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "options": self.options}
        if tools:
            payload["tools"] = tools
        if fmt:
            payload["format"] = fmt
        if self.think is not None:
            payload["think"] = self.think
        r = requests.post(self.url, json=payload, timeout=self.timeout)
        if r.status_code == 400 and "think" in r.text.lower() and "think" in payload:
            # model doesn't support the think switch: retry without it
            self.think = None
            payload.pop("think")
            r = requests.post(self.url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["message"]

    def chat_json(self, messages, schema, retries=2):
        for attempt in range(retries + 1):
            msg = self.chat(messages, fmt=schema)
            try:
                return json.loads(msg.get("content") or "")
            except json.JSONDecodeError:
                log(f"  invalid JSON from model (attempt {attempt + 1})")
        return None


# ---------------------------------------------------------------- agent
class TopicResearcher:
    """Runs the research loop for one topic and keeps a registry of seen sources."""

    def __init__(self, llm, web, cfg, newsletter_cfg, today):
        self.llm, self.web = llm, web
        self.max_calls = cfg.get("max_tool_calls", 10)
        self.min_pages = cfg.get("min_pages_read", 2)
        self.nl = newsletter_cfg
        self.today = today
        self.seen = {}  # norm(url) -> {url, title, snippet, text}

    # tool implementations -------------------------------------------------
    def _web_search(self, query, mode):
        results = self.web.search(query, mode=mode)
        for r in results:
            self.seen.setdefault(norm(r["url"]), {"url": r["url"], "title": r["title"],
                                                  "snippet": r["snippet"], "text": ""})
        if not results:
            return f"No results for: {query}"
        lines = [f"Results for: {query}"]
        for i, r in enumerate(results, 1):
            extra = f" ({r['source']}, {r['date'][:10]})" if r["source"] else ""
            lines.append(f"{i}. {r['title']}{extra}\n   URL: {r['url']}\n   {r['snippet']}")
        return "\n".join(lines)

    def _read_webpage(self, url):
        page = self.web.read(url)
        entry = self.seen.setdefault(norm(url), {"url": url, "title": "", "snippet": "", "text": ""})
        entry["title"] = entry["title"] or page["title"]
        entry["text"] = page["text"]
        if norm(page["url"]) != norm(url):  # redirected: register final URL too
            self.seen[norm(page["url"])] = entry
        return f"URL: {page['url']}\nTitle: {page['title']}\n\n{page['text']}"

    def pages_read(self):
        return {id(v): v for v in self.seen.values() if v["text"]}.values()

    # main loop -------------------------------------------------------------
    def research(self, topic):
        mode = topic.get("search_mode", "web")
        system = (
            f"You are the research assistant for a family newsletter. Today is {self.today:%A, %B %d, %Y}. "
            f"The family lives in {self.nl.get('location', 'Canada')}. "
            "Your knowledge is out of date, so rely only on what you find with the tools.\n"
            "Process: call web_search 3-6 times with focused queries, then call read_webpage on the "
            f"3-5 most relevant, recent and reputable results. Stay within {self.max_calls} tool calls. "
            "Prefer stories from the past 1-2 days. When you have enough material, reply with the single "
            "word DONE."
        )
        user = (f"Topic: {topic['name']}\nBrief: {topic['brief']}\n"
                f"Starting ideas for queries: {', '.join(topic.get('seed_queries', []))}")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        calls = 0
        while calls < self.max_calls:
            msg = self.llm.chat(messages, tools=TOOLS)
            tool_calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": msg.get("content", ""),
                             "tool_calls": tool_calls})
            if not tool_calls:
                break
            for tc in tool_calls:
                fn = tc.get("function", {})
                name, args = fn.get("name"), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                calls += 1
                try:
                    if name == "web_search":
                        log(f"  search: {args.get('query')}")
                        result = self._web_search(args.get("query", ""), mode)
                    elif name == "read_webpage":
                        log(f"  read:   {args.get('url')}")
                        result = self._read_webpage(args.get("url", ""))
                    else:
                        result = f"Unknown tool '{name}'. Use web_search or read_webpage."
                except Exception as e:
                    result = f"Tool error: {e}"
                    log(f"    -> {e}")
                messages.append({"role": "tool", "tool_name": name, "content": result})

        if len(list(self.pages_read())) < self.min_pages:
            log(f"  model read {len(list(self.pages_read()))} page(s); running seed queries directly")
            self._fallback(topic, mode)

    def _fallback(self, topic, mode):
        for q in topic.get("seed_queries", []):
            try:
                log(f"  search (fallback): {q}")
                results = self.web.search(q, mode=mode)
            except Exception as e:
                log(f"    -> {e}")
                continue
            for r in results:
                self.seen.setdefault(norm(r["url"]), {"url": r["url"], "title": r["title"],
                                                      "snippet": r["snippet"], "text": ""})
            for r in results[:3]:
                if len(list(self.pages_read())) >= self.min_pages + 1:
                    return
                try:
                    log(f"  read (fallback): {r['url']}")
                    self._read_webpage(r["url"])
                except Exception as e:
                    log(f"    -> {e}")

    # writing ---------------------------------------------------------------
    def write(self, topic):
        notes, n = [], 0
        for entry in self.pages_read():
            n += 1
            notes.append(f"[Source {n}] {entry['title']}\nURL: {entry['url']}\n{entry['text']}")
        read_urls = {norm(e["url"]) for e in self.pages_read()}
        for entry in self.seen.values():
            if norm(entry["url"]) not in read_urls and entry["snippet"]:
                n += 1
                notes.append(f"[Source {n}, snippet only] {entry['title']}\nURL: {entry['url']}\n{entry['snippet']}")
        if not notes:
            return []

        items = topic.get("items", 4)
        system = (
            f"You write the '{topic['name']}' section of a family newsletter. "
            f"Audience and tone: {self.nl.get('reading_level', 'clear and friendly')}. "
            f"Write in {self.nl.get('language', 'English')}. Today is {self.today:%B %d, %Y}.\n"
            f"Pick the {items} most relevant and interesting stories for this brief: {topic['brief']}\n"
            "Rules: use ONLY facts stated in the sources below; never invent numbers, dates or quotes. "
            "Each story: a short headline, a 2-3 sentence summary, one sentence on why it matters to "
            "a family, and source_url copied EXACTLY from the source it came from. "
            "Do not repeat the same story twice. Fewer stories is better than weak ones."
        )
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": "SOURCES:\n\n" + "\n\n---\n\n".join(notes)}]
        data = self.llm.chat_json(messages, STORIES_SCHEMA) or {}

        # VERIFY: keep only stories whose source the agent really saw
        stories, used = [], set()
        for s in data.get("stories", []):
            key = norm(s.get("source_url", ""))
            if key not in self.seen:
                log(f"  dropped story with unverified source: {s.get('source_url')}")
                continue
            if key in used:
                continue
            used.add(key)
            src = self.seen[key]
            stories.append({
                "headline": s.get("headline", "").strip(),
                "summary": s.get("summary", "").strip(),
                "why_it_matters": s.get("why_it_matters", "").strip(),
                "source_url": src["url"],
                "source_title": src["title"],
            })
        return stories[:items]


def write_intro(llm, nl_cfg, sections, today):
    headlines = "\n".join(f"- [{s['name']}] {st['headline']}" for s in sections for st in s["stories"])
    if not headlines:
        return ""
    messages = [
        {"role": "system", "content": (
            f"You are the editor of '{nl_cfg['title']}', a daily family newsletter. "
            f"Write a warm, 2-3 sentence editor's note for the issue of {today:%B %d, %Y} that "
            "previews the highlights below. No greeting like 'Dear family', no sign-off, no emojis. "
            f"Write in {nl_cfg.get('language', 'English')}.")},
        {"role": "user", "content": headlines},
    ]
    data = llm.chat_json(messages, INTRO_SCHEMA) or {}
    return data.get("intro", "").strip()


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Build this week's family newsletter.")
    ap.add_argument("--config", default=str(HERE / "config.toml"))
    ap.add_argument("--model", help="override the Ollama model from config")
    ap.add_argument("--topic", action="append", help="only run these topic names (repeatable)")
    args = ap.parse_args()

    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    if args.model:
        cfg["ollama"]["model"] = args.model

    nl, rs, out = cfg["newsletter"], cfg.get("research", {}), cfg.get("output", {})
    topics = cfg["topics"]
    if args.topic:
        wanted = {t.lower() for t in args.topic}
        topics = [t for t in topics if t["name"].lower() in wanted]
        if not topics:
            sys.exit(f"No topics match {args.topic}")

    llm = Ollama(cfg["ollama"])
    web = WebTools(region=nl.get("region", "ca-en"), max_results=rs.get("search_results", 6),
                   timelimit=rs.get("timelimit", "w"), max_page_chars=rs.get("max_page_chars", 5000),
                   block_private=rs.get("block_private_addresses", True))
    today = dt.date.today()
    started = time.time()
    log(f"Building issue {today} with model {llm.model}")

    sections = []
    for topic in topics:
        t0 = time.time()
        log(f"Topic: {topic['name']}")
        researcher = TopicResearcher(llm, web, rs, nl, today)
        try:
            researcher.research(topic)
            stories = researcher.write(topic)
        except requests.RequestException as e:
            log(f"  Ollama/network error, skipping topic: {e}")
            stories = []
        log(f"  {len(stories)} stories in {time.time() - t0:.0f}s")
        sections.append({"name": topic["name"], "stories": stories})

    if not any(s["stories"] for s in sections):
        sys.exit("No stories were produced; not publishing an empty issue.")

    intro = write_intro(llm, nl, sections, today)
    site = Path(out.get("site_dir", "site"))
    if not site.is_absolute():
        site = HERE / site
    issues_dir = site / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)

    issue = {"date": today.isoformat(), "title": nl["title"], "subtitle": nl.get("subtitle", ""),
             "intro": intro, "model": llm.model, "sections": sections}
    (issues_dir / f"{today}.json").write_text(json.dumps(issue, indent=2, ensure_ascii=False), "utf-8")
    html = render_issue(issue)
    (issues_dir / f"{today}.html").write_text(html, "utf-8")
    (site / "latest.html").write_text(html.replace('href="../', 'href="'), "utf-8")

    all_issues = []
    for p in sorted(issues_dir.glob("*.json"), reverse=True):
        try:
            all_issues.append(json.loads(p.read_text("utf-8")))
        except json.JSONDecodeError:
            pass
    (site / "index.html").write_text(render_index(nl, all_issues), "utf-8")

    log(f"Published {issues_dir / f'{today}.html'} in {(time.time() - started) / 60:.1f} min")


if __name__ == "__main__":
    main()
