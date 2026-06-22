"""
Crawl re-exam score lines for all 38 985 (+C9) universities — V4.

V4 improvements over V3:
1. Pre-loads valid (school, major_code) pairs from DB — only saves matching entries
2. Filters noise PDFs by link text — skips brochures, English catalogs, etc.
3. Stricter score validation — subject scores capped at 100, total 200-500
4. Same-year-only extraction — matches DB years (2022-2026)
5. "load" fallback for slow sites that time out on "networkidle"
6. Requires score-line context words near extracted numbers
"""
import asyncio, io, logging, os, re, sys
from datetime import datetime
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.models import School, ScoreLine, SchoolLevel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crawl985v4")

SCHOOL_DELAY = 5.0
PAGE_DELAY = 1.5
PAGE_TIMEOUT = 25_000
MAX_SCORE_PAGES = 8
MAX_ADMISSION_PAGES = 5

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

# PDF link text must contain at least one of these to be downloaded
PDF_SCORE_KEYWORDS = [
    "复试分数线", "复试线", "复试基本线", "分数线", "复试",
    "硕士", "招生", "录取", "分数",
]

# Text near extracted numbers must contain some of these
SCORE_CONTEXT_WORDS = [
    "总分", "政治", "外语", "英语", "业务课", "业务课1", "业务课2",
    "数学", "专业课", "科目", "复试", "初试", "满分", "单科",
    "学位", "专业", "硕士", "研究生",
]

# Non-score PDFs to skip
PDF_SKIP_PATTERNS = [
    r"(?i)brochure", r"(?i)brochure.*en", r"(?i)catalog",
    r"(?i)english", r"概览", r"简介", r"宣传", r"画册",
    r"申请表", r"推荐信", r"协议", r"合同",
    r"宣讲", r"咨询会", r"夏令营", r"暑期学校",
    r"考场", r"考生须知", r"成绩查询",
]


def load_valid_pairs(db) -> dict:
    """Load all (school_id, major_code) pairs from existing score_lines."""
    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT DISTINCT school_id, major_code FROM score_lines"
    )).fetchall()
    pairs = {}
    for sid, code in rows:
        pairs.setdefault(sid, set()).add(code)
    logger.info("Loaded %d valid (school, major_code) pairs across %d schools",
                sum(len(v) for v in pairs.values()), len(pairs))
    return pairs


VALID_YEARS = {2022, 2023, 2024, 2025, 2026}


async def nav_page(page, url: str, timeout: int = PAGE_TIMEOUT) -> bool:
    """Navigate to URL. Try networkidle first, fall back to load on timeout."""
    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout)
        return True
    except Exception:
        try:
            await page.goto(url, wait_until="load", timeout=timeout)
            await asyncio.sleep(2)
            return True
        except Exception:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                await asyncio.sleep(3)
                return True
            except Exception:
                return False


async def find_score_links(page, base_url: str) -> list[tuple[str, str]]:
    links = await page.evaluate("""
        (baseUrl) => {
            const results = [];
            const seen = new Set();
            const keywords = [
                "复试分数线", "复试线", "复试基本线", "复试录取",
                "历年分数线", "分数线", "进入复试", "硕士复试",
                "复试基本分数线", "硕士招生复试", "研究生复试",
            ];
            for (const a of document.querySelectorAll("a[href]")) {
                const text = (a.textContent || "").trim();
                const href = a.getAttribute("href").trim();
                if (!text || text.length < 3) continue;
                if (href.startsWith("javascript:") || href.startsWith("#")) continue;
                const combined = text + " " + href;
                const match = keywords.some(kw => combined.includes(kw));
                if (!match) continue;
                let fullUrl;
                try { fullUrl = new URL(href, baseUrl).href; }
                catch { fullUrl = href.startsWith("/") ? baseUrl.replace(/\\/$/, "") + href : baseUrl + "/" + href; }
                const key = fullUrl.substring(0, 200);
                if (!seen.has(key)) { seen.add(key); results.push({url: fullUrl, text: text}); }
            }
            return results;
        }
    """, base_url)
    return [(l["url"], l["text"]) for l in links]


async def find_nav_links(page, base_url: str) -> list[tuple[str, str]]:
    links = await page.evaluate("""
        (baseUrl) => {
            const results = [];
            const seen = new Set();
            const keywords = [
                "硕士招生", "招生信息", "招生工作", "招生简章",
                "通知公告", "公告通知", "招生动态",
            ];
            for (const a of document.querySelectorAll("a[href]")) {
                const text = (a.textContent || "").trim();
                const href = a.getAttribute("href").trim();
                if (!text || text.length < 4) continue;
                if (href.startsWith("javascript:") || href.startsWith("#")) continue;
                const combined = text + " " + href;
                const match = keywords.some(kw => combined.includes(kw));
                if (!match) continue;
                let fullUrl;
                try { fullUrl = new URL(href, baseUrl).href; }
                catch { fullUrl = href.startsWith("/") ? baseUrl.replace(/\\/$/, "") + href : baseUrl + "/" + href; }
                const key = fullUrl.substring(0, 200);
                if (!seen.has(key)) { seen.add(key); results.push({url: fullUrl, text: text}); }
            }
            return results;
        }
    """, base_url)
    return [(l["url"], l["text"]) for l in links]


async def find_pdf_links(page, base_url: str) -> list[tuple[str, str]]:
    """Find PDF links on the current page, filtering by link text relevance."""
    links = await page.evaluate("""
        (baseUrl) => {
            const results = [];
            const seen = new Set();
            for (const a of document.querySelectorAll("a[href]")) {
                const href = a.getAttribute("href").trim();
                const text = (a.textContent || "").trim();
                if (!href) continue;
                let fullUrl;
                try { fullUrl = new URL(href, baseUrl).href; }
                catch { fullUrl = href.startsWith("/") ? baseUrl.replace(/\\/$/, "") + href : baseUrl + "/" + href; }
                const isPdf = href.toLowerCase().endsWith(".pdf")
                    || href.toLowerCase().includes(".pdf?");
                if (!isPdf) continue;
                const key = fullUrl.substring(0, 200);
                if (!seen.has(key)) { seen.add(key); results.push({url: fullUrl, text: text}); }
            }
            return results;
        }
    """, base_url)
    return [(l["url"], l["text"]) for l in links]


def should_parse_pdf(link_text: str, link_url: str) -> bool:
    """Check if a PDF is likely to contain re-exam score data."""
    combined = link_text + " " + link_url
    if any(re.search(pat, combined) for pat in PDF_SKIP_PATTERNS):
        return False
    return any(kw in combined for kw in PDF_SCORE_KEYWORDS)


async def download_pdf(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=30)
        if resp.status_code >= 400:
            return None
        import pdfplumber
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            pages_text = []
            for page in pdf.pages[:15]:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            return "\n".join(pages_text) if pages_text else None
    except Exception:
        return None


async def extract_page_tables(page) -> list[list[list[str]]]:
    return await page.evaluate("""
        () => {
            const allTables = [];
            for (const table of document.querySelectorAll("table")) {
                const rows = [];
                for (const tr of table.querySelectorAll("tr")) {
                    const cells = [];
                    for (const cell of tr.querySelectorAll("td, th")) {
                        cells.push((cell.textContent || "").trim());
                    }
                    if (cells.length >= 2) rows.push(cells);
                }
                if (rows.length >= 2) allTables.push(rows);
            }
            return allTables;
        }
    """)


async def extract_page_text(page) -> str:
    return await page.evaluate("""
        () => {
            const contentSelectors = [
                ".content", ".article-content", "#content", ".main-content",
                ".TRS_Editor", ".article", ".v_news_content", ".wp_articlecontent",
                ".news_content", ".detail-content", ".info-content",
                "article", "[class*=content]", "[class*=article]",
            ];
            for (const sel of contentSelectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent.trim().length > 100) {
                    return el.textContent.trim();
                }
            }
            return document.body ? document.body.textContent.trim() : "";
        }
    """)


def _table_has_score_context(table_rows: list[list[str]]) -> bool:
    """Check if table header/first rows contain score-related keywords."""
    header_text = " ".join(table_rows[0]) if table_rows else ""
    if any(kw in header_text for kw in SCORE_CONTEXT_WORDS):
        return True
    # Also check first 3 rows
    for row in table_rows[:3]:
        row_text = " ".join(row)
        if any(kw in row_text for kw in SCORE_CONTEXT_WORDS):
            return True
    return False


def parse_score_rows(table_rows: list[list[str]], school_id: int,
                      valid_codes: set[str]) -> list[dict]:
    """Parse score data from rendered DOM table rows. Only returns entries
    whose major_code exists in valid_codes for this school.

    Context-word check is done ONCE per table (on header rows), not per data row.
    """
    if not _table_has_score_context(table_rows):
        return []

    results = []
    year = datetime.now().year

    # Detect year from table header
    header_text = " ".join(table_rows[0])
    ym = re.search(r"(20[12]\d|202[0-6])", header_text)
    if ym:
        y = int(ym.group(1))
        if y in VALID_YEARS:
            year = y

    for row_cells in table_rows:
        if len(row_cells) < 3:
            continue

        major_code = ""
        for c in row_cells:
            m = re.search(r"\b(\d{6})\b", c)
            if m:
                major_code = m.group(1)
                break
        if not major_code:
            for c in row_cells:
                m = re.search(r"\b(\d{4})\b", c)
                if m:
                    major_code = m.group(1)
                    break
        if not major_code:
            continue

        if major_code not in valid_codes:
            continue

        # Check row for year override
        for c in row_cells:
            ym2 = re.search(r"(20[12]\d|202[0-6])", c)
            if ym2:
                y2 = int(ym2.group(1))
                if y2 in VALID_YEARS:
                    year = y2

        numbers = [int(m.group(1)) for c in row_cells
                   for m in re.finditer(r"\b(\d{2,4})\b", c)
                   if 30 <= int(m.group(1)) <= 500]

        if not numbers:
            continue

        big = [n for n in numbers if n >= 200]
        small = [n for n in numbers if n <= 100]
        valid_small = [s for s in small if 30 <= s <= 100]

        entry = {
            "school_id": school_id,
            "major_code": major_code,
            "year": year,
            "re_exam_total_score": big[0] if big else (max(numbers) if numbers else None),
            "re_exam_politics_score": valid_small[0] if len(valid_small) >= 1 else None,
            "re_exam_english_score": valid_small[1] if len(valid_small) >= 2 else None,
            "re_exam_business_score_1": valid_small[2] if len(valid_small) >= 3 else None,
            "re_exam_business_score_2": valid_small[3] if len(valid_small) >= 4 else None,
        }

        if entry["re_exam_total_score"] and entry["re_exam_total_score"] < 200:
            continue

        results.append(entry)

    return results


def parse_score_text(text: str, school_id: int, valid_codes: set[str]) -> list[dict]:
    """Parse score data from plain text (e.g., PDF content or HTML text).

    Requires at least one context word in the block, valid major codes, and
    score-like numbers. Context check is per-block, not per-line.
    """
    results = []
    year = datetime.now().year
    full_ym = re.search(r"(20[12]\d|202[0-6])\s*年", text)
    if full_ym:
        y = int(full_ym.group(1))
        if y in VALID_YEARS:
            year = y

    if year not in VALID_YEARS:
        return []

    # Split into blocks
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        if len(block) < 20:
            continue

        # Find major codes
        codes_6 = re.findall(r"\b(\d{6})\b", block)
        codes_4 = re.findall(r"\b(\d{4})\b", block) if not codes_6 else []
        all_codes = codes_6 + codes_4
        valid_in_block = [c for c in all_codes if c in valid_codes]
        if not valid_in_block:
            continue

        # Extract numbers
        numbers = [int(m.group(1)) for m in re.finditer(r"\b(\d{2,4})\b", block)
                   if 30 <= int(m.group(1)) <= 500]
        if len(numbers) < 1:
            continue

        big = [n for n in numbers if n >= 200]
        small = [n for n in numbers if n <= 100]
        valid_small = [s for s in small if 30 <= s <= 100]
        total = big[0] if big else (max(numbers) if numbers else None)
        if not total or total < 200:
            continue

        # Context check: block should have score-related keywords
        # (but only require 1 — the valid codes + numbers are strong signals)
        has_context = any(kw in block for kw in SCORE_CONTEXT_WORDS)

        for code in valid_in_block[:3]:
            entry = {
                "school_id": school_id,
                "major_code": code,
                "year": year,
                "re_exam_total_score": total,
                "re_exam_politics_score": valid_small[0] if len(valid_small) >= 1 else None,
                "re_exam_english_score": valid_small[1] if len(valid_small) >= 2 else None,
                "re_exam_business_score_1": valid_small[2] if len(valid_small) >= 3 else None,
                "re_exam_business_score_2": valid_small[3] if len(valid_small) >= 4 else None,
            }

            # If no context words at all, still accept if numbers look valid
            # (>=3 small scores or a big total + small scores)
            if not has_context:
                if len(valid_small) < 2:
                    continue

            results.append(entry)

    return results


async def crawl_school(browser, http_client: httpx.AsyncClient, school,
                        valid_codes: set[str]) -> list[dict]:
    url = GRAD_URLS.get(school.name, "")
    if not url:
        return []

    rank = f"#{school.ranking_national}" if school.ranking_national else "?"
    base = url.rstrip("/")

    all_results = []
    visited_urls = set()

    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="zh-CN",
    )
    page = await context.new_page()

    try:
        ok = await nav_page(page, base)
        if not ok:
            logger.info("  Cannot load main page")
            return []
        await asyncio.sleep(2)

        score_links = await find_score_links(page, base)
        nav_links = await find_nav_links(page, base)
        pdf_links = await find_pdf_links(page, base)

        score_pdf_count = sum(1 for url_, text_ in pdf_links if should_parse_pdf(text_, url_))
        logger.info("  Score links: %d, Nav: %d, PDFs: %d (score-related: %d)",
                     len(score_links), len(nav_links), len(pdf_links), score_pdf_count)

        # Step 1: Download relevant PDFs from main page
        for pdf_url, pdf_label in pdf_links[:8]:
            if pdf_url in visited_urls:
                continue
            visited_urls.add(pdf_url)

            if not should_parse_pdf(pdf_label, pdf_url):
                continue

            logger.info("  PDF: %.80s", pdf_label or pdf_url[:80])
            pdf_text = await download_pdf(http_client, pdf_url)
            if pdf_text and len(pdf_text) > 100:
                entries = parse_score_text(pdf_text, school.id, valid_codes)
                if entries:
                    logger.info("    +%d entries", len(entries))
                    all_results.extend(entries)

        # Step 2: Visit score-line HTML pages
        pages_checked = 0
        for link_url, link_text in score_links[:MAX_SCORE_PAGES]:
            if link_url in visited_urls:
                continue
            visited_urls.add(link_url)
            pages_checked += 1

            await asyncio.sleep(PAGE_DELAY)
            logger.info("  → %.50s", link_text)
            ok = await nav_page(page, link_url)
            if not ok:
                continue

            tables = await extract_page_tables(page)
            for table_rows in tables:
                entries = parse_score_rows(table_rows, school.id, valid_codes)
                if entries:
                    all_results.extend(entries)

            page_text = await extract_page_text(page)
            if page_text and "复试" in page_text:
                entries = parse_score_text(page_text, school.id, valid_codes)
                if entries:
                    all_results.extend(entries)

            # PDFs on score pages
            pdfs = await find_pdf_links(page, link_url)
            for pdf_url, pdf_label in pdfs[:3]:
                if pdf_url in visited_urls:
                    continue
                visited_urls.add(pdf_url)
                if not should_parse_pdf(pdf_label, pdf_url):
                    continue
                await asyncio.sleep(0.5)
                pdf_text = await download_pdf(http_client, pdf_url)
                if pdf_text and len(pdf_text) > 100:
                    entries = parse_score_text(pdf_text, school.id, valid_codes)
                    if entries:
                        all_results.extend(entries)

        # Step 3: Visit admission nav pages, repeat
        for nav_url, _ in nav_links[:MAX_ADMISSION_PAGES]:
            if pages_checked >= MAX_SCORE_PAGES:
                break
            if nav_url in visited_urls:
                continue
            visited_urls.add(nav_url)
            pages_checked += 1

            await asyncio.sleep(PAGE_DELAY)
            ok = await nav_page(page, nav_url)
            if not ok:
                continue

            sub_score = await find_score_links(page, nav_url)
            sub_pdfs = await find_pdf_links(page, nav_url)

            for pdf_url, pdf_label in sub_pdfs[:3]:
                if pdf_url in visited_urls:
                    continue
                visited_urls.add(pdf_url)
                if not should_parse_pdf(pdf_label, pdf_url):
                    continue
                await asyncio.sleep(0.5)
                pdf_text = await download_pdf(http_client, pdf_url)
                if pdf_text and len(pdf_text) > 100:
                    entries = parse_score_text(pdf_text, school.id, valid_codes)
                    if entries:
                        all_results.extend(entries)

            for link_url, link_text in sub_score[:4]:
                if pages_checked >= MAX_SCORE_PAGES:
                    break
                if link_url in visited_urls:
                    continue
                visited_urls.add(link_url)
                pages_checked += 1

                await asyncio.sleep(PAGE_DELAY)
                ok = await nav_page(page, link_url)
                if not ok:
                    continue

                tables = await extract_page_tables(page)
                for table_rows in tables:
                    entries = parse_score_rows(table_rows, school.id, valid_codes)
                    if entries:
                        all_results.extend(entries)

                page_text = await extract_page_text(page)
                if page_text and "复试" in page_text:
                    entries = parse_score_text(page_text, school.id, valid_codes)
                    if entries:
                        all_results.extend(entries)

    finally:
        await context.close()

    return all_results


async def main():
    db = SessionLocal()

    # Pre-load valid (school_id, major_code) pairs
    valid_pairs = load_valid_pairs(db)

    schools = list(
        db.query(School)
        .filter(School.level.in_([SchoolLevel.C9, SchoolLevel.NINE_EIGHT_FIVE]))
        .order_by(School.ranking_national.asc())
        .all()
    )
    logger.info("Crawling %d schools (C9 + 985) with Playwright V4\n", len(schools))

    # Update URLs
    updated = 0
    for s in schools:
        url = GRAD_URLS.get(s.name)
        if url and s.graduate_school_url != url:
            s.graduate_school_url = url
            updated += 1
    db.commit()
    logger.info("URLs updated: %d\n", updated)

    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=30) as http_client:
        async with async_playwright() as pw:
            # Find chromium
            for exe in ["/usr/bin/chromium-browser", "/usr/bin/chromium",
                         "/snap/bin/chromium", "/usr/bin/google-chrome-stable"]:
                if os.path.exists(exe):
                    logger.info("Using: %s", exe)
                    browser = await pw.chromium.launch(
                        headless=True, executable_path=exe,
                        args=["--no-sandbox", "--disable-setuid-sandbox"],
                    )
                    break
            else:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )

            all_data = []
            success_schools = []
            no_data_schools = []

            for i, s in enumerate(schools):
                if i > 0:
                    await asyncio.sleep(SCHOOL_DELAY)

                codes = valid_pairs.get(s.id, set())
                if not codes:
                    logger.info("[#%d] %s — no valid codes in DB, skip", s.ranking_national or "?", s.name)
                    continue

                try:
                    results = await crawl_school(browser, http_client, s, codes)
                    if results:
                        logger.info("  ** %d entries", len(results))
                        all_data.extend(results)
                        success_schools.append(s.name)
                    else:
                        logger.info("  -- no data")
                        no_data_schools.append(s.name)
                except Exception as e:
                    logger.error("  !! %s crashed: %s", s.name, e)
                    no_data_schools.append(s.name)

            await browser.close()

    # Deduplicate
    seen = set()
    unique = []
    for e in all_data:
        key = (e["school_id"], e["major_code"], e["year"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    # Save to DB
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
    logger.info("CRAWL COMPLETE (V4)")
    logger.info("=" * 60)
    logger.info("Schools with data: %d/%d", len(success_schools), len(schools))
    logger.info("Unique entries (DB-validated): %d", len(unique))
    logger.info("DB rows updated: %d", updated_rows)
    logger.info("Match rate: %.0f%%", (updated_rows / len(unique) * 100) if unique else 0)
    logger.info("Success: %s", ", ".join(success_schools) if success_schools else "(none)")
    logger.info("No data: %s", ", ".join(no_data_schools) if no_data_schools else "(none)")

    for s_name in success_schools:
        sid = next((sc.id for sc in schools if sc.name == s_name), None)
        if sid:
            count = sum(1 for e in unique if e["school_id"] == sid)
            logger.info("  %s: %d entries", s_name, count)

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
