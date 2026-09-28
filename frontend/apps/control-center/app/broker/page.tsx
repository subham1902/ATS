"use client";

import React, { useEffect, useState } from "react";
import { Card } from "@ats/ui";

type BrokerCapabilities = {
  market_quotes: boolean;
  streaming: boolean;
  historical_data: boolean;
  instruments: boolean;
  market_status: boolean;
  positions_read: boolean;
  orders_read: boolean;
  sandbox_support: boolean;
};

type BrokerManifest = {
  broker_id: string;
  display_name: string;
  supported_data_modes: string[];
  auth_modes: string[];
  capabilities: BrokerCapabilities;
  status: string;
};

export default function BrokerHubPage() {
  const [manifests, setManifests] = useState<BrokerManifest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/v1/brokers/manifests");
        if (res.ok) {
          const data = await res.json();
          setManifests(data);
        }
      } catch (err) {
        console.error("Failed to load broker manifests:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleTestConnection = async (brokerId: string) => {
    try {
      const res = await fetch(`/v1/brokers/${brokerId}/test`, { method: "POST" });
      const data = await res.json();
      alert(`Test Result: ${data.message}`);
    } catch (err) {
      alert("Failed to test connection.");
    }
  };

  if (loading) return <div style={{ padding: 24 }}>Loading Broker Hub...</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>Multi-Broker Connection Hub</h1>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#6b7280" }}>
          Connect and configure broker integrations safely. Execution is restricted to Paper Broker in this mode.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: 24 }}>
        {manifests.map((broker) => (
          <Card key={broker.broker_id} title={broker.display_name}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 14, color: "#6b7280" }}>Connection State</span>
                <span style={{ 
                  fontSize: 12, fontWeight: 700, padding: "4px 8px", borderRadius: 4,
                  backgroundColor: broker.status === "CONNECTED" ? "#dcfce7" : "#fef9c3",
                  color: broker.status === "CONNECTED" ? "#15803d" : "#ca8a04"
                }}>
                  {broker.status}
                </span>
              </div>
              
              <div style={{ fontSize: 13 }}>
                <h4 style={{ margin: "0 0 8px 0", color: "#374151" }}>Capabilities</h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {Object.entries(broker.capabilities).map(([cap, enabled]) => (
                    <div key={cap} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ color: enabled ? "#16a34a" : "#ef4444" }}>{enabled ? "✓" : "✗"}</span>
                      <span style={{ color: "#6b7280" }}>{cap.replace("_", " ")}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ fontSize: 13 }}>
                <h4 style={{ margin: "0 0 8px 0", color: "#374151" }}>Supported Modes</h4>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {broker.supported_data_modes.map((mode) => (
                    <span key={mode} style={{ backgroundColor: "#f3f4f6", padding: "2px 6px", borderRadius: 4, color: "#4b5563" }}>
                      {mode}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <button 
                  onClick={() => handleTestConnection(broker.broker_id)}
                  style={{ padding: "8px 16px", backgroundColor: "#f3f4f6", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, color: "#374151" }}
                >
                  Test Connection
                </button>
                <button style={{ padding: "8px 16px", backgroundColor: "#2563eb", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, color: "white" }}>
                  Configure Auth
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
