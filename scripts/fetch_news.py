#!/usr/bin/env python3
"""Stáhne RSS kanály, vyfiltruje kriminálky, přiřadí prefekturu a uloží docs/data/news.json."""
import json, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "news.json"
KEEP_DAYS, MAX_ITEMS = 7, 3000

# Ověřte si URL kanálů, adresy se u médií občas mění. Přidávejte další (regionální deníky apod.).
FEEDS = [
    ("NHK 社会", "https://www.nhk.or.jp/rss/news/cat1.xml"),
    ("Yahoo! 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
    ("Yahoo! 地域", "https://news.yahoo.co.jp/rss/categories/local.xml"),
    ("毎日新聞 速報", "https://mainichi.jp/rss/etc/mainichi-flash.rss"),
    ("朝日新聞", "https://www.asahi.com/rss/asahi/newsheadlines.rdf"),
]

CATEGORIES = {  # pořadí = priorita
    "murder":  ["殺人", "殺害", "死体遺棄", "遺体", "刺され", "刺殺"],
    "robbery": ["強盗", "ひったくり"],
    "assault": ["傷害", "暴行", "殴", "刺した"],
    "arson":   ["放火"],
    "drugs":   ["覚醒剤", "大麻", "麻薬", "薬物", "コカイン"],
    "fraud":   ["詐欺", "闇バイト", "不正アクセス"],
    "theft":   ["窃盗", "盗んだ", "盗み", "万引", "空き巣", "車上狙い"],
    "traffic": ["ひき逃げ", "飲酒運転", "危険運転"],
    "other":   ["逮捕", "容疑者", "容疑で", "送検", "指名手配", "わいせつ", "不同意"],
}

PREFS = ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県","群馬県",
 "埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県","山梨県","長野県",
 "岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県",
 "鳥取県","島根県","岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県","福岡県",
 "佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]

CITIES = {  # město → prefektura (doplňte podle potřeby)
 "札幌":"北海道","函館":"北海道","旭川":"北海道","仙台":"宮城県","さいたま":"埼玉県","川口":"埼玉県",
 "千葉市":"千葉県","船橋":"千葉県","柏市":"千葉県","新宿":"東京都","渋谷":"東京都","池袋":"東京都",
 "八王子":"東京都","町田":"東京都","横浜":"神奈川県","川崎":"神奈川県","相模原":"神奈川県","藤沢":"神奈川県",
 "横須賀":"神奈川県","新潟市":"新潟県","金沢":"石川県","長野市":"長野県","静岡市":"静岡県","浜松":"静岡県",
 "名古屋":"愛知県","豊橋":"愛知県","岡崎":"愛知県","京都市":"京都府","大阪市":"大阪府","堺市":"大阪府",
 "東大阪":"大阪府","神戸":"兵庫県","姫路":"兵庫県","西宮":"兵庫県","奈良市":"奈良県","和歌山市":"和歌山県",
 "岡山市":"岡山県","倉敷":"岡山県","広島市":"広島県","福山":"広島県","松山":"愛媛県","高松":"香川県",
 "福岡市":"福岡県","北九州":"福岡県","久留米":"福岡県","熊本市":"熊本県","鹿児島市":"鹿児島県","那覇":"沖縄県",
}

def classify(text):
    for cat, words in CATEGORIES.items():
        if any(w in text for w in words):
            return cat

def find_pref(text):
    hits = [(text.find(p), p) for p in PREFS if p in text]
    hits += [(text.find(c), p) for c, p in CITIES.items() if c in text]
    return min(hits)[1] if hits else None

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "japan-crime-map/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    for el in root.iter():
        el.tag = el.tag.split("}")[-1]
    for it in list(root.iter("item")) + list(root.iter("entry")):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not link:
            l = it.find("link")
            link = l.get("href", "") if l is not None else ""
        desc = re.sub(r"<[^>]+>", "", it.findtext("description") or it.findtext("summary") or "")[:200]
        date = (it.findtext("pubDate") or it.findtext("date") or it.findtext("updated")
                or it.findtext("published") or "")
        yield title, link, desc, date

def to_iso(s):
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: d = datetime.now(timezone.utc)
    if d.tzinfo is None: d = d.replace(tzinfo=timezone(timedelta(hours=9)))
    return d.astimezone(timezone.utc).isoformat()

def main():
    old = json.loads(OUT.read_text("utf-8"))["items"] if OUT.exists() else []
    items = {i["link"]: i for i in old}
    for name, url in FEEDS:
        try:
            for title, link, desc, date in parse(fetch(url)):
                if not title or not link or link in items: continue
                cat = classify(title + desc)
                if not cat: continue
                items[link] = {"title": title, "link": link, "summary": desc, "source": name,
                               "time": to_iso(date), "category": cat,
                               "prefecture": find_pref(title + desc)}
        except Exception as e:
            print(f"! {name}: {e}", file=sys.stderr)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    out = sorted((i for i in items.values() if i["time"] >= cutoff),
                 key=lambda i: i["time"], reverse=True)[:MAX_ITEMS]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "items": out},
                              ensure_ascii=False, indent=1), "utf-8")
    print(f"Uloženo {len(out)} zpráv")

if __name__ == "__main__":
    main()
