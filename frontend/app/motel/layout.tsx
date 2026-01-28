"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
    LayoutDashboard,
    CalendarCheck,
    Users,
    Settings,
    ChevronLeft,
    Menu,
    X,
    LogOut,
    Phone,
    Bell,
    MessageSquare,
} from "lucide-react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { TenantProvider, useTenant } from "@/contexts/TenantContext";
import SystemAlerts from "@/components/ui/system-alerts";

const navigation = [
    { name: "Dashboard", href: "/motel", icon: LayoutDashboard },
    { name: "Reservations", href: "/motel/reservations", icon: CalendarCheck },
    { name: "Guests", href: "/motel/guests", icon: Users },
    { name: "Notifications", href: "/motel/notifications", icon: Bell },
    { name: "Call Logs", href: "/motel/call-logs", icon: MessageSquare },
    { name: "Settings", href: "/motel/settings", icon: Settings },
];

function MotelLayoutContent({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();
    const { user, loading } = useAuth();
    const { tenant, isLoading: tenantLoading } = useTenant();
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [collapsed, setCollapsed] = useState(false);

    // Redirect to login if not authenticated
    useEffect(() => {
        if (!loading && !user) {
            router.push("/login");
        }
    }, [user, loading, router]);

    const isActive = (href: string) => {
        if (href === "/motel") return pathname === "/motel";
        return pathname.startsWith(href);
    };

    // Show loading state
    if (loading || tenantLoading) {
        return (
            <div className="min-h-screen bg-[#FBF8F5] flex items-center justify-center">
                <div className="text-gray-400">Loading...</div>
            </div>
        );
    }

    // Don't render if not authenticated
    if (!user) {
        return null;
    }

    return (
        <div className="min-h-screen bg-[#FBF8F5]">
            {/* Mobile sidebar overlay */}
            <AnimatePresence>
                {sidebarOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 z-40 lg:hidden"
                        onClick={() => setSidebarOpen(false)}
                    />
                )}
            </AnimatePresence>

            {/* Sidebar */}
            <aside
                className={`fixed top-0 left-0 z-50 h-full bg-gradient-to-b from-slate-900 to-slate-800 text-white transition-all duration-300 
                    ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} 
                    lg:translate-x-0
                    ${collapsed ? "lg:w-20" : "lg:w-64"}`}
            >
                {/* Logo Area */}
                <div className="h-20 flex items-center justify-between px-4 border-b border-white/10">
                    {!collapsed && (
                        <div className="flex items-center gap-3">
                            {/* Logo placeholder */}
                            <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center border transition-colors"
                                style={{
                                    backgroundColor: `${tenant.colors.primary}20`,
                                    color: tenant.colors.primary,
                                    borderColor: `${tenant.colors.primary}20`
                                }}
                            >
                                <span className="text-lg font-bold">{tenant.logoChar}</span>
                            </div>
                            <div>
                                <h1 className="font-bold text-lg leading-tight text-white">{tenant.name}</h1>
                                <p className="text-xs" style={{ color: tenant.colors.primary }}>CRM Dashboard</p>
                            </div>
                        </div>
                    )}
                    {collapsed && (
                        <div className="w-full flex justify-center">
                            <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center border"
                                style={{
                                    backgroundColor: `${tenant.colors.primary}20`,
                                    color: tenant.colors.primary,
                                    borderColor: `${tenant.colors.primary}20`
                                }}
                            >
                                <span className="text-lg font-bold">{tenant.logoChar}</span>
                            </div>
                        </div>
                    )}

                    {/* Close button for mobile */}
                    <button
                        onClick={() => setSidebarOpen(false)}
                        className="lg:hidden p-2 hover:bg-white/10 rounded-lg"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Navigation */}
                <nav className="p-4 space-y-2">
                    {navigation.map((item) => {
                        // Niche-Specific Filtering
                        if (tenant.industry === "food") {
                            // Food Niche: Hide Motel specific items
                            if (["Reservations", "Guests", "Notifications"].includes(item.name)) return null;
                        }

                        return (
                            <Link
                                key={item.name}
                                href={`${item.href}?tenant=${tenant.id}`}
                                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200
                                    ${isActive(item.href)
                                        ? "shadow-lg border"
                                        : "text-slate-400 hover:bg-white/5 hover:text-white"
                                    }
                                    ${collapsed ? "justify-center" : ""}`}
                                style={isActive(item.href) ? {
                                    backgroundColor: `${tenant.colors.primary}10`,
                                    color: tenant.colors.primary,
                                    borderColor: `${tenant.colors.primary}20`
                                } : {}}
                                title={collapsed ? item.name : undefined}
                            >
                                <item.icon className="w-5 h-5 flex-shrink-0" />
                                {!collapsed && <span className="font-medium">{item.name}</span>}
                            </Link>
                        );
                    })}

                    {/* EXT: Square Dashboard Link (Specific for Food/Saranda) */}
                    {tenant.industry === "food" && (
                        <a
                            href="https://squareup.com/dashboard" // Real link would go here
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-slate-400 hover:bg-white/5 hover:text-white ${collapsed ? "justify-center" : ""}`}
                            title={collapsed ? "Square Dashboard" : undefined}
                        >
                            <LayoutDashboard className="w-5 h-5 flex-shrink-0 text-green-500" />
                            {!collapsed && <span className="font-medium">Square POS</span>}
                        </a>
                    )}
                </nav>

                {/* Bottom Section */}
                <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-white/10">
                    {/* Collapse Toggle (desktop only) */}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="hidden lg:flex w-full items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-colors mb-2"
                    >
                        <ChevronLeft className={`w-5 h-5 transition-transform ${collapsed ? "rotate-180" : ""}`} />
                        {!collapsed && <span className="font-medium">Collapse</span>}
                    </button>

                    {/* Logout */}
                    <button
                        onClick={async () => {
                            try {
                                const { account } = await import("@/lib/appwrite");
                                await account.deleteSession("current");
                            } catch { }
                            window.location.href = "/login";
                        }}
                        className={`flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-colors w-full
                            ${collapsed ? "justify-center" : ""}`}
                    >
                        <LogOut className="w-5 h-5" />
                        {!collapsed && <span className="font-medium">Log Out</span>}
                    </button>

                    {/* Powered by Ovela */}
                    {!collapsed && (
                        <div className="mt-4 text-center">
                            <p className="text-xs text-slate-600">Powered by</p>
                            <p className="text-sm font-semibold text-slate-500">Ovela AI</p>
                        </div>
                    )}
                </div>
            </aside>

            {/* Main Content */}
            <div className={`transition-all duration-300 ${collapsed ? "lg:ml-20" : "lg:ml-64"}`}>
                {/* Top Header */}
                <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 lg:px-8 sticky top-0 z-30">
                    {/* Mobile menu button */}
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
                    >
                        <Menu className="w-5 h-5 text-gray-600" />
                    </button>

                    {/* Page title area */}
                    <div className="hidden lg:block">
                        <h2 className="text-lg font-semibold text-gray-900">
                            {navigation.find((n) => isActive(n.href))?.name || "Dashboard"}
                        </h2>
                    </div>

                    {/* Right side */}
                    <div className="flex items-center gap-4">
                        {/* Reception Phone */}
                        <div className="hidden md:flex items-center gap-2 text-sm text-gray-600">
                            <Phone className="w-4 h-4" />
                            <span>(03) 5726 1788</span>
                        </div>

                        {/* System Health Alerts */}
                        <SystemAlerts />

                        {/* Status indicator */}
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 rounded-full text-sm">
                            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                            <span className="hidden sm:inline font-medium">Voice AI Active</span>
                        </div>
                    </div>
                </header>

                {/* Page Content */}
                <main className="p-4 lg:p-8">
                    {children}
                </main>
            </div>
        </div>
    );
}

import { Suspense } from "react";

export default function MotelLayout({ children }: { children: React.ReactNode }) {
    return (
        <AuthProvider>
            <Suspense fallback={<div className="min-h-screen bg-[#FBF8F5]" />}>
                <TenantProvider>
                    <MotelLayoutContent>{children}</MotelLayoutContent>
                </TenantProvider>
            </Suspense>
        </AuthProvider>
    );
}
