#!/usr/bin/env python3
"""Stáhne RSS zprávy, vybere kriminální, přiřadí prefekturu a kategorii, zapíše data/news.json.
Jen standardní knihovna. Spouštět z kořene repozitáře: python scripts/fetch_news.py"""
import json, re, sys, urllib.request, email.utils
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path("data/news.json")
KEEP_DAYS = 14
JST = timezone(timedelta(hours=9))

# Můžeš upravit/přidat. Nefunkční feed se přeskočí a vypíše se do logu.
FEEDS = [
    ("NHK", "https://www3.nhk.or.jp/rss/news/cat3.xml"),
    ("Yahoo!ニュース 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
    ("Yahoo!ニュース 地域", "https://news.yahoo.co.jp/rss/topics/local.xml"),
    ("毎日新聞", "https://mainichi.jp/rss/etc/mainichi-flash.rss"),
    ("朝日新聞", "https://www.asahi.com/rss/asahi/national.rdf"),
]

PREFS = ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]

# Hledané výrazy -> prefektura. Delší výrazy se hledají první a zamaskují se,
# takže "東京都" nikdy nespadne pod "京都".
NEEDLES = {p: p for p in PREFS}
for p in PREFS:
    NEEDLES[p.rstrip("県都府")] = p if p != "北海道" else p
NEEDLES.update({"警視庁": "東京都", "道警": "北海道"})
for w in "千代田区 新宿区 文京区 台東区 墨田区 江東区 品川区 目黒区 大田区 世田谷区 渋谷区 中野区 杉並区 豊島区 荒川区 板橋区 練馬区 足立区 葛飾区 江戸川区 歌舞伎町 池袋 秋葉原 六本木 八王子 立川 町田".split():
    NEEDLES[w] = "東京都"
for city, pref in {"札幌":"北海道","仙台":"宮城県","さいたま":"埼玉県","横浜":"神奈川県","川崎市":"神奈川県","相模原":"神奈川県",
                   "名古屋":"愛知県","大阪市":"大阪府","堺市":"大阪府","京都市":"京都府","神戸":"兵庫県","福岡市":"福岡県",
                   "北九州":"福岡県","広島市":"広島県","那覇":"沖縄県","千葉市":"千葉県","新潟市":"新潟県","静岡市":"静岡県","熊本市":"熊本県"}.items():
    NEEDLES[city] = pref
ORDERED = sorted(NEEDLES, key=len, reverse=True)

def find_pref(text):
    hits = []
    for n in ORDERED:
        start = 0
        while (i := text.find(n, start)) != -1:
            hits.append((i, NEEDLES[n]))
            text = text[:i] + "\0" * len(n) + text[i + len(n):]
            start = i + len(n)
    return min(hits)[1] if hits else None

GATE = re.compile(r"逮捕|容疑|送検|起訴|事件|警察|県警|警視庁|府警|道警|強盗|殺人|殺害|放火|詐欺|ひき逃げ")
CATS = [
    ("murder",  r"殺人|殺害|刺殺|絞殺|死体遺棄|遺体|殺され"),
    ("robbery", r"強盗|強奪|ひったくり"),
    ("arson",   r"放火"),
    ("drugs",   r"覚醒剤|覚せい剤|大麻|麻薬|薬物|MDMA|コカイン"),
    ("fraud",   r"詐欺|架空請求|闇バイト"),
    ("theft",   r"窃盗|万引|盗難|盗んだ|盗んで|盗み"),
    ("assault", r"傷害|暴行|刺され|刺した|殴"),
    ("traffic", r"ひき逃げ|飲酒運転|酒気帯び|あおり運転|死亡事故|交通事故"),
]
CATS = [(c, re.compile(r)) for c, r in CATS]

def categorize(text):
    for c, rx in CATS:
        if rx.search(text):
            return c
    return "other"

def tag(el): return el.tag.rsplit("}", 1)[-1]

def parse_time(s):
    if not s: return None
    try: d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=JST)
    return d.astimezone(timezone.utc)

def parse_feed(data, source):
    root = ET.fromstring(data)
    for el in root.iter():
        if tag(el) not in ("item", "entry"): continue
        d = {}
        for c in el:
            t = tag(c)
            if t == "link" and not (c.text or "").strip():
                d["link"] = c.get("href", "")
            else:
                d.setdefault(t, (c.text or "").strip())
        title = d.get("title", "")
        desc = re.sub(r"<[^>]+>", "", d.get("description", "") or d.get("summary", ""))
        link = d.get("link") or d.get("guid", "")
        t = parse_time(d.get("pubDate") or d.get("date") or d.get("published") or d.get("updated"))
        if not title or not link: continue
        text = title + " " + desc
        if not GATE.search(text): continue
        yield {"title": title, "link": link, "source": source,
               "time": (t or datetime.now(timezone.utc)).isoformat(),
               "category": categorize(text), "prefecture": find_pref(text)}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (japan-crime-news-map)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def main():
    items = {}
    if OUT.exists():
        try:
            for i in json.loads(OUT.read_text("utf-8")).get("items", []): items[i["link"]] = i
        except Exception as e: print("old news.json unreadable:", e)
    new = 0
    for source, url in FEEDS:
        try:
            got = list(parse_feed(fetch(url), source))
            print(f"{source}: {len(got)} crime items")
            for i in got:
                if i["link"] not in items: new += 1
                items[i["link"]] = i
        except Exception as e:
            print(f"{source}: FAILED ({e})", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    out = sorted((i for i in items.values() if datetime.fromisoformat(i["time"]) >= cutoff),
                 key=lambda i: i["time"], reverse=True)[:3000]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "items": out},
                              ensure_ascii=False), "utf-8")
    print(f"{new} new, {len(out)} total")

if __name__ == "__main__":
    main()
