"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ThemeProvider, useTheme } from "@/contexts/ThemeContext";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import { Menu, X } from "lucide-react";

// ⚠️ DEV MODE: Set to false for production
const DEV_MODE = false;

function DashboardLayoutContent({ children }: { children: React.ReactNode }) {
    const { user, loading } = useAuth();
    const { darkMode } = useTheme();
    const router = useRouter();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    useEffect(() => {
        // Skip auth redirect in dev mode
        if (DEV_MODE) return;

        if (!loading && !user) {
            router.push("/login");
        }
    }, [user, loading, router]);

    // Close sidebar when clicking outside on mobile
    useEffect(() => {
        const handleResize = () => {
            if (window.innerWidth >= 1024) {
                setSidebarOpen(false);
            }
        };
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    // Loading state (skip in dev mode)
    if (!DEV_MODE && loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "var(--theme-bg, #fafafa)" }}>
                <div className="animate-pulse" style={{ color: darkMode ? "rgb(156, 163, 175)" : "rgb(156, 163, 175)" }}>Loading...</div>
            </div>
        );
    }

    // Not authenticated (skip check in dev mode)
    if (!DEV_MODE && !user) {
        return null;
    }

    return (
        <div className="min-h-screen flex transition-colors duration-300">
            {/* Mobile Menu Button */}
            <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden fixed top-4 left-4 z-[60] p-2 rounded-lg bg-card border border-border shadow-md"
                aria-label="Toggle menu"
            >
                {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>

            {/* Overlay for mobile */}
            {sidebarOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/50 z-40"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar - hidden on mobile unless open */}
            <div className={`
                fixed lg:static inset-y-0 left-0 z-50
                transform transition-transform duration-300 ease-in-out
                ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
            `}>
                <DashboardSidebar />
            </div>

            {/* Main Content - full width on mobile */}
            <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-y-auto h-screen scrollbar-hide pt-16 lg:pt-8">
                {/* Dev mode indicator */}
                {DEV_MODE && (
                    <div className="fixed top-2 right-2 bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded-full z-50">
                        DEV MODE
                    </div>
                )}
                {children}
            </main>
        </div>
    );
}

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <AuthProvider>
            <ThemeProvider>
                <DashboardLayoutContent>{children}</DashboardLayoutContent>
            </ThemeProvider>
        </AuthProvider>
    );
}
