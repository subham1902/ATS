import { describe, it, expect, vi, beforeEach } from 'vitest';
import { POST } from '../app/api/jev/route';
import { GET as HealthGET } from '../app/api/jev/health/route';
import { NextResponse } from 'next/server';

// Mock the typesafe-ai sdk
vi.mock('ai', () => ({
  experimental_evaluate: vi.fn().mockResolvedValue({
    marketRegime: 'TRENDING',
    signalQuality: 'STRONG',
    riskState: 'LOW',
    engineAgreement: 'AGREEMENT',
    anomalySuspected: false,
    requiresReview: false
  })
}));

vi.mock('@ai-sdk/typesafe-ai', () => ({
  typeSafeAi: {
    evaluationModel: vi.fn().mockReturnValue('mock-model')
  }
}));

describe('Jev API Adapter', () => {
  beforeEach(() => {
    process.env.JEV_ENABLED = 'true';
    process.env.JEV_MODE = 'shadow';
    process.env.JEV_MODEL = 'typesafe-ai/jev';
    process.env.AI_GATEWAY_API_KEY = 'test-key';
  });

  it('handles health check successfully', async () => {
    const res = await HealthGET();
    const data = await res.json();
    expect(data.enabled).toBe(true);
    expect(data.configured).toBe(true);
    expect(data.mode).toBe('shadow');
  });

  it('bypasses evaluate if JEV_ENABLED is false', async () => {
    process.env.JEV_ENABLED = 'false';
    const req = new Request('http://localhost', {
      method: 'POST',
      body: JSON.stringify({ test: 'state' })
    });
    const res = await POST(req);
    const data = await res.json();
    expect(data.status).toBe('disabled');
  });

  it('evaluates state successfully in shadow mode', async () => {
    const req = new Request('http://localhost', {
      method: 'POST',
      body: JSON.stringify({ test: 'state' })
    });
    const res = await POST(req);
    const data = await res.json();
    expect(data.status).toBe('success');
    expect(data.mode).toBe('shadow');
    expect(data.assessment).toBeDefined();
    expect(data.assessment.marketRegime).toBe('TRENDING');
  });
});
