import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const ARTIFACT_SCREENSHOT_DIR = 'C:\\Users\\subha\\.gemini\\antigravity-ide\\brain\\5765598c-b602-4e14-9d8b-0580d1ebe38a\\screenshots';

test.beforeAll(() => {
  if (!fs.existsSync(ARTIFACT_SCREENSHOT_DIR)) {
    fs.mkdirSync(ARTIFACT_SCREENSHOT_DIR, { recursive: true });
  }
});

test.describe('ATS Operator Cockpit V2 Acceptance', () => {
  test('01 - Overview Page Loads & PAPER Mode Visible', async ({ page }, testInfo) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `01_overview_${projectName}.png`),
      fullPage: true,
    });
  });

  test('02 - Trade Desk / Cockpit Page & Chart Controls', async ({ page }, testInfo) => {
    await page.goto('/trades');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `02_trade_desk_${projectName}.png`),
      fullPage: true,
    });
  });

  test('03 - Positions Page', async ({ page }, testInfo) => {
    await page.goto('/positions');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `03_positions_${projectName}.png`),
      fullPage: true,
    });
  });

  test('04 - Opportunities / Candidates Page', async ({ page }, testInfo) => {
    await page.goto('/candidates');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `04_opportunities_${projectName}.png`),
      fullPage: true,
    });
  });

  test('05 - Agent & Governance Pages', async ({ page }, testInfo) => {
    await page.goto('/harness');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `05_agents_${projectName}.png`),
      fullPage: true,
    });
  });

  test('06 - Operator Intelligence & Session Review', async ({ page }, testInfo) => {
    await page.goto('/operator-intelligence');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `06_session_review_${projectName}.png`),
      fullPage: true,
    });
  });

  test('07 - System Page Boundary & Truthful Wording', async ({ page }, testInfo) => {
    await page.goto('/settings');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toBeVisible();

    // Verify Truthful wording
    const safetyBoundary = page.locator('.safety-boundary');
    await expect(safetyBoundary).toContainText('PAPER ONLY');
    await expect(safetyBoundary).toContainText('DISABLED');
    await expect(safetyBoundary).toContainText('GOVERNED BY RISK + A04');
    await expect(safetyBoundary).toContainText('BOUNDED RUNTIME API');

    const projectName = testInfo.project.name;
    await page.screenshot({
      path: path.join(ARTIFACT_SCREENSHOT_DIR, `07_system_page_${projectName}.png`),
      fullPage: true,
    });
  });
});
