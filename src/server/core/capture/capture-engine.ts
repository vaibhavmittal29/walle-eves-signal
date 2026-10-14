import { CaptureConfig } from '../config.js';
import { captureWithHttpDom, RawDomCaptureOutput } from './http-dom-engine.js';
import { captureWithPlaywright, PlaywrightCaptureOutput } from './playwright-engine.js';
import { classifyCaptureResponse, ClassificationResult } from './classifier.js';

export type UnifiedCaptureResult = RawDomCaptureOutput | PlaywrightCaptureOutput;

export interface ExecuteCaptureOutcome {
  capture?: UnifiedCaptureResult;
  classification: ClassificationResult;
  durationMs: number;
}

export async function executeCapture(
  url: string,
  config: CaptureConfig,
  screenshotDir?: string
): Promise<ExecuteCaptureOutcome> {
  const startTime = Date.now();

  try {
    let capture: UnifiedCaptureResult;

    if (config.engine === 'playwright') {
      capture = await captureWithPlaywright(url, config, screenshotDir);
    } else {
      capture = await captureWithHttpDom(url, config);
    }

    const classification = classifyCaptureResponse(capture.httpStatus, capture.sanitizedDom);

    return {
      capture,
      classification,
      durationMs: Date.now() - startTime,
    };
  } catch (err: any) {
    const classification = classifyCaptureResponse(undefined, undefined, err);
    return {
      classification,
      durationMs: Date.now() - startTime,
    };
  }
}
