import { NextResponse } from 'next/server';

// @ts-ignore - Assuming experimental_evaluate is provided by the package
import { experimental_evaluate } from 'ai';
import { typeSafeAi } from '@ai-sdk/typesafe-ai';

export async function POST(req: Request) {
  try {
    const isEnabled = process.env.JEV_ENABLED === 'true';
    if (!isEnabled) {
      return NextResponse.json({ status: 'disabled' }, { status: 200 });
    }

    const mode = process.env.JEV_MODE || 'shadow';
    const modelName = process.env.JEV_MODEL || 'typesafe-ai/jev';
    
    // Parse the candidate snapshot
    const state = await req.json();

    // Provide an AbortController for bounded request timeout (e.g. 5 seconds)
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const start = Date.now();
    let result;
    try {
      result = await experimental_evaluate({
        model: typeSafeAi.evaluationModel(modelName),
        abortSignal: controller.signal,
        state: state,
        questions: {
          marketRegime: { instructions: 'Evaluate market regime', type: 'choice', criteria: { TRENDING: null, RANGING: null, VOLATILE: null, UNCERTAIN: null } },
          signalQuality: { instructions: 'Evaluate signal quality', type: 'choice', criteria: { STRONG: null, MODERATE: null, WEAK: null, INVALID: null } },
          riskState: { instructions: 'Evaluate risk state', type: 'choice', criteria: { LOW: null, MEDIUM: null, HIGH: null, EXTREME: null } },
          engineAgreement: { instructions: 'Evaluate engine agreement', type: 'choice', criteria: { AGREEMENT: null, PARTIAL: null, CONFLICT: null, INSUFFICIENT_DATA: null } },
          anomalySuspected: { instructions: 'Is there an anomaly?', type: 'boolean' },
          requiresReview: { instructions: 'Does this require human review?', type: 'boolean' }
        }

      });
    } finally {
      clearTimeout(timeout);
    }
    
    const latencyMs = Date.now() - start;

    return NextResponse.json({
      status: 'success',
      mode,
      latencyMs,
      assessment: result,
      model: modelName
    });

  } catch (err: any) {
    // Graceful failure
    return NextResponse.json({
      status: 'error',
      message: err.message,
    }, { status: 200 });
  }
}
