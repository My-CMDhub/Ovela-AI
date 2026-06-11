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
import { ThemeStudio } from "@/components/ui/theme-switcher";

const navigation = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Reservations", href: "/dashboard/reservations", icon: CalendarCheck },
    { name: "Guests", href: "/dashboard/guests", icon: Users },
    { name: "Notifications", href: "/dashboard/notifications", icon: Bell },
    { name: "Call Logs", href: "/dashboard/call-logs", icon: MessageSquare },
    { name: "Settings", href: "/dashboard/settings", icon: Settings },
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

    const isAdmin = user?.labels?.includes("admin");

    // Note: Admin switching logic removed for unified architecture and security
    // The dashboard now purely reflects the user's assigned tenant context automatically

    const isActive = (href: string) => {
        if (href === "/dashboard") return pathname === "/dashboard";
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
        <div className="min-h-screen font-sans transition-colors duration-300" style={{ backgroundColor: "var(--theme-bg)", color: "var(--theme-text)" }}>
            <ThemeStudio />
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
                className={`fixed top-0 left-0 z-50 h-full transition-all duration-300 border-r
                    ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} 
                    lg:translate-x-0
                    ${collapsed ? "lg:w-20" : "lg:w-64"}`}
                style={{
                    backgroundColor: "var(--theme-surface)",
                    borderColor: "var(--theme-border)",
                    color: "var(--theme-text)"
                }}
            >
                {/* Logo Area */}
                <div className="h-20 flex flex-col items-center justify-center border-b" style={{ borderColor: "var(--theme-border)" }}>
                    <div className="flex items-center gap-3 w-full px-6">
                        {/* Logo */}
                        <div
                            className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg shadow-sm"
                            style={{
                                backgroundColor: "var(--theme-primary)",
                                color: "var(--theme-bg)"
                            }}
                        >
                            {tenant.logoChar}
                        </div>
                        {!collapsed && (
                            <div className="flex flex-col justify-center min-w-0 flex-1">
                                <h1 className="font-bold text-base leading-tight truncate" style={{ color: "var(--theme-text)" }}>
                                    {tenant.name}
                                </h1>
                                <p className="text-xs truncate" style={{ color: "var(--theme-muted)" }}>
                                    CRM Dashboard
                                </p>
                            </div>
                        )}
                    </div>

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

                        return (
                            <Link
                                key={item.name}
                                href={`${item.href}?tenant=${tenant.id}`}
                                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-medium
                                    ${isActive(item.href) ? "shadow-sm" : "hover:bg-black/5 dark:hover:bg-white/5"}
                                    ${collapsed ? "justify-center" : ""}`}
                                style={isActive(item.href) ? {
                                    backgroundColor: "var(--theme-primary)",
                                    color: "var(--theme-bg)",
                                } : { color: "var(--theme-muted)" }}
                                title={collapsed ? item.name : undefined}
                            >
                                <item.icon className="w-5 h-5 flex-shrink-0" />
                                {!collapsed && <span className="font-medium">{item.name}</span>}
                            </Link>
                        );
                    })}
                </nav>

                {/* Bottom Section */}
                <div className="absolute bottom-0 left-0 right-0 p-4 border-t" style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-surface)" }}>
                    {/* Collapse Toggle (desktop only) */}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="hidden lg:flex w-full items-center gap-3 px-4 py-3 rounded-xl transition-colors mb-2 font-medium"
                        style={{ color: "var(--theme-muted)" }}
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
                        className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors w-full font-medium hover:bg-red-50 dark:hover:bg-red-950/30 hover:text-red-500
                            ${collapsed ? "justify-center" : ""}`}
                        style={{ color: "var(--theme-muted)" }}
                    >
                        <LogOut className="w-5 h-5" />
                        {!collapsed && <span className="font-medium">Log Out</span>}
                    </button>

                    {/* Powered by Ovela */}
                    {!collapsed && (
                        <div className="mt-4 text-center">
                            <p className="text-xs" style={{ color: "var(--theme-muted)" }}>Powered by</p>
                            <p className="text-sm font-semibold" style={{ color: "var(--theme-text)" }}>Ovela AI</p>
                        </div>
                    )}
                </div>
            </aside>

            {/* Main Content */}
            <div className={`transition-all duration-300 ${collapsed ? "lg:ml-20" : "lg:ml-64"}`}>
                {/* Top Header */}
                <header className="h-16 border-b flex items-center justify-between px-4 lg:px-8 sticky top-0 z-30"
                    style={{ backgroundColor: "var(--theme-bg)", borderColor: "var(--theme-border)" }}>
                    {/* Mobile menu button */}
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="lg:hidden p-2 rounded-lg"
                        style={{ color: "var(--theme-muted)" }}
                    >
                        <Menu className="w-5 h-5 text-gray-600" />
                    </button>

                    {/* Page title area */}
                    <div className="hidden lg:block">
                        <h2 className="text-lg font-semibold" style={{ color: "var(--theme-text)" }}>
                            {navigation.find((n) => isActive(n.href))?.name || "Dashboard"}
                        </h2>
                    </div>

                    {/* Right side */}
                    <div className="flex items-center gap-4">
                        {/* Reception Phone */}
                        <div className="hidden md:flex items-center gap-2 text-sm" style={{ color: "var(--theme-muted)" }}>
                            <Phone className="w-4 h-4" />
                            <span>{tenant.contact_phone}</span>
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
                <main className="p-4 lg:p-8 overflow-hidden relative">
                    <AnimatePresence mode="wait">
                        {children}
                    </AnimatePresence>
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
