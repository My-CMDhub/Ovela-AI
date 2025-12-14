"use client";

import { useEffect, useState, useCallback } from "react";
import { client, databases, DATABASE_ID } from "@/lib/appwrite";
import { Query } from "appwrite";
import KPICard from "@/components/dashboard/KPICard";
import { Calendar, Users, MessageSquare, Activity, Wifi, WifiOff, Flame, Zap } from "lucide-react";
import { motion } from "framer-motion";
import { useTheme } from "@/contexts/ThemeContext";

// Backend API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Booking {
    $id: string;
    service_name: string;
    booking_date: string;
    booking_time: string;
    status: string;
    customer_name: string;
    customer_email: string;
}

interface Conversation {
    $id: string;
    whatsapp_id: string;
    last_message: string;
    $updatedAt: string;
}

export default function DashboardPage() {
    const { theme, industry } = useTheme();
    const [todayBookings, setTodayBookings] = useState<Booking[]>([]);
    const [upcomingCount, setUpcomingCount] = useState(0);
    const [totalCustomers, setTotalCustomers] = useState(0);
    const [activeConversations, setActiveConversations] = useState(0);
    const [recentActivity, setRecentActivity] = useState<Conversation[]>([]);
    const [loading, setLoading] = useState(true);
    const [isLive, setIsLive] = useState(false);
    const [privacyMode, setPrivacyMode] = useState(false);

    const fetchDashboardData = useCallback(async () => {
        try {
            const [statsRes, bookingsRes] = await Promise.all([
                fetch(`${API_URL}/api/dashboard/stats`).then(r => r.json()).catch(() => null),
                fetch(`${API_URL}/api/dashboard/bookings/today`).then(r => r.json()).catch(() => null)
            ]);

            if (statsRes?.success) setUpcomingCount(statsRes.upcoming_appointments || 0);
            if (bookingsRes?.success) setTodayBookings(bookingsRes.bookings || []);

            try {
                const conversationsRes = await databases.listDocuments(DATABASE_ID, "conversations", [Query.equal("status", "active")]);
                setActiveConversations(conversationsRes.total);

                const recentRes = await databases.listDocuments(DATABASE_ID, "conversations", [Query.orderDesc("$updatedAt"), Query.limit(5)]);
                setRecentActivity(recentRes.documents as unknown as Conversation[]);

                const customersRes = await databases.listDocuments(DATABASE_ID, "customers", [Query.limit(1)]);
                setTotalCustomers(customersRes.total);
            } catch (appwriteErr) {
                console.log("Appwrite fetch skipped:", appwriteErr);
            }

        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDashboardData();

        let unsubscribe: (() => void) | undefined;

        try {
            if (client && typeof client.subscribe === 'function') {
                unsubscribe = client.subscribe(`databases.${DATABASE_ID}.collections.conversations.documents`, () => fetchDashboardData());
                setIsLive(true);
            }
        } catch { setIsLive(false); }

        const pollInterval = setInterval(fetchDashboardData, 30000);

        return () => {
            if (unsubscribe) unsubscribe();
            clearInterval(pollInterval);
        };
    }, [fetchDashboardData]);

    const formatTime = (timeProp: string) => {
        try {
            if (timeProp.includes(":") && timeProp.length === 5) {
                const [h, m] = timeProp.split(":");
                const date = new Date();
                date.setHours(parseInt(h), parseInt(m));
                return date.toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", timeZone: "Australia/Melbourne" });
            }
            return new Date(timeProp).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", timeZone: "Australia/Melbourne" });
        } catch { return "—"; }
    };

    if (loading) {
        return (
            <div className="animate-pulse space-y-6">
                <div className="h-8 w-48 bg-muted rounded" />
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="h-32 bg-muted rounded-xl" />
                    ))}
                </div>
            </div>
        );
    }

    // === CARD STYLING BASED ON INDUSTRY ===
    const getCardClass = () => {
        if (industry === "beauty") return "glass-panel rounded-2xl overflow-hidden";
        if (industry === "fitness") return "bg-card border-2 border-primary/20 rounded-xl overflow-hidden";
        return "bg-card border border-border rounded-lg shadow-sm overflow-hidden"; // Medical default
    };

    const getHeaderClass = () => {
        if (industry === "beauty") return "p-4 border-b border-white/20 flex items-center justify-between";
        if (industry === "fitness") return "p-4 border-b-2 border-primary/30 flex items-center justify-between bg-primary/5";
        return "p-4 border-b border-border flex items-center justify-between bg-secondary/30"; // Medical
    };

    const getItemHoverClass = () => {
        if (industry === "beauty") return "hover:bg-white/30";
        if (industry === "fitness") return "hover:bg-primary/10";
        return "hover:bg-secondary/50"; // Medical
    };

    return (
        <div>
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                        {theme.terminology.dashboard}
                        <span className="text-2xl">{theme.personality.emoji}</span>
                    </h1>
                    <p className="text-muted-foreground mt-1 text-sm">{theme.personality.greeting}</p>
                </div>

                <div className="flex items-center gap-4">
                    {industry === "health" && (
                        <button
                            onClick={() => setPrivacyMode(!privacyMode)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors ${privacyMode ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border"}`}
                        >
                            <Users className="w-3 h-3" /> {privacyMode ? "Privacy On" : "Privacy Off"}
                        </button>
                    )}

                    {industry === "fitness" && (
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md border-2 border-primary/50 text-xs font-bold text-primary bg-primary/10">
                            <Flame className="w-3 h-3" />
                            <span>STREAK: 7 days</span>
                        </div>
                    )}

                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs font-medium ${isLive ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:border-emerald-900" : "bg-muted text-muted-foreground border-border"}`}>
                        {isLive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                        {isLive ? "Online" : "Offline"}
                    </div>
                </div>
            </div>

            {/* KPI Cards */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
            >
                <KPICard
                    title={theme.metrics.primary}
                    value={todayBookings.length}
                    icon={Calendar}
                    subtitle={`${upcomingCount} upcoming`}
                />
                <KPICard
                    title={industry === "fitness" ? "Active Members" : theme.metrics.secondary}
                    value={totalCustomers}
                    icon={Users}
                />
                <KPICard
                    title={industry === "fitness" ? "Classes Booked" : "Active Inquiries"}
                    value={activeConversations}
                    icon={MessageSquare}
                />
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Schedule Card */}
                <div className={getCardClass()}>
                    <div className={getHeaderClass()}>
                        <h2 className={`text-sm font-semibold uppercase tracking-wider ${industry === "fitness" ? "text-primary font-bold" : "text-foreground"}`}>
                            {theme.terminology.booking} Schedule
                        </h2>
                        <Calendar className={`w-4 h-4 ${industry === "fitness" ? "text-primary" : "text-muted-foreground"}`} />
                    </div>

                    {todayBookings.length === 0 ? (
                        <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                            <p className="text-sm">No {theme.terminology.booking.toLowerCase()}s scheduled</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-border/50">
                            {todayBookings.map((booking) => (
                                <div key={booking.$id} className={`p-4 flex items-center justify-between transition-colors ${getItemHoverClass()}`}>
                                    <div className="flex items-center gap-4">
                                        <div className={`w-14 text-sm font-bold ${industry === "fitness" ? "text-primary" : "text-foreground"}`}>
                                            {formatTime(booking.booking_time)}
                                        </div>
                                        <div>
                                            <p className={`text-sm font-medium text-foreground ${privacyMode ? "privacy-blur" : ""}`}>
                                                {booking.customer_name || "Guest"}
                                            </p>
                                            <p className="text-xs text-muted-foreground">{booking.service_name}</p>
                                        </div>
                                    </div>
                                    <span className={`inline-flex items-center px-2 py-1 rounded text-[10px] font-medium uppercase tracking-wide ${industry === "fitness"
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-primary/10 text-primary"
                                        }`}>
                                        {booking.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Activity Feed */}
                <div className={getCardClass()}>
                    <div className={getHeaderClass()}>
                        <h2 className={`text-sm font-semibold uppercase tracking-wider ${industry === "fitness" ? "text-primary font-bold" : "text-foreground"}`}>
                            {industry === "fitness" ? "Member Activity" : "Communication"}
                        </h2>
                        {industry === "fitness" ? <Zap className="w-4 h-4 text-primary" /> : <Activity className="w-4 h-4 text-muted-foreground" />}
                    </div>

                    {recentActivity.length === 0 ? (
                        <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                            <p className="text-sm">No recent activity</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-border/50">
                            {recentActivity.map((conv) => (
                                <div key={conv.$id} className={`p-4 flex items-start justify-between transition-colors ${getItemHoverClass()}`}>
                                    <div className="flex gap-3 overflow-hidden">
                                        <div className="mt-1">
                                            <div className={`w-2 h-2 rounded-full animate-pulse ${industry === "fitness" ? "bg-primary" : "bg-primary"}`} />
                                        </div>
                                        <div className="min-w-0">
                                            <p className={`text-sm font-medium text-foreground ${privacyMode ? "privacy-blur" : ""}`}>
                                                {conv.whatsapp_id}
                                            </p>
                                            <p className="text-xs text-muted-foreground truncate max-w-[200px] mt-0.5">
                                                {industry === "fitness" ? "Member inquiry..." : (conv.last_message || "No content")}
                                            </p>
                                        </div>
                                    </div>
                                    <span className="text-[10px] text-muted-foreground font-mono">
                                        {new Date(conv.$updatedAt).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" })}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
