"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    CalendarCheck,
    BedDouble,
    Clock,
    Sun,
    Moon,
    Phone,
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
    const [recentReservations, setRecentReservations] = useState<Reservation[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (tenant?.id) {
            setLoading(true);
            fetchDashboardData();
        }
    }, [tenant?.id]);

    const fetchDashboardData = async () => {
        try {
            const [statsRes, reservationsRes] = await Promise.all([
                fetchWithAuth(`/api/dashboard/stats?tenant_id=${tenant.id}`),
                fetchWithAuth(`/api/dashboard/reservations?limit=5&tenant_id=${tenant.id}`),
            ]);

            if (statsRes.ok) {
                const data = await statsRes.json();
                if (data.success) setStats(data.stats);
            }

            if (reservationsRes.ok) {
                const data = await reservationsRes.json();
                if (data.success) setRecentReservations(data.reservations);
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
            title: "Today's Check-ins",
            value: stats.todayCheckIns,
            icon: Sun,
            color: "text-amber-600",
            bg: "bg-amber-50",
        },
        {
            title: "Today's Check-outs",
            value: stats.todayCheckOuts,
            icon: Moon,
            color: "text-indigo-600",
            bg: "bg-indigo-50",
        },
        {
            title: "Occupancy Rate",
            value: `${occupancyRate}%`,
            subtitle: `${stats.occupiedRooms} of ${stats.totalRooms} rooms`,
            icon: BedDouble,
            color: "text-[#8B2332]",
            bg: "bg-red-50",
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
            <div className="grid lg:grid-cols-3 gap-6">
                {/* Recent Reservations */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="lg:col-span-2 rounded-2xl shadow-sm border"
                    style={{ backgroundColor: "var(--theme-surface)", borderColor: "var(--theme-border)" }}
                >
                    <div className="p-6 border-b" style={{ borderColor: "var(--theme-border)" }}>
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold" style={{ color: "var(--theme-text)" }}>
                                Recent Reservations
                            </h2>
                            <a
                                href="/dashboard/reservations"
                                className="text-sm hover:underline font-medium"
                                style={{ color: "var(--theme-primary)" }}
                            >
                                View all
                            </a>
                        </div>
                    </div>
                    <div className="divide-y divide-gray-50">
                        {loading ? (
                            <div className="p-8 text-center text-gray-400">
                                Loading reservations...
                            </div>
                        ) : recentReservations.length === 0 ? (
                            <div className="p-8 text-center text-gray-400">
                                <CalendarCheck className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>No reservations yet</p>
                                <p className="text-sm mt-1">Voice bookings will appear here</p>
                            </div>
                        ) : (
                            recentReservations.map((res) => (
                                <div
                                    key={res.$id}
                                    className="p-4 transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg shadow-sm" style={{ backgroundColor: "var(--theme-bg)", color: "var(--theme-primary)" }}>
                                                {getRoomTypeIcon(res.room_type)}
                                            </div>
                                            <div>
                                                <p className="font-medium" style={{ color: "var(--theme-text)" }}>
                                                    {res.guest_name}
                                                </p>
                                                <p className="text-sm" style={{ color: "var(--theme-muted)" }}>
                                                    {res.room_type?.charAt(0).toUpperCase() + res.room_type?.slice(1)} Room
                                                    {" · "}
                                                    {formatDate(res.check_in_date)} → {formatDate(res.check_out_date)}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(res.status)}`}>
                                                {res.status.replace("_", " ")}
                                            </span>
                                            <span className="text-xs text-gray-400 font-mono">
                                                {res.booking_reference}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </motion.div>

                {/* Quick Stats & Actions */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="space-y-6"
                >
                    {/* Voice AI Status */}
                    <div className="rounded-2xl p-6"
                        style={{ backgroundColor: "var(--theme-bg)", borderColor: "var(--theme-primary)", borderWidth: '1px' }}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                                style={{ backgroundColor: "var(--theme-surface)", color: "var(--theme-primary)" }}>
                                <Phone className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="font-semibold" style={{ color: "var(--theme-text)" }}>Voice AI</h3>
                                <p className="text-sm" style={{ color: "var(--theme-primary)" }}>Ovela Receptionist</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 mb-3">
                            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.5)]"></span>
                            <span className="text-sm font-medium" style={{ color: "var(--theme-text)" }}>Active & Ready</span>
                        </div>
                        <p className="text-sm" style={{ color: "var(--theme-muted)" }}>
                            Answering calls 24/7, booking rooms, and helping guests
                        </p>
                    </div>
                </motion.div>
            </div>
        </div>
    );
}
