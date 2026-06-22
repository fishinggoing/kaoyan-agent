"""
研招网 (yz.chsi.com.cn) 招生专业目录爬虫

Usage:
  python -m scripts.crawl_yz_majors                    # crawl top 985/211 schools
  python -m scripts.crawl_yz_majors --all               # crawl all schools
  python -m scripts.crawl_yz_majors --school-ids 1 2 3  # specific schools

How it works:
  1. Opens yz.chsi.com.cn/zsml/dw.do in a real browser (Playwright)
  2. Prompts user to log in once (saves cookies for subsequent runs)
  3. For each school, types the school name into the search form
  4. Clicks through to get major listings
  5. Saves confirmed majors to the database (marks has_graduate=True)
"""

import asyncio
import json
import os
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models import School, Major, SchoolCategory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AUTH_FILE = Path(__file__).resolve().parent.parent / "data" / "yz_auth.json"
DB_PATH = Path(__file__).resolve().parent.parent / "gradschool.db"

YANZHAO_DW_URL = "https://yz.chsi.com.cn/zsml/dw.do"
REQUEST_DELAY = 3.0  # seconds between requests (polite crawling)


def get_target_schools(all_schools: bool = False, school_ids: list[int] | None = None):
    """Get list of schools to crawl, ordered by priority (985/211 first)."""
    db = SessionLocal()
    try:
        from sqlalchemy import select
        from app.models import SchoolLevel

        if school_ids:
            schools = list(db.execute(
                select(School).where(School.id.in_(school_ids))
            ).scalars().all())
        elif all_schools:
            schools = list(db.execute(
                select(School)
                .order_by(School.ranking_national.asc().nulls_last())
            ).scalars().all())
        else:
            # Default: 985 + 211 schools (~115 schools)
            schools = list(db.execute(
                select(School).where(
                    School.level.in_([SchoolLevel.C9, SchoolLevel.NINE_EIGHT_FIVE, SchoolLevel.TWO_ONE_ONE])
                ).order_by(School.ranking_national.asc().nulls_last())
            ).scalars().all())

        return schools
    finally:
        db.close()


async def crawl_school(page, school_name: str, province: str) -> list[dict]:
    """Search for a school on 研招网 and extract its graduate major listing."""
    majors = []

    try:
        # Navigate to the school search page
        await page.goto(YANZHAO_DW_URL, wait_until="networkidle")

        # Type school name into the search input
        # The Vue SPA has an auto-complete input for school name
        search_input = page.locator('input[placeholder*="招生单位"]')
        if await search_input.count() == 0:
            search_input = page.locator('.search-input input').first
        if await search_input.count() == 0:
            search_input = page.locator('input.ivu-input').first

        if await search_input.count() > 0:
            await search_input.fill("")
            await search_input.type(school_name, delay=100)
            await page.wait_for_timeout(1000)

            # Click the search button
            search_btn = page.locator('button:has-text("查询")')
            if await search_btn.count() == 0:
                search_btn = page.locator('.search-btn').first
            if await search_btn.count() > 0:
                await search_btn.click()
                await page.wait_for_timeout(3000)

                # Parse results from the rendered page
                # Look for the result list items rendered by Vue
                result_items = page.locator('.result-item, .school-item, .list-item')
                count = await result_items.count()

                if count == 0:
                    # Try looking for any links that might be school results
                    links = page.locator('a[href*="schId"]')
                    count = await links.count()

                logger.info(f"  Found {count} result items for '{school_name}'")

                # Click first matching school to get to major listing
                if count > 0:
                    first_result = result_items.first
                    await first_result.click()
                    await page.wait_for_timeout(3000)

                    # Parse major table on the school detail page
                    major_rows = page.locator('table tr, .major-row, .major-item')
                    row_count = await major_rows.count()
                    logger.info(f"  School detail: {row_count} major rows")

                    for i in range(min(row_count, 200)):
                        try:
                            row = major_rows.nth(i)
                            text = await row.text_content()
                            if text and text.strip():
                                majors.append({"raw_text": text.strip()})
                        except Exception:
                            continue
            else:
                logger.warning(f"  Could not find search button")
        else:
            logger.warning(f"  Could not find search input")

    except Exception as e:
        logger.error(f"  Error crawling '{school_name}': {e}")

    return majors


async def main_async(schools: list[School]):
    """Main async crawl loop."""
    from playwright.async_api import async_playwright

    logger.info(f"Starting crawl for {len(schools)} schools")
    logger.info(f"Auth file: {AUTH_FILE}")

    async with async_playwright() as p:
        # Load saved auth state if available
        storage_state = None
        if AUTH_FILE.exists():
            storage_state = str(AUTH_FILE)
            logger.info("Using saved auth state")

        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = await context.new_page()

        # Navigate to check login state
        await page.goto(YANZHAO_DW_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Check if login is needed
        login_needed = await page.locator('text=登录').count() > 0
        if login_needed or not AUTH_FILE.exists():
            logger.info("=" * 60)
            logger.info("LOGIN REQUIRED — please log in manually in the browser window")
            logger.info("After logging in, come back to this terminal and press Enter")
            logger.info("=" * 60)
            input("Press Enter after you've logged in...")

            # Save auth state for future runs
            await context.storage_state(path=str(AUTH_FILE))
            logger.info(f"Auth state saved to {AUTH_FILE}")

        # Now crawl each school
        db = SessionLocal()
        try:
            new_count = 0
            for i, school in enumerate(schools):
                if i > 0:
                    await asyncio.sleep(REQUEST_DELAY)

                logger.info(f"[{i+1}/{len(schools)}] {school.name} ({school.province})")
                results = await crawl_school(page, school.name, school.province)

                if results:
                    logger.info(f"  Got {len(results)} major entries for {school.name}")
                    # TODO: Parse major codes from results and update database

        finally:
            db.close()

        await browser.close()

    logger.info("Crawl complete")


def main():
    parser = argparse.ArgumentParser(description="Crawl 研招网 for school major data")
    parser.add_argument("--all", action="store_true", help="Crawl all schools")
    parser.add_argument("--school-ids", type=int, nargs="+", help="Specific school IDs")
    args = parser.parse_args()

    schools = get_target_schools(all_schools=args.all, school_ids=args.school_ids)
    logger.info(f"Target schools: {len(schools)}")

    if not schools:
        logger.warning("No schools to crawl")
        return

    asyncio.run(main_async(schools))


if __name__ == "__main__":
    main()
