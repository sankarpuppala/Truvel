/** After the whole run: remove the videos the tests posted.
 *
 * The tests upload genuine (tiny) videos through the real endpoint to have
 * something to watch. The product has no delete-my-upload route, so this calls
 * the cleanup script directly rather than adding one just for tests.
 */
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export default function globalTeardown(): void {
  // ES modules have no __dirname; derive it from the module's own URL.
  const here = path.dirname(fileURLToPath(import.meta.url));
  const backend = path.resolve(here, '..', '..', 'backend');
  const python = path.join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  try {
    const out = execFileSync(python, ['-m', 'scripts.remove_test_media'], {
      cwd: backend,
      encoding: 'utf-8',
    });
    console.log(out.split('\n').filter((line) => line.startsWith('removed')).join(''));
  } catch (error) {
    console.warn('Could not remove test uploads:', String(error).slice(0, 200));
  }
}
