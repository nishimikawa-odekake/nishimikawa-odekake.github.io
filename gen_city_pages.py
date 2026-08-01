#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
あいち子育ておでかけマップ - 市町村別SEOページ自動生成スクリプト

正マスターデータ: /root/kosodate-data/spots_map.json
出力先: /root/site/city-{slug}.html （ルート直下）
索引: index.html の読みものセクション付近に「市町村から探す」を追加
sitemap.xml に生成ページを追加

再実行可能（idempotent）: 既存の city-*.html は毎回上書きされる。
"""
import json
import re
import collections
import datetime
import os

SITE_DIR = "/root/site"
DATA_PATH = "/root/kosodate-data/spots_map.json"
BASE_URL = "https://nishimikawa-odekake.com"
GA_ID = "G-8CDXHXFG9F"
TODAY = datetime.date.today().isoformat()

# --- 市町村名 正規化 -------------------------------------------------
COUNTIES = ['丹羽郡', '愛知郡', '海部郡', '知多郡', '西春日井郡']


def normalize_city(city):
    if not city:
        return city
    c = city.strip()
    if c.startswith('名古屋市'):
        return '名古屋市'
    for co in COUNTIES:
        if c.startswith(co):
            return c[len(co):]
    c = re.sub(r'（.*郡）', '', c)
    return c


# --- 市町村名 -> ローマ字slug -----------------------------------------
CITY_SLUGS = {
    '名古屋市': 'nagoya',
    '岡崎市': 'okazaki',
    '一宮市': 'ichinomiya',
    '安城市': 'anjo',
    '刈谷市': 'kariya',
    '西尾市': 'nishio',
    '東海市': 'tokai',
    '豊田市': 'toyota',
    '豊川市': 'toyokawa',
    '半田市': 'handa',
    '蒲郡市': 'gamagori',
    '大府市': 'obu',
    'みよし市': 'miyoshi',
    '碧南市': 'hekinan',
    '常滑市': 'tokoname',
    '尾張旭市': 'owariasahi',
    '豊橋市': 'toyohashi',
    '小牧市': 'komaki',
    '長久手市': 'nagakute',
    '稲沢市': 'inazawa',
    '豊明市': 'toyoake',
    '北名古屋市': 'kitanagoya',
    '東浦町': 'higashiura',
    '春日井市': 'kasugai',
    '犬山市': 'inuyama',
    '新城市': 'shinshiro',
    '愛西市': 'aisai',
    '田原市': 'tahara',
    '知立市': 'chiryu',
    '岩倉市': 'iwakura',
    '清須市': 'kiyosu',
    '弥富市': 'yatomi',
    '東郷町': 'togo',
    '日進市': 'nisshin',
    '豊山町': 'toyoyama',
    '武豊町': 'taketoyo',
    'あま市': 'ama',
    '蟹江町': 'kanie',
    '高浜市': 'takahama',
    '瀬戸市': 'seto',
    '幸田町': 'kota',
    '知多市': 'chita',
    '南知多町': 'minamichita',
    '江南市': 'konan',
    '津島市': 'tsushima',
    '大治町': 'oharu',
    '大口町': 'oguchi',
    '阿久比町': 'agui',
    '扶桑町': 'fuso',
    '飛島村': 'tobishima',
    '美浜町': 'mihama',
}

MIN_SPOTS = 5


def esc(s):
    if s is None:
        return ''
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def badge_list(spot):
    badges = []
    if spot.get('is_free'):
        badges.append('無料')
    if spot.get('rain_friendly'):
        badges.append('雨の日OK')
    if spot.get('has_kids_space'):
        badges.append('キッズスペース')
    if spot.get('has_zashiki'):
        badges.append('お座敷')
    if spot.get('nursing_room'):
        badges.append('授乳室')
    if spot.get('diaper_changing'):
        badges.append('おむつ替え台')
    if spot.get('stroller_access'):
        badges.append('ベビーカーOK')
    if spot.get('parking'):
        badges.append('駐車場あり')
    return badges


def spot_card(spot, extra_class=""):
    badges = badge_list(spot)
    badge_html = ''.join(f'<span class="badge">{esc(b)}</span>' for b in badges)
    ka = spot.get('kid_appeal') or spot.get('summary') or ''
    links = []
    if spot.get('official_url'):
        links.append(f'<a class="btn" href="{esc(spot["official_url"])}" target="_blank" rel="noopener">公式サイト</a>')
    if spot.get('google_maps_url'):
        links.append(f'<a class="btn ghost" href="{esc(spot["google_maps_url"])}" target="_blank" rel="noopener">Googleマップ</a>')
    links_html = ''.join(links)
    info_bits = []
    if spot.get('price_text'):
        info_bits.append(f'<dt>料金</dt><dd>{esc(spot["price_text"])}</dd>')
    if spot.get('business_hours'):
        info_bits.append(f'<dt>営業時間</dt><dd>{esc(spot["business_hours"])}</dd>')
    if spot.get('closed_days'):
        info_bits.append(f'<dt>休み</dt><dd>{esc(spot["closed_days"])}</dd>')
    info_html = f'<dl class="info">{"".join(info_bits)}</dl>' if info_bits else ''
    checked = spot.get('checked_at') or ''
    ck_html = f'<p class="ck">確認日: {esc(checked)}</p>' if checked else ''
    return (f'<article class="card {extra_class}"><h3>{esc(spot["name"])}</h3>'
            f'<p class="ka">{esc(ka)}</p>'
            f'<div class="badges">{badge_html}</div>'
            f'{info_html}'
            f'<div class="links">{links_html}</div>'
            f'{ck_html}</article>')


def jidokan_card(spot):
    links = []
    if spot.get('official_url'):
        links.append(f'<a class="btn" href="{esc(spot["official_url"])}" target="_blank" rel="noopener">公式サイト</a>')
    if spot.get('google_maps_url'):
        links.append(f'<a class="btn ghost" href="{esc(spot["google_maps_url"])}" target="_blank" rel="noopener">Googleマップ</a>')
    links_html = ''.join(links)
    ka = spot.get('kid_appeal') or spot.get('summary') or ''
    info_bits = []
    if spot.get('business_hours'):
        info_bits.append(f'<dt>開館時間</dt><dd>{esc(spot["business_hours"])}</dd>')
    if spot.get('closed_days'):
        info_bits.append(f'<dt>休み</dt><dd>{esc(spot["closed_days"])}</dd>')
    info_html = f'<dl class="info">{"".join(info_bits)}</dl>' if info_bits else ''
    return (f'<article class="card jd"><h3>{esc(spot["name"])}</h3>'
            f'<p class="ka">{esc(ka)}</p>{info_html}'
            f'<div class="links">{links_html}</div></article>')


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}');
</script>
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="あいち子育ておでかけマップ">
<meta property="og:image" content="{base}/og-logo.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#e08a5b">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script type="application/ld+json">{{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{{"@type": "ListItem", "position": 1, "name": "あいち子育ておでかけマップ", "item": "{base}/"}}, {{"@type": "ListItem", "position": 2, "name": "{city}の子連れおでかけスポット一覧"}}]}}</script>
<style>*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;background:#faf6ef;color:#3d3a34;line-height:1.7;-webkit-text-size-adjust:100%}}
a{{color:#c9713f}}img{{max-width:100%;display:block}}
.wrap{{max-width:760px;margin:0 auto;padding:0 14px}}
header.hero{{background:linear-gradient(160deg,#fbe6d3,#f6ede0);padding:20px 0 16px;border-bottom:1px solid #e7ddcd}}
header.hero .bc{{font-size:.78rem;color:#7a746a;margin:0 0 8px}}
header.hero .bc a{{color:#7a746a}}
h1{{font-size:1.35rem;margin:0 0 8px;letter-spacing:.02em;color:#c9713f}}
.lead{{font-size:.95rem;color:#5c574e;margin:0}}
main{{padding:18px 0 8px}}
h2.sec{{font-size:1.1rem;margin:26px 0 12px;color:#3d3a34;border-left:5px solid #e08a5b;padding-left:10px}}
.card{{background:#fffdf9;border:1px solid #e7ddcd;border-radius:16px;padding:16px;margin:0 0 14px;box-shadow:0 1px 2px rgba(0,0,0,.03)}}
.card h3{{font-size:1.05rem;margin:0 0 8px}}
.ka{{margin:0 0 10px;font-size:.92rem;color:#5c574e}}
.badges{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}}
.badge{{display:inline-block;background:#fbf1e3;color:#a8703f;border:1px solid #ecd9bf;border-radius:999px;padding:3px 10px;font-size:.72rem;font-weight:700}}
dl.info{{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:0 0 12px;font-size:.85rem}}
dl.info dt{{color:#7a746a}}dl.info dd{{margin:0}}
.links{{display:flex;gap:8px;flex-wrap:wrap}}
.btn{{display:inline-block;background:#e08a5b;color:#fff;text-decoration:none;padding:8px 14px;border-radius:999px;font-size:.85rem;font-weight:700}}
.btn.ghost{{background:#fff;color:#c9713f;border:1px solid #e0b090}}
.ck{{font-size:.72rem;color:#9a948a;margin:10px 0 0}}
.jd{{background:#f6f2ea}}
.tohome{{display:block;text-align:center;background:#c9713f;color:#fff;text-decoration:none;padding:14px;border-radius:14px;font-weight:700;margin:22px 0 8px}}
.toplan{{display:block;text-align:center;background:#fff;color:#c9713f;border:1px solid #e0b090;text-decoration:none;padding:12px;border-radius:14px;font-weight:700;margin:0 0 22px}}
.rel{{margin:14px 0}}
.rel h3{{font-size:.95rem;margin:0 0 8px}}
.rel ul{{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:8px}}
.rel a{{display:inline-block;background:#fffdf9;border:1px solid #e7ddcd;border-radius:999px;padding:7px 13px;font-size:.83rem;text-decoration:none}}
footer{{border-top:1px solid #e7ddcd;padding:18px 0 40px;color:#7a746a;font-size:.78rem;text-align:center}}
.note{{background:#fbf1e3;border:1px solid #ecd9bf;border-radius:12px;padding:12px 14px;font-size:.82rem;color:#6b6459;margin:16px 0}}
.empty{{font-size:.88rem;color:#9a948a;margin:0 0 14px}}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
<p class="bc"><a href="{base}/">あいち子育ておでかけマップ</a> &rsaquo; {city}の子連れおでかけスポット一覧</p>
<h1>{city}の子連れおでかけスポット一覧</h1>
<p class="lead">{lead}</p>
</div></header>
<main><div class="wrap">

<h2 class="sec">🎠 遊びスポット一覧（{play_count}件）</h2>
{play_cards}

<h2 class="sec">🍽️ 子連れOKのごはん</h2>
{food_cards}

<h2 class="sec">🏠 児童館・支援センター（{jidokan_count}件）</h2>
{jidokan_cards}

<a class="tohome" href="{base}/">地図で{city}周辺のスポットを見る →</a>
<a class="toplan" href="{base}/plan.html">おでかけプランナーで自分だけのコースを作る →</a>

<nav class="rel"><h3>関連ページ</h3><ul>{rel_links}</ul></nav>

<div class="note">掲載情報は作成時点のものです。営業時間・料金・休館日などは変更される場合がありますので、お出かけ前に公式サイト等で最新情報をご確認ください。本サイトは各施設・自治体の公式サイトではありません。</div>
</div></main>
<footer><div class="wrap">あいち子育ておでかけマップ｜愛知の子連れおでかけ・遊び場・ランチ検索<div class="footlinks" style="margin-top:8px;font-size:.72rem"><a href="{base}/about.html">運営者情報</a> | <a href="{base}/disclaimer.html">免責事項</a> | <a href="{base}/privacy.html">プライバシーポリシー</a> | <a href="https://docs.google.com/forms/d/e/1FAIpQLSdcSuUG_4MbFgNq-Ejn_cfDvXKhQdQZh4DxITrDiKlo4ocFfw/viewform" target="_blank" rel="noopener">お問い合わせ</a> | <a href="{base}/request.html">掲載情報の修正・削除依頼</a></div></div></footer>
</body>
</html>
"""


def build_page(city, spots):
    play_spots = [s for s in spots if not s.get('is_jidokan')]
    jidokan_spots = [s for s in spots if s.get('is_jidokan')]
    food_spots = [s for s in play_spots if s.get('food_available')]

    play_count = len(play_spots)
    jidokan_count = len(jidokan_spots)

    lead = f"{city}の子連れで行けるスポット{play_count}件と児童館{jidokan_count}館をまとめました。"
    if jidokan_count == 0:
        lead = f"{city}の子連れで行けるスポット{play_count}件をまとめました。"

    play_cards = ''.join(spot_card(s) for s in play_spots) or '<p class="empty">現在、掲載スポットを準備中です。</p>'
    jidokan_cards = ''.join(jidokan_card(s) for s in jidokan_spots) or '<p class="empty">現在、掲載中の児童館・支援センター情報はありません。</p>'
    if food_spots:
        food_cards = ''.join(spot_card(s) for s in food_spots)
    else:
        food_cards = (f'<p class="empty">{city}内で飲食可否の確認が取れている子連れスポットは現在準備中です。'
                       f'<a href="{BASE_URL}/p/aichi-lunch.html">愛知の子連れランチ一覧</a>もあわせてご覧ください。</p>')

    slug = CITY_SLUGS.get(city)
    canonical = f"{BASE_URL}/city-{slug}.html"
    title = f"{city}の子連れおでかけスポット一覧｜あいち子育ておでかけマップ"
    description = f"{city}で子連れで行ける遊びスポット{play_count}件・児童館{jidokan_count}館をまとめました。無料・雨の日OK・キッズスペースありなど条件つきで探せます。"

    rel_links = (f'<li><a href="{BASE_URL}/">地図で探す</a></li>'
                 f'<li><a href="{BASE_URL}/plan.html">おでかけプランナー</a></li>'
                 f'<li><a href="{BASE_URL}/p/aichi-lunch.html">愛知の子連れランチ一覧</a></li>'
                 f'<li><a href="{BASE_URL}/p/aichi-muryo.html">愛知の無料スポット一覧</a></li>')

    html = PAGE_TEMPLATE.format(
        ga_id=GA_ID,
        title=esc(title),
        description=esc(description),
        canonical=canonical,
        base=BASE_URL,
        city=esc(city),
        lead=esc(lead),
        play_count=play_count,
        play_cards=play_cards,
        food_cards=food_cards,
        jidokan_count=jidokan_count,
        jidokan_cards=jidokan_cards,
        rel_links=rel_links,
    )
    return html, slug, play_count, jidokan_count


def update_sitemap(slugs):
    path = os.path.join(SITE_DIR, 'sitemap.xml')
    with open(path, encoding='utf-8') as f:
        content = f.read()
    existing_locs = set(re.findall(r'<loc>(.*?)</loc>', content))
    new_entries = []
    for slug in slugs:
        loc = f"{BASE_URL}/city-{slug}.html"
        if loc in existing_locs:
            continue
        new_entries.append(f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{TODAY}</lastmod>\n  </url>\n")
    if new_entries:
        content = content.replace('</urlset>', ''.join(new_entries) + '</urlset>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    return len(new_entries)


def update_index(city_list):
    """Insert a compact '市町村から探す' link list into index.html near the readings section."""
    path = os.path.join(SITE_DIR, 'index.html')
    with open(path, encoding='utf-8') as f:
        content = f.read()

    marker_start = '<!-- CITY_INDEX_START -->'
    marker_end = '<!-- CITY_INDEX_END -->'

    links_html = ''.join(
        f'<a href="./city-{CITY_SLUGS[c]}.html">{esc(c)}</a>'
        for c in city_list
    )
    block = (
        f'\n<div class="wrap">\n'
        f'  {marker_start}\n'
        f'  <section class="city-index" aria-label="市町村から探す" style="margin:18px 0">\n'
        f'    <details>\n'
        f'      <summary style="cursor:pointer;font-size:.92rem;font-weight:700;color:#3d3a34;padding:8px 0">📍 市町村から探す</summary>\n'
        f'      <div style="display:flex;flex-wrap:wrap;gap:6px 10px;padding:8px 2px;font-size:.82rem">{links_html}</div>\n'
        f'    </details>\n'
        f'  </section>\n'
        f'  {marker_end}\n'
        f'</div>\n'
    )

    if marker_start in content and marker_end in content:
        pre = content.split(marker_start)[0]
        post = content.split(marker_end)[1]
        inner = block.strip('\n')
        content = pre + inner + post
    else:
        anchor = '<div class="wrap">\n  <section class="readings"'
        if anchor in content:
            content = content.replace(anchor, block.strip('\n') + '\n\n' + anchor, 1)
        else:
            content = content.replace('</body>', block + '</body>')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    with open(DATA_PATH, encoding='utf-8') as f:
        data = json.load(f)
    published = [d for d in data if d.get('status') == 'published']

    by_city = collections.defaultdict(list)
    for d in published:
        c = normalize_city(d.get('city'))
        by_city[c].append(d)

    target_cities = sorted(
        [c for c, spots in by_city.items() if len(spots) >= MIN_SPOTS and c in CITY_SLUGS],
        key=lambda c: -len(by_city[c])
    )

    generated = []
    for city in target_cities:
        spots = by_city[city]
        html, slug, play_count, jidokan_count = build_page(city, spots)
        out_path = os.path.join(SITE_DIR, f"city-{slug}.html")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        generated.append((city, slug, len(spots), play_count, jidokan_count))

    slugs = [CITY_SLUGS[c] for c in target_cities]
    added = update_sitemap(slugs)
    update_index(target_cities)

    print(f"Generated {len(generated)} city pages.")
    for city, slug, total, play, jd in generated:
        print(f"  {city} (city-{slug}.html): total={total} play={play} jidokan={jd}")
    print(f"Sitemap: added {added} new <url> entries.")


if __name__ == '__main__':
    main()
