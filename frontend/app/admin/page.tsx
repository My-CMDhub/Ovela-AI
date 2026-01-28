"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutDashboard, Users, AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function AdminPage() {
    const { user, loading } = useAuth();
    const router = useRouter();
    const [stats] = useState({
        tenants: 2,
        activeCalls: 0,
        alerts: 0
    });

    useEffect(() => {
        if (!loading && !user) {
            router.push("/login");
        }
    }, [user, loading, router]);

    if (loading) return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-500">Loading Admin...</div>;

    if (!user) return null;

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
            {/* Top Bar */}
            <header className="h-16 border-b border-slate-800 flex items-center justify-between px-8 bg-slate-900/50 backdrop-blur">
                <div className="flex items-center gap-3">
                    <ShieldCheck className="w-6 h-6 text-emerald-400" />
                    <h1 className="text-lg font-bold tracking-tight">Ovela <span className="text-slate-500 font-normal">Admin</span></h1>
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-400">
                    <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        Updates Live
                    </div>
                </div>
            </header>

            <main className="p-8 max-w-7xl mx-auto space-y-8">
                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                        <div className="flex justify-between items-start mb-4">
                            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                                <Users className="w-5 h-5" />
                            </div>
                            <span className="text-xs font-mono text-slate-500">TOTAL</span>
                        </div>
                        <p className="text-3xl font-bold text-white">{stats.tenants}</p>
                        <p className="text-sm text-slate-500 mt-1">Active Tenants</p>
                    </div>

                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                        <div className="flex justify-between items-start mb-4">
                            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                                <LayoutDashboard className="w-5 h-5" />
                            </div>
                            <span className="text-xs font-mono text-slate-500">LIVE</span>
                        </div>
                        <p className="text-3xl font-bold text-white max-w-full truncate">System Normal</p>
                        <p className="text-sm text-slate-500 mt-1">Status</p>
                    </div>

                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                        <div className="flex justify-between items-start mb-4">
                            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
                                <AlertTriangle className="w-5 h-5" />
                            </div>
                            <span className="text-xs font-mono text-slate-500">ATTENTION</span>
                        </div>
                        <p className="text-3xl font-bold text-white">{stats.alerts}</p>
                        <p className="text-sm text-slate-500 mt-1">Pending Alerts</p>
                    </div>
                </div>

                {/* Tenants List */}
                <div className="space-y-4">
                    <h2 className="text-lg font-semibold text-slate-200">Your Clients</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Coal Creek */}
                        <Link href="/dashboard?tenant=coalcreek" className="group relative overflow-hidden bg-slate-900 border border-slate-800 hover:border-amber-500/30 p-6 rounded-2xl transition-all hover:shadow-2xl hover:shadow-amber-500/10">
                            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="flex justify-between items-center relative z-10">
                                <div>
                                    <h3 className="text-xl font-bold text-white group-hover:text-amber-400 transition-colors">Coal Creek Motel</h3>
                                    <p className="text-sm text-slate-500 mt-1">Korumburra, VIC</p>
                                </div>
                                <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-amber-400 transform group-hover:translate-x-1 transition-all" />
                            </div>
                        </Link>

                        {/* Saranda */}
                        <Link href="/dashboard?tenant=saranda" className="group relative overflow-hidden bg-slate-900 border border-slate-800 hover:border-sky-500/30 p-6 rounded-2xl transition-all hover:shadow-2xl hover:shadow-sky-500/10">
                            <div className="absolute inset-0 bg-gradient-to-br from-sky-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="flex justify-between items-center relative z-10">
                                <div>
                                    <h3 className="text-xl font-bold text-white group-hover:text-sky-400 transition-colors">Saranda on Hutton</h3>
                                    <p className="text-sm text-slate-500 mt-1">The Entrance, NSW</p>
                                </div>
                                <ArrowRight className="w-5 h-5 text-slate-600 group-hover:text-sky-400 transform group-hover:translate-x-1 transition-all" />
                            </div>
                        </Link>
                    </div>
                </div>
            </main>
        </div>
    );
}
