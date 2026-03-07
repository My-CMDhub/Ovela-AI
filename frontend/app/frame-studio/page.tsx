"use client"

import React, { useState, useRef, useCallback, useEffect } from "react"

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
type FrameColor = "black" | "silver" | "gold" | "purple" | "steel"
type BgMode = "color" | "gradient" | "transparent"

interface VideoAdjust {
    scale: number
    offsetX: number
    offsetY: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants – iPhone 15 Pro proportions (width=375, height=812 logical pts)
// We render the frame at 390×845 CSS px, matching iPhone 15 Pro screen ratio.
// The "screen area" inside the frame starts at the right insets below.
// ─────────────────────────────────────────────────────────────────────────────
const FRAME_W = 390        // CSS px — total frame outer width
const FRAME_H = 845        // CSS px — total frame outer height
const CORNER_R = 54        // outer corner radius px
const BORDER = 14          // frame border thickness px
const SCREEN_R = 44        // screen inner corner radius
const SCREEN_W = FRAME_W - BORDER * 2
const SCREEN_H = FRAME_H - BORDER * 2

const FRAME_COLORS: Record<FrameColor, { outer: string; inner: string; label: string; swatch: string }> = {
    black: { outer: "linear-gradient(145deg,#2c2c2e,#1c1c1e,#2c2c2e)", inner: "#0a0a0a", label: "Space Black", swatch: "#2c2c2e" },
    silver: { outer: "linear-gradient(145deg,#e8e8e8,#c8c8cc,#e8e8e8)", inner: "#1a1a1a", label: "Natural Titanium", swatch: "#c8c8cc" },
    gold: { outer: "linear-gradient(145deg,#e6d5a8,#c9a96e,#e6d5a8)", inner: "#1a1a1a", label: "Desert Titanium", swatch: "#c9a96e" },
    purple: { outer: "linear-gradient(145deg,#5e4a8a,#4a3a6e,#5e4a8a)", inner: "#0f0f1a", label: "Black Titanium", swatch: "#4a3a6e" },
    steel: { outer: "linear-gradient(145deg,#f0f0f2,#b0b8c8,#dde2ea,#8a96a8,#eaeef2)", inner: "#0a0a0a", label: "Stainless Steel", swatch: "#b8c4d0" },
}

// ─────────────────────────────────────────────────────────────────────────────
// iPhone 15 Pro Frame SVG  (rendered at 390×845)
// ─────────────────────────────────────────────────────────────────────────────
function IPhone15ProFrame({ color, children }: { color: FrameColor; children?: React.ReactNode }) {
    const { outer, inner } = FRAME_COLORS[color]

    return (
        <div
            style={{
                position: "relative",
                width: FRAME_W,
                height: FRAME_H,
                borderRadius: CORNER_R,
                background: outer,
                boxShadow: `
          0 0 0 1px rgba(255,255,255,0.08),
          inset 0 1px 0 rgba(255,255,255,0.15),
          inset 0 -1px 0 rgba(0,0,0,0.4),
          0 60px 120px -20px rgba(0,0,0,0.7),
          0 30px 60px -20px rgba(0,0,0,0.5)
        `,
                flexShrink: 0,
            }}
        >
            {/* ── Side buttons (left: mute + vol up + vol down) ── */}
            {/* Mute toggle */}
            <div style={{
                position: "absolute", left: -3, top: 108,
                width: 4, height: 30,
                background: "linear-gradient(to right, #1a1a1a, #333)",
                borderRadius: "2px 0 0 2px",
                boxShadow: "-2px 0 4px rgba(0,0,0,0.5)",
            }} />
            {/* Vol up */}
            <div style={{
                position: "absolute", left: -3, top: 158,
                width: 4, height: 54,
                background: "linear-gradient(to right, #1a1a1a, #333)",
                borderRadius: "2px 0 0 2px",
                boxShadow: "-2px 0 4px rgba(0,0,0,0.5)",
            }} />
            {/* Vol down */}
            <div style={{
                position: "absolute", left: -3, top: 222,
                width: 4, height: 54,
                background: "linear-gradient(to right, #1a1a1a, #333)",
                borderRadius: "2px 0 0 2px",
                boxShadow: "-2px 0 4px rgba(0,0,0,0.5)",
            }} />
            {/* Power button (right) */}
            <div style={{
                position: "absolute", right: -3, top: 180,
                width: 4, height: 76,
                background: "linear-gradient(to left, #1a1a1a, #333)",
                borderRadius: "0 2px 2px 0",
                boxShadow: "2px 0 4px rgba(0,0,0,0.5)",
            }} />

            {/* ── Screen bezel (inner dark ring) ── */}
            <div style={{
                position: "absolute",
                inset: BORDER,
                borderRadius: SCREEN_R,
                background: inner,
                overflow: "hidden",
                boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.04)",
            }}>
                {/* ── Video / content area ── */}
                {children}

                {/* Dynamic Island removed — video already has real notch recorded in */}

                {/* ── Home indicator ── */}
                <div style={{
                    position: "absolute",
                    bottom: 10,
                    left: "50%",
                    transform: "translateX(-50%)",
                    width: 132,
                    height: 5,
                    background: "rgba(255,255,255,0.25)",
                    borderRadius: 3,
                    zIndex: 20,
                }} />

                {/* Screen glare */}
                <div style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: SCREEN_R,
                    background: "linear-gradient(135deg, rgba(255,255,255,0.07) 0%, transparent 50%)",
                    pointerEvents: "none",
                    zIndex: 10,
                }} />
            </div>

            {/* Frame glare */}
            <div style={{
                position: "absolute",
                inset: 0,
                borderRadius: CORNER_R,
                background: "linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 45%)",
                pointerEvents: "none",
            }} />
        </div>
    )
}

// ─────────────────────────────────────────────────────────────────────────────
// Slider control
// ─────────────────────────────────────────────────────────────────────────────
function Slider({ label, value, min, max, step = 0.01, unit = "", onChange }: {
    label: string; value: number; min: number; max: number; step?: number; unit?: string
    onChange: (v: number) => void
}) {
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, color: "#888", letterSpacing: "0.06em", textTransform: "uppercase" }}>{label}</span>
                <span style={{ fontSize: 12, color: "#ddd", fontVariantNumeric: "tabular-nums", minWidth: 48, textAlign: "right" }}>
                    {unit === "%" ? `${Math.round(value * 100)}%` : value.toFixed(0) + unit}
                </span>
            </div>
            <div style={{ position: "relative", height: 4, background: "#333", borderRadius: 2 }}>
                <div style={{
                    position: "absolute", left: 0, top: 0, height: "100%",
                    width: `${((value - min) / (max - min)) * 100}%`,
                    background: "linear-gradient(to right, #7c5cbf, #a78bfa)",
                    borderRadius: 2,
                }} />
                <input
                    type="range" min={min} max={max} step={step} value={value}
                    onChange={e => onChange(parseFloat(e.target.value))}
                    style={{
                        position: "absolute", inset: 0, width: "100%", height: "100%",
                        opacity: 0, cursor: "pointer", margin: 0,
                    }}
                    aria-label={label}
                />
            </div>
        </div>
    )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────
export default function FrameStudioPage() {
    const [videoUrl, setVideoUrl] = useState<string | null>(null)
    const [videoFile, setVideoFile] = useState<File | null>(null)
    const [frameColor, setFrameColor] = useState<FrameColor>("black")
    const [bgMode, setBgMode] = useState<BgMode>("color")
    const [bgColor, setBgColor] = useState("#0a0a0a")
    const [bgGradient, setBgGradient] = useState<[string, string]>(["#0a0a0a", "#1a0a2a"])
    const [adjust, setAdjust] = useState<VideoAdjust>({ scale: 1, offsetX: 0, offsetY: 0 })
    const [isDragging, setIsDragging] = useState(false)
    const [isExporting, setIsExporting] = useState(false)
    const [exportProgress, setExportProgress] = useState(0)
    const [isPlaying, setIsPlaying] = useState(true)
    const [videoError, setVideoError] = useState<string | null>(null)

    const videoRef = useRef<HTMLVideoElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)

    // ── Video upload ──────────────────────────────────────────────────────────
    const handleFileSelect = useCallback((file: File) => {
        if (!file.type.startsWith("video/")) {
            setVideoError("Please upload a video file (MP4, MOV, WebM).")
            return
        }
        setVideoError(null)
        setVideoFile(file)
        const url = URL.createObjectURL(file)
        setVideoUrl(url)
        setAdjust({ scale: 1, offsetX: 0, offsetY: 0 })
    }, [])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFileSelect(file)
    }, [handleFileSelect])

    const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFileSelect(file)
    }

    // ── Play/pause toggle ─────────────────────────────────────────────────────
    const handlePlayPause = () => {
        if (!videoRef.current) return
        if (videoRef.current.paused) {
            videoRef.current.play()
            setIsPlaying(true)
        } else {
            videoRef.current.pause()
            setIsPlaying(false)
        }
    }

    // ── Background style ──────────────────────────────────────────────────────
    const getBgStyle = (): React.CSSProperties => {
        if (bgMode === "transparent") return { background: "transparent" }
        if (bgMode === "gradient") return {
            background: `linear-gradient(135deg, ${bgGradient[0]}, ${bgGradient[1]})`
        }
        return { background: bgColor }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Canvas-based export
    // The approach:
    //  1. Draw background on canvas
    //  2. Draw the video frame (clipped to the screen area with rounded corners)
    //  3. Draw the iPhone frame SVG paths on top
    //  4. Capture via captureStream + MediaRecorder
    // ─────────────────────────────────────────────────────────────────────────
    const handleExport = async () => {
        if (!videoRef.current || !canvasRef.current || !videoUrl) return
        setIsExporting(true)
        setExportProgress(0)

        const vid = videoRef.current
        const canvas = canvasRef.current

        // ── Export canvas: 1080 × 1920 (9:16 portrait) ────────────────────────
        const EXPORT_W = 1080
        const EXPORT_H = 1920
        canvas.width = EXPORT_W
        canvas.height = EXPORT_H

        const ctx = canvas.getContext("2d", { alpha: bgMode === "transparent" })!
        ctx.imageSmoothingEnabled = true
        ctx.imageSmoothingQuality = "high"

        const frameColorData = FRAME_COLORS[frameColor]

        // ── Uniform phone scale so it matches the preview exactly ──────────────
        // Leave 5% padding on each side → background visible around the phone.
        const PADDING = 0.05
        const uniformScale = Math.min(
            (EXPORT_W * (1 - PADDING * 2)) / FRAME_W,
            (EXPORT_H * (1 - PADDING * 2)) / FRAME_H
        )

        const fw = FRAME_W * uniformScale        // phone outer width on canvas
        const fh = FRAME_H * uniformScale        // phone outer height on canvas
        const fx = (EXPORT_W - fw) / 2           // centered horizontally
        const fy = (EXPORT_H - fh) / 2           // centered vertically

        const cr = CORNER_R * uniformScale
        const border = BORDER * uniformScale
        const sx = fx + border
        const sy = fy + border
        const sw = SCREEN_W * uniformScale
        const sh = SCREEN_H * uniformScale
        const screenR = SCREEN_R * uniformScale

        // ── drawFrame: redraws entire scene each animation frame ───────────────
        const drawFrame = () => {
            // 1. Background
            if (bgMode === "transparent") {
                ctx.clearRect(0, 0, EXPORT_W, EXPORT_H)
            } else if (bgMode === "gradient") {
                const grad = ctx.createLinearGradient(0, 0, EXPORT_W, EXPORT_H)
                grad.addColorStop(0, bgGradient[0])
                grad.addColorStop(1, bgGradient[1])
                ctx.fillStyle = grad
                ctx.fillRect(0, 0, EXPORT_W, EXPORT_H)
            } else {
                ctx.fillStyle = bgColor
                ctx.fillRect(0, 0, EXPORT_W, EXPORT_H)
            }

            // 2. Phone outer frame gradient
            const frameGrad = ctx.createLinearGradient(fx, fy, fx + fw, fy + fh)
            if (frameColor === "black") {
                frameGrad.addColorStop(0, "#2c2c2e"); frameGrad.addColorStop(0.5, "#1c1c1e"); frameGrad.addColorStop(1, "#2c2c2e")
            } else if (frameColor === "silver") {
                frameGrad.addColorStop(0, "#e8e8e8"); frameGrad.addColorStop(0.5, "#c8c8cc"); frameGrad.addColorStop(1, "#e8e8e8")
            } else if (frameColor === "gold") {
                frameGrad.addColorStop(0, "#e6d5a8"); frameGrad.addColorStop(0.5, "#c9a96e"); frameGrad.addColorStop(1, "#e6d5a8")
            } else if (frameColor === "steel") {
                frameGrad.addColorStop(0, "#f0f0f2"); frameGrad.addColorStop(0.25, "#b0b8c8"); frameGrad.addColorStop(0.5, "#dde2ea"); frameGrad.addColorStop(0.75, "#8a96a8"); frameGrad.addColorStop(1, "#eaeef2")
            } else {
                frameGrad.addColorStop(0, "#5e4a8a"); frameGrad.addColorStop(0.5, "#4a3a6e"); frameGrad.addColorStop(1, "#5e4a8a")
            }
            ctx.save()
            // High-quality 3D drop shadow mimicking the live preview
            ctx.shadowColor = "rgba(0,0,0,0.6)"
            ctx.shadowBlur = 80 * uniformScale
            ctx.shadowOffsetY = 30 * uniformScale

            roundRect(ctx, fx, fy, fw, fh, cr)
            ctx.fillStyle = frameGrad
            ctx.fill()
            ctx.restore()

            // 3. Screen background
            ctx.save(); roundRect(ctx, sx, sy, sw, sh, screenR); ctx.fillStyle = frameColorData.inner; ctx.fill(); ctx.restore()

            // 4. Video – cover fill with user scale/offset adjustments
            const { scale, offsetX, offsetY } = adjust
            const vw = vid.videoWidth, vh = vid.videoHeight
            const fitScale = Math.max(sw / vw, sh / vh)        // object-fit: cover
            const drawnW = vw * fitScale * scale
            const drawnH = vh * fitScale * scale
            const vidX = sx + (sw - drawnW) / 2 + offsetX * uniformScale
            const vidY = sy + (sh - drawnH) / 2 + offsetY * uniformScale
            ctx.save(); roundRect(ctx, sx, sy, sw, sh, screenR); ctx.clip()
            ctx.drawImage(vid, vidX, vidY, drawnW, drawnH); ctx.restore()

            // 5. Home indicator
            const hiW = 132 * uniformScale, hiH = 5 * uniformScale
            ctx.save(); roundRect(ctx, sx + sw / 2 - hiW / 2, sy + sh - 14 * uniformScale, hiW, hiH, hiH / 2)
            ctx.fillStyle = "rgba(255,255,255,0.25)"; ctx.fill(); ctx.restore()

            // 6. Frame glare
            const glareGrad = ctx.createLinearGradient(fx, fy, fx + fw * 0.55, fy + fh * 0.55)
            glareGrad.addColorStop(0, "rgba(255,255,255,0.1)"); glareGrad.addColorStop(1, "rgba(255,255,255,0)")
            ctx.save(); roundRect(ctx, fx, fy, fw, fh, cr); ctx.fillStyle = glareGrad; ctx.fill(); ctx.restore()

            // 7. Side buttons (centered precisely on the frame)
            ctx.save()
            ctx.fillStyle = frameColor === "silver" ? "#aaa" : "#333"

            // Apply same shadow as frame for cohesive 3D effect
            ctx.shadowColor = "rgba(0,0,0,0.6)"
            ctx.shadowBlur = 80 * uniformScale
            ctx.shadowOffsetY = 30 * uniformScale

            const btnW = 4 * uniformScale
            // Silent/mute
            roundRect(ctx, fx - btnW, fy + 108 * uniformScale, btnW, 30 * uniformScale, 2); ctx.fill()
            // Vol up
            roundRect(ctx, fx - btnW, fy + 158 * uniformScale, btnW, 54 * uniformScale, 2); ctx.fill()
            // Vol down
            roundRect(ctx, fx - btnW, fy + 222 * uniformScale, btnW, 54 * uniformScale, 2); ctx.fill()
            // Power
            roundRect(ctx, fx + fw, fy + 180 * uniformScale, btnW, 76 * uniformScale, 2); ctx.fill()
            ctx.restore()
        }

        // ── Audio routing: video element → AudioContext → MediaStreamDestination ─
        // canvas.captureStream() only yields video tracks. We pipe the video
        // element's audio through an AudioContext to capture it separately.
        let audioCtx: AudioContext | null = null
        let audioDestination: MediaStreamAudioDestinationNode | null = null
        try {
            audioCtx = new AudioContext()
            audioDestination = audioCtx.createMediaStreamDestination()
            const src = audioCtx.createMediaElementSource(vid)
            src.connect(audioDestination)         // → recorder
            src.connect(audioCtx.destination)     // → speakers (audible during export)
        } catch (e) {
            // createMediaElementSource fails if already called on this element
            console.warn("Audio capture setup:", e)
            audioCtx = null; audioDestination = null
        }

        // ── Build combined MediaStream (canvas video + audio) ──────────────────
        const wasLooping = vid.loop
        vid.loop = false
        vid.currentTime = 0
        await vid.play()
        if (audioCtx?.state === "suspended") await audioCtx.resume()

        const fps = 30
        const canvasVideoStream = (canvas as any).captureStream(fps) as MediaStream
        const combinedStream = new MediaStream()
        canvasVideoStream.getVideoTracks().forEach((t: MediaStreamTrack) => combinedStream.addTrack(t))
        if (audioDestination) {
            audioDestination.stream.getAudioTracks().forEach(t => combinedStream.addTrack(t))
        }

        // Best quality: VP9+Opus at 25 Mbps video / 256 kbps audio
        const mimeType =
            MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus") ? "video/webm;codecs=vp9,opus" :
                MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus") ? "video/webm;codecs=vp8,opus" :
                    "video/webm"

        const recorder = new MediaRecorder(combinedStream, {
            mimeType,
            videoBitsPerSecond: 25_000_000,
            audioBitsPerSecond: 256_000,
        })

        const chunks: Blob[] = []
        recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data) }

        recorder.onstop = () => {
            const blob = new Blob(chunks, { type: "video/webm" })
            const a = document.createElement("a")
            a.href = URL.createObjectURL(blob)
            a.download = "frame-studio-export.webm"
            a.click()
            vid.loop = wasLooping
            audioCtx?.close()
            setIsExporting(false)
            setExportProgress(0)
        }

        const duration = vid.duration
        recorder.start(100)   // flush data chunks every 100 ms

        // ── Time-driven render loop ────────────────────────────────────────────
        let rafId: number
        const renderLoop = () => {
            drawFrame()
            setExportProgress(Math.min(vid.currentTime / duration, 0.98))
            if (!vid.ended) rafId = requestAnimationFrame(renderLoop)
        }

        const handleEnded = () => {
            cancelAnimationFrame(rafId)
            drawFrame()  // flush final frame
            if (recorder.state === "recording") recorder.stop()
        }
        vid.addEventListener("ended", handleEnded, { once: true })

        rafId = requestAnimationFrame(renderLoop)
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    const resetAdjust = () => setAdjust({ scale: 1, offsetX: 0, offsetY: 0 })

    // ─────────────────────────────────────────────────────────────────────────
    // Inline video style (inside frame preview)
    // ─────────────────────────────────────────────────────────────────────────
    const getVideoStyle = (): React.CSSProperties => ({
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        objectFit: "cover",
        objectPosition: `${50 + adjust.offsetX / (SCREEN_W / 100)}% ${50 + adjust.offsetY / (SCREEN_H / 100)}%`,
        transform: `scale(${adjust.scale})`,
        transformOrigin: "center center",
    })

    // ─────────────────────────────────────────────────────────────────────────
    // Render
    // ─────────────────────────────────────────────────────────────────────────
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
                padding: "20px 40px",
                borderBottom: "1px solid rgba(255,255,255,0.06)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "rgba(255,255,255,0.02)",
                backdropFilter: "blur(20px)",
                position: "sticky",
                top: 0,
                zIndex: 100,
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "linear-gradient(135deg, #7c5cbf, #a78bfa)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 16,
                    }}>🎬</div>
                    <div>
                        <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em" }}>Frame Studio</div>
                        <div style={{ fontSize: 11, color: "#666", marginTop: 1 }}>iPhone 15 Pro · Portrait Video</div>
                    </div>
                </div>

                {/* Nav tabs */}
                <div style={{ display: "flex", gap: 6 }}>
                    <a href="/frame-studio" style={navTabStyle(true)}>🎬 Frame Studio</a>
                    <a href="/background-creator" style={navTabStyle(false)}>🎨 BG Creator</a>
                </div>

                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    {videoUrl && (
                        <button
                            onClick={handlePlayPause}
                            style={btnStyle("ghost")}
                            aria-label="Toggle play/pause"
                        >
                            {isPlaying ? "⏸ Pause" : "▶ Play"}
                        </button>
                    )}
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        style={btnStyle("secondary")}
                        aria-label="Upload video"
                    >
                        📂 Upload Video
                    </button>
                    {videoUrl && (
                        <button
                            onClick={handleExport}
                            disabled={isExporting}
                            style={btnStyle("primary", isExporting)}
                            aria-label="Export video with frame"
                        >
                            {isExporting
                                ? `⏳ Exporting ${Math.round(exportProgress * 100)}%`
                                : "⬇ Export with Frame"}
                        </button>
                    )}
                </div>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="video/*"
                    style={{ display: "none" }}
                    onChange={handleFileInputChange}
                    id="video-upload-input"
                    aria-label="Video file input"
                />
            </header>

            {/* Main workspace */}
            <main style={{
                flex: 1,
                display: "flex",
                overflow: "hidden",
            }}>

                {/* ── Left Panel: Settings ── */}
                <aside style={{
                    width: 280,
                    background: "#111",
                    borderRight: "1px solid rgba(255,255,255,0.06)",
                    overflowY: "auto",
                    padding: "24px 20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 28,
                    flexShrink: 0,
                }}>

                    {/* Frame Color */}
                    <section>
                        <SectionLabel>Frame Color</SectionLabel>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                            {(Object.keys(FRAME_COLORS) as FrameColor[]).map(c => (
                                <button
                                    key={c}
                                    onClick={() => setFrameColor(c)}
                                    aria-label={`Frame color: ${FRAME_COLORS[c].label}`}
                                    style={{
                                        display: "flex", alignItems: "center", gap: 8,
                                        padding: "8px 10px",
                                        borderRadius: 10,
                                        border: frameColor === c
                                            ? "1.5px solid #a78bfa"
                                            : "1.5px solid rgba(255,255,255,0.08)",
                                        background: frameColor === c ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.03)",
                                        cursor: "pointer",
                                        transition: "all 0.15s",
                                    }}
                                >
                                    <div style={{
                                        width: 14, height: 14, borderRadius: "50%",
                                        background: FRAME_COLORS[c].swatch,
                                        boxShadow: "0 0 0 1px rgba(255,255,255,0.2)",
                                        flexShrink: 0,
                                    }} />
                                    <span style={{ fontSize: 11, color: frameColor === c ? "#c4b5fd" : "#999", whiteSpace: "nowrap" }}>
                                        {FRAME_COLORS[c].label}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* Background */}
                    <section>
                        <SectionLabel>Background</SectionLabel>
                        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                            {(["color", "gradient", "transparent"] as BgMode[]).map(m => (
                                <button
                                    key={m}
                                    onClick={() => setBgMode(m)}
                                    aria-label={`Background mode: ${m}`}
                                    style={{
                                        flex: 1, padding: "7px 4px",
                                        borderRadius: 8,
                                        border: bgMode === m ? "1.5px solid #a78bfa" : "1.5px solid rgba(255,255,255,0.08)",
                                        background: bgMode === m ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.03)",
                                        color: bgMode === m ? "#c4b5fd" : "#888",
                                        fontSize: 11, cursor: "pointer", textTransform: "capitalize",
                                    }}
                                >
                                    {m}
                                </button>
                            ))}
                        </div>

                        {bgMode === "color" && (
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <input
                                    type="color"
                                    value={bgColor}
                                    onChange={e => setBgColor(e.target.value)}
                                    style={{ width: 36, height: 36, borderRadius: 8, border: "none", cursor: "pointer", background: "none" }}
                                    aria-label="Background color"
                                />
                                <span style={{ fontSize: 12, color: "#888", fontFamily: "monospace" }}>{bgColor}</span>
                            </div>
                        )}

                        {bgMode === "gradient" && (
                            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                                <div>
                                    <div style={{ fontSize: 10, color: "#666", marginBottom: 4 }}>From</div>
                                    <input type="color" value={bgGradient[0]}
                                        onChange={e => setBgGradient([e.target.value, bgGradient[1]])}
                                        style={{ width: 36, height: 36, borderRadius: 8, border: "none", cursor: "pointer" }}
                                        aria-label="Gradient start color"
                                    />
                                </div>
                                <div style={{ color: "#555", marginTop: 16 }}>→</div>
                                <div>
                                    <div style={{ fontSize: 10, color: "#666", marginBottom: 4 }}>To</div>
                                    <input type="color" value={bgGradient[1]}
                                        onChange={e => setBgGradient([bgGradient[0], e.target.value])}
                                        style={{ width: 36, height: 36, borderRadius: 8, border: "none", cursor: "pointer" }}
                                        aria-label="Gradient end color"
                                    />
                                </div>
                            </div>
                        )}

                        {bgMode === "transparent" && (
                            <div style={{
                                fontSize: 11, color: "#666", padding: "8px 10px",
                                background: "rgba(255,255,255,0.03)", borderRadius: 8,
                                border: "1px dashed rgba(255,255,255,0.1)",
                            }}>
                                Exports with transparency (WebM alpha channel). Perfect for compositing.
                            </div>
                        )}
                    </section>

                    {/* Video Adjustments */}
                    <section>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                            <SectionLabel style={{ marginBottom: 0 }}>Video Adjustments</SectionLabel>
                            {(adjust.scale !== 1 || adjust.offsetX !== 0 || adjust.offsetY !== 0) && (
                                <button onClick={resetAdjust} style={{
                                    fontSize: 10, color: "#a78bfa", border: "none",
                                    cursor: "pointer", padding: "2px 6px",
                                    borderRadius: 4, background: "rgba(167,139,250,0.1)",
                                }} aria-label="Reset video adjustments">
                                    Reset
                                </button>
                            )}
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                            <Slider
                                label="Scale"
                                value={adjust.scale}
                                min={0.5}
                                max={2.5}
                                step={0.01}
                                unit="%"
                                onChange={v => setAdjust(a => ({ ...a, scale: v }))}
                            />
                            <Slider
                                label="Offset X"
                                value={adjust.offsetX}
                                min={-100}
                                max={100}
                                step={1}
                                unit="px"
                                onChange={v => setAdjust(a => ({ ...a, offsetX: v }))}
                            />
                            <Slider
                                label="Offset Y"
                                value={adjust.offsetY}
                                min={-150}
                                max={150}
                                step={1}
                                unit="px"
                                onChange={v => setAdjust(a => ({ ...a, offsetY: v }))}
                            />
                        </div>
                    </section>

                    {/* Export info */}
                    <section style={{
                        padding: "12px 14px",
                        background: "rgba(167,139,250,0.06)",
                        borderRadius: 10,
                        border: "1px solid rgba(167,139,250,0.15)",
                    }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "#a78bfa", marginBottom: 8 }}>Export Info</div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                            {[
                                ["Resolution", "1080 × 1920"],
                                ["Format", "WebM (VP9 + Opus)"],
                                ["Bitrate", "25 Mbps"],
                                ["FPS", "30"],
                            ].map(([k, v]) => (
                                <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
                                    <span style={{ fontSize: 11, color: "#666" }}>{k}</span>
                                    <span style={{ fontSize: 11, color: "#ccc", fontFamily: "monospace" }}>{v}</span>
                                </div>
                            ))}
                        </div>
                    </section>

                </aside>

                {/* ── Center: Preview Canvas ── */}
                <div style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "40px 60px",
                    overflow: "auto",
                    position: "relative",
                }}>

                    {/* Checkerboard for transparent bg */}
                    <div style={{
                        position: "absolute", inset: 0, zIndex: 0,
                        backgroundImage: bgMode === "transparent"
                            ? "linear-gradient(45deg, #1a1a1a 25%, transparent 25%), linear-gradient(-45deg, #1a1a1a 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1a1a1a 75%), linear-gradient(-45deg, transparent 75%, #1a1a1a 75%)"
                            : "none",
                        backgroundSize: "20px 20px",
                        backgroundPosition: "0 0, 0 10px, 10px -10px, -10px 0px",
                    }} />

                    {/* Preview background */}
                    <div style={{
                        position: "absolute", inset: 0, zIndex: 0,
                        ...getBgStyle(),
                        opacity: bgMode === "transparent" ? 0 : 1,
                    }} />

                    {/* Phone preview */}
                    <div style={{ position: "relative", zIndex: 1 }}>
                        <IPhone15ProFrame color={frameColor}>
                            {videoUrl ? (
                                <video
                                    ref={videoRef}
                                    src={videoUrl}
                                    autoPlay
                                    loop
                                    playsInline
                                    style={getVideoStyle()}
                                    onPlay={() => setIsPlaying(true)}
                                    onPause={() => setIsPlaying(false)}
                                    aria-label="Preview video"
                                />
                            ) : (
                                /* Drop zone */
                                <div
                                    onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
                                    onDragLeave={() => setIsDragging(false)}
                                    onDrop={handleDrop}
                                    onClick={() => fileInputRef.current?.click()}
                                    style={{
                                        position: "absolute", inset: 0,
                                        display: "flex", flexDirection: "column",
                                        alignItems: "center", justifyContent: "center",
                                        gap: 12, cursor: "pointer",
                                        background: isDragging
                                            ? "rgba(167,139,250,0.12)"
                                            : "linear-gradient(180deg, #111 0%, #0a0a0a 100%)",
                                        transition: "background 0.2s",
                                        borderRadius: SCREEN_R,
                                    }}
                                    role="button"
                                    tabIndex={0}
                                    aria-label="Drop video or click to upload"
                                    onKeyDown={e => e.key === "Enter" && fileInputRef.current?.click()}
                                >
                                    <div style={{
                                        width: 60, height: 60, borderRadius: 16,
                                        background: "rgba(167,139,250,0.15)",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        fontSize: 26,
                                        border: isDragging ? "2px solid #a78bfa" : "2px dashed rgba(167,139,250,0.3)",
                                        transition: "all 0.2s",
                                    }}>🎬</div>
                                    <div style={{ textAlign: "center" }}>
                                        <div style={{ fontSize: 13, color: "#888", fontWeight: 500 }}>
                                            {isDragging ? "Drop video here" : "Drop or click to upload"}
                                        </div>
                                        <div style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
                                            MP4 · MOV · WebM
                                        </div>
                                        <div style={{ fontSize: 10, color: "#444", marginTop: 2 }}>
                                            Optimal: 492 × 1026
                                        </div>
                                    </div>
                                </div>
                            )}
                        </IPhone15ProFrame>

                        {/* Dimension badge */}
                        <div style={{
                            position: "absolute", bottom: -30, left: "50%", transform: "translateX(-50%)",
                            fontSize: 11, color: "#555",
                            whiteSpace: "nowrap",
                        }}>
                            {FRAME_W} × {FRAME_H} px preview · 1080 × 1920 export
                        </div>
                    </div>
                </div>

                {/* ── Right gutter: tips ── */}
                <aside style={{
                    width: 220,
                    background: "#0d0d0d",
                    borderLeft: "1px solid rgba(255,255,255,0.05)",
                    padding: "24px 16px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 20,
                    flexShrink: 0,
                }}>
                    <SectionLabel>Tips</SectionLabel>

                    {[
                        { emoji: "📐", title: "Optimal Size", body: "Record at 492 × 1026 or any 9:16 portrait ratio for best fit." },
                        { emoji: "🖱", title: "Scale & Pan", body: "Use Scale to zoom your video in or out. Use Offset X/Y to reposition." },
                        { emoji: "🎨", title: "Backgrounds", body: "Pick a solid color, gradient, or transparent to extract just the phone for compositing." },
                        { emoji: "⬇", title: "Export", body: "Exports at 1080×1920/10Mbps. Chrome gives MP4; other browsers give WebM." },
                        { emoji: "⚡", title: "Performance", body: "Export takes real-time — same duration as your video." },
                    ].map(({ emoji, title, body }) => (
                        <div key={title} style={{
                            padding: "12px 12px",
                            background: "rgba(255,255,255,0.02)",
                            borderRadius: 10,
                            border: "1px solid rgba(255,255,255,0.05)",
                        }}>
                            <div style={{ fontSize: 16, marginBottom: 5 }}>{emoji}</div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: "#ddd", marginBottom: 4 }}>{title}</div>
                            <div style={{ fontSize: 11, color: "#666", lineHeight: 1.5 }}>{body}</div>
                        </div>
                    ))}

                    {videoError && (
                        <div style={{
                            padding: "10px 12px",
                            background: "rgba(239,68,68,0.1)",
                            border: "1px solid rgba(239,68,68,0.3)",
                            borderRadius: 10,
                            fontSize: 11, color: "#fca5a5",
                        }}>
                            ⚠ {videoError}
                        </div>
                    )}
                </aside>
            </main>

            {/* Hidden canvas used for export */}
            <canvas ref={canvasRef} style={{ display: "none" }} aria-hidden="true" />
        </div>
    )
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: draw rounded rect on canvas ctx
// ─────────────────────────────────────────────────────────────────────────────
function roundRect(
    ctx: CanvasRenderingContext2D,
    x: number, y: number, w: number, h: number, r: number
) {
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.lineTo(x + w - r, y)
    ctx.quadraticCurveTo(x + w, y, x + w, y + r)
    ctx.lineTo(x + w, y + h - r)
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
    ctx.lineTo(x + r, y + h)
    ctx.quadraticCurveTo(x, y + h, x, y + h - r)
    ctx.lineTo(x, y + r)
    ctx.quadraticCurveTo(x, y, x + r, y)
    ctx.closePath()
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers: style factories
// ─────────────────────────────────────────────────────────────────────────────
function navTabStyle(active: boolean): React.CSSProperties {
    return {
        padding: "7px 14px", borderRadius: 8, fontSize: 12, fontWeight: 500,
        textDecoration: "none", cursor: "pointer",
        border: active ? "1.5px solid #a78bfa" : "1.5px solid rgba(255,255,255,0.08)",
        background: active ? "rgba(167,139,250,0.12)" : "rgba(255,255,255,0.03)",
        color: active ? "#c4b5fd" : "#888",
        transition: "all 0.15s",
        display: "inline-block",
    }
}

function btnStyle(variant: "primary" | "secondary" | "ghost", disabled = false): React.CSSProperties {
    const base: React.CSSProperties = {
        padding: "8px 16px",
        borderRadius: 10,
        fontSize: 13,
        fontWeight: 500,
        cursor: disabled ? "not-allowed" : "pointer",
        border: "none",
        opacity: disabled ? 0.5 : 1,
        transition: "all 0.15s",
        letterSpacing: "-0.01em",
        fontFamily: "inherit",
        whiteSpace: "nowrap",
    }
    if (variant === "primary") return {
        ...base,
        background: "linear-gradient(135deg, #7c5cbf, #a78bfa)",
        color: "#fff",
        boxShadow: "0 2px 12px rgba(167,139,250,0.3)",
    }
    if (variant === "secondary") return {
        ...base,
        background: "rgba(255,255,255,0.08)",
        color: "#ddd",
        border: "1px solid rgba(255,255,255,0.1)",
    }
    return {
        ...base,
        background: "transparent",
        color: "#999",
    }
}

function SectionLabel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "#555",
            marginBottom: 12,
            ...style,
        }}>
            {children}
        </div>
    )
}
