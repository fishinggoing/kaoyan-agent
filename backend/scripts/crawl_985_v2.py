"""
Crawl re-exam score lines for all 38 985 (+C9) universities — V2.

Smarter crawling: follows actual admission links instead of guessing URLs.
"""
import asyncio, io, logging, os, random, re, ssl, sys
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.models import School, ScoreLine, SchoolLevel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crawl985v2")

REQUEST_DELAY = 3.0
PAGE_DELAY = 1.0
MAX_DETAIL_PAGES = 12
TIMEOUT = 20

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

GRAD_URLS = {
    "清华大学": "https://yz.tsinghua.edu.cn/",
    "北京大学": "https://admission.pku.edu.cn/",
    "浙江大学": "https://yjsy.zju.edu.cn/",
    "上海交通大学": "https://yzb.sjtu.edu.cn/",
    "复旦大学": "https://gsao.fudan.edu.cn/",
    "南京大学": "https://yzb.nju.edu.cn/",
    "中国科学技术大学": "https://yz.ustc.edu.cn/",
    "西安交通大学": "http://yz.xjtu.edu.cn/",
    "哈尔滨工业大学": "http://yzb.hit.edu.cn/",
    "中国人民大学": "http://pgs.ruc.edu.cn/",
    "北京航空航天大学": "https://yzb.buaa.edu.cn/",
    "北京理工大学": "https://grd.bit.edu.cn/",
    "北京师范大学": "https://yz.bnu.edu.cn/",
    "中国农业大学": "http://yz.cau.edu.cn/",
    "中央民族大学": "https://grs.muc.edu.cn/",
    "南开大学": "https://yzb.nankai.edu.cn/",
    "天津大学": "http://yzb.tju.edu.cn/",
    "大连理工大学": "http://gs.dlut.edu.cn/",
    "东北大学": "http://www.graduate.neu.edu.cn/",
    "吉林大学": "http://zsb.jlu.edu.cn/",
    "同济大学": "https://yz.tongji.edu.cn/",
    "华东师范大学": "https://yjszs.ecnu.edu.cn/",
    "厦门大学": "https://zs.xmu.edu.cn/",
    "山东大学": "https://www.yz.sdu.edu.cn/",
    "中国海洋大学": "http://yz.ouc.edu.cn/",
    "武汉大学": "https://gs.whu.edu.cn/",
    "华中科技大学": "http://gszs.hust.edu.cn/",
    "湖南大学": "http://gra.hnu.edu.cn/",
    "中南大学": "https://gra.csu.edu.cn/",
    "中山大学": "https://graduate.sysu.edu.cn/",
    "华南理工大学": "https://yz.scut.edu.cn/",
    "四川大学": "https://yz.scu.edu.cn/",
    "重庆大学": "http://yz.cqu.edu.cn/",
    "电子科技大学": "https://yz.uestc.edu.cn/",
    "西北工业大学": "https://yzb.nwpu.edu.cn/",
    "西北农林科技大学": "https://yz.nwsuaf.edu.cn/",
    "兰州大学": "https://yz.lzu.edu.cn/",
}


def random_ua():
    return random.choice(USER_AGENTS)


async def fetch(client, url):
    try:
        resp = await client.get(url, headers={
            "User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }, timeout=TIMEOUT)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "html" in ct or not ct:
                return resp.text
    except Exception:
        pass
    return None


def find_links(html, base_url, keywords):
    """Find all <a> links whose text or href contains any keyword. Returns [(url, text)]."""
    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"].strip()
        if not text or len(text) < 3:
            continue
        full = urljoin(base_url, href)
        if full.startswith(("javascript:", "mailto:", "#")):
            continue
        combined = text + " " + href
        if any(kw in combined for kw in keywords):
            key = full[:200]
            if key not in seen:
                seen.add(key)
                results.append((full, text))
    return results


def parse_score_data(html, school_id):
    """Parse score line data from an HTML page. Returns list of dicts."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    page_text = soup.get_text()

    # Determine year
    year = datetime.now().year
    m = re.search(r"(20[12]\d|202[0-6])", page_text)
    if m:
        year = int(m.group(1))

    results = []
    for table in soup.select("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        ttext = table.get_text()

        # Check for score indicators
        score_kws = sum(1 for kw in ["复试", "分数线", "总分", "政治", "英语", "业务课"]
                       if kw in ttext)
        if score_kws < 2:
            continue

        nums_count = len(re.findall(r"\b\d{2,4}\b", ttext))
        if nums_count < 5:
            continue

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            cts = [c.get_text(strip=True) for c in cells]

            # Find major code
            major_code = ""
            for ct in cts:
                m = re.search(r"\b(\d{6})\b", ct)
                if m:
                    major_code = m.group(1)
                    break
            if not major_code:
                for ct in cts:
                    m = re.search(r"\b(\d{4})\b", ct)
                    if m:
                        major_code = m.group(1)
                        break
            if not major_code:
                continue

            numbers = []
            for ct in cts:
                for m in re.finditer(r"\b(\d{2,4})\b", ct):
                    numbers.append(int(m.group(1)))

            scores = [n for n in numbers if 30 <= n <= 500]
            if not scores:
                continue

            big = [s for s in scores if s >= 200]
            small = [s for s in scores if s < 200]

            entry = {
                "school_id": school_id, "major_code": major_code, "year": year,
                "re_exam_total_score": big[0] if big else (max(scores) if scores else None),
                "re_exam_politics_score": small[0] if len(small) >= 1 else None,
                "re_exam_english_score": small[1] if len(small) >= 2 else None,
                "re_exam_business_score_1": small[2] if len(small) >= 3 else None,
                "re_exam_business_score_2": small[3] if len(small) >= 4 else None,
            }
            results.append(entry)

    return results


async def crawl_school(client, school):
    """Crawl one school for re-exam score lines."""
    url = GRAD_URLS.get(school.name, "")
    if not url:
        return []

    base = url.rstrip("/")
    rank = f"#{school.ranking_national}" if school.ranking_national else "?"
    logger.info("[%s] %s → %s", rank, school.name, base)

    # Step 1: Fetch main page, find admission-related links
    html = await fetch(client, base)
    if not html:
        logger.info("  Cannot fetch main page")
        return []

    # Find links: "复试分数线" or "硕士研究生招生复试" or "历年分数线"
    score_links = find_links(html, base, [
        "复试分数线", "复试线", "复试基本线", "复试录取",
        "历年分数线", "分数线", "进入复试",
    ])
    # Also find admission sub-pages
    admission_links = find_links(html, base, [
        "硕士招生", "招生信息", "招生工作", "招生简章",
        "通知公告", "公告通知",
    ])

    logger.info("  Score links: %d, Admission nav links: %d", len(score_links), len(admission_links))

    all_results = []
    visited = set()

    # Step 2: Visit score-related links first
    for link_url, link_text in score_links[:8]:
        if link_url in visited:
            continue
        visited.add(link_url)
        await asyncio.sleep(PAGE_DELAY)

        page_html = await fetch(client, link_url)
        if not page_html:
            continue

        logger.info("  → %s: %s", link_text[:40], link_url[:100])
        entries = parse_score_data(page_html, school.id)
        if entries:
            logger.info("    %d score entries", len(entries))
            all_results.extend(entries)

    # Step 3: Visit admission sub-pages, find more score links there
    pages_checked = len(score_links)
    for nav_url, _ in admission_links[:6]:
        if pages_checked >= MAX_DETAIL_PAGES:
            break
        if nav_url in visited:
            continue
        visited.add(nav_url)
        await asyncio.sleep(PAGE_DELAY)

        sub_html = await fetch(client, nav_url)
        if not sub_html:
            continue

        pages_checked += 1
        sub_score_links = find_links(sub_html, nav_url, [
            "复试分数线", "复试线", "复试基本线", "复试录取",
            "历年分数线", "分数线",
        ])

        if sub_score_links:
            logger.info("  → Nav page: %s → %d score links", nav_url[:80], len(sub_score_links))

        for link_url, link_text in sub_score_links[:5]:
            if pages_checked >= MAX_DETAIL_PAGES:
                break
            if link_url in visited:
                continue
            visited.add(link_url)
            await asyncio.sleep(PAGE_DELAY)
            pages_checked += 1

            detail_html = await fetch(client, link_url)
            if not detail_html:
                continue

            logger.info("    → %s: %s", link_text[:40], link_url[:100])
            entries = parse_score_data(detail_html, school.id)
            if entries:
                logger.info("      %d score entries", len(entries))
                all_results.extend(entries)

    return all_results


async def main():
    db = SessionLocal()
    schools = list(
        db.query(School)
        .filter(School.level.in_([SchoolLevel.C9, SchoolLevel.NINE_EIGHT_FIVE]))
        .order_by(School.ranking_national.asc())
        .all()
    )
    logger.info("Crawling %d schools (C9 + 985)\n", len(schools))

    # Update URLs
    updated = 0
    for s in schools:
        url = GRAD_URLS.get(s.name)
        if url and s.graduate_school_url != url:
            s.graduate_school_url = url
            updated += 1
    db.commit()
    logger.info("URLs updated: %d\n", updated)

    # Crawl
    all_data = []
    success = []
    no_data = []

    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=TIMEOUT) as client:
        for i, s in enumerate(schools):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)
            try:
                results = await crawl_school(client, s)
                if results:
                    logger.info("  ** TOTAL: %d entries", len(results))
                    all_data.extend(results)
                    success.append(s.name)
                else:
                    logger.info("  -- no data")
                    no_data.append(s.name)
            except Exception as e:
                logger.error("  !! %s: %s", s.name, e)
                no_data.append(s.name)

    # Deduplicate and save
    seen = set()
    unique = []
    for e in all_data:
        key = (e["school_id"], e["major_code"], e["year"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    updated_rows = 0
    for entry in unique:
        result = (
            db.query(ScoreLine)
            .filter(
                ScoreLine.school_id == entry["school_id"],
                ScoreLine.major_code == entry["major_code"],
                ScoreLine.year == entry["year"],
            )
            .update(
                {
                    ScoreLine.re_exam_total_score: entry["re_exam_total_score"],
                    ScoreLine.re_exam_politics_score: entry["re_exam_politics_score"],
                    ScoreLine.re_exam_english_score: entry["re_exam_english_score"],
                    ScoreLine.re_exam_business_score_1: entry["re_exam_business_score_1"],
                    ScoreLine.re_exam_business_score_2: entry["re_exam_business_score_2"],
                },
                synchronize_session=False,
            )
        )
        updated_rows += result
    db.commit()

    logger.info("\n" + "=" * 60)
    logger.info("CRAWL COMPLETE")
    logger.info("=" * 60)
    logger.info("Success: %d/%d schools", len(success), len(schools))
    logger.info("Unique score entries: %d", len(unique))
    logger.info("DB rows updated: %d", updated_rows)
    logger.info("With data: %s", ", ".join(success))
    logger.info("No data:   %s", ", ".join(no_data))
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
