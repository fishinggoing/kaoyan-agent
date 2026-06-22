"""
Crawl re-exam score lines for all 38 985 (+C9) universities.

Strategy:
1. Update graduate_school_url for all 985 schools
2. For each school, try multiple approaches to find score line pages:
   a. Search for "复试分数线" on the main page and sub-pages
   b. Try known score line URL paths
   c. Parse any HTML tables or PDF files found
3. Save re-exam scores to the score_lines table

Usage: python scripts/crawl_985_score_lines.py
"""

import asyncio
import io
import logging
import os
import random
import re
import ssl
import sys
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import update

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.models import School, ScoreLine, SchoolLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("crawl_985")

# ── Polite crawling config ───────────────────────────────────────────────
REQUEST_DELAY = 4.0          # seconds between schools
PAGE_DELAY = 1.5             # seconds between pages within same school
MAX_PAGES_PER_SCHOOL = 15    # max pages to check per school
TIMEOUT = 20

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# Known graduate admission URLs for ALL 38 985+C9 schools
GRAD_URLS: dict[str, str] = {
    # ── C9 (9) ───────────────────────────────────────────────────────────
    "清华大学": "https://yz.tsinghua.edu.cn/",
    "北京大学": "https://admission.pku.edu.cn/",
    "浙江大学": "https://yjsy.zju.edu.cn/",
    "上海交通大学": "https://yzb.sjtu.edu.cn/",
    "复旦大学": "https://gsao.fudan.edu.cn/",
    "南京大学": "https://yzb.nju.edu.cn/",
    "中国科学技术大学": "https://yz.ustc.edu.cn/",
    "西安交通大学": "http://yz.xjtu.edu.cn/",
    "哈尔滨工业大学": "http://yzb.hit.edu.cn/",
    # ── 985 (29) ─────────────────────────────────────────────────────────
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

# Score-related keywords for finding relevant pages
SCORE_KEYWORDS = [
    "复试分数线", "复试基本分数线", "硕士复试分数线",
    "复试线", "复试基本线", "进入复试", "初试成绩基本要求",
    "复试录取工作办法", "硕士招生复试", "硕士研究生复试",
    "复试通知", "复试名单",
]

# Common paths where score lines might be found
SCORE_PAGE_PATHS = [
    "zsxx/sszs/fsl/", "zsxx/fsl/", "zsxx/sszs/",
    "zs/sszs/", "zs/sszs/fsl/", "tzgg/", "sszs/",
    "info/1035/", "info/1033/", "info/1036/",
    "zhaosheng/", "xwzx/tzgg/", "xwzx.htm",
    "sszsjy/", "yjszs/", "yjszs/sszs/",
    "tongzhi/", "gonggao/", "tz/",
]

_unsafe_ctx = ssl.create_default_context()
_unsafe_ctx.check_hostname = False
_unsafe_ctx.verify_mode = ssl.CERT_NONE
_unsafe_ctx.set_ciphers("DEFAULT:@SECLEVEL=1")


def random_ua() -> str:
    return random.choice(USER_AGENTS)


# ── HTTP ─────────────────────────────────────────────────────────────────

async def check_robots(client: httpx.AsyncClient, base_url: str) -> set[str]:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = await client.get(robots_url, headers={"User-Agent": random_ua()}, timeout=10)
        if resp.status_code == 200:
            disallowed = set()
            for line in resp.text.splitlines():
                line = line.strip().lower()
                if line.startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed.add(path)
            return disallowed
    except Exception:
        pass
    return set()


def is_allowed(url: str, disallowed: set[str]) -> bool:
    if not disallowed:
        return True
    parsed = urlparse(url)
    path = parsed.path or "/"
    for d in disallowed:
        if path.startswith(d):
            return False
    return True


async def fetch_page(
    client: httpx.AsyncClient, url: str, disallowed: set[str] | None = None
) -> str | None:
    if disallowed is not None and not is_allowed(url, disallowed):
        return None
    headers = {
        "User-Agent": random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        resp = await client.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "html" in ct or not ct:
                return resp.text
        elif resp.status_code >= 500:
            # Retry once for server errors
            await asyncio.sleep(2)
            resp = await client.get(url, headers=headers, timeout=TIMEOUT)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "html" in ct or not ct:
                    return resp.text
    except Exception:
        pass
    return None


async def fetch_pdf(
    client: httpx.AsyncClient, url: str
) -> bytes | None:
    """Fetch a PDF file, return bytes."""
    headers = {"User-Agent": random_ua()}
    try:
        resp = await client.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "pdf" in ct or url.lower().endswith(".pdf"):
                return resp.content
    except Exception:
        pass
    return None


# ── Link discovery ───────────────────────────────────────────────────────

def find_score_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Find links to score line pages. Returns list of (url, title)."""
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"].strip()
        if not text or len(text) < 3:
            continue
        full_url = urljoin(base_url, href)
        if full_url.startswith(("javascript:", "mailto:", "#")):
            continue
        # Check both link text and URL for score-related keywords
        combined = text + href.lower()
        if any(kw in combined for kw in SCORE_KEYWORDS):
            links.append((full_url, text))
    return links


def find_news_list_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Find links to news/list pages (where score pages might be listed)."""
    soup = BeautifulSoup(html, "lxml")
    links = []
    list_keywords = ["通知公告", "招生信息", "硕士招生", "新闻动态",
                      "通知", "公告", "招生", "新闻"]
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"].strip()
        if not text or len(text) < 2:
            continue
        full_url = urljoin(base_url, href)
        if full_url.startswith(("javascript:", "mailto:", "#")):
            continue
        if any(kw in text for kw in list_keywords):
            links.append((full_url, text))
    return links


# ── PDF parsing ──────────────────────────────────────────────────────────

def parse_pdf_score_table(pdf_bytes: bytes, school_id: int) -> list[dict]:
    """Attempt to extract score line data from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        logger.debug("pdfplumber not available, skipping PDF")
        return []

    results = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:10]:  # max 10 pages
                text = page.extract_text()
                if not text:
                    continue
                # Check if this page contains score line data
                if not any(kw in text for kw in ["复试", "分数线", "总分"]):
                    continue

                # Try to extract tables first
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    entries = _parse_pdf_table(table, school_id, text)
                    results.extend(entries)
    except Exception as e:
        logger.debug("PDF parse error: %s", e)

    return results


def _parse_pdf_table(table: list[list[str | None]], school_id: int, page_text: str) -> list[dict]:
    """Parse a single table from a PDF page."""
    results = []
    # Determine year from page text
    m = re.search(r"(20[12]\d|202[0-6])", page_text)
    year = int(m.group(1)) if m else datetime.now().year

    for row in table[1:]:  # skip header
        if not row or len(row) < 3:
            continue
        texts = [str(c).strip() if c else "" for c in row]

        # Find major code (6 digits)
        major_code = ""
        for t in texts:
            m = re.search(r"\b(\d{6})\b", t)
            if m:
                major_code = m.group(1)
                break
        if not major_code:
            # Try 4-digit discipline code
            for t in texts:
                m = re.search(r"\b(\d{4})\b", t)
                if m:
                    major_code = m.group(1)
                    break
        if not major_code:
            continue

        # Extract all numbers
        all_nums = []
        for t in texts:
            for m in re.finditer(r"\b(\d{2,4})\b", t):
                all_nums.append(int(m.group(1)))

        scores = [n for n in all_nums if 30 <= n <= 500]
        if not scores:
            continue

        entry = {
            "school_id": school_id,
            "major_code": major_code,
            "year": year,
            "re_exam_total_score": None,
            "re_exam_politics_score": None,
            "re_exam_english_score": None,
            "re_exam_business_score_1": None,
            "re_exam_business_score_2": None,
        }

        # Heuristic: total >= 200, per-subject < 200 and >= 30
        big = [s for s in scores if s >= 200]
        small = [s for s in scores if s < 200]

        if big:
            entry["re_exam_total_score"] = big[0]
        elif scores:
            entry["re_exam_total_score"] = max(scores)

        # Assign per-subject scores
        if len(small) >= 1:
            entry["re_exam_politics_score"] = small[0]
        if len(small) >= 2:
            entry["re_exam_english_score"] = small[1]
        if len(small) >= 3:
            entry["re_exam_business_score_1"] = small[2]
        if len(small) >= 4:
            entry["re_exam_business_score_2"] = small[3]

        results.append(entry)

    return results


# ── HTML parsing ─────────────────────────────────────────────────────────

def parse_score_tables(html: str, school_id: int) -> list[dict]:
    """Parse score line tables from HTML."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    page_text = soup.get_text()
    page_year = datetime.now().year
    m = re.search(r"(20[12]\d|202[0-6])", page_text)
    if m:
        page_year = int(m.group(1))

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    for table in soup.select("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        ttext = table.get_text()
        # Quick check: has score indicators
        score_kws = sum(1 for kw in ["复试", "分数线", "总分", "政治", "英语", "业务课"]
                       if kw in ttext)
        if score_kws < 2:
            continue

        nums_in_table = len(re.findall(r"\b\d{2,4}\b", ttext))
        if nums_in_table < 5:
            continue

        # Parse rows
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]

            # Find major code
            major_code = ""
            for ct in cell_texts:
                m = re.search(r"\b(\d{6})\b", ct)
                if m:
                    major_code = m.group(1)
                    break
            if not major_code:
                for ct in cell_texts:
                    m = re.search(r"\b(\d{4})\b", ct)
                    if m:
                        major_code = m.group(1)
                        break
            if not major_code:
                continue

            # Extract numbers
            all_nums = []
            for ct in cell_texts:
                for m in re.finditer(r"\b(\d{2,4})\b", ct):
                    all_nums.append(int(m.group(1)))

            scores = [n for n in all_nums if 30 <= n <= 500]
            if not scores:
                continue

            entry = {
                "school_id": school_id,
                "major_code": major_code,
                "year": page_year,
                "re_exam_total_score": None,
                "re_exam_politics_score": None,
                "re_exam_english_score": None,
                "re_exam_business_score_1": None,
                "re_exam_business_score_2": None,
            }

            big = [s for s in scores if s >= 200]
            small = [s for s in scores if s < 200]

            if big:
                entry["re_exam_total_score"] = big[0]
            elif scores:
                entry["re_exam_total_score"] = max(scores)

            if len(small) >= 1:
                entry["re_exam_politics_score"] = small[0]
            if len(small) >= 2:
                entry["re_exam_english_score"] = small[1]
            if len(small) >= 3:
                entry["re_exam_business_score_1"] = small[2]
            if len(small) >= 4:
                entry["re_exam_business_score_2"] = small[3]

            results.append(entry)

    return results


# ── School crawler ───────────────────────────────────────────────────────

async def crawl_one_school(
    client: httpx.AsyncClient, school: School
) -> list[dict]:
    """Crawl score lines for one school."""
    if not school.graduate_school_url:
        return []

    base_url = school.graduate_school_url.rstrip("/")
    rank_str = f"#{school.ranking_national}" if school.ranking_national else "?"
    logger.info("[%s] %s → %s", rank_str, school.name, base_url)

    disallowed = await check_robots(client, base_url)
    all_results: list[dict] = []
    visited: set[str] = set()
    page_queue: list[tuple[str, str]] = [(base_url, "home")]

    # Add common paths
    for path in SCORE_PAGE_PATHS:
        url = f"{base_url}/{path}"
        if url not in visited:
            page_queue.append((url, path))

    pages_checked = 0
    pdf_links: list[str] = []

    while page_queue and pages_checked < MAX_PAGES_PER_SCHOOL:
        url, source = page_queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        if pages_checked > 0:
            await asyncio.sleep(PAGE_DELAY)
        pages_checked += 1

        # Check if it's a PDF
        if url.lower().endswith(".pdf"):
            pdf_bytes = await fetch_pdf(client, url)
            if pdf_bytes:
                logger.info("  [p%d] PDF: %s (%d bytes)", pages_checked, url[:100], len(pdf_bytes))
                entries = parse_pdf_score_table(pdf_bytes, school.id)
                if entries:
                    logger.info("    → %d score entries from PDF", len(entries))
                    all_results.extend(entries)
            continue

        html = await fetch_page(client, url, disallowed)
        if not html:
            continue

        # Check for score line content
        if any(kw in html for kw in ["复试分数线", "复试线", "复试基本线",
                                       "初试成绩基本要求", "进入复试"]):
            logger.info("  [p%d] %s ← %s", pages_checked, source, url[:100])

            # Try to parse tables
            entries = parse_score_tables(html, school.id)
            if entries:
                logger.info("    → %d score entries", len(entries))
                all_results.extend(entries)

        # Find more links: score pages and news list pages
        score_links = find_score_links(html, url)
        for link_url, link_text in score_links[:10]:
            if link_url not in visited:
                if link_url.lower().endswith(".pdf"):
                    pdf_links.append(link_url)
                else:
                    page_queue.append((link_url, f"link:{link_text[:30]}"))

        # Also find news list pages on the first few pages
        if pages_checked <= 3:
            news_links = find_news_list_links(html, url)
            for link_url, _ in news_links[:5]:
                if link_url not in visited:
                    page_queue.append((link_url, "newslist"))

    # Process PDFs last (they're slow)
    for pdf_url in pdf_links[:5]:
        if pdf_url in visited:
            continue
        visited.add(pdf_url)
        await asyncio.sleep(PAGE_DELAY)
        pdf_bytes = await fetch_pdf(client, pdf_url)
        if pdf_bytes:
            logger.info("  [pdf] %s (%d bytes)", pdf_url[:100], len(pdf_bytes))
            entries = parse_pdf_score_table(pdf_bytes, school.id)
            if entries:
                logger.info("    → %d score entries from PDF", len(entries))
                all_results.extend(entries)

    return all_results


# ── Main ─────────────────────────────────────────────────────────────────

async def main():
    db = SessionLocal()

    # Get all 985+C9 schools
    schools = list(
        db.query(School)
        .filter(School.level.in_([SchoolLevel.C9, SchoolLevel.NINE_EIGHT_FIVE]))
        .order_by(School.ranking_national.asc())
        .all()
    )
    logger.info("Found %d schools (C9 + 985)\n", len(schools))

    # Phase 0: Update URLs
    updated = 0
    for s in schools:
        url = GRAD_URLS.get(s.name)
        if url and s.graduate_school_url != url:
            s.graduate_school_url = url
            updated += 1
    db.commit()
    logger.info("Updated %d graduate_school_url entries\n", updated)

    # Phase 1: Crawl
    logger.info("=" * 60)
    logger.info("Starting crawl (max %d pages/school, %.1fs delay)",
                MAX_PAGES_PER_SCHOOL, REQUEST_DELAY)
    logger.info("=" * 60)

    all_data = []
    success_schools = []

    async with httpx.AsyncClient(
        verify=False, follow_redirects=True, timeout=TIMEOUT
    ) as client:
        for i, school in enumerate(schools):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)
            try:
                results = await crawl_one_school(client, school)
                if results:
                    logger.info("  ** TOTAL %d entries for %s", len(results), school.name)
                    all_data.extend(results)
                    success_schools.append(school.name)
                elif school.graduate_school_url:
                    logger.info("  -- no score data found for %s", school.name)
            except Exception as e:
                logger.error("  !! Error %s: %s", school.name, e)

    # Phase 2: Save results
    logger.info("\n" + "=" * 60)
    logger.info("Saving %d score entries from %d schools",
                len(all_data), len(success_schools))
    logger.info("=" * 60)

    # Deduplicate by (school_id, major_code, year)
    seen = set()
    unique = []
    for e in all_data:
        key = (e["school_id"], e["major_code"], e["year"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    # Update existing score_lines rows
    updated_count = 0
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
        updated_count += result

    db.commit()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CRAWL COMPLETE")
    logger.info("=" * 60)
    logger.info("Schools with data: %d/%d", len(success_schools), len(schools))
    logger.info("Total unique entries: %d", len(unique))
    logger.info("DB rows updated: %d", updated_count)
    logger.info("")
    logger.info("Schools with data: %s", ", ".join(success_schools))

    no_data = [s.name for s in schools
               if s.name not in success_schools and s.graduate_school_url]
    if no_data:
        logger.info("Schools WITHOUT data: %s", ", ".join(no_data))

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
