"use client";

import { useState, useEffect, useCallback } from "react";
import {
    Phone,
    Clock,
    RefreshCw,
    User,
    ChevronDown,
    ChevronUp,
    Search,
    Calendar,
    Download,
    CheckCircle,
    AlertTriangle,
    MessageSquare
} from "lucide-react";

interface TranscriptMessage {
    role: "ai" | "user";
    text: string;
    timestamp: string;
}

interface CallLog {
    id: string;
    phone: string;
    created_at: string;
    duration_seconds: number;
    exchange_count: number;
    outcome: string;
    transcript: TranscriptMessage[];
    call_sid: string;
}

interface TabCounts {
    completed: number;
    issues: number;
    all: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ovela-12c561a30285.herokuapp.com";

export default function CallLogsPage() {
    const [logs, setLogs] = useState<CallLog[]>([]);
    const [counts, setCounts] = useState<TabCounts>({ completed: 0, issues: 0, all: 0 });
    const [filter, setFilter] = useState<string>("completed");
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    // Filters
    const [phoneSearch, setPhoneSearch] = useState("");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const fetchLogs = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.append("status", filter);
            if (phoneSearch) params.append("phone", phoneSearch);
            if (startDate) params.append("start_date", startDate);
            if (endDate) params.append("end_date", endDate);

            const res = await fetch(`${API_URL}/api/motel/call-logs?${params.toString()}`);
            const data = await res.json();

            if (data.success) {
                setLogs(data.logs || []);
                setCounts(data.counts || { completed: 0, issues: 0, all: 0 });
            }
        } catch (error) {
            console.error("Failed to fetch call logs:", error);
        } finally {
            setLoading(false);
        }
    }, [filter, phoneSearch, startDate, endDate]);

    useEffect(() => {
        fetchLogs();

        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchLogs, 30000);
        return () => clearInterval(interval);
    }, [fetchLogs]);

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return "N/A";
        try {
            return new Date(dateStr).toLocaleDateString("en-AU", {
                weekday: "short",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return dateStr;
        }
    };

    const getOutcomeBadge = (outcome: string) => {
        switch (outcome) {
            case "completed":
            case "booking_completed":
                return <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Completed</span>;
            case "transferred":
                return <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full flex items-center gap-1"><Phone className="w-3 h-3" /> Transferred</span>;
            case "timeout_silence":
            case "timeout_duration":
                return <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs rounded-full flex items-center gap-1"><Clock className="w-3 h-3" /> Timeout</span>;
            case "spam_terminated":
            case "abuse_timeout":
                return <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Issue</span>;
            default:
                return <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full">{outcome}</span>;
        }
    };

    const exportToCSV = () => {
        if (logs.length === 0) return;

        const headers = ["Phone", "Date", "Duration", "Exchanges", "Outcome", "Transcript Summary"];
        const rows = logs.map(log => [
            log.phone,
            log.created_at,
            formatDuration(log.duration_seconds),
            log.exchange_count.toString(),
            log.outcome,
            log.transcript.map(m => `[${m.role.toUpperCase()}] ${m.text}`).join(" | ").slice(0, 200) + "..."
        ]);

        const csvContent = [
            headers.join(","),
            ...rows.map(row => row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(","))
        ].join("\n");

        const blob = new Blob([csvContent], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `call-logs-${new Date().toISOString().split("T")[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const toggleExpand = (id: string) => {
        setExpandedId(expandedId === id ? null : id);
    };

    return (
        <div className="p-4 md:p-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Call Logs</h1>
                    <p className="text-gray-500">AI conversation transcripts with guests</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={exportToCSV}
                        className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 text-gray-700"
                    >
                        <Download className="w-4 h-4" />
                        Export CSV
                    </button>
                    <button
                        onClick={fetchLogs}
                        className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 text-gray-700"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 mb-6">
                <div className="flex flex-col md:flex-row gap-4">
                    {/* Phone Search */}
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Search Phone</label>
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input
                                type="text"
                                value={phoneSearch}
                                onChange={(e) => setPhoneSearch(e.target.value)}
                                placeholder="0412 345 678..."
                                className="w-full pl-10 pr-4 py-2 border border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:text-white"
                            />
                        </div>
                    </div>

                    {/* Date Range */}
                    <div className="flex gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">From</label>
                            <div className="relative">
                                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                <input
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="pl-10 pr-4 py-2 border border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:text-white"
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">To</label>
                            <div className="relative">
                                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                <input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="pl-10 pr-4 py-2 border border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:text-white"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Filter Tabs */}
            <div className="flex flex-wrap gap-2 mb-6">
                {[
                    { key: "completed", label: "Completed", count: counts.completed },
                    { key: "issues", label: "Issues", count: counts.issues },
                    { key: "all", label: "All Calls", count: counts.all },
                ].map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setFilter(tab.key)}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${filter === tab.key
                            ? "bg-[#8B2332] text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                            }`}
                    >
                        {tab.label}
                        {tab.count > 0 && (
                            <span className={`px-1.5 py-0.5 text-xs rounded-full ${filter === tab.key
                                ? "bg-white/20 text-white"
                                : "bg-gray-200 text-gray-600"
                                }`}>
                                {tab.count}
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* Call Logs List */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#8B2332]"></div>
                </div>
            ) : logs.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-xl">
                    <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No call logs found</p>
                    <p className="text-sm text-gray-400 mt-1">Try adjusting your filters</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {logs.map((log) => (
                        <div
                            key={log.id}
                            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-md transition-shadow"
                        >
                            {/* Card Header */}
                            <div
                                className="p-4 md:p-6 cursor-pointer"
                                onClick={() => toggleExpand(log.id)}
                            >
                                <div className="flex flex-col lg:flex-row justify-between items-start gap-4">
                                    <div className="space-y-2 flex-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            {getOutcomeBadge(log.outcome)}
                                            <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                {formatDuration(log.duration_seconds)}
                                            </span>
                                            <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full flex items-center gap-1">
                                                <MessageSquare className="w-3 h-3" />
                                                {log.exchange_count} exchanges
                                            </span>
                                        </div>

                                        <div className="flex items-center gap-3">
                                            <User className="w-5 h-5 text-gray-400" />
                                            <a
                                                href={`tel:${log.phone}`}
                                                className="font-medium text-gray-900 dark:text-white hover:text-[#8B2332]"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                {log.phone}
                                            </a>
                                        </div>

                                        {/* Preview of first message */}
                                        {log.transcript.length > 0 && (
                                            <p className="text-sm text-gray-500 line-clamp-2">
                                                {log.transcript.slice(0, 2).map(m =>
                                                    `[${m.role.toUpperCase()}] ${m.text}`
                                                ).join(" → ")}
                                            </p>
                                        )}

                                        <p className="text-xs text-gray-400">
                                            {formatDate(log.created_at)}
                                        </p>
                                    </div>

                                    {/* Expand/Collapse Button */}
                                    <div className="flex items-center gap-2">
                                        <a
                                            href={`tel:${log.phone}`}
                                            onClick={(e) => e.stopPropagation()}
                                            className="flex items-center gap-2 px-3 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200"
                                        >
                                            <Phone className="w-4 h-4" />
                                            Call Back
                                        </a>
                                        <button className="p-2 hover:bg-gray-100 rounded-lg">
                                            {expandedId === log.id ? (
                                                <ChevronUp className="w-5 h-5 text-gray-400" />
                                            ) : (
                                                <ChevronDown className="w-5 h-5 text-gray-400" />
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Expanded Transcript */}
                            {expandedId === log.id && (
                                <div className="border-t border-gray-200 dark:border-gray-700 p-4 md:p-6 bg-gray-50 dark:bg-gray-900">
                                    <h4 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                                        <MessageSquare className="w-4 h-4" />
                                        Conversation Transcript
                                    </h4>
                                    <div className="space-y-3 max-h-96 overflow-y-auto">
                                        {log.transcript.map((message, idx) => (
                                            <div
                                                key={idx}
                                                className={`flex ${message.role === 'ai' ? 'justify-start' : 'justify-end'}`}
                                            >
                                                <div
                                                    className={`max-w-[80%] p-3 rounded-lg ${message.role === 'ai'
                                                            ? 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                                                            : 'bg-[#8B2332] text-white'
                                                        }`}
                                                >
                                                    <p className="text-xs font-semibold mb-1 opacity-70">
                                                        {message.role === 'ai' ? '🤖 AI' : '👤 Guest'}
                                                    </p>
                                                    <p className={`text-sm ${message.role === 'ai' ? 'text-gray-700 dark:text-gray-300' : 'text-white'}`}>
                                                        {message.text}
                                                    </p>
                                                    <p className="text-xs opacity-50 mt-1 text-right">
                                                        {message.timestamp}
                                                    </p>
                                                </div>
                                            </div>
                                        ))}
                                        {log.transcript.length === 0 && (
                                            <p className="text-gray-400 text-center py-4">No transcript available</p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
