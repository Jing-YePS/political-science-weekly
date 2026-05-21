#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import textwrap
import time
import urllib.parse
import urllib.request


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORTS_DIR = os.path.join(ROOT, "reports")
INDEX_PATH = os.path.join(ROOT, "index.html")

JOURNALS = [
    {"name": "American Political Science Review", "issns": ["0003-0554", "1537-5943"]},
    {"name": "American Journal of Political Science", "issns": ["0092-5853", "1540-5907"]},
    {"name": "Journal of Politics", "issns": ["0022-3816", "1468-2508"]},
    {"name": "World Politics", "issns": ["0043-8871", "1086-3338"]},
    {"name": "International Organization", "issns": ["0020-8183", "1531-5088"]},
    {"name": "Comparative Political Studies", "issns": ["0010-4140", "1552-3829"]},
    {"name": "British Journal of Political Science", "issns": ["0007-1234", "1469-2112"]},
    {"name": "Political Analysis", "issns": ["1047-1987", "1476-4989"]},
    {"name": "Political Behavior", "issns": ["0190-9320", "1573-6687"]},
    {"name": "Governance", "issns": ["0952-1895", "1468-0491"]},
    {"name": "Perspectives on Politics", "issns": ["1537-5927", "1541-0986"]},
    {"name": "The China Quarterly", "issns": ["0305-7410", "1468-2648"]},
    {"name": "American Sociological Review", "issns": ["0003-1224", "1939-8271"]},
]

EXCLUDED_SUBTYPES = {
    "book review",
    "review",
    "erratum",
    "correction",
    "editorial",
    "introduction",
    "front matter",
    "back matter",
}


def iso_date(value):
    return value.isoformat()


def parse_args():
    today = dt.date.today()
    default_end = today - dt.timedelta(days=today.weekday() + 1)
    default_start = default_end - dt.timedelta(days=6)
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-date", default=iso_date(today))
    parser.add_argument("--from-date", default=iso_date(default_start))
    parser.add_argument("--to-date", default=iso_date(default_end))
    return parser.parse_args()


def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "political-science-weekly/1.0 (mailto:example@example.com)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "political-science-weekly/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read(600_000)
        encoding = response.headers.get_content_charset() or "utf-8"
        return raw.decode(encoding, errors="replace")


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def date_parts_to_date(parts):
    if not parts:
        return None
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def item_date(item):
    for key in ("published-online", "published-print", "published", "created"):
        parts = item.get(key, {}).get("date-parts", [[]])[0]
        date = date_parts_to_date(parts)
        if date:
            return date
    return None


def author_names(authors):
    names = []
    for author in authors or []:
        given = author.get("given", "")
        family = author.get("family", "")
        name = " ".join(part for part in [given, family] if part).strip()
        if name:
            names.append(name)
    return "; ".join(names) if names else "页面未说明"


def crossref_items(journal, from_date, to_date):
    rows = []
    seen = set()
    for issn in journal["issns"]:
        params = urllib.parse.urlencode(
            {
                "filter": f"from-pub-date:{from_date},until-pub-date:{to_date},type:journal-article",
                "select": "DOI,title,author,published,published-online,published-print,created,subtype,container-title,abstract,URL",
                "rows": "100",
                "sort": "published",
                "order": "desc",
            }
        )
        url = f"https://api.crossref.org/journals/{issn}/works?{params}"
        try:
            data = fetch_json(url)
        except Exception as exc:
            print(f"warning: Crossref failed for {journal['name']} {issn}: {exc}", file=sys.stderr)
            continue
        for item in data.get("message", {}).get("items", []):
            doi = item.get("DOI")
            title = clean_text((item.get("title") or [""])[0])
            key = (doi or title).lower()
            if not key or key in seen:
                continue
            subtype = clean_text(item.get("subtype", "")).lower()
            if subtype in EXCLUDED_SUBTYPES or any(token in title.lower() for token in ["book review", "erratum", "correction"]):
                continue
            date = item_date(item)
            if not date:
                continue
            if not (from_date <= iso_date(date) <= to_date):
                continue
            seen.add(key)
            rows.append(
                {
                    "journal": journal["name"],
                    "title": title,
                    "authors": author_names(item.get("author")),
                    "date": iso_date(date),
                    "doi": doi or "",
                    "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                    "abstract": clean_text(item.get("abstract", "")),
                }
            )
        time.sleep(0.2)
    return rows


def abstract_from_page(url):
    if not url:
        return ""
    try:
        page = fetch_text(url)
    except Exception:
        return ""
    candidates = []
    for pattern in [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']citation_abstract["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
        match = re.search(pattern, page, flags=re.I)
        if match:
            candidates.append(clean_text(match.group(1)))
    if candidates:
        return max(candidates, key=len)
    return ""


def collect_papers(from_date, to_date):
    papers = []
    empty_journals = []
    seen = set()
    for journal in JOURNALS:
        items = crossref_items(journal, from_date, to_date)
        if not items:
            empty_journals.append(journal["name"])
        for item in items:
            key = (item.get("doi") or item["title"]).lower()
            if key in seen:
                continue
            seen.add(key)
            if not item["abstract"]:
                item["abstract"] = abstract_from_page(item["url"])
            papers.append(item)
    papers.sort(key=lambda row: (row["date"], row["journal"], row["title"]))
    return papers, empty_journals


def openai_json(papers):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not papers:
        return []
    try:
        from openai import OpenAI
    except Exception as exc:
        print(f"warning: openai package unavailable: {exc}", file=sys.stderr)
        return []

    client = OpenAI(api_key=api_key)
    payload = [
        {
            "journal": paper["journal"],
            "title": paper["title"],
            "authors": paper["authors"],
            "date": paper["date"],
            "doi": paper["doi"],
            "url": paper["url"],
            "abstract": paper["abstract"] or "摘要未说明",
        }
        for paper in papers
    ]
    prompt = (
        "你是政治学和社会学期刊周报助手。请基于给定论文元数据和摘要生成中文表格字段。"
        "不要编造摘要没有的信息；资料不足时写“摘要未说明”或“页面未说明”。"
        "只输出 JSON 对象，格式为 {\"papers\": [...]}。papers 数组中每个对象包含 keys: "
        "chinese_abstract, topic, question, method, data, findings。"
    )
    response = client.responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        text={"format": {"type": "json_object"}},
    )
    text = response.output_text
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        for key in ("papers", "items", "results"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
    if isinstance(parsed, list):
        return parsed
    return []


def fallback_analysis(paper):
    abstract = paper.get("abstract") or ""
    if abstract:
        zh = "需要设置 OPENAI_API_KEY 后自动翻译。英文摘要：" + abstract[:900]
    else:
        zh = "页面未说明摘要；需要人工核对论文页面。"
    return {
        "chinese_abstract": zh,
        "topic": "待模型归纳",
        "question": "摘要未说明",
        "method": "摘要未说明",
        "data": "摘要未说明",
        "findings": "摘要未说明",
    }


def enrich_papers(papers):
    generated = []
    try:
        generated = openai_json(papers)
    except Exception as exc:
        print(f"warning: OpenAI enrichment failed: {exc}", file=sys.stderr)
    for idx, paper in enumerate(papers):
        analysis = generated[idx] if idx < len(generated) and isinstance(generated[idx], dict) else fallback_analysis(paper)
        paper.update(
            {
                "chinese_abstract": clean_text(analysis.get("chinese_abstract", "")) or fallback_analysis(paper)["chinese_abstract"],
                "topic": clean_text(analysis.get("topic", "")) or "摘要未说明",
                "question": clean_text(analysis.get("question", "")) or "摘要未说明",
                "method": clean_text(analysis.get("method", "")) or "摘要未说明",
                "data": clean_text(analysis.get("data", "")) or "摘要未说明",
                "findings": clean_text(analysis.get("findings", "")) or "摘要未说明",
            }
        )
    return papers


def esc(value):
    return html.escape(str(value or ""), quote=True)


def paper_rows(papers):
    rows = []
    for paper in papers:
        source = paper.get("url") or (f"https://doi.org/{paper['doi']}" if paper.get("doi") else "")
        doi_label = paper.get("doi") or "来源"
        rows.append(
            textwrap.dedent(
                f"""
                <tr>
                  <td>{esc(paper["journal"])}</td>
                  <td>{esc(paper["title"])}</td>
                  <td>{esc(paper["authors"])}</td>
                  <td>{esc(paper["date"])}</td>
                  <td>{esc(paper["chinese_abstract"])}</td>
                  <td>{esc(paper["topic"])}</td>
                  <td>{esc(paper["question"])}</td>
                  <td>{esc(paper["method"])}</td>
                  <td>{esc(paper["data"])}</td>
                  <td>{esc(paper["findings"])}</td>
                  <td><a href="{esc(source)}">{esc(doi_label)}</a></td>
                </tr>
                """
            ).strip()
        )
    return "\n".join(rows)


def render_report(report_date, from_date, to_date, papers, empty_journals):
    empty = "、".join(empty_journals) if empty_journals else "无"
    rows = paper_rows(papers) or '<tr><td colspan="11">本周未检索到符合条件的新研究论文。</td></tr>'
    return textwrap.dedent(
        f"""\
        <!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{esc(report_date)} 政治学与社会科学英文期刊周报</title>
          <link rel="stylesheet" href="../site.css">
        </head>
        <body>
          <main class="page">
            <header class="masthead">
              <p class="eyebrow">Weekly Literature Monitor</p>
              <h1>{esc(report_date)} 周报</h1>
              <p class="lede">覆盖日期：{esc(from_date)} 至 {esc(to_date)}。收录范围为主要英文政治学期刊、The China Quarterly 与 American Sociological Review 的新发表、FirstView、OnlineFirst 或 advance articles。</p>
              <p class="report-meta"><a href="../index.html">返回周报目录</a></p>
            </header>

            <section class="summary">
              <strong>本周概览</strong>
              <span>本期确认收录 {len(papers)} 篇研究论文或正式学术文章；排除书评、勘误、编者按和非研究性内容。</span>
              <span>本周未在监测窗口内确认新研究论文的期刊：{esc(empty)}。</span>
              <span>检索说明：方法和资料字段基于论文页面、Crossref 元数据、摘要和可访问说明归纳；来源不足处标明“摘要未说明”或“页面未说明”。</span>
            </section>

            <section class="section">
              <h2>论文表</h2>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>期刊</th>
                      <th>英文题目</th>
                      <th>作者</th>
                      <th>发表日期</th>
                      <th>中文摘要</th>
                      <th>研究主题</th>
                      <th>研究问题</th>
                      <th>研究方法</th>
                      <th>研究资料/数据</th>
                      <th>主要发现</th>
                      <th>来源</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows}
                  </tbody>
                </table>
              </div>
            </section>
          </main>
        </body>
        </html>
        """
    )


def update_index(report_date, from_date, to_date, count):
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        index = handle.read()
    item = textwrap.dedent(
        f"""\
        <li>
          <a href="reports/{esc(report_date)}.html">{esc(report_date)}</a>
          <span>{count} 篇论文 · 覆盖 {esc(from_date)} 至 {esc(to_date)}</span>
        </li>"""
    )
    pattern = re.compile(r'        <li>\s*<a href="reports/' + re.escape(report_date) + r'\.html">.*?</li>\n?', re.S)
    index = pattern.sub("", index)
    index = index.replace('        <li class="empty">尚未生成周报。第一次自动更新后会出现在这里。</li>\n', "")
    marker = '      <ul class="report-list">\n'
    if marker not in index:
        raise RuntimeError("Cannot find report-list in index.html")
    index = index.replace(marker, marker + textwrap.indent(item, "        ") + "\n", 1)
    with open(INDEX_PATH, "w", encoding="utf-8") as handle:
        handle.write(index)


def main():
    args = parse_args()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    papers, empty_journals = collect_papers(args.from_date, args.to_date)
    papers = enrich_papers(papers)
    report_html = render_report(args.report_date, args.from_date, args.to_date, papers, empty_journals)
    report_path = os.path.join(REPORTS_DIR, f"{args.report_date}.html")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(report_html)
    update_index(args.report_date, args.from_date, args.to_date, len(papers))
    print(f"report={report_path}")
    print(f"papers={len(papers)}")
    print(f"empty_journals={'; '.join(empty_journals) if empty_journals else 'none'}")


if __name__ == "__main__":
    main()
