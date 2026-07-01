import { useState, useRef, useEffect } from "react";

const USE_CASES = [
  { id: "gaming-1080p", label: "Gaming 1080p", icon: "🎮" },
  { id: "gaming-1440p", label: "Gaming 1440p", icon: "🖥️" },
  { id: "content-creation", label: "Content Creation", icon: "🎬" },
  { id: "workstation", label: "Workstation / 3D", icon: "⚙️" },
  { id: "streaming", label: "Gaming + Streaming", icon: "📡" },
  { id: "office", label: "Office / Daily Use", icon: "💼" },
];

const PRIORITY_OPTIONS = [
  { id: "performance", label: "Max Performance" },
  { id: "value", label: "Best Value" },
  { id: "future-proof", label: "Future-Proof" },
  { id: "quiet", label: "Quiet & Cool" },
];

const categoryColors = {
  CPU: "#e8435a",
  GPU: "#7c4dff",
  Motherboard: "#00b4d8",
  RAM: "#06d6a0",
  Storage: "#f4a261",
  PSU: "#ffd166",
  Case: "#a8dadc",
  Cooler: "#74b3ce",
};

function PartCard({ part, index }) {
  const [expanded, setExpanded] = useState(false);
  const color = categoryColors[part.category] || "#888";

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.04)",
        border: `1px solid rgba(255,255,255,0.08)`,
        borderLeft: `3px solid ${color}`,
        borderRadius: "10px",
        padding: "14px 16px",
        marginBottom: "10px",
        cursor: "pointer",
        transition: "background 0.2s",
        animationDelay: `${index * 0.07}s`,
        animation: "slideIn 0.4s ease both",
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              fontSize: "10px",
              fontWeight: 700,
              letterSpacing: "0.1em",
              color: color,
              background: `${color}22`,
              padding: "3px 8px",
              borderRadius: "4px",
              textTransform: "uppercase",
              minWidth: "90px",
              textAlign: "center",
            }}
          >
            {part.category}
          </span>
          <span style={{ color: "#f0f0f0", fontSize: "14px", fontFamily: "'DM Mono', monospace" }}>
            {part.name}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "15px", fontFamily: "'DM Mono', monospace" }}>
            {part.price_egp.toLocaleString()} EGP
          </span>
          <span style={{ color: "#666", fontSize: "12px" }}>{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && (
        <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
          {part.store && (
            <p style={{ color: "#06d6a0", fontSize: "12px", marginBottom: "4px", fontWeight: "bold" }}>
              Store: {part.store}
            </p>
          )}
          <p style={{ color: "#aaa", fontSize: "13px", marginBottom: "8px", lineHeight: 1.6 }}>{part.notes}</p>
          <a
            href={`https://egprices.com/en/search/?q=${encodeURIComponent(part.egprices_search || part.name)}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              fontSize: "12px",
              color: "#4fc3f7",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              background: "rgba(79,195,247,0.1)",
              padding: "4px 10px",
              borderRadius: "5px",
              border: "1px solid rgba(79,195,247,0.2)",
              transition: "background 0.2s",
            }}
          >
            🔍 Find on EGPrices.com
          </a>
        </div>
      )}
    </div>
  );
}

function FeasibilityBadge({ feasibility, note }) {
  const config = {
    feasible: { color: "#06d6a0", bg: "#06d6a022", icon: "✓", label: "Feasible" },
    tight: { color: "#ffd166", bg: "#ffd16622", icon: "⚠", label: "Tight Budget" },
    infeasible: { color: "#e8435a", bg: "#e8435a22", icon: "✗", label: "Infeasible" },
  }[feasibility] || { color: "#aaa", bg: "#aaa22", icon: "?", label: "Unknown" };

  return (
    <div style={{
      background: config.bg,
      border: `1px solid ${config.color}44`,
      borderRadius: "10px",
      padding: "12px 16px",
      display: "flex",
      gap: "10px",
      alignItems: "flex-start",
      marginBottom: "20px",
    }}>
      <span style={{ color: config.color, fontSize: "18px", fontWeight: 700 }}>{config.icon}</span>
      <div>
        <span style={{ color: config.color, fontWeight: 700, fontSize: "13px", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {config.label}
        </span>
        <p style={{ color: "#bbb", fontSize: "13px", margin: "4px 0 0", lineHeight: 1.5 }}>{note}</p>
      </div>
    </div>
  );
}

export default function PCBuilder() {
  const [budget, setBudget] = useState("");
  const [useCase, setUseCase] = useState("");
  const [priority, setPriority] = useState("value");
  const [extras, setExtras] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("parts");
  const resultRef = useRef(null);

  // You can change this if your FastAPI server runs on a different port/host
  const API_URL = "http://localhost:8000/build";

  useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  const handleBuild = async () => {
    if (!budget || !useCase) return;
    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          budget: parseInt(budget, 10),
          use_case: useCase,
          priority: priority,
          notes: extras || "",
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData?.detail || `HTTP ${response.status} - Server Error`);
      }

      const parsed = await response.json();
      setResult(parsed);
    } catch (err) {
      setError(`Error: ${err.message || "Failed to generate build. Is the backend running?"}`);
    } finally {
      setLoading(false);
    }
  };

  const totalBudget = parseInt(budget) || 0;
  const overBudget = result && result.total_estimated > totalBudget;

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0d0f14",
      color: "#e8e8e8",
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
      padding: "0",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&family=Bebas+Neue&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 4px; } 
        ::-webkit-scrollbar-track { background: #111; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
        input, textarea { outline: none; }
        .chip:hover { background: rgba(255,255,255,0.12) !important; }
        .chip.active { background: rgba(229,57,53,0.2) !important; border-color: #e53935 !important; color: #ff6b6b !important; }
        .build-btn:hover:not(:disabled) { background: #c0392b !important; transform: translateY(-1px); }
        .build-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .tab { cursor: pointer; transition: all 0.2s; }
        .tab.active { color: #fff !important; border-bottom: 2px solid #e53935 !important; }
        .tab:hover { color: #ddd !important; }
      `}</style>

      {/* Header */}
      <div style={{
        background: "linear-gradient(180deg, #1a0a0a 0%, #0d0f14 100%)",
        borderBottom: "1px solid #1e1e1e",
        padding: "32px 24px 24px",
        textAlign: "center",
      }}>
        <div style={{ fontSize: "11px", letterSpacing: "0.3em", color: "#e53935", textTransform: "uppercase", marginBottom: "10px", fontFamily: "'DM Mono', monospace" }}>
          Egyptian Market · Powered by Live Market Data & AI
        </div>
        <h1 style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: "clamp(42px, 8vw, 72px)",
          letterSpacing: "0.05em",
          color: "#fff",
          lineHeight: 1,
          marginBottom: "8px",
        }}>
          EG PC BUILDER
        </h1>
        <p style={{ color: "#666", fontSize: "14px", maxWidth: "480px", margin: "0 auto" }}>
          AI-powered builds based on real-time prices · Compare results on EGPrices.com
        </p>
      </div>

      {/* Form */}
      <div style={{ maxWidth: "680px", margin: "0 auto", padding: "32px 20px" }}>
        
        {/* Budget */}
        <div style={{ marginBottom: "28px" }}>
          <label style={{ display: "block", fontSize: "11px", letterSpacing: "0.15em", color: "#888", textTransform: "uppercase", marginBottom: "10px", fontFamily: "'DM Mono', monospace" }}>
            Budget (EGP)
          </label>
          <div style={{ position: "relative" }}>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="e.g. 30000"
              style={{
                width: "100%",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "10px",
                padding: "14px 16px 14px 48px",
                color: "#fff",
                fontSize: "22px",
                fontFamily: "'DM Mono', monospace",
                fontWeight: 500,
              }}
            />
            <span style={{ position: "absolute", left: "16px", top: "50%", transform: "translateY(-50%)", color: "#555", fontSize: "14px", fontFamily: "'DM Mono', monospace" }}>
              EGP
            </span>
          </div>
          <div style={{ display: "flex", gap: "8px", marginTop: "8px", flexWrap: "wrap" }}>
            {[15000, 25000, 40000, 60000, 90000].map((b) => (
              <button
                key={b}
                onClick={() => setBudget(String(b))}
                className="chip"
                style={{
                  background: budget === String(b) ? "rgba(229,57,53,0.2)" : "rgba(255,255,255,0.06)",
                  border: `1px solid ${budget === String(b) ? "#e53935" : "rgba(255,255,255,0.1)"}`,
                  color: budget === String(b) ? "#ff6b6b" : "#888",
                  borderRadius: "6px",
                  padding: "5px 12px",
                  fontSize: "12px",
                  fontFamily: "'DM Mono', monospace",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                {b.toLocaleString()}
              </button>
            ))}
          </div>
        </div>

        {/* Use Case */}
        <div style={{ marginBottom: "28px" }}>
          <label style={{ display: "block", fontSize: "11px", letterSpacing: "0.15em", color: "#888", textTransform: "uppercase", marginBottom: "10px", fontFamily: "'DM Mono', monospace" }}>
            Primary Use Case
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
            {USE_CASES.map((uc) => (
              <button
                key={uc.id}
                onClick={() => setUseCase(uc.id)}
                style={{
                  background: useCase === uc.id ? "rgba(229,57,53,0.15)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${useCase === uc.id ? "#e53935" : "rgba(255,255,255,0.08)"}`,
                  borderRadius: "10px",
                  padding: "14px 10px",
                  cursor: "pointer",
                  color: useCase === uc.id ? "#ff9999" : "#aaa",
                  fontSize: "13px",
                  textAlign: "center",
                  transition: "all 0.2s",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <span style={{ fontSize: "22px" }}>{uc.icon}</span>
                {uc.label}
              </button>
            ))}
          </div>
        </div>

        {/* Priority */}
        <div style={{ marginBottom: "28px" }}>
          <label style={{ display: "block", fontSize: "11px", letterSpacing: "0.15em", color: "#888", textTransform: "uppercase", marginBottom: "10px", fontFamily: "'DM Mono', monospace" }}>
            Build Priority
          </label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {PRIORITY_OPTIONS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPriority(p.id)}
                className="chip"
                style={{
                  background: priority === p.id ? "rgba(229,57,53,0.2)" : "rgba(255,255,255,0.06)",
                  border: `1px solid ${priority === p.id ? "#e53935" : "rgba(255,255,255,0.1)"}`,
                  color: priority === p.id ? "#ff6b6b" : "#888",
                  borderRadius: "8px",
                  padding: "8px 16px",
                  fontSize: "13px",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Extras */}
        <div style={{ marginBottom: "28px" }}>
          <label style={{ display: "block", fontSize: "11px", letterSpacing: "0.15em", color: "#888", textTransform: "uppercase", marginBottom: "10px", fontFamily: "'DM Mono', monospace" }}>
            Additional Notes <span style={{ opacity: 0.5, textTransform: "none", letterSpacing: 0 }}>(optional)</span>
          </label>
          <textarea
            value={extras}
            onChange={(e) => setExtras(e.target.value)}
            placeholder="e.g. Prefer AMD, need WiFi included, already have a case, want RGB..."
            rows={3}
            style={{
              width: "100%",
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "10px",
              padding: "14px 16px",
              color: "#ccc",
              fontSize: "14px",
              resize: "vertical",
              lineHeight: 1.6,
            }}
          />
        </div>

        {/* Build Button */}
        <button
          onClick={handleBuild}
          disabled={!budget || !useCase || loading}
          className="build-btn"
          style={{
            width: "100%",
            background: "#e53935",
            color: "#fff",
            border: "none",
            borderRadius: "12px",
            padding: "16px",
            fontSize: "16px",
            fontWeight: 700,
            letterSpacing: "0.05em",
            cursor: "pointer",
            transition: "all 0.2s",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "10px",
          }}
        >
          {loading ? (
            <>
              <div style={{ width: "18px", height: "18px", border: "2px solid rgba(255,255,255,0.3)", borderTop: "2px solid #fff", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
              Generating Build...
            </>
          ) : (
            <>⚡ Generate My Build</>
          )}
        </button>

        {error && (
          <div style={{ marginTop: "16px", background: "rgba(232,67,90,0.1)", border: "1px solid #e8435a44", borderRadius: "10px", padding: "12px 16px", color: "#e8435a", fontSize: "14px" }}>
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div ref={resultRef} style={{ marginTop: "40px", animation: "slideIn 0.5s ease both" }}>
            {/* Summary */}
            <div style={{
              background: "linear-gradient(135deg, rgba(229,57,53,0.1), rgba(124,77,255,0.1))",
              border: "1px solid rgba(229,57,53,0.2)",
              borderRadius: "14px",
              padding: "20px",
              marginBottom: "20px",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", flexWrap: "wrap", marginBottom: "12px" }}>
                <div>
                  <div style={{ fontSize: "11px", letterSpacing: "0.2em", color: "#888", textTransform: "uppercase", fontFamily: "'DM Mono', monospace", marginBottom: "6px" }}>
                    Recommended Build
                  </div>
                  <p style={{ color: "#e8e8e8", fontSize: "15px", lineHeight: 1.6, maxWidth: "420px" }}>{result.summary}</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "36px", color: overBudget ? "#ffd166" : "#06d6a0", lineHeight: 1 }}>
                    {result.total_estimated?.toLocaleString()}
                  </div>
                  <div style={{ fontSize: "12px", color: "#666", fontFamily: "'DM Mono', monospace" }}>EGP TOTAL</div>
                  {overBudget && <div style={{ fontSize: "11px", color: "#ffd166", marginTop: "2px" }}>+{(result.total_estimated - totalBudget).toLocaleString()} over budget</div>}
                </div>
              </div>
              <FeasibilityBadge feasibility={result.feasibility} note={result.feasibility_note} />
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: "0", borderBottom: "1px solid rgba(255,255,255,0.08)", marginBottom: "20px" }}>
              {["parts", "alternatives", "tips"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`tab ${activeTab === tab ? "active" : ""}`}
                  style={{
                    background: "none",
                    border: "none",
                    borderBottom: "2px solid transparent",
                    padding: "10px 20px",
                    fontSize: "13px",
                    letterSpacing: "0.08em",
                    textTransform: "capitalize",
                    color: activeTab === tab ? "#fff" : "#666",
                    cursor: "pointer",
                    fontFamily: "'DM Mono', monospace",
                  }}
                >
                  {tab === "parts" ? `Parts (${result.parts?.length || 0})` : tab === "alternatives" ? `Alternatives` : "Tips & Upgrades"}
                </button>
              ))}
            </div>

            {activeTab === "parts" && (
              <div>
                {result.parts?.map((part, i) => <PartCard key={i} part={part} index={i} />)}
              </div>
            )}

            {activeTab === "alternatives" && (
              <div>
                {result.alternatives?.map((alt, i) => (
                  <div key={i} style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    borderRadius: "10px",
                    padding: "14px 16px",
                    marginBottom: "10px",
                    animation: "slideIn 0.4s ease both",
                    animationDelay: `${i * 0.08}s`,
                  }}>
                    <div style={{ fontSize: "11px", color: "#888", textTransform: "uppercase", letterSpacing: "0.1em", fontFamily: "'DM Mono', monospace", marginBottom: "6px" }}>{alt.part}</div>
                    <div style={{ color: "#e0e0e0", fontSize: "14px", marginBottom: "6px", fontWeight: 500 }}>→ {alt.alternative}</div>
                    <div style={{ color: "#888", fontSize: "13px" }}>{alt.reason}</div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "tips" && (
              <div>
                {result.tips?.map((tip, i) => (
                  <div key={i} style={{
                    display: "flex",
                    gap: "12px",
                    padding: "14px 16px",
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    borderRadius: "10px",
                    marginBottom: "10px",
                    animation: "slideIn 0.4s ease both",
                    animationDelay: `${i * 0.08}s`,
                  }}>
                    <span style={{ color: "#e53935", fontSize: "16px", marginTop: "1px" }}>→</span>
                    <p style={{ color: "#bbb", fontSize: "14px", lineHeight: 1.6 }}>{tip}</p>
                  </div>
                ))}
                {result.upgrade_path && (
                  <div style={{
                    background: "rgba(124,77,255,0.1)",
                    border: "1px solid rgba(124,77,255,0.2)",
                    borderRadius: "10px",
                    padding: "16px",
                    marginTop: "8px",
                  }}>
                    <div style={{ fontSize: "11px", letterSpacing: "0.15em", color: "#9c7bff", textTransform: "uppercase", fontFamily: "'DM Mono', monospace", marginBottom: "8px" }}>
                      Upgrade Path
                    </div>
                    <p style={{ color: "#ccc", fontSize: "14px", lineHeight: 1.6 }}>{result.upgrade_path}</p>
                  </div>
                )}
              </div>
            )}

            {/* EGPrices CTA */}
            <div style={{
              marginTop: "24px",
              background: "rgba(79,195,247,0.05)",
              border: "1px solid rgba(79,195,247,0.15)",
              borderRadius: "12px",
              padding: "16px 20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "12px",
            }}>
              <div>
                <div style={{ color: "#4fc3f7", fontWeight: 600, fontSize: "14px", marginBottom: "3px" }}>Verify Prices on EGPrices.com</div>
                <div style={{ color: "#666", fontSize: "12px" }}>Click each part above to search it — prices vary by store and update daily</div>
              </div>
              <a
                href="https://egprices.com/en/category/computers"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  background: "rgba(79,195,247,0.15)",
                  border: "1px solid rgba(79,195,247,0.3)",
                  color: "#4fc3f7",
                  padding: "8px 16px",
                  borderRadius: "8px",
                  fontSize: "13px",
                  textDecoration: "none",
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                }}
              >
                Open EGPrices →
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}