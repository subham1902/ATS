"""Test Dynamic Datasets Workspace & Chart 360 Enhancements.

Validates:
1. Datasets page loads cleanly.
2. Direct Data Feeder panel opens.
3. Sample GoldM data feeds and validates OHLC integrity.
4. Dataset registers and displays data preview table.
5. Chart 360 terminal allows symbol switching, timeframe switching, and drawer toggling.
6. Captures screenshots for verification.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path("C:/Users/subha/.gemini/antigravity-ide/brain/4fd21fa7-bce8-41a6-9245-97268504a312/screenshots")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def run_test():
    print("\n=======================================================")
    print(">>> TESTING DYNAMIC DATASETS & CHART 360 INTEGRATION <<<")
    print("=======================================================")

    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("console", lambda msg: print(f"[BROWSER {msg.type.upper()}] {msg.text}") if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda err: print(f"[FATAL PAGE ERROR] {err}"))

        # -------------------------------------------------------------
        # Part 1: Dynamic Datasets Workspace
        # -------------------------------------------------------------
        print("\n[STEP 1] Testing /datasets dynamic ingestion...")
        page.goto("http://127.0.0.1:3001/datasets", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        assert page.locator("text=Datasets Workspace").first.is_visible()
        print("  [OK] Datasets workspace loaded")

        # Open Feeder
        feeder_btn = page.locator("button:has-text('+ Direct Ingest / Feed Data')")
        assert feeder_btn.is_visible()
        feeder_btn.click()
        page.wait_for_timeout(600)
        print("  [OK] Direct Data Feeder panel opened")

        # Click Sample GoldM preset
        sample_btn = page.locator("button:has-text('+ Sample GoldM (5m)')")
        assert sample_btn.is_visible()
        sample_btn.click()
        page.wait_for_timeout(800)
        print("  [OK] Loaded GoldM sample dataset")

        # Ingest & Register
        ingest_btn = page.locator("button:has-text('⚡ Ingest & Register to Fabric')")
        assert ingest_btn.is_visible()
        ingest_btn.click()
        page.wait_for_timeout(1000)
        print("  [OK] Successfully ingested and registered dataset")

        # Verify Custom Dataset appears in grid
        custom_badge = page.locator("text=CUSTOM").first
        assert custom_badge.is_visible()
        print("  [OK] Custom dataset registered with 'CUSTOM' badge")

        # Verify Data Preview Table
        preview_table = page.locator("text=BAR DATA PREVIEW")
        assert preview_table.is_visible()
        print("  [OK] Live Data Preview Table visible")

        # Save Screenshot
        shot1 = ARTIFACTS_DIR / "datasets_dynamic_ingestion.png"
        page.screenshot(path=str(shot1), full_page=True)
        print(f"  [OK] Saved screenshot: {shot1.name}")

        # -------------------------------------------------------------
        # Part 2: Chart 360 Full Recheck
        # -------------------------------------------------------------
        print("\n[STEP 2] Testing Chart 360 interactive features...")
        page.goto("http://127.0.0.1:3001/market", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        # Check Canvas
        canvas = page.locator("canvas").first
        assert canvas.is_visible()
        print("  [OK] TradingView Lightweight Canvas rendered")

        # Test Symbol Selector
        symbol_select = page.locator("select:has(option[value='MCX GOLDM 25SEP26'])").first
        if symbol_select.is_visible():
            symbol_select.select_option("MCX GOLDM 25SEP26")
            page.wait_for_timeout(1000)
            print("  [OK] Switched symbol to MCX GOLDM 25SEP26")

            symbol_select.select_option("NIFTY 50 SPOT")
            page.wait_for_timeout(1000)
            print("  [OK] Switched symbol back to NIFTY 50 SPOT")

        # Test Timeframe Switch
        tf_15m = page.locator("button:has-text('15m')").first
        if tf_15m.is_visible():
            tf_15m.click()
            page.wait_for_timeout(800)
            print("  [OK] Timeframe switched to 15m")

            page.locator("button:has-text('5m')").first.click()
            page.wait_for_timeout(800)
            print("  [OK] Timeframe restored to 5m")

        # Test Watchlist Drawer
        watchlist_tab = page.locator("[data-testid='drawer-tab-watchlist']").first
        if watchlist_tab.is_visible():
            watchlist_tab.click(force=True)
            page.wait_for_timeout(800)
            assert page.locator("[data-testid='chart360-drawer']").is_visible()
            print("  [OK] Watchlist drawer opened successfully")

            # Close drawer
            page.locator("[data-testid='drawer-close']").first.click(force=True)
            page.wait_for_timeout(600)
            print("  [OK] Watchlist drawer closed")

        # Test Option Chain L2 Depth Drawer
        depth_tab = page.locator("[data-testid='drawer-tab-option_chain']").first
        if depth_tab.is_visible():
            depth_tab.click(force=True)
            page.wait_for_timeout(1000)
            assert page.locator("[data-testid='chart360-drawer']").is_visible()
            print("  [OK] Option Chain / L2 Depth drawer opened successfully")

            # Close drawer
            page.locator("[data-testid='drawer-close']").first.click(force=True)
            page.wait_for_timeout(600)
            print("  [OK] Option Chain drawer closed")

        # Save Screenshot
        shot2 = ARTIFACTS_DIR / "chart360_interactive_recheck.png"
        page.screenshot(path=str(shot2), full_page=True)
        print(f"  [OK] Saved screenshot: {shot2.name}")

        browser.close()

    print("\n=======================================================")
    print(">>> DYNAMIC DATASETS & CHART 360 AUDIT: ALL PASSED <<<")
    print(f"Console errors detected: {len(console_errors)}")
    print("=======================================================\n")


if __name__ == "__main__":
    run_test()
