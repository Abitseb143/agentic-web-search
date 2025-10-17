import { useState, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function App() {
  const [query, setQuery] = useState("");
  const [k, setK] = useState(6);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // 🌊 Blue bubbles background
  useEffect(() => {
    const canvas = document.getElementById("bgCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const bubbles = Array.from({ length: 40 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 12 + 6,
      dx: (Math.random() - 0.5) * 0.4,
      dy: Math.random() * 0.4 + 0.2, // upward drift
    }));

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      bubbles.forEach((b) => {
        const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
        g.addColorStop(0, "rgba(0,150,255,0.8)");
        g.addColorStop(1, "rgba(0,150,255,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();

        b.y -= b.dy;
        b.x += b.dx;

        if (b.y + b.r < 0) {
          b.y = canvas.height + b.r;
          b.x = Math.random() * canvas.width;
        }
        if (b.x < 0 || b.x > canvas.width) b.dx *= -1;
      });
      requestAnimationFrame(animate);
    };
    animate();

    return () => window.removeEventListener("resize", resize);
  }, []);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const res = await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, k }),
      });

      const raw = await res.text();
      console.log("API_BASE:", API_BASE);
      console.log("HTTP", res.status, raw);

      if (!res.ok) throw new Error(raw || `HTTP ${res.status}`);

      const json = JSON.parse(raw);
      setData(json);
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const copyAnswer = async () => {
    if (data?.answer) {
      await navigator.clipboard.writeText(data.answer);
      alert("Answer copied!");
    }
  };

  return (
    <>
      <canvas id="bgCanvas" className="bg-canvas" />

      <main className="container">
        <header className="header">
          <h1 className="title">
            🔍 <span className="glow">Agentic Web Search</span> 🌊
          </h1>
        </header>

        <p className="subtitle">
          Ask a question, get a sourced summary. Citations like <span className="kbd">[1]</span> link to sources below.
        </p>

        <form className="form" onSubmit={onSubmit}>
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask anything…"
            required
          />
          <input
            className="number"
            type="number"
            min={1}
            max={10}
            value={k}
            onChange={(e) => setK(parseInt(e.target.value || "6", 10))}
            title="Number of search results"
          />
          <button className="btn" type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        {/* Diagnostics so you always see something */}
        <div className="card" style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Diagnostics</div>
          <div><span className="mono">API_BASE:</span> {API_BASE}</div>
          {loading && <div>Loading…</div>}
          {error && <div style={{ color: "#ff7b7b" }}>Error: {String(error)}</div>}
          {!loading && !data && !error && <div>No data yet. Submit a query.</div>}
        </div>

        {data && (
          <>
            <h2 className="section-title">💬 Query</h2>
            <div className="card">{data.query}</div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 16 }}>
              <h2 className="section-title" style={{ margin: 0 }}>🧠 Answer</h2>
              <button className="btn" style={{ height: 36, padding: "0 12px" }} onClick={copyAnswer}>
                Copy
              </button>
            </div>

            <div className="answer">
              {data?.answer?.trim()
                ? data.answer
                : <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(data, null, 2)}</pre>}
            </div>

            <h2 className="section-title">📚 Sources</h2>
            <ol className="sources">
              {Array.isArray(data?.sources) && data.sources.length > 0
                ? data.sources.map((s, i) => (
                    <li key={i} id={`s-${i + 1}`}>
                      <a href={s.link} target="_blank" rel="noreferrer">
                        [{i + 1}] {s.title}
                      </a>
                    </li>
                  ))
                : <em>(No sources returned)</em>}
            </ol>
          </>
        )}
      </main>
    </>
  );
}
