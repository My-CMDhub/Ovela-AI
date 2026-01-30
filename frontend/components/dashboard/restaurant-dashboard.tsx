"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    LayoutDashboard,
    Phone,
    PhoneMissed,
    PhoneIncoming,
    Clock,
    ArrowRight,
    ExternalLink
} from "lucide-react";
import { useTenant } from "@/contexts/TenantContext";
import { client, DATABASE_ID } from "@/lib/appwrite";
import Link from "next/link";

interface CallLog {
    id: string;
    phone: string;
    duration_seconds: number;
    outcome: string;
    sms_status?: string;
    created_at: string;
}

export default function RestaurantDashboard() {
    const { tenant } = useTenant();
    const [stats, setStats] = useState({
        totalCalls: 0,
        missedCalls: 0,
        avgDuration: "0s",
    });
    const [recentCalls, setRecentCalls] = useState<CallLog[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchCalls = async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const res = await fetch(`/api/dashboard/call-logs?limit=5&tenant_id=${tenant.id}`);
            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    setRecentCalls(data.logs);

                    const avgSecs = data.counts?.avg_duration || 0;
                    const mins = Math.floor(avgSecs / 60);
                    const secs = Math.round(avgSecs % 60);
                    const avgStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

                    setStats({
                        totalCalls: data.counts?.all || 0,
                        missedCalls: data.counts?.issues || 0,
                        avgDuration: avgStr
                    });
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchCalls();

        const collectionId = `call_transcripts_${tenant.id}`;
        console.log(`📡 Subscribing to: ${collectionId}`);

        const unsubscribe = client.subscribe(
            `databases.${DATABASE_ID}.collections.${collectionId}.documents`,
            (response) => {
                if (response.events.some(e => e.includes(".create") || e.includes(".update"))) {
                    fetchCalls(true);
                }
            }
        );

        return () => unsubscribe();
    }, [tenant.id]);

    const kpiCards = [
        {
            title: "Total Calls Today",
            value: stats.totalCalls,
            icon: PhoneIncoming,
            color: "text-blue-500",
            bg: "bg-blue-50",
        },
        {
            title: "Missed/Issues",
            value: stats.missedCalls,
            icon: PhoneMissed,
            color: "text-red-500",
            bg: "bg-red-50",
        },
        {
            title: "Avg Call Time",
            value: stats.avgDuration,
            icon: Clock,
            color: "text-emerald-500",
            bg: "bg-emerald-50",
        },
    ];

    return (
        <div className="space-y-6">
            {/* Unique Restaurant Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">
                        {tenant.name} Dashboard
                    </h1>
                    <p className="text-gray-600 mt-1">
                        Voice AI Summary
                    </p>
                </div>

                {/* Square Integration Badge */}
                <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full text-xs font-medium text-gray-600 border border-gray-200">
                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                    Square POS Connected
                </div>
            </div>

            {/* Quick Actions Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <motion.a
                    href="https://squareup.com/dashboard"
                    target="_blank"
                    rel="noopener noreferrer"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="group relative overflow-hidden bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl p-8 text-white shadow-lg hover:shadow-xl transition-all"
                >
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <LayoutDashboard className="w-32 h-32" />
                    </div>

                    <div className="relative z-10">
                        <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center mb-4 text-white">
                            <LayoutDashboard className="w-6 h-6" />
                        </div>
                        <h3 className="text-xl font-bold mb-2">Open Square POS</h3>
                        <p className="text-gray-400 mb-6 max-w-sm">
                            Manage orders, menu items, and table bookings directly in your Square Dashboard.
                        </p>
                        <div className="flex items-center gap-2 text-sm font-medium text-white group-hover:gap-3 transition-all">
                            Launch Dashboard <ExternalLink className="w-4 h-4" />
                        </div>
                    </div>
                </motion.a>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100"
                >
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center text-blue-500">
                                <Phone className="w-6 h-6" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-gray-900">Phone Activity</h3>
                                <p className="text-sm text-gray-500">Today's metrics</p>
                            </div>
                        </div>
                        <span className="flex h-3 w-3 relative">
                            <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                        </span>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        {kpiCards.map((card) => (
                            <div key={card.title} className="text-center p-3 rounded-lg bg-gray-50">
                                <card.icon className={`w-5 h-5 mx-auto mb-2 ${card.color}`} />
                                <div className="text-xl font-bold text-gray-900">{card.value}</div>
                                <div className="text-xs text-gray-500">{card.title}</div>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </div>

            {/* Recent Calls List */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
            >
                <div className="p-6 border-b border-gray-100 flex justify-between items-center">
                    <h3 className="font-semibold text-gray-900">Recent Customer Calls</h3>
                    <Link href="/dashboard/call-logs" className="text-sm font-medium text-blue-500 hover:text-blue-600 flex items-center gap-1">
                        View All <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>
                <div className="divide-y divide-gray-50">
                    {recentCalls.length === 0 ? (
                        <div className="p-8 text-center text-gray-400">No recent calls</div>
                    ) : (
                        recentCalls.map((call) => (
                            <div key={call.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-500">
                                        <Phone className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-gray-900">{call.phone}</p>
                                        <p className="text-xs text-gray-500">
                                            {new Date(call.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </p>
                                    </div>
                                </div>
                                <span className={`text-xs px-2 py-1 rounded-full ${call.outcome === 'completed' || call.outcome === 'transferred'
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-red-100 text-red-700'
                                    }`}>
                                    {call.outcome}
                                </span>
                                {call.sms_status && call.sms_status !== 'none' && (
                                    <span className={`ml-2 text-xs px-2 py-1 rounded-full ${call.sms_status === 'sent'
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'bg-yellow-100 text-yellow-700'
                                        }`}>
                                        SMS: {call.sms_status}
                                    </span>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </motion.div>
        </div>
    );
}
