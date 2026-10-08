"use client";

import { useEffect, useState } from "react";

interface Template {
  name: string;
  purpose: string;
  capabilities: string[];
  status: string;
}

export function ResearchTemplates() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    fetch("/v1/strategy-os/templates")
      .then(async (response) => {
        if (!response.ok) throw new Error("TEMPLATES_UNAVAILABLE");
        const result = (await response.json()) as Template[];
        if (active) setTemplates(result);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <section aria-label="Research agent templates">
      <h2>Research laboratory templates</h2>
      <p>Proposal only. Templates are not running jobs and hold no financial authority.</p>
      {error && <p role="alert">Research templates unavailable.</p>}
      <ul>
        {templates.map((template) => (
          <li key={template.name}>
            <strong>{template.name}</strong> · {template.status}
            <p>{template.purpose}</p>
            <p>Allowed: {template.capabilities.join(", ")}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
