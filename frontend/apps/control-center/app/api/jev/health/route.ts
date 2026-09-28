import { NextResponse } from 'next/server';

export async function GET() {
  const isEnabled = process.env.JEV_ENABLED === 'true';
  const mode = process.env.JEV_MODE || 'shadow';
  const modelName = process.env.JEV_MODEL || 'typesafe-ai/jev';
  const hasKey = !!process.env.AI_GATEWAY_API_KEY;

  return NextResponse.json({
    enabled: isEnabled,
    configured: hasKey,
    mode,
    model: modelName,
    gatewayReachable: hasKey, 
    lastCallStatus: "unknown"
  });
}
