"use client";

import React, { useEffect, useState } from "react";
import { Card } from "@ats/ui";

type SettingField = {
  name: string;
  type: string;
  required: boolean;
  allowed_values: any[] | null;
  min_value: number | null;
  max_value: number | null;
  secret: boolean;
  restart_required: boolean;
  governance_locked: boolean;
  description: string;
};

type SettingsSection = {
  name: string;
  fields: SettingField[];
};

type SettingsSchema = {
  version: string;
  sections: SettingsSection[];
};

type SettingsValue = {
  effective_value: any;
  source_layer: string;
  default_value: any;
  current_override: any;
  governance_state: string;
};

type SettingsPayload = {
  values: Record<string, Record<string, SettingsValue>>;
};

export default function SettingsPage() {
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [values, setValues] = useState<SettingsPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const schemaRes = await fetch("/v1/settings/schema");
        const s = await schemaRes.json();
        setSchema(s);
        const valsRes = await fetch("/v1/settings/values");
        const v = await valsRes.json();
        setValues(v);
      } catch (err) {
        console.error("Failed to load settings:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div style={{ padding: 24 }}>Loading settings...</div>;
  }

  if (!schema || !values) {
    return <div style={{ padding: 24, color: "red" }}>Failed to load settings from control plane.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>Platform Settings</h1>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#6b7280" }}>
          Dynamic Control Plane (v{schema.version}). Modifications are audited.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {schema.sections.map((section) => (
          <Card key={section.name} title={section.name}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {section.fields.map((field) => {
                const val = values.values[section.name]?.[field.name];
                return (
                  <div
                    key={field.name}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      paddingBottom: 12,
                      borderBottom: "1px solid #f3f4f6",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{field.name}</span>
                      {field.governance_locked && (
                        <span
                          style={{
                            fontSize: 11,
                            backgroundColor: "#fee2e2",
                            color: "#dc2626",
                            padding: "2px 6px",
                            borderRadius: 4,
                            fontWeight: 600,
                          }}
                        >
                          LOCKED
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: 12, color: "#6b7280" }}>{field.description}</span>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
                      {field.allowed_values ? (
                        <select
                          disabled={field.governance_locked}
                          defaultValue={val?.effective_value}
                          style={{
                            padding: "6px 12px",
                            borderRadius: 6,
                            border: "1px solid #d1d5db",
                            fontSize: 14,
                            width: 200,
                          }}
                        >
                          {field.allowed_values.map((v) => (
                            <option key={v} value={v}>
                              {String(v)}
                            </option>
                          ))}
                        </select>
                      ) : field.type === "boolean" ? (
                        <input
                          type="checkbox"
                          disabled={field.governance_locked}
                          defaultChecked={val?.effective_value}
                        />
                      ) : (
                        <input
                          type={field.type === "number" ? "number" : "text"}
                          disabled={field.governance_locked}
                          defaultValue={val?.effective_value}
                          style={{
                            padding: "6px 12px",
                            borderRadius: 6,
                            border: "1px solid #d1d5db",
                            fontSize: 14,
                            width: 200,
                          }}
                        />
                      )}
                      <span style={{ fontSize: 12, color: "#9ca3af", fontStyle: "italic" }}>
                        Source: {val?.source_layer}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
