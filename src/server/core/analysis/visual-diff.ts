import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import fs from 'fs';
import path from 'path';

export interface VisualDiffResult {
  diffPixels: number;
  diffPercentage: number;
  totalPixels: number;
  width: number;
  height: number;
  diffImagePath?: string;
  diffImageBuffer?: Buffer;
}

/**
 * Normalizes two PNG images to equal dimensions by padding the smaller one with transparent background.
 */
function normalizePngDimensions(img1: PNG, img2: PNG): { width: number; height: number; a: PNG; b: PNG } {
  const width = Math.max(img1.width, img2.width);
  const height = Math.max(img1.height, img2.height);

  if (img1.width === width && img1.height === height && img2.width === width && img2.height === height) {
    return { width, height, a: img1, b: img2 };
  }

  const padded1 = new PNG({ width, height });
  const padded2 = new PNG({ width, height });

  // Fill with transparent zeros
  padded1.data.fill(0);
  padded2.data.fill(0);

  PNG.bitblt(img1, padded1, 0, 0, img1.width, img1.height, 0, 0);
  PNG.bitblt(img2, padded2, 0, 0, img2.width, img2.height, 0, 0);

  return { width, height, a: padded1, b: padded2 };
}

export function compareScreenshots(
  sourceA: string | Buffer,
  sourceB: string | Buffer,
  outputPath?: string,
  threshold = 0.1
): VisualDiffResult {
  const bufA = typeof sourceA === 'string' ? fs.readFileSync(sourceA) : sourceA;
  const bufB = typeof sourceB === 'string' ? fs.readFileSync(sourceB) : sourceB;

  const raw1 = PNG.sync.read(bufA);
  const raw2 = PNG.sync.read(bufB);

  const { width, height, a, b } = normalizePngDimensions(raw1, raw2);

  const diffPng = new PNG({ width, height });

  const diffPixels = pixelmatch(a.data, b.data, diffPng.data, width, height, {
    threshold,
    includeAA: false,
    diffColor: [255, 0, 102], // Vivid magenta for visual diff clarity
  });

  const totalPixels = width * height;
  const diffPercentage = totalPixels > 0 ? (diffPixels / totalPixels) * 100 : 0;

  const diffImageBuffer = PNG.sync.write(diffPng);

  if (outputPath) {
    const parent = path.dirname(outputPath);
    if (!fs.existsSync(parent)) {
      fs.mkdirSync(parent, { recursive: true });
    }
    fs.writeFileSync(outputPath, diffImageBuffer);
  }

  return {
    diffPixels,
    diffPercentage: Math.round(diffPercentage * 100) / 100,
    totalPixels,
    width,
    height,
    diffImagePath: outputPath,
    diffImageBuffer,
  };
}
