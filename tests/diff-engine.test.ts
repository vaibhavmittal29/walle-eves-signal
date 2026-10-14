import { describe, it, expect } from 'vitest';
import { computeMyersDiff } from '../src/server/core/analysis/myers-diff.js';
import { compareScreenshots } from '../src/server/core/analysis/visual-diff.js';
import { PNG } from 'pngjs';

describe('Myers Text Diff & Pixelmatch Visual Diff Engine [T]', () => {
  it('computes accurate Myers line and word additions and deletions', () => {
    const textV1 = `Engineering Department Announcements
Fall 2026 Curriculum Updates
Laboratory sessions start on Monday.`;

    const textV2 = `Engineering Department Announcements
Fall 2026 Curriculum Updates (REVISED)
Laboratory sessions start on Wednesday.
Extra line added at bottom.`;

    const diffResult = computeMyersDiff(textV1, textV2, { includeWordDiff: true });

    // Assertions on line additions and deletions
    expect(diffResult.additions).toBeGreaterThan(0);
    expect(diffResult.deletions).toBeGreaterThan(0);

    // Verify unified patch contains standard diff markers (+ and -)
    expect(diffResult.unifiedPatch).toContain('---');
    expect(diffResult.unifiedPatch).toContain('+++');
    expect(diffResult.unifiedPatch).toContain('+Fall 2026 Curriculum Updates (REVISED)');
    expect(diffResult.unifiedPatch).toContain('-Fall 2026 Curriculum Updates');

    // Verify word diff includes both unchanged and modified tokens
    expect(diffResult.wordChanges).toBeDefined();
    const addedWord = diffResult.wordChanges?.find(w => w.type === 'added' && w.value.includes('REVISED'));
    expect(addedWord).toBeDefined();
  });

  it('runs pixelmatch visual comparison and calculates mismatched pixel percentage', () => {
    // Generate synthetic Image A (100x100 white square)
    const imgA = new PNG({ width: 100, height: 100 });
    imgA.data.fill(255); // White background
    const bufA = PNG.sync.write(imgA);

    // Identical image comparison yields 0 diff pixels
    const resIdentical = compareScreenshots(bufA, bufA);
    expect(resIdentical.diffPixels).toBe(0);
    expect(resIdentical.diffPercentage).toBe(0);

    // Generate synthetic Image B (100x100 with red 20x20 box in the center)
    const imgB = new PNG({ width: 100, height: 100 });
    imgB.data.fill(255); // White background
    // Draw 20x20 red square
    for (let y = 40; y < 60; y++) {
      for (let x = 40; x < 60; x++) {
        const idx = (100 * y + x) << 2;
        imgB.data[idx] = 255;     // R
        imgB.data[idx + 1] = 0;   // G
        imgB.data[idx + 2] = 0;   // B
        imgB.data[idx + 3] = 255; // Alpha
      }
    }
    const bufB = PNG.sync.write(imgB);

    // Compare Image A and Image B
    const resDiff = compareScreenshots(bufA, bufB);
    expect(resDiff.diffPixels).toBe(400); // 20 * 20 = 400 pixels altered
    expect(resDiff.totalPixels).toBe(10000);
    expect(resDiff.diffPercentage).toBe(4); // 400 / 10000 = 4%
    expect(resDiff.diffImageBuffer).toBeDefined();
  });
});
