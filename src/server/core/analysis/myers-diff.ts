import * as diff from 'diff';

export interface DiffChunk {
  type: 'added' | 'removed' | 'unchanged';
  value: string;
  count?: number;
}

export interface MyersDiffResult {
  additions: number;
  deletions: number;
  lineChanges: DiffChunk[];
  wordChanges?: DiffChunk[];
  unifiedPatch: string;
}

export function computeMyersDiff(
  previousText: string,
  currentText: string,
  options: { includeWordDiff?: boolean; label?: string } = {}
): MyersDiffResult {
  const lineParts = diff.diffLines(previousText, currentText);

  let additions = 0;
  let deletions = 0;

  const lineChanges: DiffChunk[] = lineParts.map(part => {
    const linesCount = part.value.split('\n').filter(l => l.length > 0).length;
    if (part.added) {
      additions += linesCount;
      return { type: 'added', value: part.value, count: linesCount };
    }
    if (part.removed) {
      deletions += linesCount;
      return { type: 'removed', value: part.value, count: linesCount };
    }
    return { type: 'unchanged', value: part.value, count: linesCount };
  });

  let wordChanges: DiffChunk[] | undefined;
  if (options.includeWordDiff) {
    const wordParts = diff.diffWords(previousText, currentText);
    wordChanges = wordParts.map(part => {
      if (part.added) return { type: 'added', value: part.value };
      if (part.removed) return { type: 'removed', value: part.value };
      return { type: 'unchanged', value: part.value };
    });
  }

  const patchLabel = options.label || 'content.txt';
  const unifiedPatch = diff.createPatch(patchLabel, previousText, currentText, 'Previous', 'Current');

  return {
    additions,
    deletions,
    lineChanges,
    wordChanges,
    unifiedPatch,
  };
}
