import { signIn } from './account';
import { test } from '@playwright/test';
test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const PAGES: [string, string][] = [
  ['nearby', '/'], ['watch', '/watch'], ['explore', '/explore'],
  ['map', '/explore?view=map'], ['place', '/explore'], ['you', '/you'],
  ['studio', '/you?view=studio'], ['settings', '/settings'],
];
for (const [name, path] of PAGES) {
  test(`laptop ${name}`, async ({ page }) => {
    await signIn(page);
    await page.goto(path);
    if (name === 'place') await page.locator('.row').first().click();
    await page.waitForTimeout(name === 'map' ? 3200 : 1600);
    await page.screenshot({ path: `../results/screens/laptop-${test.info().project.name}/${name}.png` });
  });
}
