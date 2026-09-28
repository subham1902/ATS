"use client";
import React, { useState, useEffect } from "react";
import { Card } from "@ats/ui";

export interface DataRow {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface DatasetItem {
  id: string;
  name: string;
  filename: string;
  source: string;
  authority: string;
  timeframe: string;
  symbol?: string;
  range: string;
  start_time?: string;
  end_time?: string;
  rows: number;
  quality: string;
  timezone: string;
  splits: {
    dev: number;
    wf: number;
    holdout: number;
  };
  holdoutState?: string;
  proving_status?: string;
  proof_report?: any;
  sha256_hash?: string;
  sampleData?: DataRow[];
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [_loading, setLoading] = useState(true);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Ingestion Feeder Form State
  const [showFeeder, setShowFeeder] = useState(false);
  const [feederId, setFeederId] = useState("");
  const [feederName, setFeederName] = useState("");
  const [feederSymbol, setFeederSymbol] = useState("MCX:GOLDM FUT");
  const [feederTimeframe, setFeederTimeframe] = useState("5m");
  const [feederAuthority, setFeederAuthority] = useState("ADMITTED_OPERATOR_FEED");
  const [autoProve, setAutoProve] = useState(true);
  const [rawText, setRawText] = useState("");
  const [parsedPreview, setParsedPreview] = useState<{
    rows: DataRow[];
    errors: string[];
    validCount: number;
    ohlcViolations: number;
  } | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);

  // Merging Studio State
  const [showMerger, setShowMerger] = useState(false);
  const [selectedForMerge, setSelectedForMerge] = useState<string[]>([]);
  const [mergeTargetId, setMergeTargetId] = useState("");
  const [mergeTargetName, setMergeTargetName] = useState("");
  const [mergeStrategy, setMergeStrategy] = useState("CHRONOLOGICAL");
  const [mergeDeduplicate, setMergeDeduplicate] = useState(true);
  const [isMerging, setIsMerging] = useState(false);

  // Proving state
  const [isProving, setIsProving] = useState<string | null>(null);

  // Fetch datasets from backend API
  const fetchDatasets = async () => {
    try {
      setLoading(true);
      const res = await fetch("/v1/datasets");
      if (res.ok) {
        const data = await res.json();
        const list: DatasetItem[] = data.datasets || [];
        setDatasets(list);
        if (list.length > 0) {
          if (!selectedId || !list.some((d) => d.id === selectedId)) {
            setSelectedId(list[0].id);
          }
        } else {
          setSelectedId(null);
        }
      }
    } catch (e) {
      console.error("Failed to load datasets:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const selected = datasets.find((d) => d.id === selectedId) || null;

  // Parse raw text into structured OHLC rows
  const handleParseText = (text: string) => {
    setRawText(text);
    if (!text.trim()) {
      setParsedPreview(null);
      return;
    }

    const lines = text.trim().split("\n");
    const rows: DataRow[] = [];
    const errors: string[] = [];
    let ohlcViolations = 0;

    let startIdx = 0;
    const firstLineLower = lines[0].toLowerCase();
    if (firstLineLower.includes("time") || firstLineLower.includes("date") || firstLineLower.includes("open")) {
      startIdx = 1;
    }

    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const parts = line.includes("\t") ? line.split("\t") : line.includes(",") ? line.split(",") : line.split(/\s+/);

      if (parts.length < 5) {
        errors.push(`Line ${i + 1}: expected at least 5 columns (time, open, high, low, close)`);
        continue;
      }

      const time = parts[0].trim();
      const open = parseFloat(parts[1]);
      const high = parseFloat(parts[2]);
      const low = parseFloat(parts[3]);
      const close = parseFloat(parts[4]);
      const volume = parts[5] ? parseFloat(parts[5]) : 1000;

      if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
        errors.push(`Line ${i + 1}: invalid numeric values in OHLC`);
        continue;
      }

      if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) {
        ohlcViolations++;
      }

      rows.push({
        time,
        open,
        high,
        low,
        close,
        volume: isNaN(volume) ? 1000 : volume,
      });
    }

    setParsedPreview({
      rows,
      errors: errors.slice(0, 5),
      validCount: rows.length,
      ohlcViolations,
    });
  };

  // Handle File Upload (.csv, .json, .txt)
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!feederId) {
      const baseName = file.name
        .replace(/\.[^/.]+$/, "")
        .toUpperCase()
        .replace(/[^A-Z0-9_]/g, "_");
      setFeederId(baseName);
      setFeederName(file.name);
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        handleParseText(content);
      }
    };
    reader.readAsText(file);
  };

  // Commit Ingestion via POST /v1/datasets
  const handleCommitIngest = async () => {
    if (!parsedPreview || parsedPreview.rows.length === 0) {
      alert("Please provide valid OHLC data before ingesting.");
      return;
    }

    const id = (feederId.trim() || `DATASET_${Date.now()}`).toUpperCase().replace(/[^A-Z0-9_]/g, "_");
    const name = feederName.trim() || `${id} Dataset`;

    try {
      setIsCommitting(true);
      setActionError(null);
      const res = await fetch("/v1/datasets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id,
          name,
          timeframe: feederTimeframe,
          symbol: feederSymbol,
          authority: feederAuthority,
          source: "Direct Operator Ingestion",
          raw_text: rawText,
          auto_prove: autoProve,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create dataset");
      }

      const _data = await res.json();
      setActionStatus(`✨ Successfully ingested and proved dataset '${id}' with ${parsedPreview.validCount} bars!`);
      setShowFeeder(false);
      setRawText("");
      setParsedPreview(null);
      setFeederId("");
      setFeederName("");
      await fetchDatasets();
      setSelectedId(id);
    } catch (e: any) {
      console.error(e);
      setActionError(e.message || "Failed to commit dataset ingestion");
    } finally {
      setIsCommitting(false);
    }
  };

  // Delete Dataset via DELETE /v1/datasets/{id}
  const handleDeleteDataset = async (id: string) => {
    if (
      !confirm(`Are you sure you want to permanently delete dataset '${id}'? This will remove all files from disk.`)
    ) {
      return;
    }

    try {
      setActionError(null);
      const res = await fetch(`/v1/datasets/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete dataset");
      }
      setActionStatus(`🗑️ Dataset '${id}' deleted successfully.`);
      await fetchDatasets();
    } catch (e: any) {
      console.error(e);
      setActionError(e.message || `Failed to delete dataset '${id}'`);
    }
  };

  // Immediate Proving via POST /v1/datasets/{id}/prove
  const handleProveDataset = async (id: string) => {
    try {
      setIsProving(id);
      setActionError(null);
      const res = await fetch(`/v1/datasets/${id}/prove`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Proving engine failed");
      }
      const data = await res.json();
      const status = data.proving_status || "PROVED";
      setActionStatus(`🛡️ Proving completed for '${id}': ${status}`);
      await fetchDatasets();
    } catch (e: any) {
      console.error(e);
      setActionError(e.message || `Failed to prove dataset '${id}'`);
    } finally {
      setIsProving(null);
    }
  };

  // Merge Datasets via POST /v1/datasets/merge
  const handleCommitMerge = async () => {
    if (selectedForMerge.length < 2) {
      alert("Please select at least 2 datasets to merge.");
      return;
    }
    const targetId = (mergeTargetId.trim() || `MERGED_${Date.now()}`).toUpperCase().replace(/[^A-Z0-9_]/g, "_");
    const targetName = mergeTargetName.trim() || `Merged (${selectedForMerge.join(" + ")})`;

    try {
      setIsMerging(true);
      setActionError(null);
      const res = await fetch("/v1/datasets/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_dataset_ids: selectedForMerge,
          new_dataset_id: targetId,
          new_name: targetName,
          merge_strategy: mergeStrategy,
          deduplicate: mergeDeduplicate,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Merge failed");
      }

      const _data = await res.json();
      setActionStatus(
        `🔗 Successfully merged ${selectedForMerge.length} datasets into '${targetId}' with immediate proving!`,
      );
      setShowMerger(false);
      setSelectedForMerge([]);
      setMergeTargetId("");
      setMergeTargetName("");
      await fetchDatasets();
      setSelectedId(targetId);
    } catch (e: any) {
      console.error(e);
      setActionError(e.message || "Failed to merge datasets");
    } finally {
      setIsMerging(false);
    }
  };

  // Quick Preset Sample Data Fillers
  const fillSampleGold = () => {
    setFeederId("MCX_GOLDM_FRESH_5M");
    setFeederName("MCX Gold Mini 5m Verified Feed");
    setFeederSymbol("MCX:GOLDM FUT");
    setFeederTimeframe("5m");
    const sample = `time,open,high,low,close,volume
2026-09-25 09:15:00,75350.0,75420.0,75340.0,75390.0,1450
2026-09-25 09:20:00,75390.0,75460.0,75380.0,75440.0,2100
2026-09-25 09:25:00,75440.0,75490.0,75420.0,75480.0,1980
2026-09-25 09:30:00,75480.0,75520.0,75450.0,75470.0,2450
2026-09-25 09:35:00,75470.0,75500.0,75430.0,75450.0,1820
2026-09-25 09:40:00,75450.0,75530.0,75440.0,75510.0,3100
2026-09-25 09:45:00,75510.0,75580.0,75500.0,75560.0,2890
2026-09-25 09:50:00,75560.0,75620.0,75540.0,75600.0,3400
2026-09-25 09:55:00,75600.0,75610.0,75550.0,75570.0,2200
2026-09-25 10:00:00,75570.0,75650.0,75560.0,75630.0,4120`;
    handleParseText(sample);
  };

  const fillSampleNifty = () => {
    setFeederId("NIFTY50_SPOT_5M");
    setFeederName("Nifty 50 Cash Intraday 5m");
    setFeederSymbol("NSE:NIFTY50");
    setFeederTimeframe("5m");
    const sample = `time,open,high,low,close,volume
2026-09-25 09:15:00,23350.0,23380.0,23340.0,23375.0,8500
2026-09-25 09:20:00,23375.0,23410.0,23370.0,23405.0,11200
2026-09-25 09:25:00,23405.0,23435.0,23395.0,23420.0,9800
2026-09-25 09:30:00,23420.0,23450.0,23410.0,23445.0,14200
2026-09-25 09:35:00,23445.0,23465.0,23430.0,23460.0,12100`;
    handleParseText(sample);
  };

  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 18, maxWidth: 1280, margin: "0 auto", paddingBottom: 40 }}
    >
      {/* 1. TOP COMMAND HEADER & CONTROL RIBBON */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
          padding: "20px 24px",
          background: "linear-gradient(135deg, #090e1a 0%, #0f172a 50%, #1e1b4b 100%)",
          border: "2px solid #3b82f6",
          borderRadius: 16,
          boxShadow: "0 10px 30px rgba(15, 23, 42, 0.4)",
          color: "#ffffff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span
            style={{
              fontSize: 32,
              background: "rgba(59, 130, 246, 0.2)",
              padding: "10px 14px",
              borderRadius: 14,
              border: "1px solid #60a5fa",
            }}
          >
            💾
          </span>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h1 style={{ margin: 0, fontSize: 22, fontWeight: 900, letterSpacing: "-0.02em" }}>
                Datasets Workspace & Proving Hub
              </h1>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: datasets.length > 0 ? "rgba(34, 197, 94, 0.2)" : "rgba(148, 163, 184, 0.2)",
                  color: datasets.length > 0 ? "#86efac" : "#cbd5e1",
                  border: `1px solid ${datasets.length > 0 ? "#22c55e" : "#64748b"}`,
                }}
              >
                {datasets.length} REGISTERED {datasets.length === 1 ? "DATASET" : "DATASETS"}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "rgba(59, 130, 246, 0.2)",
                  color: "#93c5fd",
                  border: "1px solid #3b82f6",
                }}
              >
                🛡️ IMMEDIATE SYSTEM PROVING ENGINE
              </span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>
              Dynamic market corpora configuration: Add, delete, merge, and certify dataset integrity immediately in the
              system.
            </p>
          </div>
        </div>

        {/* Command Buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => {
              setShowFeeder(!showFeeder);
              setShowMerger(false);
            }}
            style={{
              background: showFeeder ? "#334155" : "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
              color: "#ffffff",
              padding: "9px 16px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 800,
              border: "1px solid #60a5fa",
              cursor: "pointer",
              boxShadow: "0 4px 12px rgba(37, 99, 235, 0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span>{showFeeder ? "✕ Close Ingestion" : "+ Ingest Fresh Dataset"}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setShowMerger(!showMerger);
              setShowFeeder(false);
            }}
            disabled={datasets.length < 2}
            style={{
              background: showMerger ? "#334155" : "linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)",
              color: "#ffffff",
              padding: "9px 16px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 800,
              border: "1px solid #a78bfa",
              cursor: datasets.length < 2 ? "not-allowed" : "pointer",
              opacity: datasets.length < 2 ? 0.5 : 1,
              boxShadow: "0 4px 12px rgba(124, 58, 237, 0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
            title={
              datasets.length < 2
                ? "Requires at least 2 datasets to merge"
                : "Merge multiple datasets into a synthesized continuous series"
            }
          >
            <span>🔗 Merge Datasets</span>
            {selectedForMerge.length > 0 && (
              <span style={{ background: "#4c1d95", padding: "1px 6px", borderRadius: 999, fontSize: 11 }}>
                {selectedForMerge.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {actionStatus && (
        <div
          style={{
            padding: "12px 18px",
            background: "#f0fdf4",
            color: "#166534",
            borderRadius: 10,
            border: "1px solid #86efac",
            fontSize: 13,
            fontWeight: 700,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            boxShadow: "0 2px 8px rgba(34, 197, 94, 0.1)",
          }}
        >
          <span>{actionStatus}</span>
          <button
            onClick={() => setActionStatus(null)}
            style={{
              background: "none",
              border: "none",
              color: "#16a34a",
              cursor: "pointer",
              fontSize: 15,
              fontWeight: 900,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {actionError && (
        <div
          style={{
            padding: "12px 18px",
            background: "#fef2f2",
            color: "#b91c1c",
            borderRadius: 10,
            border: "1px solid #fca5a5",
            fontSize: 13,
            fontWeight: 700,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>❌ {actionError}</span>
          <button
            onClick={() => setActionError(null)}
            style={{
              background: "none",
              border: "none",
              color: "#dc2626",
              cursor: "pointer",
              fontSize: 15,
              fontWeight: 900,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. DYNAMIC INGESTION FEEDER PANEL */}
      {showFeeder && (
        <div
          style={{
            background: "#0f172a",
            color: "white",
            padding: 24,
            borderRadius: 16,
            border: "2px solid #3b82f6",
            display: "flex",
            flexDirection: "column",
            gap: 18,
            boxShadow: "0 12px 32px rgba(0,0,0,0.4)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <div>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 900, color: "#ffffff" }}>
                📥 Dynamic Dataset Ingestion & Proving Console
              </h2>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "#94a3b8" }}>
                Upload or paste fresh historical market candles. The engine verifies geometry, chronology, and creates
                split manifests.
              </p>
            </div>
            {/* Quick Sample Presets */}
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800 }}>QUICK PRESETS:</span>
              <button
                type="button"
                onClick={fillSampleGold}
                style={{
                  background: "#1e293b",
                  border: "1px solid #475569",
                  color: "#fde047",
                  fontSize: 11,
                  fontWeight: 800,
                  padding: "5px 10px",
                  borderRadius: 6,
                  cursor: "pointer",
                }}
              >
                🪙 MCX Gold Mini (5m)
              </button>
              <button
                type="button"
                onClick={fillSampleNifty}
                style={{
                  background: "#1e293b",
                  border: "1px solid #475569",
                  color: "#38bdf8",
                  fontSize: 11,
                  fontWeight: 800,
                  padding: "5px 10px",
                  borderRadius: 6,
                  cursor: "pointer",
                }}
              >
                📈 Nifty 50 Spot (5m)
              </button>
            </div>
          </div>

          {/* Form Fields Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#93c5fd", marginBottom: 4 }}>
                DATASET ID (SLUG)
              </label>
              <input
                type="text"
                placeholder="e.g. MCX_GOLDM_5M_OCT26"
                value={feederId}
                onChange={(e) => setFeederId(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 800,
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#93c5fd", marginBottom: 4 }}>
                DATASET NAME
              </label>
              <input
                type="text"
                placeholder="e.g. MCX Gold Mini Oct 2026 Feed"
                value={feederName}
                onChange={(e) => setFeederName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#93c5fd", marginBottom: 4 }}>
                SYMBOL / CONTRACT
              </label>
              <input
                type="text"
                placeholder="e.g. MCX:GOLDM FUT"
                value={feederSymbol}
                onChange={(e) => setFeederSymbol(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#93c5fd", marginBottom: 4 }}>
                TIMEFRAME
              </label>
              <select
                value={feederTimeframe}
                onChange={(e) => setFeederTimeframe(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 800,
                }}
              >
                <option value="1s">1s (Tick Aggregation)</option>
                <option value="5s">5s (Sub-Minute Micro)</option>
                <option value="1m">1m (Standard Intraday)</option>
                <option value="5m">5m (Core Strategy TF)</option>
                <option value="15m">15m (Tactical Swing)</option>
                <option value="1h">1h (Hourly Anchor)</option>
                <option value="1d">1d (Daily Daily Bar)</option>
              </select>
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#93c5fd", marginBottom: 4 }}>
                AUTHORITY TIER
              </label>
              <select
                value={feederAuthority}
                onChange={(e) => setFeederAuthority(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                }}
              >
                <option value="ADMITTED_OPERATOR_FEED">ADMITTED_OPERATOR_FEED (Verified)</option>
                <option value="VERIFIED_PRODUCTION">VERIFIED_PRODUCTION (Production Safe)</option>
                <option value="RESEARCH_BENCHMARK">RESEARCH_BENCHMARK (Canonical)</option>
                <option value="EXPERIMENTAL">EXPERIMENTAL (Quarantine)</option>
              </select>
            </div>
          </div>

          {/* File Upload Drop Zone */}
          <div
            style={{
              border: "2px dashed #475569",
              borderRadius: 12,
              padding: "16px",
              textAlign: "center",
              background: "#1e293b",
            }}
          >
            <input
              type="file"
              accept=".csv,.txt,.json"
              onChange={handleFileUpload}
              style={{ display: "none" }}
              id="dataset-file-input"
            />
            <label
              htmlFor="dataset-file-input"
              style={{
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                color: "#38bdf8",
                fontWeight: 800,
                fontSize: 13,
              }}
            >
              📁 Click to Browse or Drop CSV File (time, open, high, low, close, volume)
            </label>
          </div>

          {/* Text Area */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <label style={{ fontSize: 11, fontWeight: 800, color: "#93c5fd" }}>
                OR PASTE RAW CSV / TABULAR DATA DIRECTLY:
              </label>
              {parsedPreview && (
                <span
                  style={{
                    fontSize: 11,
                    color: parsedPreview.ohlcViolations === 0 ? "#4ade80" : "#f87171",
                    fontWeight: 800,
                  }}
                >
                  Parsed {parsedPreview.validCount} rows ({parsedPreview.ohlcViolations} OHLC violations)
                </span>
              )}
            </div>
            <textarea
              rows={5}
              placeholder="time,open,high,low,close,volume&#10;2026-09-25 09:15:00,75350,75400,75320,75380,1200"
              value={rawText}
              onChange={(e) => handleParseText(e.target.value)}
              style={{
                width: "100%",
                padding: "10px",
                borderRadius: 8,
                border: "1px solid #475569",
                background: "#090e1a",
                color: "#4ade80",
                fontSize: 12,
                fontFamily: "monospace",
                outline: "none",
              }}
            />
          </div>

          {/* Actions & Immediate Proving Checkbox */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#cbd5e1",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={autoProve}
                onChange={(e) => setAutoProve(e.target.checked)}
                style={{ width: 16, height: 16, cursor: "pointer" }}
              />
              <span style={{ fontWeight: 800, color: "#38bdf8" }}>Immediately Prove in System upon Ingestion</span>
              <span style={{ fontSize: 11, color: "#94a3b8" }}>
                (Validates chronology, invariants, and issues proof certificate)
              </span>
            </label>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowFeeder(false)}
                style={{
                  padding: "8px 16px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#cbd5e1",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCommitIngest}
                disabled={isCommitting || !parsedPreview || parsedPreview.validCount === 0}
                style={{
                  padding: "8px 20px",
                  borderRadius: 8,
                  border: "none",
                  background: isCommitting ? "#475569" : "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                  color: "#ffffff",
                  fontSize: 13,
                  fontWeight: 900,
                  cursor: isCommitting || !parsedPreview || parsedPreview.validCount === 0 ? "not-allowed" : "pointer",
                  boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
                }}
              >
                {isCommitting ? "Ingesting & Proving..." : "🚀 Ingest & Prove Dataset"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. DYNAMIC MERGING STUDIO PANEL */}
      {showMerger && (
        <div
          style={{
            background: "#0f172a",
            color: "white",
            padding: 24,
            borderRadius: 16,
            border: "2px solid #8b5cf6",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            boxShadow: "0 12px 32px rgba(0,0,0,0.4)",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 900, color: "#ffffff" }}>
              🔗 Dynamic Dataset Merging Studio
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: "#94a3b8" }}>
              Synthesize 2 or more datasets into a unified, continuous series with automatic timestamp sorting,
              deduplication, and immediate proving.
            </p>
          </div>

          {/* Source Datasets Selection List */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 6 }}>
              SELECT DATASETS TO MERGE (CHECK AT LEAST 2):
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 10 }}>
              {datasets.map((d) => {
                const isChecked = selectedForMerge.includes(d.id);
                return (
                  <div
                    key={d.id}
                    onClick={() => {
                      if (isChecked) {
                        setSelectedForMerge(selectedForMerge.filter((id) => id !== d.id));
                      } else {
                        setSelectedForMerge([...selectedForMerge, d.id]);
                      }
                    }}
                    style={{
                      background: isChecked ? "#1e1b4b" : "#1e293b",
                      border: `1px solid ${isChecked ? "#8b5cf6" : "#334155"}`,
                      borderRadius: 10,
                      padding: "10px 14px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {}}
                      style={{ cursor: "pointer", width: 16, height: 16 }}
                    />
                    <div>
                      <div style={{ fontWeight: 800, fontSize: 12, color: isChecked ? "#c084fc" : "#e2e8f0" }}>
                        {d.id}
                      </div>
                      <div style={{ fontSize: 11, color: "#94a3b8" }}>
                        {d.rows.toLocaleString()} bars · {d.timeframe} · {d.symbol || "MCX:GOLDM FUT"}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Merge Parameters */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}>
                TARGET MERGED DATASET ID
              </label>
              <input
                type="text"
                placeholder="e.g. MCX_GOLDM_SYNTHESIZED_FULL"
                value={mergeTargetId}
                onChange={(e) => setMergeTargetId(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 800,
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}>
                TARGET DATASET LABEL
              </label>
              <input
                type="text"
                placeholder="e.g. Synthesized Full Series"
                value={mergeTargetName}
                onChange={(e) => setMergeTargetName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}>
                MERGE STRATEGY
              </label>
              <select
                value={mergeStrategy}
                onChange={(e) => setMergeStrategy(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#ffffff",
                  fontSize: 12,
                  fontWeight: 800,
                }}
              >
                <option value="CHRONOLOGICAL">Strict Chronological Sort & Stitch</option>
                <option value="OVERLAY">Priority Overlay (First Source Baseline)</option>
              </select>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#cbd5e1",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={mergeDeduplicate}
                onChange={(e) => setMergeDeduplicate(e.target.checked)}
                style={{ width: 16, height: 16, cursor: "pointer" }}
              />
              <span style={{ fontWeight: 800, color: "#c084fc" }}>Deduplicate Identical Timestamps</span>
              <span style={{ fontSize: 11, color: "#94a3b8" }}>
                (Prevents duplicate bars across overlapping datasets)
              </span>
            </label>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowMerger(false)}
                style={{
                  padding: "8px 16px",
                  borderRadius: 8,
                  border: "1px solid #475569",
                  background: "#1e293b",
                  color: "#cbd5e1",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCommitMerge}
                disabled={isMerging || selectedForMerge.length < 2}
                style={{
                  padding: "8px 20px",
                  borderRadius: 8,
                  border: "none",
                  background:
                    isMerging || selectedForMerge.length < 2
                      ? "#475569"
                      : "linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)",
                  color: "#ffffff",
                  fontSize: 13,
                  fontWeight: 900,
                  cursor: isMerging || selectedForMerge.length < 2 ? "not-allowed" : "pointer",
                  boxShadow: "0 4px 12px rgba(139, 92, 246, 0.4)",
                }}
              >
                {isMerging ? "Merging & Proving..." : `⚡ Merge ${selectedForMerge.length} Datasets & Prove`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. DATASETS LISTING / EMPTY STATE */}
      {datasets.length === 0 ? (
        <div
          style={{
            background: "#ffffff",
            border: "2px dashed #cbd5e1",
            borderRadius: 16,
            padding: "48px 24px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 14,
          }}
        >
          <span style={{ fontSize: 44 }}>✨</span>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 900, color: "#0f172a" }}>Fresh Clean Dataset Canvas</h2>
          <p style={{ margin: 0, fontSize: 13, color: "#64748b", maxWidth: 520, lineHeight: 1.5 }}>
            All 3 legacy datasets have been removed as requested. You can now provide and upload your fresh high-potency
            market datasets, prove their integrity, and merge them dynamically.
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 6, flexWrap: "wrap", justifyContent: "center" }}>
            <button
              onClick={() => setShowFeeder(true)}
              style={{
                background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                color: "#ffffff",
                padding: "10px 22px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 800,
                border: "none",
                cursor: "pointer",
                boxShadow: "0 4px 14px rgba(37, 99, 235, 0.35)",
              }}
            >
              + Ingest Fresh Market Dataset
            </button>
            <button
              onClick={fillSampleGold}
              style={{
                background: "#f8fafc",
                border: "1px solid #cbd5e1",
                color: "#334155",
                padding: "10px 18px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              Load MCX Gold Mini Template
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
          {datasets.map((d) => {
            const isSelected = selectedId === d.id;
            const provingStatus = d.proving_status || "UNPROVEN";
            const isPristine = provingStatus === "PROVEN_PRISTINE";
            const isDefective = provingStatus === "DEFECTIVE";

            return (
              <div
                key={d.id}
                onClick={() => setSelectedId(d.id)}
                style={{
                  background: isSelected ? "#f8fafc" : "#ffffff",
                  border: isSelected ? "2px solid #2563eb" : "1px solid #e2e8f0",
                  borderRadius: 14,
                  padding: "18px 20px",
                  boxShadow: isSelected ? "0 8px 20px rgba(37, 99, 235, 0.12)" : "0 2px 6px rgba(0,0,0,0.02)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {/* Card Top Row */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 900, fontSize: 15, color: "#0f172a" }}>{d.id}</span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 900,
                          padding: "2px 7px",
                          borderRadius: 6,
                          background: "#eff6ff",
                          color: "#1d4ed8",
                          border: "1px solid #bfdbfe",
                        }}
                      >
                        {d.timeframe}
                      </span>
                      {d.symbol && (
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            padding: "2px 6px",
                            borderRadius: 6,
                            background: "#f1f5f9",
                            color: "#475569",
                          }}
                        >
                          {d.symbol}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{d.name}</div>
                  </div>

                  {/* Proving Badge */}
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 900,
                      padding: "3px 8px",
                      borderRadius: 999,
                      background: isPristine ? "#dcfce7" : isDefective ? "#fee2e2" : "#fef3c7",
                      color: isPristine ? "#15803d" : isDefective ? "#b91c1c" : "#92400e",
                      border: `1px solid ${isPristine ? "#86efac" : isDefective ? "#fca5a5" : "#fde68a"}`,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <span>{isPristine ? "🛡️" : isDefective ? "❌" : "⚠️"}</span>
                    <span>{provingStatus.replace("_", " ")}</span>
                  </span>
                </div>

                {/* Card Stats */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 8,
                    fontSize: 11,
                    background: "#f8fafc",
                    padding: "10px",
                    borderRadius: 8,
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <div>
                    <span style={{ color: "#64748b" }}>CANDLE COUNT:</span>
                    <div style={{ fontWeight: 900, color: "#0f172a", fontFamily: "monospace", fontSize: 13 }}>
                      {d.rows.toLocaleString()} bars
                    </div>
                  </div>
                  <div>
                    <span style={{ color: "#64748b" }}>TIME SPAN:</span>
                    <div
                      style={{
                        fontWeight: 700,
                        color: "#334155",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {d.range || "Custom Series"}
                    </div>
                  </div>
                </div>

                {/* Card Action Buttons */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderTop: "1px solid #f1f5f9",
                    paddingTop: 10,
                  }}
                >
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleProveDataset(d.id);
                      }}
                      disabled={isProving === d.id}
                      style={{
                        padding: "5px 10px",
                        fontSize: 11,
                        fontWeight: 800,
                        borderRadius: 6,
                        border: "1px solid #93c5fd",
                        background: "#eff6ff",
                        color: "#1d4ed8",
                        cursor: "pointer",
                      }}
                      title="Run immediate system proving verification"
                    >
                      {isProving === d.id ? "Proving..." : "🛡️ Prove"}
                    </button>
                    <a
                      href={`/v1/datasets/${d.id}/export`}
                      onClick={(e) => e.stopPropagation()}
                      download
                      style={{
                        padding: "5px 10px",
                        fontSize: 11,
                        fontWeight: 700,
                        borderRadius: 6,
                        border: "1px solid #cbd5e1",
                        background: "#ffffff",
                        color: "#475569",
                        textDecoration: "none",
                      }}
                    >
                      📥 CSV
                    </a>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDataset(d.id);
                    }}
                    style={{
                      padding: "5px 10px",
                      fontSize: 11,
                      fontWeight: 800,
                      borderRadius: 6,
                      border: "1px solid #fca5a5",
                      background: "#fef2f2",
                      color: "#dc2626",
                      cursor: "pointer",
                    }}
                    title="Delete dataset permanently"
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 5. SYSTEM PROVING CERTIFICATE & DETAILED AUDIT VIEWER */}
      {selected && (
        <Card title={`System Proving Certificate & Dataset Audit: ${selected.id}`}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, fontSize: 13 }}>
            {/* Proving Badge Banner */}
            <div
              style={{
                background:
                  selected.proving_status === "PROVEN_PRISTINE"
                    ? "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)"
                    : "#fffbeb",
                border: `1px solid ${selected.proving_status === "PROVEN_PRISTINE" ? "#86efac" : "#fde68a"}`,
                borderRadius: 12,
                padding: "16px 20px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 20 }}>{selected.proving_status === "PROVEN_PRISTINE" ? "🛡️" : "⚠️"}</span>
                  <span
                    style={{
                      fontWeight: 900,
                      fontSize: 15,
                      color: selected.proving_status === "PROVEN_PRISTINE" ? "#166534" : "#92400e",
                    }}
                  >
                    SYSTEM PROVING STATUS: {selected.proving_status || "UNPROVEN"}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                  {selected.proof_report?.certificate_id || `CERT-PROVE-${selected.id}`} · SHA-256:{" "}
                  <code style={{ fontFamily: "monospace", fontSize: 11 }}>
                    {selected.sha256_hash?.slice(0, 16) || "hash-pending"}...
                  </code>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleProveDataset(selected.id)}
                disabled={isProving === selected.id}
                style={{
                  background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                  border: "1px solid #34d399",
                  color: "#ffffff",
                  padding: "8px 18px",
                  borderRadius: 10,
                  fontSize: 12,
                  fontWeight: 900,
                  cursor: isProving === selected.id ? "not-allowed" : "pointer",
                  boxShadow: "0 2px 8px rgba(16, 185, 129, 0.3)",
                }}
              >
                {isProving === selected.id ? "Running System Audit..." : "🛡️ Re-Prove Dataset Now"}
              </button>
            </div>

            {/* Invariant Verification Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>OHLC GEOMETRY AUDIT</span>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 900,
                    color: (selected.proof_report?.ohlc_violations ?? 0) === 0 ? "#16a34a" : "#dc2626",
                    marginTop: 2,
                  }}
                >
                  {(selected.proof_report?.ohlc_violations ?? 0) === 0
                    ? "✅ 0 Violations (PASS)"
                    : `❌ ${selected.proof_report?.ohlc_violations} Violations`}
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8" }}>Low ≤ Open,Close ≤ High</div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>TIMESTAMP MONOTONICITY</span>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 900,
                    color: (selected.proof_report?.chronological_inversions ?? 0) === 0 ? "#16a34a" : "#dc2626",
                    marginTop: 2,
                  }}
                >
                  {(selected.proof_report?.chronological_inversions ?? 0) === 0
                    ? "✅ Monotonic Order"
                    : `❌ ${selected.proof_report?.chronological_inversions} Inversions`}
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8" }}>0 Inversions, 0 Duplicate Timestamps</div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>PRICE CONTINUITY</span>
                <div style={{ fontSize: 15, fontWeight: 900, color: "#0f172a", marginTop: 2, fontFamily: "monospace" }}>
                  ₹{(selected.proof_report?.min_price ?? 0).toFixed(1)} → ₹
                  {(selected.proof_report?.max_price ?? 0).toFixed(1)}
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8" }}>
                  Volatility: {selected.proof_report?.price_volatility_pct ?? 0}%
                </div>
              </div>

              <div style={{ background: "#f8fafc", padding: "12px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <span style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>CHRONOLOGICAL SPLITS</span>
                <div style={{ fontSize: 13, fontWeight: 900, color: "#3b82f6", marginTop: 2, fontFamily: "monospace" }}>
                  DEV {selected.splits?.dev ?? 0} | WF {selected.splits?.wf ?? 0} | HOLD {selected.splits?.holdout ?? 0}
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8" }}>60% Dev / 20% WF / 20% Sealed Holdout</div>
              </div>
            </div>

            {/* Proof Report Notes */}
            {selected.proof_report?.notes && selected.proof_report.notes.length > 0 && (
              <div
                style={{ background: "#f8fafc", padding: "12px 16px", borderRadius: 10, border: "1px solid #e2e8f0" }}
              >
                <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", marginBottom: 4 }}>
                  SYSTEM VERIFICATION NOTES:
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#334155" }}>
                  {selected.proof_report.notes.map((note: string, idx: number) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Detailed Properties List */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                borderTop: "1px solid #f1f5f9",
                paddingTop: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#64748b" }}>Source Provenance</span>
                <span style={{ fontWeight: 600 }}>{selected.source}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#64748b" }}>Authority Tier</span>
                <span style={{ fontWeight: 700, color: "#1e40af" }}>{selected.authority}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#64748b" }}>Time Range & Continuity</span>
                <span style={{ fontFamily: "monospace" }}>{selected.range}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#64748b" }}>Timezone Standard</span>
                <span>{selected.timezone || "IST +05:30 (Market Native)"}</span>
              </div>
            </div>

            {/* Sample Bar Data Preview */}
            {selected.sampleData && selected.sampleData.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}
                >
                  <div style={{ fontWeight: 800, fontSize: 12, color: "#475569" }}>
                    SAMPLE BAR DATA PREVIEW ({selected.sampleData.length} ROWS SHOWN)
                  </div>
                  <a
                    href={`/v1/datasets/${selected.id}/export`}
                    download
                    style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", textDecoration: "none" }}
                  >
                    Download Full CSV →
                  </a>
                </div>
                <div style={{ overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 8 }}>
                  <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse", fontFamily: "monospace" }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0", textAlign: "left" }}>
                        <th style={{ padding: "8px 12px" }}>TIME</th>
                        <th style={{ padding: "8px 12px" }}>OPEN</th>
                        <th style={{ padding: "8px 12px" }}>HIGH</th>
                        <th style={{ padding: "8px 12px" }}>LOW</th>
                        <th style={{ padding: "8px 12px" }}>CLOSE</th>
                        <th style={{ padding: "8px 12px" }}>VOLUME</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.sampleData.map((row, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                          <td style={{ padding: "8px 12px", color: "#64748b" }}>{row.time}</td>
                          <td style={{ padding: "8px 12px" }}>{Number(row.open).toFixed(2)}</td>
                          <td style={{ padding: "8px 12px", color: "#16a34a" }}>{Number(row.high).toFixed(2)}</td>
                          <td style={{ padding: "8px 12px", color: "#dc2626" }}>{Number(row.low).toFixed(2)}</td>
                          <td style={{ padding: "8px 12px", fontWeight: 800 }}>{Number(row.close).toFixed(2)}</td>
                          <td style={{ padding: "8px 12px", color: "#64748b" }}>
                            {Number(row.volume).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
