"""
Stock Monitor - Bursa Malaysia + US Stocks
Sends news + price alerts to Telegram
Runs 4x daily: 07:00 / 12:00 / 17:00 / 22:00 JST
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta
import yfinance as yf

# ─────────────────────────────────────────
# CONFIG — fill these in or set as env vars
# ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "YOUR_CHAT_ID")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY",  "YOUR_ANTHROPIC_KEY")

# ─────────────────────────────────────────
# WATCHLIST
# ─────────────────────────────────────────
US_HOLDINGS = {
    "MSFT":  "Microsoft",
    "QQQ":   "Nasdaq ETF",
    "TSLA":  "Tesla",
    "VOO":   "S&P500 ETF",
}

US_WATCHLIST = {
    "NVDA":  "NVIDIA",
    "AMD":   "AMD",
    "TSM":   "TSMC",
    "AAPL":  "Apple",
    "GOOGL": "Google",
    "AMZN":  "Amazon",
    "META":  "Meta",
    "PLTR":  "Palantir",
    "MU":    "Micron",
    "SMCI":  "SuperMicro",
}

MY_HOLDINGS = {
    "1155.KL":  "MAYBANK",
    "5212.KL":  "PAVREIT",
    "5176.KL":  "SUNREIT",
    "5227.KL":  "IGBREIT",
}

MY_WATCHLIST = {
    "1295.KL":  "PBBANK",
    "1066.KL":  "RHBBANK",
    "1023.KL":  "CIMB",
    "4677.KL":  "YTL",
}

# ─────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────
JST = timezone(timedelta(hours=9))

def get_jst_now():
    return datetime.now(JST)

def get_session_header(hour: int) -> str:
    headers = {
        7:  "🌅 早安快訊",
        12: "☀️ 午間快訊",
        17: "🌆 收盤快訊",
        22: "🌙 美股盤中",
    }
    return headers.get(hour, "📊 市場快訊")

def get_market_context(hour: int) -> dict:
    """Return which markets are active and search focus per time slot."""
    contexts = {
        7:  {
            "us_focus":  "premarket",
            "my_focus":  "pre-open",
            "search_us": "US stock premarket news futures today",
            "search_my": "Bursa Malaysia market outlook today",
            "label":     "盤前"
        },
        12: {
            "us_focus":  "closed",
            "my_focus":  "midday",
            "search_us": "Wall Street overnight US stock news",
            "search_my": "Bursa Malaysia KLCI midday trading today",
            "label":     "盤中"
        },
        17: {
            "us_focus":  "premarket",
            "my_focus":  "closing",
            "search_us": "US stock premarket earnings news today",
            "search_my": "Bursa Malaysia closing summary today",
            "label":     "收盤/盤前"
        },
        22: {
            "us_focus":  "active",
            "my_focus":  "closed",
            "search_us": "US stock market live news movers today",
            "search_my": "Malaysia market recap today",
            "label":     "美股盤中"
        },
    }
    return contexts.get(hour, contexts[7])

# ─────────────────────────────────────────
# PRICE FETCHER
# ─────────────────────────────────────────
def get_prices(tickers: list) -> dict:
    """Fetch current prices via yfinance. Returns {ticker: {price, change_pct}}"""
    prices = {}
    try:
        data = yf.download(
            tickers,
            period="2d",
            interval="1d",
            progress=False,
            auto_adjust=True
        )
        close = data["Close"]
        for ticker in tickers:
            try:
                col = ticker if ticker in close.columns else close.columns[0]
                vals = close[col].dropna()
                if len(vals) >= 2:
                    prev, curr = float(vals.iloc[-2]), float(vals.iloc[-1])
                    pct = ((curr - prev) / prev) * 100
                    prices[ticker] = {"price": curr, "change_pct": pct}
                elif len(vals) == 1:
                    prices[ticker] = {"price": float(vals.iloc[-1]), "change_pct": 0.0}
            except Exception:
                pass
    except Exception as e:
        print(f"[Price] Error: {e}")
    return prices

def format_price_line(ticker: str, display: str, price_data: dict, currency: str = "USD") -> str:
    """Format: TICKER $123.45 (+1.23%)"""
    if ticker not in price_data:
        return f"{display} — 價格暫無"
    p = price_data[ticker]
    price = p["price"]
    pct   = p["change_pct"]
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
    sym   = "RM" if currency == "MYR" else "$"
    return f"{display} {sym}{price:.2f} {arrow}{abs(pct):.2f}%"

# ─────────────────────────────────────────
# NEWS FETCHER VIA CLAUDE
# ─────────────────────────────────────────
def fetch_news_with_claude(tickers_us: list, tickers_my: list, context: dict) -> dict:
    """
    Ask Claude (with web_search tool) to find news for each ticker.
    Returns {ticker: {"headline": str, "sentiment": str}} or empty if no news.
    """
    ticker_list_us = ", ".join(tickers_us)
    ticker_list_my = ", ".join([t.replace(".KL","") for t in tickers_my])

    prompt = f"""You are a financial news scanner. Search for NEWS ONLY from the LAST 6 HOURS.

Search these US stocks: {ticker_list_us}
Also search: {context['search_us']}

Search these Malaysia stocks: {ticker_list_my}
Also search: {context['search_my']}

Also search: USD MYR exchange rate, crude oil price today, Fed news today, China economy news

RULES:
- Only include a stock if there is REAL news from last 6 hours
- Skip stocks with no recent news (do not fabricate)
- Sentiment: BULLISH, BEARISH, or NEUTRAL

Respond ONLY with valid JSON, no other text:
{{
  "us": {{
    "TICKER": {{"headline": "...", "sentiment": "BULLISH|BEARISH|NEUTRAL"}},
    ...
  }},
  "my": {{
    "TICKER": {{"headline": "...", "sentiment": "BULLISH|BEARISH|NEUTRAL"}},
    ...
  }},
  "macro": [
    {{"topic": "...", "headline": "...", "sentiment": "BULLISH|BEARISH|NEUTRAL"}}
  ]
}}
Only include tickers/topics with actual news. Empty arrays/objects if nothing found."""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "web-search-2025-03-05",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract text from response
        for block in data.get("content", []):
            if block.get("type") == "text":
                text = block["text"].strip()
                # Strip markdown code fences if present
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                return json.loads(text.strip())

    except json.JSONDecodeError as e:
        print(f"[Claude] JSON parse error: {e}")
    except Exception as e:
        print(f"[Claude] API error: {e}")

    return {"us": {}, "my": {}, "macro": []}

# ─────────────────────────────────────────
# MESSAGE BUILDER
# ─────────────────────────────────────────
SENTIMENT_EMOJI = {
    "BULLISH": "🟢",
    "BEARISH": "🔴",
    "NEUTRAL": "⚪",
}

def build_message(hour: int, prices_us: dict, prices_my: dict, news: dict) -> str | None:
    now     = get_jst_now()
    header  = get_session_header(hour)
    context = get_market_context(hour)
    time_str = now.strftime("%H:%M")

    lines = [f"{header} {time_str} JST", ""]

    has_content = False

    # ── US section ──
    us_lines = []

    # Holdings first
    for ticker, name in {**US_HOLDINGS, **US_WATCHLIST}.items():
        price_line = format_price_line(ticker, ticker, prices_us, "USD")
        news_item  = news.get("us", {}).get(ticker)
        if news_item:
            emoji = SENTIMENT_EMOJI.get(news_item["sentiment"], "⚪")
            us_lines.append(f"{emoji} {price_line}")
            us_lines.append(f"   └ {news_item['headline']}")
            has_content = True
        elif ticker in US_HOLDINGS:
            # Always show holdings price even without news
            us_lines.append(f"⚪ {price_line}")

    if us_lines:
        lines.append("━━━ 🇺🇸 美股 ━━━")
        lines.extend(us_lines)
        lines.append("")

    # ── Malaysia section ──
    my_lines = []

    for ticker, name in {**MY_HOLDINGS, **MY_WATCHLIST}.items():
        short = ticker.replace(".KL", "")
        price_line = format_price_line(ticker, name, prices_my, "MYR")
        news_item  = news.get("my", {}).get(short) or news.get("my", {}).get(name)
        if news_item:
            emoji = SENTIMENT_EMOJI.get(news_item["sentiment"], "⚪")
            my_lines.append(f"{emoji} {price_line}")
            my_lines.append(f"   └ {news_item['headline']}")
            has_content = True
        elif ticker in MY_HOLDINGS:
            my_lines.append(f"⚪ {price_line}")

    if my_lines:
        lines.append("━━━ 🇲🇾 馬股 ━━━")
        lines.extend(my_lines)
        lines.append("")

    # ── Macro section ──
    macro_items = news.get("macro", [])
    if macro_items:
        lines.append("━━━ 🌐 宏觀 ━━━")
        for item in macro_items[:3]:
            emoji = SENTIMENT_EMOJI.get(item.get("sentiment", "NEUTRAL"), "⚪")
            lines.append(f"{emoji} {item['topic']}: {item['headline']}")
        has_content = True
        lines.append("")

    # No news at all → skip sending
    if not has_content:
        return None

    lines.append(f"🔎 下次更新 {context['label']}")
    return "\n".join(lines)

# ─────────────────────────────────────────
# TELEGRAM SENDER
# ─────────────────────────────────────────
def send_telegram(message: str) -> bool:
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()
        print("[Telegram] ✅ Message sent")
        return True
    except Exception as e:
        print(f"[Telegram] ❌ Error: {e}")
        return False

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    now  = get_jst_now()
    hour = now.hour
    print(f"[Monitor] Running at {now.strftime('%Y-%m-%d %H:%M')} JST (hour={hour})")

    # Only run at designated hours
    if hour not in [7, 12, 17, 22]:
        print(f"[Monitor] Not a scheduled hour ({hour}), exiting.")
        return

    context = get_market_context(hour)

    # 1. Fetch prices
    print("[Prices] Fetching US prices...")
    all_us_tickers = list(US_HOLDINGS.keys()) + list(US_WATCHLIST.keys())
    prices_us = get_prices(all_us_tickers)

    print("[Prices] Fetching Malaysia prices...")
    all_my_tickers = list(MY_HOLDINGS.keys()) + list(MY_WATCHLIST.keys())
    prices_my = get_prices(all_my_tickers)

    # 2. Fetch news via Claude
    print("[News] Fetching news via Claude...")
    news = fetch_news_with_claude(
        tickers_us=list(US_HOLDINGS.keys()) + list(US_WATCHLIST.keys()),
        tickers_my=list(MY_HOLDINGS.keys()) + list(MY_WATCHLIST.keys()),
        context=context
    )

    # 3. Build message
    message = build_message(hour, prices_us, prices_my, news)

    if message is None:
        print("[Monitor] No news found, skipping Telegram send.")
        return

    print("[Message] Built:\n" + message)

    # 4. Send to Telegram
    send_telegram(message)


if __name__ == "__main__":
    main()
