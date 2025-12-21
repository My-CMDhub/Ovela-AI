"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    CalendarCheck,
    BedDouble,
    Users,
    Clock,
    ArrowUpRight,
    ArrowDownRight,
    Sun,
    Moon,
    Phone,
    TrendingUp,
} from "lucide-react";

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

export default function MotelDashboard() {
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
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            const [statsRes, reservationsRes] = await Promise.all([
                fetch("/api/motel/stats"),
                fetch("/api/motel/reservations?limit=5"),
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
            case "pending": return "bg-yellow-100 text-yellow-700";
            case "checked_in": return "bg-blue-100 text-blue-700";
            case "cancelled": return "bg-red-100 text-red-700";
            default: return "bg-gray-100 text-gray-700";
        }
    };

    const getRoomTypeIcon = (type: string) => {
        switch (type) {
            case "queen": return "👑";
            case "twin": return "🛏️";
            case "family": return "👨‍👩‍👧‍👦";
            case "accessible": return "♿";
            default: return "🏨";
        }
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
                    <h1 className="text-2xl font-bold text-gray-900">
                        Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}!
                    </h1>
                    <p className="text-gray-600 mt-1">
                        Here's what's happening at The Lydoun today
                    </p>
                </div>
                <div className="text-sm text-gray-500">
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
                        className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
                    >
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-sm text-gray-500 font-medium">{card.title}</p>
                                <p className="text-3xl font-bold text-gray-900 mt-2">
                                    {loading ? "—" : card.value}
                                </p>
                                {card.subtitle && (
                                    <p className="text-xs text-gray-400 mt-1">{card.subtitle}</p>
                                )}
                            </div>
                            <div className={`p-3 rounded-xl ${card.bg}`}>
                                <card.icon className={`w-6 h-6 ${card.color}`} />
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
                    className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100"
                >
                    <div className="p-6 border-b border-gray-100">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-gray-900">
                                Recent Reservations
                            </h2>
                            <a
                                href="/motel/reservations"
                                className="text-sm text-[#8B2332] hover:underline font-medium"
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
                                    className="p-4 hover:bg-gray-50 transition-colors"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 bg-[#8B2332]/10 rounded-xl flex items-center justify-center text-lg">
                                                {getRoomTypeIcon(res.room_type)}
                                            </div>
                                            <div>
                                                <p className="font-medium text-gray-900">
                                                    {res.guest_name}
                                                </p>
                                                <p className="text-sm text-gray-500">
                                                    {res.room_type?.charAt(0).toUpperCase() + res.room_type?.slice(1)} Room
                                                    {" · "}
                                                    {formatDate(res.check_in_date)} → {formatDate(res.check_out_date)}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(res.status)}`}>
                                                {res.status}
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
                    {/* Room Status Summary */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                        <h3 className="font-semibold text-gray-900 mb-4">Room Status</h3>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-gray-600">Queen Rooms</span>
                                <span className="text-sm font-medium">6 total</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-gray-600">Twin Rooms</span>
                                <span className="text-sm font-medium">4 total</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-gray-600">Family Rooms</span>
                                <span className="text-sm font-medium">3 total</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-gray-600">Accessible</span>
                                <span className="text-sm font-medium">2 total</span>
                            </div>
                        </div>
                    </div>

                    {/* Voice AI Status */}
                    <div className="bg-gradient-to-br from-[#8B2332] to-[#6B1A26] rounded-2xl p-6 text-white">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                                <Phone className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="font-semibold">Voice AI</h3>
                                <p className="text-sm text-white/70">Ovela Receptionist</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 mb-3">
                            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                            <span className="text-sm">Active & Ready</span>
                        </div>
                        <p className="text-sm text-white/60">
                            Answering calls 24/7, booking rooms, and helping guests
                        </p>
                    </div>
                </motion.div>
            </div>
        </div>
    );
}
