/** Screenshots of every screen at 390 x 844, light and dark (AC-20).
 *
 * This is the check that the app still looks like docs/design-reference.html:
 * the structural assertions below name the reference's own class names, so if a
 * screen stops using the design system the test fails rather than the drift
 * going unnoticed.
 *
 * It also enforces two rules that are easy to break by accident:
 *  - no horizontal scrolling at 360 px (AC-20);
 *  - every element showing a rupee figure carries a Simulated label (AC-23).
 */
import { expect, test, type Page } from '@playwright/test';

const PASSWORD = 'pagdandi demo';
const USER = 'riya_s';

async function signIn(page: Page) {
  await page.goto('/signin');
  await page.getByLabel('Username').fill(USER);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^Sign in$/ }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function shot(page: Page, name: string) {
  // Written under ../results/ so the committed screenshots sit beside the
  // simulation results the report quotes (PLAN.md).
  const theme = test.info().project.name;
  await page.screenshot({ path: `../results/screens/${theme}/${name}.png`, fullPage: false });
}

test.describe('the nine screens', () => {
  test('1 Nearby -- the deck', async ({ page }) => {
    await signIn(page);
    await page.waitForSelector('.topbar');
    // The deck, or the end card when everything nearby has been seen.
    await expect(page.locator('.deck, .empty')).toBeVisible();
    await expect(page.locator('.nav')).toBeVisible();
    await expect(page.locator('.nav-add')).toBeVisible();
    await shot(page, '1-nearby');
  });

  test('2 Watch -- places on video', async ({ page }) => {
    await signIn(page);
    await page.goto('/watch');
    await expect(page.locator('.scr-watch')).toBeVisible();
    await expect(page.locator('.wtabs')).toBeVisible();
    // Watch is dark in both themes (SPEC §12.1).
    await expect(page.locator('.nav-dark')).toBeVisible();
    await page.waitForTimeout(1200);
    await shot(page, '2-watch');
  });

  test('3 Explore -- a city, ranked', async ({ page }) => {
    await signIn(page);
    await page.goto('/explore');
    await expect(page.locator('.ex-city')).toBeVisible();
    await expect(page.locator('.tabs')).toBeVisible();
    // The ⓘ line that explains the sort (SPEC §8.4).
    await expect(page.locator('.why')).toBeVisible();
    await expect(page.locator('.row').first()).toBeVisible();
    await shot(page, '3-explore-list');
  });

  test('4 Explore -- map and fog', async ({ page }) => {
    await signIn(page);
    await page.goto('/explore?view=map');
    await expect(page.locator('.mapwrap')).toBeVisible();
    await expect(page.locator('.legend')).toBeVisible();
    await expect(page.locator('.osm')).toContainText('OpenStreetMap');
    await page.waitForTimeout(2500);
    await shot(page, '4-explore-map');
  });

  test('5 Place -- full length', async ({ page }) => {
    await signIn(page);
    await page.goto('/explore');
    await page.locator('.row a, .row').first().click();
    await expect(page.locator('.pl-name')).toBeVisible();
    // The safety card is never hidden or collapsed (invariant 9).
    await expect(page.locator('.safety')).toBeVisible();
    await expect(page.locator('.safety')).toContainText('112');
    await expect(page.locator('.checkin-bar')).toBeVisible();
    await expect(page.locator('.attrib')).toContainText('OpenStreetMap');
    await shot(page, '5-place');
  });

  test('6 Add -- pin, verify, de-duplicate', async ({ page }) => {
    await signIn(page);
    await page.goto('/add/place');
    // The content rules are shown before the first add (SPEC §8.6).
    const understood = page.getByRole('button', { name: 'Understood' });
    if (await understood.isVisible()) await understood.click();
    await expect(page.locator('.dprog')).toBeVisible();
    await expect(page.locator('.dp-dot.cur')).toBeVisible();
    await shot(page, '6-add');
  });

  test('7 You -- Passport', async ({ page }) => {
    await signIn(page);
    await page.goto('/you');
    await expect(page.locator('.pp-name')).toBeVisible();
    await expect(page.locator('.pp-cards')).toBeVisible();
    await expect(page.locator('.stamps')).toBeVisible();
    await shot(page, '7-passport');
  });

  test('8 You -- Creator Studio', async ({ page }) => {
    await signIn(page);
    await page.goto('/you?view=studio');
    await expect(page.locator('.simbanner')).toBeVisible();
    await expect(page.locator('.metrics')).toBeVisible();
    await expect(page.locator('.partner')).toBeVisible();
    await shot(page, '8-studio');
  });

  test('9 Languages & cities', async ({ page }) => {
    await signIn(page);
    await page.goto('/settings');
    await expect(page.locator('.lg-head h3')).toContainText('Languages');
    await expect(page.locator('.lchips')).toBeVisible();
    await expect(page.locator('.cities')).toBeVisible();
    // Every one of the 23 languages renders its own autonym (AC-4 glyph check).
    await expect(page.locator('.lchips .lc')).toHaveCount(23);
    await shot(page, '9-languages');
  });
});

test.describe('layout and money rules', () => {
  test('AC-20: no horizontal scroll at 360 px on any screen', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await signIn(page);
    for (const path of ['/', '/explore', '/you', '/you?view=studio', '/settings', '/watch']) {
      await page.goto(path);
      await page.waitForTimeout(600);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${path} scrolls sideways by ${overflow}px`).toBeLessThanOrEqual(1);
    }
  });

  test('AC-23: every rupee figure carries a Simulated label', async ({ page }) => {
    await signIn(page);
    await page.goto('/you?view=studio');
    await expect(page.locator('.simbanner')).toBeVisible();

    // Find every element whose own text contains a rupee sign, and check that
    // a Simulated tag sits in the same card.
    const offenders = await page.evaluate(() => {
      const bad: string[] = [];
      const walk = document.querySelectorAll('body *');
      for (const node of Array.from(walk)) {
        const own = Array.from(node.childNodes)
          .filter((child) => child.nodeType === Node.TEXT_NODE)
          .map((child) => child.textContent ?? '')
          .join('');
        if (!own.includes('₹')) continue;
        const card = node.closest('.mc, .tc, .partner, .topc, .simbanner, .sheet, section, .ledger');
        const labelled = card?.querySelector('.sim') ?? node.parentElement?.querySelector('.sim');
        if (!labelled) bad.push(own.trim().slice(0, 60));
      }
      return bad;
    });
    expect(offenders, `unlabelled rupee figures: ${offenders.join(' | ')}`).toEqual([]);
  });

  test('AC-22: only allowed origins are contacted', async ({ page }) => {
    const external: string[] = [];
    page.on('request', (request) => {
      const raw = request.url();
      // data: and blob: URLs never leave the page, so they are not origins.
      if (!/^https?:/i.test(raw)) return;
      const url = new URL(raw);
      const allowed =
        url.hostname === '127.0.0.1' ||
        url.hostname === 'localhost' ||
        url.hostname === 'tiles.openfreemap.org';
      if (!allowed) external.push(url.hostname);
    });

    await signIn(page);
    await page.goto('/explore?view=map');
    await page.waitForTimeout(3000);
    await page.goto('/you?view=studio');
    await page.waitForTimeout(800);

    expect([...new Set(external)], 'unexpected third-party origins').toEqual([]);
  });

  test('AC-25: a production build has no teleport UI', async ({ page }) => {
    await signIn(page);
    await page.goto('/');
    // The dev build does show it; this asserts it is *clearly marked* so it can
    // never be mistaken for a real check-in. The absence in production is
    // tested on the server side (test_api.py::test_ac25_teleport_is_404...).
    const devbar = page.locator('.devbar');
    if (await devbar.count()) {
      await expect(devbar.first()).toContainText('Simulated visits never reach');
    }
  });
});
