"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ThemeProvider, useTheme } from "@/contexts/ThemeContext";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";

// ⚠️ DEV MODE: Set to false for production
const DEV_MODE = false;

function DashboardLayoutContent({ children }: { children: React.ReactNode }) {
    const { user, loading } = useAuth();
    const { darkMode } = useTheme();
    const router = useRouter();

    useEffect(() => {
        // Skip auth redirect in dev mode
        if (DEV_MODE) return;

        if (!loading && !user) {
            router.push("/login");
        }
    }, [user, loading, router]);

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
            <DashboardSidebar />
            <main className="flex-1 p-8 overflow-y-auto h-screen scrollbar-hide">
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
