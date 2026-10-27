# Family Newsletter Agent

A weekly HTML newsletter, researched and written by the local LLM on the home server
(Ollama + DuckDuckGo search), served to the family network by nginx.

```
config.toml ──► newsletter_agent.py
                  │  for each topic:
                  │   1 RESEARCH  model calls web_search / read_webpage (Ollama tool calling)
                  │   2 FALLBACK  too little gathered? run seed queries directly
                  │   3 WRITE     model returns stories as JSON (Ollama structured output)
                  │   4 VERIFY    drop any story whose source page the agent never read
                  │  editor's note + 6-day weather (Open-Meteo, weather.py)
                  │  ─► render.py (escapes everything; model never writes HTML)
                  ▼
site/index.html · site/latest.html · site/issues/YYYY-MM-DD.{html,json}
                  ▼
nginx (Docker) ─► http://<server-ip>:8088
```

## Install (on the Ubuntu server)

Copy this folder to the server (e.g. `~/family-newsletter`), then:

```bash
cd ~/family-newsletter
bash install.sh
```

This creates a Python venv, starts nginx on port **8088**, and installs a systemd timer
that runs every **Sunday at 06:00** (catching up after downtime).

## Use

| Task | Command |
|---|---|
| Build an issue now | `sudo systemctl start newsletter` |
| Watch progress | `journalctl -u newsletter -f` |
| Test one topic, another model | `.venv/bin/python newsletter_agent.py --topic "Tech & AI" --model gpt-oss:20b` |
| Next scheduled run | `systemctl list-timers newsletter.timer` |
| Change topics / title / model | edit `config.toml` (no restart needed) |

Re-running on the same day overwrites that day's issue.

## Tuning

- **Speed**: a run is ~3 topics × (5-10 tool calls + 1 writing call). With `qwen3:30b-a3b` on
  CPU expect roughly 10-30 minutes; a dense 27B model can take well over an hour.
  `think = false` and fewer `max_tool_calls` make it faster.
- **Quality**: `think = true`, a stronger model, or `items` lower per topic.
- **Model can't use tools well?** The fallback still runs the seed queries, so you get an issue;
  make the `seed_queries` specific.
- **Search rate-limited**: DuckDuckGo occasionally throttles; the run continues and topics
  without material are shown as "No verified stories this week". If it becomes frequent,
  switch `webtools.py` to a self-hosted SearXNG.

## Weather

Each issue shows today plus the next 5 days (high/low, conditions, chance of precipitation),
fetched from [Open-Meteo](https://open-meteo.com) (free, no API key) right before publishing.
The numbers come straight from the forecast, never from the model. Set the location or turn it
off in the `[weather]` section of `config.toml`; if the forecast can't be fetched, the issue
is published without it.

## Safety notes

- Pages on the home network are never fetched (`block_private_addresses = true`).
- Story links can only point to pages the agent actually read during research
  (a search snippet alone is never enough).
- All model text is HTML-escaped; nginx serves the folder read-only.
- Port 8088 is meant for the LAN only; don't forward it on the router.
