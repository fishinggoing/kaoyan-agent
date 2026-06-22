"""
Crawl re-exam score lines for all 38 985 (+C9) universities — V3.

Uses Playwright for JS-rendered pages + pdfplumber for PDF attachments.
Solves the two problems that made V2 miss 90%+ of data:
1. Modern CMS (Vue/React) — Playwright renders JS before extraction
2. PDF attachments — downloads and parses with pdfplumber
"""
import asyncio, io, json, logging, os, random, re, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.models import School, ScoreLine, SchoolLevel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crawl985v3")

SCHOOL_DELAY = 5.0       # seconds between schools
PAGE_DELAY = 1.5         # seconds between pages within a school
PAGE_TIMEOUT = 25_000    # ms for page navigation
MAX_SCORE_PAGES = 8      # max score-line pages to visit per school
MAX_ADMISSION_PAGES = 5  # max admission sub-pages to explore

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

SCORE_KEYWORDS = [
    "复试分数线", "复试线", "复试基本线", "复试录取",
    "历年分数线", "分数线", "进入复试", "硕士复试",
    "复试基本分数线", "硕士招生复试", "研究生复试",
]

ADMISSION_KEYWORDS = [
    "硕士招生", "招生信息", "招生工作", "招生简章",
    "通知公告", "公告通知", "招生动态",
]

# Words that in score-line context are likely score labels
SCORE_LABEL_WORDS = {
    "总分", "政治", "外语", "英语", "业务课", "业务课1", "业务课2",
    "数学", "专业课", "科目一", "科目二", "科目三", "科目四",
    "满分", "单科", "复试", "初试",
}


async def find_score_links(page, base_url: str) -> list[tuple[str, str]]:
    """Extract all score-related links from the fully rendered page."""
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

                // Resolve relative URL
                let fullUrl;
                try {
                    fullUrl = new URL(href, baseUrl).href;
                } catch {
                    fullUrl = href.startsWith("/") ? baseUrl.replace(/\\/$/, "") + href : baseUrl + "/" + href;
                }

                const key = fullUrl.substring(0, 200);
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({url: fullUrl, text: text});
                }
            }
            return results;
        }
    """, base_url)
    return [(l["url"], l["text"]) for l in links]


async def find_nav_links(page, base_url: str) -> list[tuple[str, str]]:
    """Extract admission-related navigation links."""
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
                try {
                    fullUrl = new URL(href, baseUrl).href;
                } catch {
                    fullUrl = href.startsWith("/") ? baseUrl.replace(/\\/$/, "") + href : baseUrl + "/" + href;
                }

                const key = fullUrl.substring(0, 200);
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({url: fullUrl, text: text});
                }
            }
            return results;
        }
    """, base_url)
    return [(l["url"], l["text"]) for l in links]


async def extract_page_tables(page) -> list[dict]:
    """Extract all tables from the rendered page as list-of-rows."""
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
    """Extract visible text content from the page body."""
    return await page.evaluate("""
        () => {
            // Try content area first
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


async def find_pdf_links(page, base_url: str) -> list[tuple[str, str]]:
    """Find PDF links on the current page."""
    links = await page.evaluate("""
        (baseUrl) => {
            const results = [];
            const seen = new Set();
            for (const a of document.querySelectorAll("a[href]")) {
                const href = a.getAttribute("href").trim();
                const text = (a.textContent || "").trim();
                if (!href) continue;

                let fullUrl;
                try {
                    fullUrl = new URL(href, baseUrl).href;
                } catch {
                    fullUrl = href.startsWith("/") ? baseUrl.replace(/\\/$/, "") + href : baseUrl + "/" + href;
                }

                const isPdf = href.toLowerCase().endsWith(".pdf")
                    || href.toLowerCase().includes(".pdf?")
                    || text.includes(".pdf");
                if (!isPdf) continue;

                const key = fullUrl.substring(0, 200);
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({url: fullUrl, text: text || href});
                }
            }
            return results;
        }
    """, base_url)
    return [(l["url"], l["text"]) for l in links]


async def download_pdf(client: httpx.AsyncClient, url: str) -> str | None:
    """Download a PDF and return extracted text."""
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


def parse_score_rows(table_rows: list[list[str]], school_id: int) -> list[dict]:
    """Parse score line data from table rows (already extracted from rendered DOM).

    Handles the common patterns:
    - Row per major: | code | name | total | politics | english | biz1 | biz2 |
    - Header rows with merged cells
    """
    results = []
    current_year = datetime.now().year

    for row_cells in table_rows:
        if len(row_cells) < 3:
            continue

        # Find 6-digit major code anywhere in row
        major_code = ""
        for c in row_cells:
            m = re.search(r"\b(\d{6})\b", c)
            if m:
                major_code = m.group(1)
                break
        if not major_code:
            # Try 4-digit code
            for c in row_cells:
                m = re.search(r"\b(\d{4})\b", c)
                if m and c.strip()[:4].isdigit():
                    major_code = m.group(1)
                    break
        if not major_code:
            continue

        # Extract all numeric scores (30-500 range filters out noise)
        numbers = []
        for c in row_cells:
            for m in re.finditer(r"\b(\d{2,4})\b", c):
                num = int(m.group(1))
                if 30 <= num <= 500:
                    numbers.append(num)

        if not numbers:
            continue

        # Try to detect year from row
        for c in row_cells:
            ym = re.search(r"(20[12]\d|202[0-6])", c)
            if ym:
                current_year = int(ym.group(1))

        # Classify scores: >=200 = total, <200 = subject scores
        big = [n for n in numbers if n >= 200]
        small = [n for n in numbers if n < 200]

        entry = {
            "school_id": school_id,
            "major_code": major_code,
            "year": current_year,
            "re_exam_total_score": big[0] if big else (max(numbers) if numbers else None),
            "re_exam_politics_score": small[0] if len(small) >= 1 else None,
            "re_exam_english_score": small[1] if len(small) >= 2 else None,
            "re_exam_business_score_1": small[2] if len(small) >= 3 else None,
            "re_exam_business_score_2": small[3] if len(small) >= 4 else None,
        }
        results.append(entry)

    return results


def parse_score_text(text: str, school_id: int) -> list[dict]:
    """Fallback: parse score data from free text when no tables found.

    Looks for patterns like:
    - "总分：350" or "总分线：350"
    - "政治：55，外语：55，业务课1：90，业务课2：90，总分：350"
    - Major code followed by score numbers
    """
    results = []
    current_year = datetime.now().year

    # Find year
    ym = re.search(r"(20[12]\d|202[0-6])\s*年", text)
    if ym:
        current_year = int(ym.group(1))

    # Pattern: major code (6-digit) followed by scores on same or nearby lines
    major_blocks = re.split(r"\n{2,}", text)

    for block in major_blocks:
        # Find major code
        codes = re.findall(r"\b(\d{6})\b", block)
        if not codes:
            codes = re.findall(r"\b(\d{4})\b", block)
        if not codes:
            continue

        # Find numbers in 30-500 range
        scores_in_block = []
        for m in re.finditer(r"\b(\d{2,4})\b", block):
            num = int(m.group(1))
            if 30 <= num <= 500:
                scores_in_block.append(num)

        if len(scores_in_block) < 2:
            continue

        big = [n for n in scores_in_block if n >= 200]
        small = [n for n in scores_in_block if n < 200]

        for code in codes[:3]:
            entry = {
                "school_id": school_id,
                "major_code": code,
                "year": current_year,
                "re_exam_total_score": big[0] if big else (max(scores_in_block) if scores_in_block else None),
                "re_exam_politics_score": small[0] if len(small) >= 1 else None,
                "re_exam_english_score": small[1] if len(small) >= 2 else None,
                "re_exam_business_score_1": small[2] if len(small) >= 3 else None,
                "re_exam_business_score_2": small[3] if len(small) >= 4 else None,
            }
            results.append(entry)

    return results


async def crawl_school(browser, http_client: httpx.AsyncClient, school) -> list[dict]:
    """Crawl one school using Playwright for JS rendering + httpx for PDF download."""
    url = GRAD_URLS.get(school.name, "")
    if not url:
        logger.info("  No URL for %s", school.name)
        return []

    rank = f"#{school.ranking_national}" if school.ranking_national else "?"
    logger.info("[%s] %s → %s", rank, school.name, url)
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
        # Step 1: Load main page with JS rendering
        try:
            await page.goto(base, wait_until="networkidle", timeout=PAGE_TIMEOUT)
            await asyncio.sleep(2)  # extra settle time for late XHR
        except Exception as e:
            logger.info("  Main page load failed: %s", e)
            return []

        # Step 2: Find score-line links and admission nav links
        score_links = await find_score_links(page, base)
        nav_links = await find_nav_links(page, base)
        pdf_links = await find_pdf_links(page, base)

        logger.info("  Score links: %d, Nav links: %d, PDF links: %d",
                     len(score_links), len(nav_links), len(pdf_links))

        # Step 3: Download PDFs from main page
        for pdf_url, pdf_text_label in pdf_links[:5]:
            if pdf_url in visited_urls:
                continue
            visited_urls.add(pdf_url)
            logger.info("  PDF: %s", pdf_url[:120])
            pdf_text = await download_pdf(http_client, pdf_url)
            if pdf_text and len(pdf_text) > 50:
                entries = parse_score_text(pdf_text, school.id)
                if entries:
                    logger.info("    PDF → %d entries", len(entries))
                    all_results.extend(entries)
                else:
                    # Try regex on the raw text for table-like data
                    entries2 = parse_score_rows_from_text(pdf_text, school.id)
                    if entries2:
                        logger.info("    PDF(text) → %d entries", len(entries2))
                        all_results.extend(entries2)
            await asyncio.sleep(0.5)

        # Step 4: Visit score-line pages
        pages_checked = 0
        for link_url, link_text in (score_links[:MAX_SCORE_PAGES]):
            if link_url in visited_urls:
                continue
            visited_urls.add(link_url)
            pages_checked += 1

            await asyncio.sleep(PAGE_DELAY)
            logger.info("  → %s: %s", link_text[:50], link_url[:120])

            try:
                await page.goto(link_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
                await asyncio.sleep(1.5)
            except Exception:
                continue

            # Extract tables from rendered page
            tables = await extract_page_tables(page)
            for table_rows in tables:
                entries = parse_score_rows(table_rows, school.id)
                if entries:
                    all_results.extend(entries)

            # Also try text-based extraction
            page_text = await extract_page_text(page)
            if page_text and "复试" in page_text and "分" in page_text:
                entries = parse_score_text(page_text, school.id)
                if entries:
                    all_results.extend(entries)

            # Check for PDFs on score pages
            pdfs_on_page = await find_pdf_links(page, link_url)
            for pdf_url, _ in pdfs_on_page[:3]:
                if pdf_url in visited_urls:
                    continue
                visited_urls.add(pdf_url)
                await asyncio.sleep(0.5)
                pdf_text = await download_pdf(http_client, pdf_url)
                if pdf_text and len(pdf_text) > 50:
                    entries = parse_score_text(pdf_text, school.id)
                    if entries:
                        all_results.extend(entries)

        # Step 5: Visit admission sub-pages and repeat link discovery
        for nav_url, _ in nav_links[:MAX_ADMISSION_PAGES]:
            if pages_checked >= MAX_SCORE_PAGES:
                break
            if nav_url in visited_urls:
                continue
            visited_urls.add(nav_url)
            pages_checked += 1

            await asyncio.sleep(PAGE_DELAY)
            try:
                await page.goto(nav_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
                await asyncio.sleep(1.5)
            except Exception:
                continue

            sub_score_links = await find_score_links(page, nav_url)
            sub_pdf_links = await find_pdf_links(page, nav_url)

            # PDFs on nav pages
            for pdf_url, _ in sub_pdf_links[:3]:
                if pdf_url in visited_urls:
                    continue
                visited_urls.add(pdf_url)
                await asyncio.sleep(0.5)
                pdf_text = await download_pdf(http_client, pdf_url)
                if pdf_text and len(pdf_text) > 50:
                    entries = parse_score_text(pdf_text, school.id)
                    if entries:
                        all_results.extend(entries)

            for link_url, link_text in sub_score_links[:4]:
                if pages_checked >= MAX_SCORE_PAGES:
                    break
                if link_url in visited_urls:
                    continue
                visited_urls.add(link_url)
                pages_checked += 1

                await asyncio.sleep(PAGE_DELAY)
                try:
                    await page.goto(link_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
                    await asyncio.sleep(1.5)
                except Exception:
                    continue

                tables = await extract_page_tables(page)
                for table_rows in tables:
                    entries = parse_score_rows(table_rows, school.id)
                    if entries:
                        all_results.extend(entries)

                page_text = await extract_page_text(page)
                if page_text and "复试" in page_text:
                    entries = parse_score_text(page_text, school.id)
                    if entries:
                        all_results.extend(entries)

    finally:
        await context.close()

    return all_results


def parse_score_rows_from_text(text: str, school_id: int) -> list[dict]:
    """Parse table-like data from PDF/plain text using line-by-line analysis.

    Suitable for text extracted from PDFs where tables are rendered as aligned columns.
    """
    results = []
    year = datetime.now().year
    ym = re.search(r"(20[12]\d|202[0-6])\s*年", text)
    if ym:
        year = int(ym.group(1))

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if len(line) < 10:
            continue

        # Look for a 6-digit code
        code_m = re.search(r"\b(\d{6})\b", line)
        if not code_m:
            continue
        major_code = code_m.group(1)

        # Extract all numbers in the 30-500 range
        numbers = []
        for m in re.finditer(r"\b(\d{2,4})\b", line):
            num = int(m.group(1))
            if 30 <= num <= 500:
                numbers.append(num)

        if len(numbers) < 2:
            continue

        big = [n for n in numbers if n >= 200]
        small = [n for n in numbers if n < 200]

        results.append({
            "school_id": school_id,
            "major_code": major_code,
            "year": year,
            "re_exam_total_score": big[0] if big else (max(numbers) if numbers else None),
            "re_exam_politics_score": small[0] if len(small) >= 1 else None,
            "re_exam_english_score": small[1] if len(small) >= 2 else None,
            "re_exam_business_score_1": small[2] if len(small) >= 3 else None,
            "re_exam_business_score_2": small[3] if len(small) >= 4 else None,
        })

    return results


async def main():
    db = SessionLocal()
    schools = list(
        db.query(School)
        .filter(School.level.in_([SchoolLevel.C9, SchoolLevel.NINE_EIGHT_FIVE]))
        .order_by(School.ranking_national.asc())
        .all()
    )
    logger.info("Crawling %d schools (C9 + 985) with Playwright\n", len(schools))

    # Update URLs in DB
    updated = 0
    for s in schools:
        url = GRAD_URLS.get(s.name)
        if url and s.graduate_school_url != url:
            s.graduate_school_url = url
            updated += 1
    db.commit()
    logger.info("URLs updated: %d\n", updated)

    # Find available Chromium: prefer system install, fall back to Playwright-bundled
    chromium_paths = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    chromium_exe = None
    for p in chromium_paths:
        if os.path.exists(p):
            chromium_exe = p
            break

    # Concurrent HTTP client for PDF downloads
    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=30) as http_client:
        async with async_playwright() as pw:
            if chromium_exe:
                logger.info("Using system Chromium: %s", chromium_exe)
                browser = await pw.chromium.launch(
                    headless=True,
                    executable_path=chromium_exe,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
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
                try:
                    results = await crawl_school(browser, http_client, s)
                    if results:
                        logger.info("  ** TOTAL: %d entries from %s", len(results), s.name)
                        all_data.extend(results)
                        success_schools.append(s.name)
                    else:
                        logger.info("  -- no data from %s", s.name)
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

    # Report
    logger.info("\n" + "=" * 60)
    logger.info("CRAWL COMPLETE (V3 — Playwright)")
    logger.info("=" * 60)
    logger.info("Schools with data: %d/%d", len(success_schools), len(schools))
    logger.info("Unique score entries: %d", len(unique))
    logger.info("DB rows updated: %d", updated_rows)
    logger.info("Success: %s", ", ".join(success_schools) if success_schools else "(none)")
    logger.info("No data: %s", ", ".join(no_data_schools) if no_data_schools else "(none)")

    # Per-school breakdown
    for s_name in success_schools:
        sid = next((sc.id for sc in schools if sc.name == s_name), None)
        if sid:
            count = sum(1 for e in unique if e["school_id"] == sid)
            logger.info("  %s: %d entries", s_name, count)

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
