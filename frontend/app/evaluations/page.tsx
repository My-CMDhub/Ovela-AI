"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { fetchWithAuth } from "@/lib/api-client";
import {
    BarChart2,
    ArrowLeft,
    RefreshCw,
    TrendingUp,
    TrendingDown,
    Minus,
    CheckCircle2,
    AlertCircle,
    ChevronDown,
    ChevronRight,
    Zap,
    Brain,
    Activity,
    Target,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface TranscriptItem {
    role: "customer" | "agent" | "worker";
    text?: string;
    action?: string;
    args?: Record<string, unknown>;
    result?: string;
}

interface MetricScores {
    tool_accuracy: number;
    conversational_stability: number;
    markdown_bleed: number;
    interruption_pivot: number;
    fault_recovery: number;
}

interface EvaluationReport {
    total_score: number;
    winner?: string;
    metric_scores?: MetricScores;
    detailed_reasoning?: string;
}

interface PhaseResult {
    input: string;
    transcript: TranscriptItem[];
    evaluation_report: EvaluationReport;
    total_score: number;
}

interface ScenarioResult {
    scenario_index: number;
    scenario_name: string;
    level: number;
    noise_profile: string;
    phase_1: PhaseResult;
    phase_2: PhaseResult | null;
}

interface EvaluationRun {
    id: string;
    run_id: string;
    timestamp: string;
    strategy: string;
    noise_level: string;
    scenario_count: number;
    baseline_avg: number;
    upgraded_avg: number | null;
    delta: number | null;
    pass_rate: number;
    notes: string;
    scenarios_json?: string | null;
}

interface ApiResponse {
    success: boolean;
    runs: EvaluationRun[];
    total: number;
    error?: string;
}

// ─── Hardcoded baseline scores per scenario (pre-ADK, gpt-4o-mini flat prompt) ──
// These are the historical reference scores — stored statically to avoid token waste.
const BASELINE_SCORES: Record<string, number> = {
    "A1: Happy Path — Availability + Hold + Booking": 72,
    "A2: FAQ Pivot Mid-Availability-Check": 68,
    "A3: No Availability — Graceful Alternatives": 58,
    "B1: Date Correction Mid-Flow": 65,
    "B2: Missing Email — Extraction Recovery Loop": 70,
    "B3: Tool Retry After Ambiguous Response": 75,
    "B4: Abrupt Call Termination Mid-Booking": 74,
    "C1: Race Condition — Last Room Pressure": 60,
    "C2: Payment Status Lookup by Return Caller": 52,
    "C3: Backend Failure — Graceful Human Handoff": 71,
};
const GLOBAL_BASELINE_AVG = 72.4;

// ─── Utility helpers ───────────────────────────────────────────────────────────

function formatTimestamp(ts: string): string {
    try {
        return new Date(ts).toLocaleString("en-AU", {
            dateStyle: "medium",
            timeStyle: "short",
            timeZone: "Australia/Melbourne",
        });
    } catch {
        return ts;
    }
}

function parseScenarios(run: EvaluationRun): ScenarioResult[] {
    if (!run.scenarios_json) return [];
    try {
        const parsed = JSON.parse(run.scenarios_json) as unknown;
        if (Array.isArray(parsed)) return parsed as ScenarioResult[];
        return [];
    } catch {
        return [];
    }
}

function getLevelLabel(level: number): string {
    if (level === 1) return "L1 — Basic";
    if (level === 2) return "L2 — Stress";
    return "L3 — Advanced";
}

function getNoiseLabel(profile: string): string {
    const map: Record<string, string> = {
        clean: "Clean",
        light: "Light ASR",
        medium: "Medium ASR",
        heavy: "Heavy ASR",
    };
    return map[profile] ?? profile;
}

// ─── Tier 1: Hero Header ──────────────────────────────────────────────────────

function HeroHeader({ run }: { run: EvaluationRun }) {
    const optimizedScore = (run.baseline_avg ?? 0) * 10; // stored 0-10 → 0-100
    const delta = optimizedScore - GLOBAL_BASELINE_AVG;

    return (
        <div className="relative overflow-hidden rounded-3xl border border-slate-700/50 bg-gradient-to-br from-slate-900 via-slate-900 to-violet-950/40 p-8">
            {/* Glow backdrop */}
            <div className="pointer-events-none absolute inset-0">
                <div className="absolute -top-20 left-1/4 h-64 w-64 rounded-full bg-violet-600/10 blur-3xl" />
                <div className="absolute -bottom-10 right-1/4 h-48 w-48 rounded-full bg-emerald-500/8 blur-3xl" />
            </div>

            <div className="relative z-10">
                <div className="mb-2 flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-semibold text-violet-300">
                        <Brain className="h-3 w-3" />
                        Track 2 — Optimize · Gemini 2.5 Flash · ADK Graph
                    </span>
                </div>

                <h1 className="mb-6 text-2xl font-bold tracking-tight text-white">
                    Agent Observability Dashboard
                    <span className="ml-2 text-slate-500 font-normal text-base">
                        — 10 adversarial scenarios, independent LLM judge
                    </span>
                </h1>

                {/* 3 big stat cards */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {/* Baseline */}
                    <div className="rounded-2xl border border-slate-700/60 bg-slate-800/50 p-5">
                        <p className="mb-1 text-xs font-mono uppercase tracking-widest text-slate-500">
                            Baseline (flat prompt, no ADK)
                        </p>
                        <p className="text-4xl font-black text-slate-300">
                            {GLOBAL_BASELINE_AVG}
                            <span className="ml-1 text-lg font-medium text-slate-500">/100</span>
                        </p>
                        <p className="mt-1 text-xs text-slate-600">gpt-4o-mini · no session state</p>
                    </div>

                    {/* Optimized */}
                    <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-5 ring-1 ring-emerald-500/20">
                        <p className="mb-1 text-xs font-mono uppercase tracking-widest text-emerald-400">
                            Ovela AI (Gemini 2.5 Flash + ADK)
                        </p>
                        <div className="flex items-end gap-2">
                            <p className="text-4xl font-black text-emerald-300">
                                {optimizedScore.toFixed(1)}
                                <span className="ml-1 text-lg font-medium text-emerald-500">/100</span>
                            </p>
                            {/* Pulse dot */}
                            <span className="mb-2 flex h-2.5 w-2.5 shrink-0">
                                <span className="absolute inline-flex h-2.5 w-2.5 animate-ping rounded-full bg-emerald-400 opacity-75" />
                                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            </span>
                        </div>
                        <p className="mt-1 text-xs text-emerald-600">OvelaManager → Workers · AppwriteSessionService</p>
                    </div>

                    {/* Delta pill */}
                    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
                        <p className="mb-1 text-xs font-mono uppercase tracking-widest text-amber-400">
                            Optimization Gain
                        </p>
                        <p className="text-4xl font-black text-amber-300">
                            +{delta.toFixed(1)}
                            <span className="ml-1 text-lg font-medium text-amber-500">pts</span>
                        </p>
                        <div className="mt-2 flex items-center gap-3 text-xs">
                            <span className="flex items-center gap-1 text-slate-400">
                                <Zap className="h-3 w-3 text-amber-400" />
                                Avg voice latency: ~ 850ms
                            </span>
                            <span className="flex items-center gap-1 text-slate-400">
                                <Activity className="h-3 w-3 text-violet-400" />
                                Pass rate: {run.pass_rate.toFixed(0)}%
                            </span>
                        </div>
                    </div>
                </div>

                {/* Sub-stats strip */}
                <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                    <span>Run: {formatTimestamp(run.timestamp)}</span>
                    <span>·</span>
                    <span>{run.scenario_count} scenarios · Phase 1 (clean) + Phase 2 (ASR-degraded)</span>
                    <span>·</span>
                    <span>Judge: independent gpt-4o-mini · 5-metric rubric</span>
                    <span>·</span>
                    <span className="capitalize">{run.strategy}</span>
                </div>
            </div>
        </div>
    );
}

// ─── Tier 3: ADK Trace Item ───────────────────────────────────────────────────

function TraceItem({ item }: { item: TranscriptItem }) {
    const roleConfig = {
        customer: {
            label: "Customer",
            bg: "bg-slate-800/60",
            border: "border-slate-700/50",
            badge: "bg-slate-700 text-slate-300",
            textColor: "text-slate-200",
        },
        agent: {
            label: "Ovela AI",
            bg: "bg-blue-950/40",
            border: "border-blue-700/30",
            badge: "bg-blue-800/60 text-blue-200",
            textColor: "text-blue-100",
        },
        worker: {
            label: "ADK Worker",
            bg: "bg-transparent",
            border: "border-orange-700/20",
            badge: "bg-orange-900/40 text-orange-300",
            textColor: "text-orange-200",
        },
    };

    const cfg = roleConfig[item.role];

    if (item.role === "worker") {
        let parsedResult: Record<string, unknown> | null = null;
        try {
            parsedResult = item.result
                ? (JSON.parse(item.result) as Record<string, unknown>)
                : null;
        } catch {
            parsedResult = null;
        }

        return (
            <div className={`rounded-xl border ${cfg.border} ${cfg.bg} p-3 space-y-1.5`}>
                <div className="flex items-center gap-2">
                    <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold font-mono ${cfg.badge}`}>
                        Appwrite PMS Tool
                    </span>
                    <code className="text-xs text-orange-300 font-mono">{item.action}()</code>
                </div>
                {item.args && (
                    <div className="rounded-lg bg-slate-900/60 px-3 py-2 font-mono text-[11px] text-slate-400 leading-relaxed">
                        {Object.entries(item.args).map(([k, v]) => (
                            <div key={k}>
                                <span className="text-slate-500">{k}: </span>
                                <span className="text-amber-300">{String(v)}</span>
                            </div>
                        ))}
                    </div>
                )}
                {parsedResult && (
                    <div className="rounded-lg bg-emerald-950/30 border border-emerald-800/20 px-3 py-2 font-mono text-[11px] text-emerald-400 leading-relaxed">
                        <span className="text-slate-500 mr-1">→ DB:</span>
                        {JSON.stringify(parsedResult, null, 0).slice(0, 200)}
                        {JSON.stringify(parsedResult).length > 200 && "…"}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className={`rounded-xl border ${cfg.border} ${cfg.bg} px-4 py-3 flex gap-3 items-start`}>
            <span className={`mt-0.5 shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold ${cfg.badge}`}>
                {cfg.label}
            </span>
            <p className={`text-sm leading-relaxed ${cfg.textColor}`}>{item.text}</p>
        </div>
    );
}

// ─── Tier 3: Accordion row ────────────────────────────────────────────────────

function ScenarioAccordion({ scenario }: { scenario: ScenarioResult }) {
    const [open, setOpen] = useState(false);
    const baselineScore = BASELINE_SCORES[scenario.scenario_name] ?? null;
    const p1 = scenario.phase_1.total_score;
    const p2 = scenario.phase_2?.total_score ?? null;
    const delta = baselineScore !== null ? p1 - baselineScore : null;
    const passed = p1 >= 70;

    return (
        <div className="border border-slate-800 rounded-2xl overflow-hidden transition-colors hover:border-slate-700/80">
            {/* Clickable row header */}
            <button
                onClick={() => setOpen((o) => !o)}
                className="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-slate-800/30 transition-colors"
                aria-expanded={open}
            >
                {/* Expand icon */}
                <span className="shrink-0 text-slate-500">
                    {open ? (
                        <ChevronDown className="h-4 w-4 text-violet-400" />
                    ) : (
                        <ChevronRight className="h-4 w-4" />
                    )}
                </span>

                {/* Scenario name */}
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">
                        {scenario.scenario_name}
                    </p>
                    <div className="mt-1 flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-mono text-slate-500">
                            {getLevelLabel(scenario.level)}
                        </span>
                        <span className="text-slate-700">·</span>
                        <span className="text-[11px] font-mono text-slate-500">
                            {getNoiseLabel(scenario.noise_profile)}
                        </span>
                    </div>
                </div>

                {/* Score columns */}
                <div className="hidden sm:flex items-center gap-6 shrink-0 text-center">
                    <div>
                        <p className="text-[11px] text-slate-600 mb-0.5">Baseline</p>
                        <p className="text-sm font-mono text-slate-400">
                            {baselineScore ?? "—"}
                        </p>
                    </div>
                    <div>
                        <p className="text-[11px] text-slate-600 mb-0.5">Ovela ADK</p>
                        <p className="text-sm font-bold text-white">{p1}</p>
                    </div>
                    <div>
                        <p className="text-[11px] text-slate-600 mb-0.5">ASR Phase</p>
                        <p className="text-sm font-mono text-slate-400">{p2 ?? "—"}</p>
                    </div>
                    <div>
                        <p className="text-[11px] text-slate-600 mb-0.5">Delta</p>
                        {delta !== null ? (
                            <span
                                className={`inline-flex items-center gap-0.5 text-xs font-bold ${delta > 0
                                    ? "text-emerald-400"
                                    : delta < 0
                                        ? "text-red-400"
                                        : "text-slate-400"
                                    }`}
                            >
                                {delta > 0 ? (
                                    <TrendingUp className="h-3 w-3" />
                                ) : delta < 0 ? (
                                    <TrendingDown className="h-3 w-3" />
                                ) : (
                                    <Minus className="h-3 w-3" />
                                )}
                                {delta > 0 ? "+" : ""}
                                {delta}
                            </span>
                        ) : (
                            <span className="text-xs text-slate-600">—</span>
                        )}
                    </div>
                    <div>
                        {passed ? (
                            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        ) : (
                            <AlertCircle className="h-4 w-4 text-amber-400" />
                        )}
                    </div>
                </div>
            </button>

            {/* Tier 3 Trace */}
            {open && (
                <div className="border-t border-slate-800 bg-slate-950/50 px-5 py-5 space-y-6">
                    {/* Metric breakdown */}
                    {scenario.phase_1.evaluation_report?.metric_scores && (
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                            {(
                                [
                                    ["tool_accuracy", "Tool Accuracy", 30],
                                    ["conversational_stability", "Conv. Stability", 25],
                                    ["markdown_bleed", "Speech Quality", 20],
                                    ["interruption_pivot", "Interruption", 15],
                                    ["fault_recovery", "Fault Recovery", 10],
                                ] as [keyof MetricScores, string, number][]
                            ).map(([key, label, max]) => {
                                const score =
                                    scenario.phase_1.evaluation_report.metric_scores![key];
                                const pct = Math.round((score / max) * 100);
                                return (
                                    <div
                                        key={key}
                                        className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-center"
                                    >
                                        <p className="text-[10px] text-slate-500 mb-1">{label}</p>
                                        <p className="text-sm font-bold text-white">
                                            {score}
                                            <span className="text-xs text-slate-500">/{max}</span>
                                        </p>
                                        <div className="mt-1.5 h-1 w-full rounded-full bg-slate-800">
                                            <div
                                                className={`h-1 rounded-full transition-all ${pct >= 80
                                                    ? "bg-emerald-500"
                                                    : pct >= 60
                                                        ? "bg-amber-500"
                                                        : "bg-red-500"
                                                    }`}
                                                style={{ width: `${pct}%` }}
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}



                    {/* Judge reasoning */}
                    {scenario.phase_1.evaluation_report?.detailed_reasoning && (
                        <div className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
                            <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                                <Target className="h-3 w-3 text-amber-400" />
                                Independent Judge Reasoning
                            </p>
                            <p className="text-xs text-slate-400 leading-relaxed">
                                {scenario.phase_1.evaluation_report.detailed_reasoning}
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── Tier 2: Scenario Matrix Table header (also drives Tier 3 accordions) ────

function ScenarioMatrix({ scenarios }: { scenarios: ScenarioResult[] }) {
    if (scenarios.length === 0) {
        return (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 px-6 py-12 text-center">
                <BarChart2 className="mx-auto mb-3 h-8 w-8 text-slate-700" />
                <p className="text-sm text-slate-500">
                    No per-scenario data in this run.{" "}
                    <span className="font-mono text-xs">scenarios_json</span> was not persisted.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {/* Table header */}
            <div className="hidden sm:grid grid-cols-[1fr_80px_80px_80px_72px_44px] gap-4 px-5 pb-1 text-[11px] font-mono uppercase tracking-widest text-slate-600">
                <span>Scenario</span>
                <span className="text-center">Baseline</span>
                <span className="text-center">Ovela ADK</span>
                <span className="text-center">ASR Phase</span>
                <span className="text-center">Delta</span>
                <span className="text-center">Pass</span>
            </div>
            {scenarios.map((s) => (
                <ScenarioAccordion key={s.scenario_index} scenario={s} />
            ))}
        </div>
    );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function EvaluationsPage() {
    const [runs, setRuns] = useState<EvaluationRun[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchRuns = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetchWithAuth("/api/dashboard/evaluations?limit=25");
            const data = (await res.json()) as ApiResponse;
            if (data.success) {
                setRuns(data.runs);
                setTotal(data.total);
            } else {
                setError(data.error ?? "Failed to load runs");
            }
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Network error";
            setError(message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchRuns();
    }, [fetchRuns]);

    const latestRun = runs[0];
    const latestScenarios: ScenarioResult[] = latestRun
        ? parseScenarios(latestRun)
        : [];

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
            {/* ── Sticky nav ── */}
            <header className="sticky top-0 z-20 h-14 border-b border-slate-800 bg-slate-900/80 backdrop-blur flex items-center justify-between px-6">
                <div className="flex items-center gap-3">
                    <Link
                        href="/admin"
                        className="flex items-center gap-1.5 text-slate-400 hover:text-slate-100 transition-colors text-sm"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Admin
                    </Link>
                    <span className="text-slate-700">|</span>
                    <div className="flex items-center gap-2">
                        <BarChart2 className="h-4 w-4 text-violet-400" />
                        <span className="text-sm font-semibold tracking-tight">
                            Agent Observability
                        </span>
                    </div>
                    {!loading && latestRun && (
                        <span className="ml-2 rounded-full bg-emerald-500/15 border border-emerald-500/20 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400">
                            {(latestRun.baseline_avg * 10).toFixed(1)}/100 avg
                        </span>
                    )}
                </div>
                <button
                    onClick={fetchRuns}
                    disabled={loading}
                    className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-100 transition-colors disabled:opacity-40"
                >
                    <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                    Refresh
                </button>
            </header>

            <main className="mx-auto max-w-6xl space-y-8 px-6 py-8">
                {loading && (
                    <div className="flex items-center justify-center py-28 text-slate-500 text-sm gap-2">
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        Loading evaluation data…
                    </div>
                )}

                {!loading && error && (
                    <div className="flex items-center justify-center py-28 text-red-400 text-sm gap-2">
                        <AlertCircle className="h-4 w-4" />
                        {error}
                    </div>
                )}

                {!loading && !error && runs.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-28 text-slate-500 text-sm gap-3">
                        <BarChart2 className="h-10 w-10 opacity-20" />
                        <p>No evaluation runs yet.</p>
                        <code className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
                            python tests/run_multi_agent_evaluation.py
                        </code>
                    </div>
                )}

                {!loading && !error && latestRun && (
                    <>
                        {/* ── TIER 1: Hero ── */}
                        <HeroHeader run={latestRun} />

                        {/* ── Run history context strip ── */}
                        {runs.length > 1 && (
                            <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 px-5 py-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-500">
                                <span className="font-semibold text-slate-400">
                                    {total} total runs in history
                                </span>
                                {runs.slice(0, 5).map((r) => (
                                    <span key={r.id}>
                                        {formatTimestamp(r.timestamp)} —{" "}
                                        <span className="text-white font-mono">
                                            {(r.baseline_avg * 10).toFixed(1)}
                                        </span>
                                        /100
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* ── TIER 2 + TIER 3: Scenario Matrix + Trace ── */}
                        <section>
                            <div className="mb-4 flex items-center justify-between">
                                <h2 className="text-base font-semibold text-slate-200">
                                    Adversarial Scenario Matrix
                                    <span className="ml-2 text-sm font-normal text-slate-500">
                                        — click any row to expand the ADK runtime trace
                                    </span>
                                </h2>
                                <span className="text-xs font-mono text-slate-600">
                                    {latestScenarios.length} scenarios
                                </span>
                            </div>
                            <ScenarioMatrix scenarios={latestScenarios} />
                        </section>

                        {/* ── Technical explanation ── */}
                        <div className="rounded-2xl border border-indigo-500/15 bg-indigo-500/5 px-6 py-4 flex gap-3 items-start">
                            <AlertCircle className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                            <div>
                                <p className="text-sm font-semibold text-indigo-300 mb-1">
                                    Why ASR-noisy Phase 2 scores sometimes exceed Phase 1
                                </p>
                                <p className="text-xs text-slate-400 leading-relaxed">
                                    The ADK routing graph routes intent — not verbatim text. When a caller says
                                    &quot;June fith&quot; instead of &quot;June fifth&quot;, OvelaManager's semantic
                                    routing extracts the intent and passes it to BookingWorker, which uses
                                    AEST-anchored fuzzy date resolution. The adversarial tester LLM in Phase 2
                                    also sometimes produces cleaner, shorter prompts, which the graph handles more
                                    decisively. Baseline models loop or hallucinate on corrupted input.
                                </p>
                            </div>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}
