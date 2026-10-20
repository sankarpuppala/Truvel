/** Client-side photo and video preparation (SPEC §8.6, §9.7).
 *
 * Order matters here. EXIF GPS is read **before** the resize, because drawing
 * the image to a canvas and re-encoding it destroys all metadata -- which is
 * exactly what we want for privacy, but it means the cross-check against the
 * pin has to happen first (SPEC §9.7).
 *
 * The resize also keeps uploads small on a phone connection: a 12 MP photo
 * becomes a ~400 KB JPEG at 2048 px and q0.82.
 */

const LONG_SIDE = 2048;
const QUALITY = 0.82;

export type ExifGps = { lat: number; lng: number };

/**
 * Read EXIF GPS, or null when there is none.
 *
 * Absent EXIF is completely normal: Android's photo picker strips location
 * before the file reaches the browser. It is never required and never counted
 * against an upload (SPEC §9.7).
 */
export async function readExifGps(file: File): Promise<ExifGps | null> {
  try {
    const exifr = await import('exifr');
    const data = (await exifr.gps(file)) as { latitude?: number; longitude?: number } | undefined;
    if (!data || typeof data.latitude !== 'number' || typeof data.longitude !== 'number') {
      return null;
    }
    return { lat: data.latitude, lng: data.longitude };
  } catch {
    // A photo with unreadable metadata is still a perfectly good photo.
    return null;
  }
}

/** Resize to <= 2048 px on the long side and re-encode as JPEG q0.82. */
export async function resizePhoto(file: File): Promise<Blob> {
  const bitmap = await loadBitmap(file);
  const scale = Math.min(1, LONG_SIDE / Math.max(bitmap.width, bitmap.height));
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('This browser cannot process images.');
  context.drawImage(bitmap, 0, 0, width, height);
  if ('close' in bitmap && typeof bitmap.close === 'function') bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', QUALITY),
  );
  if (!blob) throw new Error('Could not prepare that photo.');
  return blob;
}

/**
 * A poster frame at 1 second, plus the video's duration (SPEC §8.6).
 *
 * The duration is read from the file rather than trusted from a form field,
 * and the server checks it again against the 60 s limit.
 */
export async function videoPoster(
  file: File,
): Promise<{ blob: Blob; duration: number; width: number; height: number }> {
  const url = URL.createObjectURL(file);
  try {
    const video = document.createElement('video');
    video.src = url;
    video.muted = true;
    video.playsInline = true;
    video.preload = 'metadata';

    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error('That video could not be read.'));
    });

    const duration = Number.isFinite(video.duration) ? video.duration : 0;

    // Seek to 1 s, or the midpoint of a very short clip.
    await new Promise<void>((resolve, reject) => {
      video.onseeked = () => resolve();
      video.onerror = () => reject(new Error('That video could not be read.'));
      video.currentTime = Math.min(1, Math.max(0, duration / 2));
    });

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 720;
    canvas.height = video.videoHeight || 1280;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('This browser cannot process video.');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.85),
    );
    if (!blob) throw new Error('Could not make a poster frame.');

    return { blob, duration, width: canvas.width, height: canvas.height };
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function loadBitmap(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if ('createImageBitmap' in window) {
    try {
      // `imageOrientation: 'from-image'` applies the EXIF rotation, so a
      // portrait photo is not stored sideways.
      return await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch {
      /* fall through to the <img> path */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('That image could not be read.'));
    });
    return image;
  } finally {
    // The bitmap has been decoded into the element already.
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

/** Human-readable size, for the "this is too big" message. */
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
