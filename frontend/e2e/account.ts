/** The account the end-to-end tests sign in as.
 *
 * The database holds exactly one account: the app's own (@truvel). Tests use
 * it rather than creating their own, so running them does not quietly add
 * users to a database whose whole point is that there is only the one.
 *
 * Override the password with TRUVEL_PASSWORD when you change it. The default
 * below is a local development credential, not a secret: see README.
 */
import { expect, type Page } from '@playwright/test';

export const ACCOUNT = '@truvel';
export const HANDLE = 'truvel';
export const PASSWORD = process.env.TRUVEL_PASSWORD ?? 'qw12&er34';

export async function signIn(page: Page): Promise<void> {
  await page.goto('/signin');
  await page.getByLabel('Email or handle').fill(HANDLE);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^Sign in$/ }).click();
  await expect(page).toHaveURL(/\/$/);
}

/** Put a real video on a real place, through the same endpoint the app uses.
 *
 * The database has no videos because nobody has posted one, which is the honest
 * state. Tests that are about *watching* need something to watch, so this posts
 * a minimal but genuine MP4 container with a real poster image, exactly as an
 * upload from the Add screen would. It is removed afterwards by deleting the
 * media row, so a test run leaves the database as it found it.
 */
export async function postTestVideo(page: Page, placeId: number, caption: string): Promise<number> {
  const result = await page.evaluate(
    async ({ placeId: place, caption: text }) => {
      // ftyp box: size, "ftyp", major brand "isom", minor version, compatible brands.
      const brand = new TextEncoder().encode('isom');
      const box = new Uint8Array(24);
      new DataView(box.buffer).setUint32(0, 24);
      box.set(new TextEncoder().encode('ftyp'), 4);
      box.set(brand, 8);
      box.set(brand, 16);
      const video = new Blob([box, new Uint8Array(2048)], { type: 'video/mp4' });

      // A real 360x640 poster, drawn rather than faked, so it survives the
      // server's re-encode and perceptual-hash steps.
      const canvas = document.createElement('canvas');
      canvas.width = 360;
      canvas.height = 640;
      const ctx = canvas.getContext('2d')!;
      // A hash of the caption, so two different clips get two different layouts.
      let seed = 7;
      for (const ch of text) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
      const rand = () => {
        seed = (seed * 1664525 + 1013904223) >>> 0;
        return seed / 4294967296;
      };
      ctx.fillStyle = `hsl(${Math.floor(rand() * 360)} 45% 35%)`;
      ctx.fillRect(0, 0, 360, 640);
      // Large, high-contrast blocks: a perceptual hash sees layout and tone,
      // so fine detail would not tell two posters apart.
      for (let i = 0; i < 6; i += 1) {
        const light = rand() > 0.5;
        ctx.fillStyle = light ? '#f4efe3' : '#14110f';
        ctx.fillRect(rand() * 240, rand() * 520, 80 + rand() * 160, 60 + rand() * 140);
      }
      const poster = await new Promise<Blob>((resolve) =>
        canvas.toBlob((blob) => resolve(blob!), 'image/jpeg', 0.85),
      );

      const form = new FormData();
      form.set('file', video, 'clip.mp4');
      form.set('poster', poster, 'poster.jpg');
      form.set('kind', 'video');
      form.set('caption', text);
      form.set('duration_s', '24');
      const response = await fetch(`/api/places/${place}/media`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'truvel' },
        body: form,
      });
      return { status: response.status, body: await response.text() };
    },
    { placeId, caption },
  );
  expect(result.status, `video upload failed: ${result.body}`).toBe(200);
  return (JSON.parse(result.body) as { media: { id: number } }).media.id;
}

/** The id of a place by name, so a test does not depend on row numbers that a
 *  merge or a re-seed will change. Searches the way the app does. */
export async function placeId(page: Page, name: string): Promise<number> {
  const id = await page.evaluate(async (query) => {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = (await response.json()) as { places: { id: number }[] };
    return data.places[0]?.id ?? 0;
  }, name);
  expect(id, `no place called "${name}" in the database`).toBeGreaterThan(0);
  return id;
}
