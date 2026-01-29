"use client";

import { useState, useEffect, useCallback } from "react";
import { columns, CallLog } from "@/components/call-logs/columns";
import { DataTable } from "@/components/call-logs/data-table";
import {
    RefreshCw,
    Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";

import { useAuth } from "@/contexts/AuthContext";
import { client, DATABASE_ID } from "@/lib/appwrite";

const API_URL = "";
// Force relative path to use Next.js Proxy (route.ts) for auth and routing.

export default function CallLogsPage() {
    const { user } = useAuth();
    const [logs, setLogs] = useState<CallLog[]>([]);
    const [loading, setLoading] = useState(true); // Initial load
    const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

    // Transcript Modal State (Simple dialog for now or inline expansion)
    // The data-table handles row clicks? Yes, passed to DataTable

    const fetchLogs = useCallback(async (isBackground = false) => {
        if (!isBackground) setLoading(true);
        try {
            // Fetch ALL recent logs for client-side filtering functionality 
            // (fixes the "jitter" and "friction" of server-side filtering for this size)
            const params = new URLSearchParams();
            params.append("limit", "200"); // Fetch decent chunk

            // Pass Tenant ID if authenticated
            if (user?.prefs && 'tenant_id' in user.prefs) {
                params.append("tenant_id", user.prefs['tenant_id'] as string);
            }

            const res = await fetch(`${API_URL}/api/dashboard/call-logs?${params.toString()}`);
            const data = await res.json();

            if (data.success) {
                setLogs(data.logs || []);
                setLastRefreshed(new Date());
            }
        } catch (error) {
            console.error("Failed to fetch call logs:", error);
        } finally {
            if (!isBackground) setLoading(false);
        }
    }, [user]);

    useEffect(() => {
        if (user) {
            fetchLogs();
        }

        // --- REALTIME SUBSCRIPTION ---
        if (!user) return;

        const tenantId = ((user.prefs as any)['tenant_id'] as string) || "coalcreek";
        const collectionId = `call_transcripts_${tenantId}`;

        console.log(`📡 Subscribing to realtime updates for: ${collectionId}`);

        const unsubscribe = client.subscribe(
            `databases.${DATABASE_ID}.collections.${collectionId}.documents`,
            (response) => {
                // When a new transcript record is CREATED
                if (response.events.some(e => e.includes(".create"))) {
                    console.log("🆕 New call log detected via Realtime!");
                    // Re-fetch to get the fully mapped data from backend
                    fetchLogs(true);
                }
            }
        );

        return () => {
            console.log("🔌 Unsubscribing from Realtime");
            unsubscribe();
        };
    }, [fetchLogs, user]);

    const exportToCSV = () => {
        if (logs.length === 0) return;

        const headers = ["Phone", "Date", "Duration", "Exchanges", "Outcome", "Transcript"];
        const rows = logs.map(log => [
            log.phone,
            new Date(log.created_at).toLocaleString(),
            log.duration_seconds + "s",
            log.exchange_count.toString(),
            log.outcome,
            log.transcript.map(m => `[${m.role}] ${m.text}`).join(" | ").slice(0, 500)
        ]);

        const csvContent = [
            headers.join(","),
            ...rows.map(row => row.map(cell => `"${cell?.replace(/"/g, '""') || ''}"`).join(","))
        ].join("\n");

        const blob = new Blob([csvContent], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `call-logs-${new Date().toISOString().split("T")[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900">Call Logs</h1>
                    <p className="text-slate-600 mt-2">
                        Real-time AI conversation history.
                        <span className="text-xs ml-2 opacity-60">Last updated: {lastRefreshed.toLocaleTimeString()}</span>
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        onClick={exportToCSV}
                        className="bg-white border-slate-200 text-slate-900 hover:bg-slate-50"
                    >
                        <Download className="w-4 h-4 mr-2" />
                        Export CSV
                    </Button>
                    <Button
                        variant="outline"
                        onClick={() => fetchLogs(false)}
                        className="bg-white"
                    >
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Main Table */}
            <DataTable
                columns={columns}
                data={logs}
                loading={loading}
                onRowClick={(log) => {
                    // Logic to open transcript could go here
                    // For now we rely on the row actions/expansion in columns or simplistic expansion
                    // Let's implement a quick detail view if we have time, 
                    // relying on alert for quick debug or just simple expansion?
                    // The columns.tsx already has an action menu.
                    // Let's print to console or handle expansion later.
                    console.log("Clicked", log);
                }}
            />
        </div>
    );
}
