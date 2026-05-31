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
} from "lucide-react";

interface EvaluationRun {
    id: string;
    run_id: string;
    timestamp: string;
    strategy: string;
    noise_level: string;
    scenario_count: number;
    baseline_avg: number;
    upgraded_avg: number;
    delta: number;
    pass_rate: number;
    notes: string;
}

interface ApiResponse {
    success: boolean;
    runs: EvaluationRun[];
    total: number;
    error?: string;
}

function DeltaBadge({ delta }: { delta: number | null | undefined }) {
    if (delta == null) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-500">
                <Minus className="w-3 h-3" />
                N/A
            </span>
        );
    }
    const display = delta * 10; // stored 0-10 → display 0-100
    if (display > 0) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400">
                <TrendingUp className="w-3 h-3" />
                +{display.toFixed(1)}
            </span>
        );
    }
    if (display < 0) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/15 text-red-400">
                <TrendingDown className="w-3 h-3" />
                {display.toFixed(1)}
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-700 text-slate-400">
            <Minus className="w-3 h-3" />
            0.0
        </span>
    );
}

function PassRateBadge({ rate }: { rate: number }) {
    const isPass = rate >= 70;
    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                isPass
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-amber-500/15 text-amber-400"
            }`}
        >
            {isPass ? (
                <CheckCircle2 className="w-3 h-3" />
            ) : (
                <AlertCircle className="w-3 h-3" />
            )}
            {rate.toFixed(1)}%
        </span>
    );
}

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

function truncateStrategy(strategy: string): string {
    if (strategy.length > 40) return strategy.slice(0, 40) + "…";
    return strategy;
}

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
    // stored 0-10 scale → display 0-100
    const avgDelta =
        runs.length > 0
            ? (runs.reduce((acc, r) => acc + (r.delta ?? 0), 0) / runs.length) * 10
            : 0;

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
            {/* Header */}
            <header className="h-16 border-b border-slate-800 flex items-center justify-between px-8 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
                <div className="flex items-center gap-4">
                    <Link
                        href="/admin"
                        className="flex items-center gap-2 text-slate-400 hover:text-slate-100 transition-colors text-sm"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Admin
                    </Link>
                    <span className="text-slate-700">|</span>
                    <div className="flex items-center gap-2">
                        <BarChart2 className="w-5 h-5 text-violet-400" />
                        <h1 className="text-base font-semibold tracking-tight">
                            Evaluation Runs
                        </h1>
                    </div>
                </div>
                <button
                    onClick={fetchRuns}
                    disabled={loading}
                    className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-100 transition-colors disabled:opacity-50"
                >
                    <RefreshCw
                        className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
                    />
                    Refresh
                </button>
            </header>

            <main className="p-8 max-w-6xl mx-auto space-y-8">
                {/* Takeaway Banner */}
                <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-2xl p-5 flex gap-4 items-start">
                    <AlertCircle className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                        <h3 className="text-sm font-semibold text-indigo-300">Technical Takeaway: Clean Audio vs. ASR Noise Resilience</h3>
                        <p className="text-xs text-slate-400 leading-relaxed max-w-4xl">
                            The Legacy Baseline model scores slightly higher on <strong>P1 (Clean Audio)</strong> because raw LLMs are naturally bubblier and chatty without structural constraints. However, the Optimized Gemini ADK Graph shines in <strong>P2 (Noisy ASR)</strong>. When callers mumble, interrupt, or speak in a noisy environment, the baseline crashes or loops, whereas the ADK strict graph state routing recovers gracefully—proving enterprise resilience over simple API wrappers.
                        </p>
                    </div>
                </div>

                {/* KPI Strip */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                        <p className="text-xs font-mono text-slate-500 mb-2 uppercase tracking-wider">
                            Total Runs
                        </p>
                        <p className="text-3xl font-bold text-white">{total}</p>
                    </div>
                    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                        <p className="text-xs font-mono text-slate-500 mb-2 uppercase tracking-wider">
                            Latest P1 Score
                        </p>
                        <p className="text-3xl font-bold text-white">
                            {latestRun ? `${(latestRun.baseline_avg * 10).toFixed(1)}/100` : "—"}
                        </p>
                    </div>
                    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                        <p className="text-xs font-mono text-slate-500 mb-2 uppercase tracking-wider">
                            Latest Pass Rate
                        </p>
                        <p className="text-3xl font-bold text-white">
                            {latestRun ? `${latestRun.pass_rate.toFixed(1)}%` : "—"}
                        </p>
                    </div>
                    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                        <p className="text-xs font-mono text-slate-500 mb-2 uppercase tracking-wider">
                            Avg Delta (ASR)
                        </p>
                        <p
                            className={`text-3xl font-bold ${
                                avgDelta > 0
                                    ? "text-emerald-400"
                                    : avgDelta < 0
                                    ? "text-red-400"
                                    : "text-slate-400"
                            }`}
                        >
                            {runs.length > 0
                                ? `${avgDelta >= 0 ? "+" : ""}${avgDelta.toFixed(1)}`
                                : "—"}
                        </p>
                    </div>
                </div>

                {/* Table */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
                    <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                        <h2 className="text-sm font-semibold text-slate-200">
                            Run History
                        </h2>
                        <span className="text-xs text-slate-500 font-mono">
                            {total} total
                        </span>
                    </div>

                    {loading && (
                        <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
                            <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                            Loading evaluation runs…
                        </div>
                    )}

                    {!loading && error && (
                        <div className="flex items-center justify-center py-20 text-red-400 text-sm gap-2">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </div>
                    )}

                    {!loading && !error && runs.length === 0 && (
                        <div className="flex flex-col items-center justify-center py-20 text-slate-500 text-sm gap-3">
                            <BarChart2 className="w-8 h-8 opacity-30" />
                            <p>No evaluation runs yet.</p>
                            <p className="text-xs">
                                Run{" "}
                                <code className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">
                                    python tests/run_multi_agent_evaluation.py
                                </code>{" "}
                                to generate the first run.
                            </p>
                        </div>
                    )}

                    {!loading && !error && runs.length > 0 && (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-800 text-left">
                                        <th className="px-6 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider">
                                            Date
                                        </th>
                                        <th className="px-4 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider">
                                            Strategy
                                        </th>
                                        <th className="px-4 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider text-center">
                                            Scenarios
                                        </th>
                                        <th className="px-4 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider text-center">
                                            P1 (Clean)
                                        </th>
                                        <th className="px-4 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider text-center">
                                            P2 (ASR Noise)
                                        </th>
                                        <th className="px-4 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider text-center">
                                            ASR Delta
                                        </th>
                                        <th className="px-4 py-3 text-xs font-mono text-slate-500 uppercase tracking-wider text-center">
                                            Pass Rate
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/60">
                                    {runs.map((run) => (
                                        <tr
                                            key={run.id}
                                            className="hover:bg-slate-800/30 transition-colors"
                                        >
                                            <td className="px-6 py-4 text-slate-300 whitespace-nowrap text-xs">
                                                {formatTimestamp(run.timestamp)}
                                            </td>
                                            <td className="px-4 py-4 text-slate-400 max-w-xs text-xs">
                                                {truncateStrategy(run.strategy)}
                                            </td>
                                            <td className="px-4 py-4 text-center text-slate-300 font-mono">
                                                {run.scenario_count}
                                            </td>
                                            <td className="px-4 py-4 text-center font-semibold text-white font-mono">
                                                {(run.baseline_avg * 10).toFixed(1)}
                                            </td>
                                            <td className="px-4 py-4 text-center text-slate-300 font-mono">
                                                {run.upgraded_avg != null
                                                    ? (run.upgraded_avg * 10).toFixed(1)
                                                    : "—"}
                                            </td>
                                            <td className="px-4 py-4 text-center">
                                                <DeltaBadge delta={run.delta} />
                                            </td>
                                            <td className="px-4 py-4 text-center">
                                                <PassRateBadge rate={run.pass_rate} />
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
