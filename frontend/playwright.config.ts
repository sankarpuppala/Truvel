import { defineConfig, devices } from '@playwright/test';

// 390 x 844 is the size the design reference is drawn for (SPEC §12, AC-20).
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  // One worker: the backend is a single SQLite file on a laptop, and parallel
  // workers make requests time out rather than reveal anything useful.
  workers: 1,
  reporter: [['list']],
  use: {
    // The device preset first, then our own values -- a spread that comes
    // *after* these would put the 1280x720 desktop viewport back and the
    // screenshots would not be the phone size AC-20 asks for.
    ...devices['Desktop Chrome'],
    baseURL: 'http://localhost:5173',
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: false,
    hasTouch: true,
  },
  projects: [
    { name: 'light', use: { colorScheme: 'light' } },
    { name: 'dark', use: { colorScheme: 'dark' } },
  ],
});
