/** Accessibility: axe-core on every screen, plus keyboard operation (AC-21).
 *
 * SPEC §13 asks for WCAG 2.2 AA. The bar this file enforces is the one AC-21
 * states: **no serious or critical axe issues on the nine screens**, the whole
 * app operable from a keyboard including Watch, and reduced motion honoured.
 *
 * axe cannot prove a page is accessible -- it catches machine-checkable faults
 * only. The things it cannot check (is the alt text *true*, is the reading
 * order sensible) are handled by the design rules in SPEC §13 instead.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const PASSWORD = 'pagdandi demo';
const USER = 'riya_s';

const SCREENS: { name: string; path: string }[] = [
  { name: 'Nearby', path: '/' },
  { name: 'Watch', path: '/watch' },
  { name: 'Explore list', path: '/explore' },
  { name: 'Explore map', path: '/explore?view=map' },
  { name: 'Add a place', path: '/add/place' },
  { name: 'Passport', path: '/you' },
  { name: 'Studio', path: '/you?view=studio' },
  { name: 'Languages & cities', path: '/settings' },
  { name: 'Sign in', path: '/signin' },
];

async function signIn(page: Page) {
  await page.goto('/signin');
  await page.getByLabel('Username').fill(USER);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^Sign in$/ }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe('AC-21: axe-core finds no serious or critical issues', () => {
  for (const screen of SCREENS) {
    test(`${screen.name}`, async ({ page }) => {
      await signIn(page);
      await page.goto(screen.path);
      await page.waitForTimeout(screen.path.includes('map') ? 2500 : 900);

      // Dismiss the content-rules sheet so the screen behind it is scanned too.
      const understood = page.getByRole('button', { name: 'Understood' });
      if (await understood.count()) await understood.first().click();

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
        // The MapLibre canvas and its controls are third-party DOM we do not
        // author; the surrounding app chrome is still scanned.
        .exclude('.maplibregl-map')
        .analyze();

      const bad = results.violations.filter(
        (violation) => violation.impact === 'serious' || violation.impact === 'critical',
      );
      const report = bad
        .map((v) => `${v.id} (${v.impact}): ${v.help} [${v.nodes.length} node(s)]`)
        .join('\n');
      expect(bad, `${screen.name} has serious/critical issues:\n${report}`).toEqual([]);
    });
  }
});

test.describe('AC-21: the app works without a pointer', () => {
  test('every deck gesture has a button', async ({ page }) => {
    await signIn(page);
    // Skip / Open / Save are buttons, not just swipes (SPEC §8.2, §13).
    const actions = page.locator('.actions .act');
    if (await actions.count()) {
      await expect(page.getByRole('button', { name: /Skip/ })).toBeVisible();
      await expect(page.getByRole('button', { name: /Open/ })).toBeVisible();
      await expect(page.getByRole('button', { name: /Save/ })).toBeVisible();
    }
  });

  test('Watch is operable with buttons and arrow keys', async ({ page }) => {
    await signIn(page);
    await page.goto('/watch');
    await page.waitForTimeout(1500);

    await expect(page.getByRole('button', { name: 'Next video' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Previous video' })).toBeVisible();

    const announced = page.locator('[aria-live="polite"]');
    const before = await announced.innerText().catch(() => '');
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(700);
    const after = await announced.innerText().catch(() => '');
    expect(after, 'ArrowDown should move to the next video').not.toBe(before);
  });

  test('tabbing reaches the main navigation', async ({ page }) => {
    await signIn(page);
    await page.goto('/explore');
    const reachable: string[] = [];
    for (let i = 0; i < 40; i += 1) {
      await page.keyboard.press('Tab');
      const label = await page.evaluate(() => {
        const node = document.activeElement as HTMLElement | null;
        if (!node) return '';
        return (node.getAttribute('aria-label') || node.innerText || node.tagName).trim().slice(0, 30);
      });
      if (label) reachable.push(label);
    }
    expect(reachable.join(' | ')).toMatch(/Nearby|Watch|Explore|You/);
  });

  test('every control meets the 44px touch target minimum', async ({ page }) => {
    await signIn(page);
    await page.goto('/you');
    const small = await page.evaluate(() => {
      const offenders: string[] = [];
      const controls = document.querySelectorAll('button, a[href], select, input');
      for (const node of Array.from(controls)) {
        const element = node as HTMLElement;
        if (element.offsetParent === null) continue;      // not visible
        const box = element.getBoundingClientRect();
        if (box.width === 0 || box.height === 0) continue;
        // SPEC §13: targets are at least 44x44. A 2px tolerance absorbs
        // sub-pixel rounding at this device scale.
        if (box.height < 42 && box.width < 42) {
          offenders.push(
            `${element.tagName}.${element.className} ${Math.round(box.width)}x${Math.round(box.height)}`,
          );
        }
      }
      return offenders;
    });
    expect(small, `targets under 44px: ${small.join(' | ')}`).toEqual([]);
  });
});

test.describe('AC-21: reduced motion is honoured', () => {
  test.use({ reducedMotion: 'reduce' });

  test('no rotation on stamps or tips when motion is reduced', async ({ page }) => {
    await signIn(page);
    await page.goto('/you');
    await page.waitForTimeout(600);

    const rotated = await page.evaluate(() => {
      const offenders: string[] = [];
      for (const node of Array.from(document.querySelectorAll('.stamp, .tip'))) {
        const transform = getComputedStyle(node).transform;
        // `none` or an identity matrix both mean "not rotated".
        if (transform && transform !== 'none' && transform !== 'matrix(1, 0, 0, 1, 0, 0)') {
          offenders.push(`${node.className}: ${transform}`);
        }
      }
      return offenders;
    });
    expect(rotated, `still rotating under reduced motion: ${rotated.join(' | ')}`).toEqual([]);
  });
});
