"use client"

import React, { useState, useRef, useCallback, useEffect } from "react"

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
type BgType = "solid" | "linear" | "radial" | "mesh"
type GradientAngle = 0 | 45 | 90 | 135 | 180 | 225 | 270 | 315

interface GradientStop {
    id: string
    color: string
    position: number // 0–100
}

interface SizePreset {
    label: string
    w: number
    h: number
    tag: string
}

const SIZE_PRESETS: SizePreset[] = [
    { label: "Portrait 9:16", w: 1080, h: 1920, tag: "phone" },
    { label: "Landscape 16:9", w: 1920, h: 1080, tag: "video" },
    { label: "Square 1:1", w: 1080, h: 1080, tag: "insta" },
    { label: "Story 4:5", w: 1080, h: 1350, tag: "feed" },
    { label: "Twitter Header", w: 1500, h: 500, tag: "web" },
    { label: "Desktop 2K", w: 2560, h: 1440, tag: "desk" },
    { label: "Thumbnail 16:9", w: 1280, h: 720, tag: "yt" },
    { label: "Custom", w: 0, h: 0, tag: "custom" },
]

const PRESET_GRADIENTS = [
    { label: "Midnight", stops: [{ id: "a", color: "#0f0c29", position: 0 }, { id: "b", color: "#302b63", position: 50 }, { id: "c", color: "#24243e", position: 100 }] },
    { label: "Sunset", stops: [{ id: "a", color: "#f7971e", position: 0 }, { id: "b", color: "#ffd200", position: 100 }] },
    { label: "Aurora", stops: [{ id: "a", color: "#00c6ff", position: 0 }, { id: "b", color: "#0072ff", position: 100 }] },
    { label: "Rose Gold", stops: [{ id: "a", color: "#f4c4ad", position: 0 }, { id: "b", color: "#c97b84", position: 100 }] },
    { label: "Forest", stops: [{ id: "a", color: "#134e5e", position: 0 }, { id: "b", color: "#71b280", position: 100 }] },
    { label: "Neon", stops: [{ id: "a", color: "#7f00ff", position: 0 }, { id: "b", color: "#e100ff", position: 100 }] },
    { label: "Lava", stops: [{ id: "a", color: "#f12711", position: 0 }, { id: "b", color: "#f5af19", position: 100 }] },
    { label: "Ocean", stops: [{ id: "a", color: "#1a1a2e", position: 0 }, { id: "b", color: "#16213e", position: 50 }, { id: "c", color: "#0f3460", position: 100 }] },
    { label: "Cotton", stops: [{ id: "a", color: "#ffecd2", position: 0 }, { id: "b", color: "#fcb69f", position: 100 }] },
    { label: "Nordic", stops: [{ id: "a", color: "#3a1c71", position: 0 }, { id: "b", color: "#d76d77", position: 50 }, { id: "c", color: "#ffaf7b", position: 100 }] },
    { label: "Ash", stops: [{ id: "a", color: "#232526", position: 0 }, { id: "b", color: "#414345", position: 100 }] },
    { label: "Ice", stops: [{ id: "a", color: "#e0eafc", position: 0 }, { id: "b", color: "#cfdef3", position: 100 }] },
]

function uid() { return Math.random().toString(36).slice(2, 7) }

// ─────────────────────────────────────────────────────────────────────────────
// Canvas gradient renderer
// ─────────────────────────────────────────────────────────────────────────────
function renderToCanvas(
    canvas: HTMLCanvasElement,
    w: number, h: number,
    bgType: BgType,
    solidColor: string,
    stops: GradientStop[],
    angle: GradientAngle,
    meshColors: string[],
): void {
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext("2d")!
    ctx.clearRect(0, 0, w, h)

    const sortedStops = [...stops].sort((a, b) => a.position - b.position)

    if (bgType === "solid") {
        ctx.fillStyle = solidColor
        ctx.fillRect(0, 0, w, h)
        return
    }

    if (bgType === "linear") {
        const rad = (angle * Math.PI) / 180
        const cx = w / 2, cy = h / 2
        const len = Math.abs(w * Math.cos(rad)) + Math.abs(h * Math.sin(rad))
        const x0 = cx - Math.cos(rad) * len / 2, y0 = cy - Math.sin(rad) * len / 2
        const x1 = cx + Math.cos(rad) * len / 2, y1 = cy + Math.sin(rad) * len / 2
        const grad = ctx.createLinearGradient(x0, y0, x1, y1)
        sortedStops.forEach(s => grad.addColorStop(s.position / 100, s.color))
        ctx.fillStyle = grad
        ctx.fillRect(0, 0, w, h)
        return
    }

    if (bgType === "radial") {
        const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.7)
        sortedStops.forEach(s => grad.addColorStop(s.position / 100, s.color))
        ctx.fillStyle = grad
        ctx.fillRect(0, 0, w, h)
        return
    }

    // Mesh: simple 4-corner gradient via two overlapping radial gradients
    if (bgType === "mesh") {
        const c = meshColors
        // Fill base
        ctx.fillStyle = c[0] || "#000"
        ctx.fillRect(0, 0, w, h)
        // Radial blob 1: top-right
        const g1 = ctx.createRadialGradient(w * 0.8, h * 0.2, 0, w * 0.8, h * 0.2, Math.max(w, h) * 0.7)
        g1.addColorStop(0, hexAlpha(c[1] || "#fff", 0.8)); g1.addColorStop(1, "transparent")
        ctx.fillStyle = g1; ctx.fillRect(0, 0, w, h)
        // Radial blob 2: bottom-left
        const g2 = ctx.createRadialGradient(w * 0.2, h * 0.8, 0, w * 0.2, h * 0.8, Math.max(w, h) * 0.65)
        g2.addColorStop(0, hexAlpha(c[2] || "#888", 0.75)); g2.addColorStop(1, "transparent")
        ctx.fillStyle = g2; ctx.fillRect(0, 0, w, h)
        // Radial blob 3: center
        const g3 = ctx.createRadialGradient(w * 0.5, h * 0.5, 0, w * 0.5, h * 0.5, Math.max(w, h) * 0.4)
        g3.addColorStop(0, hexAlpha(c[3] || "#444", 0.5)); g3.addColorStop(1, "transparent")
        ctx.fillStyle = g3; ctx.fillRect(0, 0, w, h)
        return
    }
}

function hexAlpha(hex: string, alpha: number) {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgba(${r},${g},${b},${alpha})`
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper sub-components
// ─────────────────────────────────────────────────────────────────────────────
function Label({ children }: { children: React.ReactNode }) {
    return <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#555", marginBottom: 10 }}>{children}</div>
}

function ColorSwatch({ color, size = 28, selected = false, onClick }: { color: string; size?: number; selected?: boolean; onClick?: () => void }) {
    return (
        <button onClick={onClick} aria-label={`Color: ${color}`} style={{
            width: size, height: size, borderRadius: 6,
            background: color,
            border: selected ? "2px solid #a78bfa" : "2px solid rgba(255,255,255,0.1)",
            cursor: "pointer", padding: 0, flexShrink: 0,
            boxShadow: selected ? "0 0 0 2px rgba(167,139,250,0.3)" : "none",
            transition: "all 0.15s",
        }} />
    )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────
export default function BackgroundCreatorPage() {
    const [bgType, setBgType] = useState<BgType>("linear")
    const [solidColor, setSolidColor] = useState("#1a0a2e")
    const [stops, setStops] = useState<GradientStop[]>([
        { id: "a", color: "#7c5cbf", position: 0 },
        { id: "b", color: "#a78bfa", position: 100 },
    ])
    const [angle, setAngle] = useState<GradientAngle>(135)
    const [meshColors, setMeshColors] = useState(["#0f0c29", "#7c5cbf", "#a78bfa", "#302b63"])
    const [selectedPreset, setSelectedPreset] = useState<SizePreset>(SIZE_PRESETS[0])
    const [customW, setCustomW] = useState(1080)
    const [customH, setCustomH] = useState(1920)
    const [exportFormat, setExportFormat] = useState<"png" | "jpg">("png")
    const [selectedStopId, setSelectedStopId] = useState<string>("a")
    const [isExporting, setIsExporting] = useState(false)
    const [zoom, setZoom] = useState(0.18)

    const canvasRef = useRef<HTMLCanvasElement>(null)
    const previewCanvasRef = useRef<HTMLCanvasElement>(null)

    const exportW = selectedPreset.tag === "custom" ? customW : selectedPreset.w
    const exportH = selectedPreset.tag === "custom" ? customH : selectedPreset.h

    // Preview aspect ratio dimensions
    const MAX_PREVIEW = 440
    const previewAspect = exportW / exportH
    const previewW = previewAspect >= 1 ? MAX_PREVIEW : Math.round(MAX_PREVIEW * previewAspect)
    const previewH = previewAspect < 1 ? MAX_PREVIEW : Math.round(MAX_PREVIEW / previewAspect)

    // ── Redraw preview canvas whenever anything changes ────────────────────────
    useEffect(() => {
        const c = previewCanvasRef.current
        if (!c) return
        renderToCanvas(c, previewW, previewH, bgType, solidColor, stops, angle, meshColors)
    }, [bgType, solidColor, stops, angle, meshColors, previewW, previewH])

    // ── Stop management ────────────────────────────────────────────────────────
    const addStop = () => {
        const newStop: GradientStop = { id: uid(), color: "#ffffff", position: 50 }
        setStops(prev => [...prev, newStop])
        setSelectedStopId(newStop.id)
    }

    const removeStop = (id: string) => {
        if (stops.length <= 2) return
        setStops(prev => prev.filter(s => s.id !== id))
        setSelectedStopId(stops[0].id)
    }

    const updateStop = (id: string, patch: Partial<GradientStop>) => {
        setStops(prev => prev.map(s => s.id === id ? { ...s, ...patch } : s))
    }

    const selectedStop = stops.find(s => s.id === selectedStopId)

    // ── Export ─────────────────────────────────────────────────────────────────
    const handleExport = useCallback(() => {
        const c = canvasRef.current
        if (!c) return
        setIsExporting(true)
        renderToCanvas(c, exportW, exportH, bgType, solidColor, stops, angle, meshColors)
        const mimeType = exportFormat === "jpg" ? "image/jpeg" : "image/png"
        const quality = exportFormat === "jpg" ? 0.96 : undefined
        c.toBlob(blob => {
            if (!blob) return
            const a = document.createElement("a")
            a.href = URL.createObjectURL(blob)
            a.download = `background-${exportW}x${exportH}.${exportFormat}`
            a.click()
            setIsExporting(false)
        }, mimeType, quality)
    }, [exportW, exportH, bgType, solidColor, stops, angle, meshColors, exportFormat])

    // ── Gradient bar CSS for the stop track ───────────────────────────────────
    const gradientBarCss = () => {
        const sorted = [...stops].sort((a, b) => a.position - b.position)
        const stopsStr = sorted.map(s => `${s.color} ${s.position}%`).join(", ")
        if (bgType === "linear") return `linear-gradient(90deg, ${stopsStr})`
        if (bgType === "radial") return `radial-gradient(circle, ${stopsStr})`
        return sorted[0]?.color || "#000"
    }

    return (
        <div style={{
            minHeight: "100vh",
            background: "#080808",
            color: "#f0f0f0",
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            display: "flex",
            flexDirection: "column",
        }}>
            {/* Header */}
            <header style={{
                padding: "18px 40px",
                borderBottom: "1px solid rgba(255,255,255,0.06)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: "rgba(255,255,255,0.02)",
                backdropFilter: "blur(20px)",
                position: "sticky", top: 0, zIndex: 100,
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "linear-gradient(135deg, #f7971e, #a78bfa)",
                        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
                    }}>🎨</div>
                    <div>
                        <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em" }}>Background Creator</div>
                        <div style={{ fontSize: 11, color: "#666", marginTop: 1 }}>Solid · Gradient · Mesh — any size</div>
                    </div>
                </div>

                {/* Nav tabs */}
                <div style={{ display: "flex", gap: 6 }}>
                    <a href="/frame-studio" style={tabStyle(false)}>🎬 Frame Studio</a>
                    <a href="/background-creator" style={tabStyle(true)}>🎨 BG Creator</a>
                </div>

                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <div style={{ display: "flex", gap: 4, background: "rgba(255,255,255,0.04)", borderRadius: 8, padding: "3px" }}>
                        {(["png", "jpg"] as const).map(f => (
                            <button key={f} onClick={() => setExportFormat(f)} style={{
                                padding: "5px 12px", borderRadius: 6, border: "none",
                                background: exportFormat === f ? "rgba(167,139,250,0.2)" : "transparent",
                                color: exportFormat === f ? "#c4b5fd" : "#666",
                                fontSize: 12, cursor: "pointer", fontFamily: "inherit", textTransform: "uppercase",
                            }}>{f}</button>
                        ))}
                    </div>
                    <button
                        onClick={handleExport}
                        disabled={isExporting}
                        style={btnStyle("primary", isExporting)}
                        aria-label="Export background image"
                    >
                        {isExporting ? "⏳ Exporting…" : `⬇ Export ${exportW}×${exportH}`}
                    </button>
                </div>
            </header>

            <main style={{ flex: 1, display: "flex", overflow: "hidden" }}>

                {/* ── Left Panel ── */}
                <aside style={{
                    width: 296,
                    background: "#111",
                    borderRight: "1px solid rgba(255,255,255,0.06)",
                    overflowY: "auto",
                    padding: "22px 18px",
                    display: "flex", flexDirection: "column", gap: 26,
                    flexShrink: 0,
                }}>

                    {/* Background Type */}
                    <section>
                        <Label>Background Type</Label>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 6 }}>
                            {(["solid", "linear", "radial", "mesh"] as BgType[]).map(t => (
                                <button key={t} onClick={() => setBgType(t)} style={{
                                    padding: "7px 2px",
                                    borderRadius: 8,
                                    border: bgType === t ? "1.5px solid #a78bfa" : "1.5px solid rgba(255,255,255,0.08)",
                                    background: bgType === t ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.03)",
                                    color: bgType === t ? "#c4b5fd" : "#777",
                                    fontSize: 10, cursor: "pointer", fontFamily: "inherit",
                                    textTransform: "capitalize",
                                }}>
                                    {t === "linear" ? "Linear" : t === "radial" ? "Radial" : t === "solid" ? "Solid" : "Mesh"}
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* Solid Color */}
                    {bgType === "solid" && (
                        <section>
                            <Label>Color</Label>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <input type="color" value={solidColor} onChange={e => setSolidColor(e.target.value)}
                                    style={{ width: 44, height: 44, borderRadius: 10, border: "none", cursor: "pointer" }}
                                    aria-label="Solid background color"
                                />
                                <div>
                                    <div style={{ fontSize: 12, color: "#ddd", fontFamily: "monospace" }}>{solidColor.toUpperCase()}</div>
                                    <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>Click to open picker</div>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* Gradient stops editor */}
                    {(bgType === "linear" || bgType === "radial") && (
                        <section>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                                <Label>Color Stops</Label>
                                <button onClick={addStop} style={{
                                    fontSize: 11, color: "#a78bfa", border: "1px solid rgba(167,139,250,0.3)",
                                    borderRadius: 6, padding: "3px 8px", background: "rgba(167,139,250,0.08)",
                                    cursor: "pointer", fontFamily: "inherit",
                                }}>+ Add Stop</button>
                            </div>

                            {/* Gradient preview bar with stop handles */}
                            <div style={{ position: "relative", height: 24, borderRadius: 8, background: gradientBarCss(), marginBottom: 14, border: "1px solid rgba(255,255,255,0.08)" }}>
                                {stops.map(s => (
                                    <button
                                        key={s.id}
                                        onClick={() => setSelectedStopId(s.id)}
                                        aria-label={`Gradient stop at ${s.position}%`}
                                        style={{
                                            position: "absolute",
                                            left: `${s.position}%`,
                                            top: "50%",
                                            transform: "translate(-50%, -50%)",
                                            width: 16, height: 16,
                                            borderRadius: "50%",
                                            background: s.color,
                                            border: selectedStopId === s.id ? "3px solid #fff" : "2px solid rgba(255,255,255,0.6)",
                                            cursor: "pointer", padding: 0,
                                            boxShadow: "0 1px 4px rgba(0,0,0,0.5)",
                                            zIndex: 2,
                                        }}
                                    />
                                ))}
                            </div>

                            {/* Selected stop editor */}
                            {selectedStop && (
                                <div style={{
                                    background: "rgba(255,255,255,0.03)", borderRadius: 10,
                                    border: "1px solid rgba(255,255,255,0.07)", padding: "12px 14px",
                                }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                                        <input type="color" value={selectedStop.color}
                                            onChange={e => updateStop(selectedStop.id, { color: e.target.value })}
                                            style={{ width: 36, height: 36, borderRadius: 8, border: "none", cursor: "pointer" }}
                                            aria-label="Stop color"
                                        />
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>Position</div>
                                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                                <div style={{ position: "relative", flex: 1, height: 4, background: "#333", borderRadius: 2 }}>
                                                    <div style={{
                                                        position: "absolute", left: 0, height: "100%",
                                                        width: `${selectedStop.position}%`,
                                                        background: "linear-gradient(to right, #7c5cbf, #a78bfa)",
                                                        borderRadius: 2,
                                                    }} />
                                                    <input type="range" min={0} max={100} value={selectedStop.position}
                                                        onChange={e => updateStop(selectedStop.id, { position: Number(e.target.value) })}
                                                        style={{ position: "absolute", inset: 0, width: "100%", opacity: 0, cursor: "pointer", margin: 0, height: "100%" }}
                                                        aria-label="Stop position"
                                                    />
                                                </div>
                                                <span style={{ fontSize: 11, color: "#ccc", minWidth: 28, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{selectedStop.position}%</span>
                                            </div>
                                        </div>
                                        {stops.length > 2 && (
                                            <button onClick={() => removeStop(selectedStop.id)} style={{
                                                background: "rgba(239,68,68,0.12)", border: "none", borderRadius: 6,
                                                color: "#f87171", fontSize: 14, cursor: "pointer", padding: "4px 8px",
                                            }} aria-label="Remove stop">✕</button>
                                        )}
                                    </div>
                                    <div style={{ fontSize: 10, color: "#555" }}>
                                        Click a handle on the bar above to select it
                                    </div>
                                </div>
                            )}

                            {/* All stops list */}
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                                {stops.map(s => (
                                    <button key={s.id} onClick={() => setSelectedStopId(s.id)} style={{
                                        display: "flex", alignItems: "center", gap: 5, padding: "4px 8px",
                                        borderRadius: 6, border: selectedStopId === s.id ? "1px solid #a78bfa" : "1px solid rgba(255,255,255,0.1)",
                                        background: selectedStopId === s.id ? "rgba(167,139,250,0.1)" : "rgba(255,255,255,0.03)",
                                        cursor: "pointer",
                                    }} aria-label={`Stop ${s.id}`}>
                                        <ColorSwatch color={s.color} size={14} />
                                        <span style={{ fontSize: 10, color: "#888", fontVariantNumeric: "tabular-nums" }}>{s.position}%</span>
                                    </button>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Linear angle picker */}
                    {bgType === "linear" && (
                        <section>
                            <Label>Angle</Label>
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
                                {([0, 45, 90, 135, 180, 225, 270, 315] as GradientAngle[]).map(a => (
                                    <button key={a} onClick={() => setAngle(a)} style={{
                                        padding: "7px 4px", borderRadius: 8, fontSize: 11,
                                        border: angle === a ? "1.5px solid #a78bfa" : "1.5px solid rgba(255,255,255,0.08)",
                                        background: angle === a ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.03)",
                                        color: angle === a ? "#c4b5fd" : "#777",
                                        cursor: "pointer", fontFamily: "monospace",
                                    }}>{a}°</button>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Mesh colors */}
                    {bgType === "mesh" && (
                        <section>
                            <Label>Mesh Points</Label>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                                {["Base (BL)", "Blob 1 (TR)", "Blob 2 (BL)", "Center"].map((lbl, i) => (
                                    <div key={lbl}>
                                        <div style={{ fontSize: 10, color: "#666", marginBottom: 5 }}>{lbl}</div>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                            <input type="color" value={meshColors[i]}
                                                onChange={e => setMeshColors(prev => prev.map((c, idx) => idx === i ? e.target.value : c))}
                                                style={{ width: 32, height: 32, borderRadius: 8, border: "none", cursor: "pointer" }}
                                                aria-label={lbl}
                                            />
                                            <span style={{ fontSize: 10, color: "#666", fontFamily: "monospace" }}>{meshColors[i]}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Preset gradients quick-pick */}
                    {bgType !== "solid" && bgType !== "mesh" && (
                        <section>
                            <Label>Preset Gradients</Label>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
                                {PRESET_GRADIENTS.map(p => {
                                    const sorted = [...p.stops].sort((a, b) => a.position - b.position)
                                    const css = `linear-gradient(135deg, ${sorted.map(s => `${s.color} ${s.position}%`).join(", ")})`
                                    return (
                                        <button key={p.label} onClick={() => { setStops(p.stops.map(s => ({ ...s }))); }}
                                            aria-label={`Preset: ${p.label}`}
                                            title={p.label}
                                            style={{
                                                height: 40, borderRadius: 8, border: "1.5px solid rgba(255,255,255,0.08)",
                                                background: css, cursor: "pointer", padding: 0,
                                                transition: "transform 0.1s, border-color 0.1s",
                                            }}
                                            onMouseEnter={e => (e.currentTarget.style.transform = "scale(1.04)")}
                                            onMouseLeave={e => (e.currentTarget.style.transform = "scale(1)")}
                                        />
                                    )
                                })}
                            </div>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginTop: 0 }}>
                                {PRESET_GRADIENTS.map(p => (
                                    <div key={p.label + "_lbl"} style={{ fontSize: 9, color: "#555", textAlign: "center", marginTop: -2 }}>{p.label}</div>
                                ))}
                            </div>
                        </section>
                    )}

                </aside>

                {/* ── Center: Preview ── */}
                <div style={{
                    flex: 1, display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center",
                    padding: 40, overflow: "auto", gap: 20, position: "relative",
                    background: "#0d0d0d",
                }}>
                    {/* Dotted grid bg */}
                    <div style={{
                        position: "absolute", inset: 0, zIndex: 0,
                        backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)",
                        backgroundSize: "24px 24px",
                    }} />

                    {/* Preview canvas */}
                    <div style={{
                        position: "relative", zIndex: 1,
                        boxShadow: "0 40px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.06)",
                        borderRadius: 8, overflow: "hidden",
                    }}>
                        <canvas ref={previewCanvasRef} style={{ display: "block" }} aria-label="Background preview" />
                    </div>

                    {/* Size badge */}
                    <div style={{ position: "relative", zIndex: 1, fontSize: 11, color: "#555", textAlign: "center" }}>
                        {exportW} × {exportH} px &nbsp;·&nbsp; {exportFormat.toUpperCase()} &nbsp;·&nbsp;
                        {bgType === "solid" ? "Solid" : bgType === "linear" ? `Linear ${angle}°` : bgType === "radial" ? "Radial" : "Mesh"} &nbsp;·&nbsp;
                        {stops.length} stops
                    </div>
                </div>

                {/* ── Right Panel: Size ── */}
                <aside style={{
                    width: 244,
                    background: "#0d0d0d",
                    borderLeft: "1px solid rgba(255,255,255,0.06)",
                    padding: "22px 16px",
                    display: "flex", flexDirection: "column", gap: 22,
                    flexShrink: 0, overflowY: "auto",
                }}>
                    <section>
                        <Label>Export Size</Label>
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            {SIZE_PRESETS.map(p => (
                                <button key={p.label} onClick={() => setSelectedPreset(p)} style={{
                                    display: "flex", alignItems: "center", justifyContent: "space-between",
                                    padding: "8px 12px", borderRadius: 10,
                                    border: selectedPreset.label === p.label ? "1.5px solid #a78bfa" : "1.5px solid rgba(255,255,255,0.07)",
                                    background: selectedPreset.label === p.label ? "rgba(167,139,250,0.1)" : "rgba(255,255,255,0.02)",
                                    cursor: "pointer", textAlign: "left",
                                }} aria-label={`Size: ${p.label}`}>
                                    <div>
                                        <div style={{ fontSize: 12, color: selectedPreset.label === p.label ? "#c4b5fd" : "#ccc", fontWeight: 500 }}>{p.label}</div>
                                        {p.tag !== "custom" && <div style={{ fontSize: 10, color: "#555", marginTop: 2, fontFamily: "monospace" }}>{p.w} × {p.h}</div>}
                                    </div>
                                    <div style={{
                                        fontSize: 9, color: "#666", background: "rgba(255,255,255,0.05)",
                                        padding: "2px 6px", borderRadius: 4, textTransform: "uppercase",
                                        letterSpacing: "0.05em",
                                    }}>{p.tag}</div>
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* Custom size inputs */}
                    {selectedPreset.tag === "custom" && (
                        <section>
                            <Label>Custom Dimensions</Label>
                            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                                {[["Width", customW, setCustomW], ["Height", customH, setCustomH]].map(([lbl, val, setter]) => (
                                    <div key={lbl as string}>
                                        <div style={{ fontSize: 10, color: "#666", marginBottom: 5 }}>{lbl as string} (px)</div>
                                        <input
                                            type="number" min={100} max={8000}
                                            value={val as number}
                                            onChange={e => (setter as (v: number) => void)(Math.max(100, Math.min(8000, Number(e.target.value))))}
                                            style={{
                                                width: "100%", padding: "8px 10px",
                                                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                                                borderRadius: 8, color: "#ddd", fontSize: 13, fontFamily: "monospace",
                                                outline: "none", boxSizing: "border-box",
                                            }}
                                            aria-label={`${lbl} in pixels`}
                                        />
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Export quality note */}
                    <div style={{
                        padding: "12px 12px", borderRadius: 10,
                        background: "rgba(167,139,250,0.06)",
                        border: "1px solid rgba(167,139,250,0.14)",
                    }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "#a78bfa", marginBottom: 8 }}>Export</div>
                        {[
                            ["Format", exportFormat.toUpperCase()],
                            ["Width", `${exportW} px`],
                            ["Height", `${exportH} px`],
                            ["Quality", exportFormat === "png" ? "Lossless" : "96%"],
                        ].map(([k, v]) => (
                            <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                                <span style={{ fontSize: 11, color: "#666" }}>{k}</span>
                                <span style={{ fontSize: 11, color: "#ccc", fontFamily: "monospace" }}>{v}</span>
                            </div>
                        ))}
                    </div>
                </aside>
            </main>

            {/* Hidden full-res canvas for export */}
            <canvas ref={canvasRef} style={{ display: "none" }} aria-hidden="true" />
        </div>
    )
}

function tabStyle(active: boolean): React.CSSProperties {
    return {
        padding: "7px 16px", borderRadius: 8, fontSize: 13, fontWeight: 500,
        textDecoration: "none", cursor: "pointer",
        border: active ? "1.5px solid #a78bfa" : "1.5px solid rgba(255,255,255,0.08)",
        background: active ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.03)",
        color: active ? "#c4b5fd" : "#888",
        transition: "all 0.15s",
    }
}

function btnStyle(variant: "primary" | "secondary", disabled = false): React.CSSProperties {
    const base: React.CSSProperties = {
        padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 500,
        cursor: disabled ? "not-allowed" : "pointer",
        border: "none", opacity: disabled ? 0.5 : 1, transition: "all 0.15s",
        letterSpacing: "-0.01em", fontFamily: "inherit", whiteSpace: "nowrap",
    }
    if (variant === "primary") return {
        ...base,
        background: "linear-gradient(135deg, #f7971e, #a78bfa)",
        color: "#fff",
        boxShadow: "0 2px 12px rgba(247,151,30,0.25)",
    }
    return { ...base, background: "rgba(255,255,255,0.08)", color: "#ddd", border: "1px solid rgba(255,255,255,0.1)" }
}
