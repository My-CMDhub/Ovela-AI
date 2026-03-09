"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    CalendarCheck,
    BedDouble,
    Clock,
    Phone,
    PhoneCall,
    Timer,
    Activity,
    CheckCircle2,
} from "lucide-react";
import { fetchWithAuth } from "@/lib/api-client";
import { useTenant } from "@/contexts/TenantContext";

interface Reservation {
    $id: string;
    guest_name: string;
    guest_phone: string;
    room_type: string;
    check_in_date: string;
    check_out_date: string;
    status: string;
    booking_reference: string;
    created_at: string;
}

interface ActionLog {
    id: string;
    phone: string;
    created_at: string;
    duration_seconds: number;
    outcome: string;
    call_summary: string;
    customer_name: string;
}

interface AiStats {
    completed: number;
    issues: number;
    all: number;
    avg_duration: number;
}

interface Stats {
    todayCheckIns: number;
    todayCheckOuts: number;
    totalRooms: number;
    occupiedRooms: number;
    pendingReservations: number;
    totalGuests: number;
}

export default function ClientDashboard() {
    const { tenant } = useTenant();
    const [stats, setStats] = useState<Stats>({
        todayCheckIns: 0,
        todayCheckOuts: 0,
        totalRooms: 15,
        occupiedRooms: 0,
        pendingReservations: 0,
        totalGuests: 0,
    });
    const [aiStats, setAiStats] = useState<AiStats>({
        completed: 0,
        issues: 0,
        all: 0,
        avg_duration: 0,
    });
    const [recentReservations, setRecentReservations] = useState<Reservation[]>([]);
    const [actionLogs, setActionLogs] = useState<ActionLog[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (tenant?.id) {
            setLoading(true);
            fetchDashboardData();
        }
    }, [tenant?.id]);

    const fetchDashboardData = async () => {
        try {
            const [statsRes, reservationsRes, logsRes] = await Promise.all([
                fetchWithAuth(`/api/dashboard/stats?tenant_id=${tenant.id}`),
                fetchWithAuth(`/api/dashboard/reservations?limit=5&tenant_id=${tenant.id}`),
                fetchWithAuth(`/api/dashboard/call-logs?limit=5&tenant_id=${tenant.id}`),
            ]);

            if (statsRes.ok) {
                const data = await statsRes.json();
                if (data.success) setStats(data.stats);
            }

            if (reservationsRes.ok) {
                const data = await reservationsRes.json();
                if (data.success) setRecentReservations(data.reservations);
            }

            if (logsRes.ok) {
                const data = await logsRes.json();
                if (data.success) {
                    setActionLogs(data.logs);
                    if (data.counts) setAiStats(data.counts);
                }
            }
        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        } finally {
            setLoading(false);
        }
    };

    const occupancyRate = stats.totalRooms > 0
        ? Math.round((stats.occupiedRooms / stats.totalRooms) * 100)
        : 0;

    const formatDate = (dateStr: string) => {
        if (!dateStr) return "";
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "confirmed": return "bg-green-100 text-green-700";
            case "pending":
            case "pending_confirmation": return "bg-yellow-100 text-yellow-700";
            case "checked_in": return "bg-blue-100 text-blue-700";
            case "cancelled": return "bg-red-100 text-red-700";
            default: return "bg-gray-100 text-gray-700";
        }
    };

    const getRoomTypeIcon = (type: string) => {
        return <BedDouble className="w-5 h-5" />;
    };

    const kpiCards = [
        {
            title: "Total Calls Handled",
            value: aiStats.all,
            icon: PhoneCall,
            color: "text-blue-600",
            bg: "bg-blue-50",
        },
        {
            title: "Successful Outcomes",
            value: aiStats.completed,
            subtitle: "Bookings, FAQs, Transfers",
            icon: CheckCircle2,
            color: "text-green-600",
            bg: "bg-green-50",
        },
        {
            title: "Reception Time Saved",
            value: `${Math.round((aiStats.all * aiStats.avg_duration) / 60)} mins`,
            icon: Timer,
            color: "text-purple-600",
            bg: "bg-purple-50",
        },
        {
            title: "Pending Bookings",
            value: stats.pendingReservations,
            icon: Clock,
            color: "text-orange-600",
            bg: "bg-orange-50",
        },
    ];

    return (
        <div className="space-y-6">
            {/* Welcome Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold" style={{ color: "var(--theme-text)" }}>
                        Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}!
                    </h1>
                    <p className="mt-1" style={{ color: "var(--theme-muted)" }}>
                        Here's what's happening at {tenant.name} today
                    </p>
                </div>
                <div className="text-sm font-medium" style={{ color: "var(--theme-muted)" }}>
                    {new Date().toLocaleDateString("en-AU", {
                        weekday: "long",
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                    })}
                </div>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {kpiCards.map((card, index) => (
                    <motion.div
                        key={card.title}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="rounded-2xl p-6 shadow-sm border transition-shadow"
                        style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}
                    >
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-sm font-medium" style={{ color: "var(--theme-muted)" }}>{card.title}</p>
                                <p className="text-3xl font-bold mt-2" style={{ color: "var(--theme-text)" }}>
                                    {loading ? "—" : card.value}
                                </p>
                                {card.subtitle && (
                                    <p className="text-xs mt-1" style={{ color: "var(--theme-muted)" }}>{card.subtitle}</p>
                                )}
                            </div>
                            <div className={`p-3 rounded-xl`} style={{ backgroundColor: "var(--theme-bg)" }}>
                                <card.icon className={`w-6 h-6`} style={{ color: "var(--theme-primary)" }} />
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>

            {/* Main Content Grid */}
            <div className="grid lg:grid-cols-3 gap-6 mt-8">
                {/* Live Action Log - Ovela's core value */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="lg:col-span-2 rounded-2xl shadow-sm border overflow-hidden"
                    style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}
                >
                    <div className="p-6 border-b bg-black/5 dark:bg-white/5" style={{ borderColor: "var(--theme-border)" }}>
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: "var(--theme-text)" }}>
                                <Activity className="w-5 h-5" />
                                Live Action Log
                            </h2>
                            <div className="flex items-center gap-2">
                                <span className="relative flex h-2.5 w-2.5">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                                </span>
                                <span className="text-xs text-green-600 font-medium uppercase tracking-wider">Monitoring</span>
                            </div>
                        </div>
                    </div>
                    <div className="divide-y divide-gray-100 dark:divide-white/10 h-[450px] overflow-y-auto">
                        {loading ? (
                            <div className="p-8 text-center text-gray-400">Loading activity...</div>
                        ) : actionLogs.length === 0 ? (
                            <div className="p-12 text-center text-gray-400 flex flex-col items-center justify-center h-full">
                                <Activity className="w-12 h-12 mb-4 opacity-30" />
                                <p className="font-medium text-lg text-foreground">No recent activity</p>
                                <p className="text-sm mt-1 max-w-sm">Ovela's actions, answered calls, and captured opportunities will appear here in real-time.</p>
                            </div>
                        ) : (
                            actionLogs.map((log) => (
                                <div key={log.id} className="p-5 transition-colors hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
                                    <div className="flex items-start gap-5">
                                        <div className={`mt-1 flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center text-lg shadow-sm border ${log.outcome === 'completed' || log.outcome === 'booking_completed' ? 'bg-green-50 border-green-100 text-green-600 dark:bg-green-500/10 dark:border-green-500/20' :
                                            log.outcome === 'transferred' ? 'bg-blue-50 border-blue-100 text-blue-600 dark:bg-blue-500/10 dark:border-blue-500/20' :
                                                'bg-orange-50 border-orange-100 text-orange-600 dark:bg-orange-500/10 dark:border-orange-500/20'
                                            }`}>
                                            <PhoneCall className="w-5 h-5" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between mb-1">
                                                <p className="font-semibold text-base truncate pr-4" style={{ color: "var(--theme-text)" }}>
                                                    {log.customer_name && log.customer_name !== "Not provided" ? log.customer_name : log.phone}
                                                </p>
                                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                    {formatDate(log.created_at)}
                                                </span>
                                            </div>
                                            <p className="text-sm leading-relaxed mb-3" style={{ color: "var(--theme-muted)" }}>
                                                {log.call_summary || (log.outcome === 'completed' ? 'Successfully answered inquiry and provided assistance.' : 'Call required human transfer or intervention.')}
                                            </p>
                                            <div className="flex items-center gap-2">
                                                <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${log.outcome === 'completed' || log.outcome === 'booking_completed' ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400' :
                                                    log.outcome === 'transferred' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400' :
                                                        'bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-400'
                                                    }`}>
                                                    {log.outcome.replace("_", " ")}
                                                </span>
                                                <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium ml-2">
                                                    <Timer className="w-3.5 h-3.5" />
                                                    {Math.round(log.duration_seconds / 60)}m {log.duration_seconds % 60}s
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </motion.div>

                {/* Right Column: AI Status & Recent Reservations */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="flex flex-col gap-6"
                >
                    {/* Voice AI Status Card */}
                    <div className="rounded-2xl p-6 shadow-sm relative overflow-hidden group"
                        style={{ backgroundColor: "var(--theme-bg)", borderColor: "var(--theme-primary)", borderWidth: '1px' }}>
                        {/* Decorative glow */}
                        <div className="absolute top-0 right-0 p-8 opacity-20 transition-opacity group-hover:opacity-40" style={{ background: "radial-gradient(circle, var(--theme-primary) 0%, transparent 70%)", transform: "translate(30%, -30%)" }} />

                        <div className="relative z-10">
                            <div className="flex items-center gap-4 mb-5">
                                <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-inner"
                                    style={{ backgroundColor: "var(--theme-surface)", color: "var(--theme-primary)" }}>
                                    <Phone className="w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-lg leading-tight" style={{ color: "var(--theme-text)" }}>Voice AI</h3>
                                    <p className="text-sm font-medium opacity-80" style={{ color: "var(--theme-primary)" }}>Ovela Receptionist</p>
                                </div>
                            </div>
                            <div className="flex items-center justify-between p-3 rounded-xl mb-4" style={{ backgroundColor: "var(--theme-surface)" }}>
                                <div className="flex items-center gap-2">
                                    <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse shadow-[0_0_12px_rgba(34,197,94,0.6)]"></span>
                                    <span className="text-sm font-bold" style={{ color: "var(--theme-text)" }}>Active & Ready</span>
                                </div>
                                <span className="text-xs font-mono px-2 py-1 rounded bg-black/5 dark:bg-white/5 text-muted-foreground">v2.4.1</span>
                            </div>
                            <p className="text-sm leading-relaxed" style={{ color: "var(--theme-muted)" }}>
                                Automatically answering inbound calls, booking into PMS, and managing capacity constraints.
                            </p>
                        </div>
                    </div>

                    {/* Compact Recent Reservations */}
                    <div className="rounded-2xl shadow-sm border flex flex-col flex-1" style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}>
                        <div className="p-4 border-b bg-black/5 dark:bg-white/5" style={{ borderColor: "var(--theme-border)" }}>
                            <div className="flex items-center justify-between">
                                <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--theme-text)" }}>
                                    PMS Sync
                                </h2>
                                <CalendarCheck className="w-4 h-4 text-muted-foreground" />
                            </div>
                        </div>
                        <div className="divide-y divide-gray-100 dark:divide-white/10 flex-1 overflow-y-auto max-h-[300px]">
                            {recentReservations.length === 0 ? (
                                <div className="p-6 text-center text-sm text-muted-foreground flex flex-col items-center">
                                    <CalendarCheck className="w-8 h-8 mb-2 opacity-20" />
                                    No recent automated bookings
                                </div>
                            ) : (
                                recentReservations.map((res) => (
                                    <div key={res.$id} className="p-4 hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors">
                                        <div className="flex justify-between items-start mb-1.5">
                                            <p className="text-sm font-semibold truncate max-w-[140px]" style={{ color: "var(--theme-text)" }}>{res.guest_name}</p>
                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${getStatusColor(res.status)}`}>
                                                {res.status.replace("_", " ")}
                                            </span>
                                        </div>
                                        <div className="flex justify-between items-center mt-2">
                                            <p className="text-xs font-medium" style={{ color: "var(--theme-muted)" }}>
                                                {formatDate(res.check_in_date)}
                                            </p>
                                            <span className="text-[10px] font-mono opacity-50 bg-black/5 dark:bg-white/10 px-1.5 py-0.5 rounded">
                                                {res.booking_reference}
                                            </span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                        <div className="p-3 border-t text-center bg-black/[0.02] dark:bg-white/[0.02] rounded-b-2xl" style={{ borderColor: "var(--theme-border)" }}>
                            <a href="/dashboard/reservations" className="text-xs font-semibold hover:underline transition-all" style={{ color: "var(--theme-primary)" }}>
                                View all synced bookings →
                            </a>
                        </div>
                    </div>
                </motion.div>
            </div>
        </div>
    );
}
