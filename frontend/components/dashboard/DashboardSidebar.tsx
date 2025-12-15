"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
    LayoutDashboard,
    Calendar,
    MessageSquare,
    Users,
    Settings,
    LogOut,
    ClipboardList,
    HelpCircle,
    Moon,
    Sun,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";

// Animated Icons
import { Sparkles } from "@/components/animate-ui/icons/sparkles";
import { Activity } from "@/components/animate-ui/icons/activity";
import { PlugZap } from "@/components/animate-ui/icons/plug-zap";
import { Route } from "@/components/animate-ui/icons/route";
import { Layers } from "@/components/animate-ui/icons/layers";
import { ChartColumn } from "@/components/animate-ui/icons/chart-column";

// Use local Next.js API proxy (adds API key server-side)
const API_URL = "/api/dashboard";

const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/dashboard/bookings", label: "Bookings", icon: Calendar },
    { href: "/dashboard/requests", label: "Requests", icon: ClipboardList, hasBadge: true },
    { href: "/dashboard/conversations", label: "Conversations", icon: MessageSquare },
    { href: "/dashboard/customers", label: "Customers", icon: Users },
    { href: "/dashboard/settings", label: "Settings", icon: Settings },
    { href: "/dashboard/setup", label: "Setup Guide", icon: HelpCircle },
];

export default function DashboardSidebar() {
    const pathname = usePathname();
    const { logout } = useAuth();
    const { darkMode, toggleDarkMode, theme, industry } = useTheme();
    const [pendingCount, setPendingCount] = useState(0);

    useEffect(() => {
        const fetchPendingCount = async () => {
            try {
                // API key is added server-side by the proxy
                const res = await fetch(`${API_URL}/requests/pending-count`);
                const data = await res.json();
                if (data.count !== undefined) setPendingCount(data.count);
            } catch (error) {
                console.error("Failed to fetch pending count:", error);
            }
        };

        fetchPendingCount();
        const interval = setInterval(fetchPendingCount, 30000);
        return () => clearInterval(interval);
    }, []);

    const handleLogout = async () => {
        await logout();
        window.location.href = "/login";
    };

    // === INDUSTRY-SPECIFIC SIDEBAR STYLES ===
    const getSidebarClass = () => {
        if (industry === "beauty") {
            return "glass-panel border-r-0";
        }
        if (industry === "fitness") {
            return "bg-card border-r-2 border-primary/30";
        }
        return "bg-card border-r border-border";
    };

    const getActiveItemClass = () => {
        if (industry === "beauty") {
            return "bg-primary/20 text-primary font-medium shadow-sm";
        }
        if (industry === "fitness") {
            return "bg-primary text-primary-foreground font-bold";
        }
        return "bg-primary/10 text-primary font-medium";
    };

    const getActiveIndicator = () => {
        if (industry === "beauty") {
            return <div className="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 bg-primary rounded-full shadow-lg" style={{ boxShadow: '0 0 8px var(--primary)' }} />;
        }
        if (industry === "fitness") {
            return <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-primary rounded-r-full" />;
        }
        return <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full" />;
    };

    const getLogoStyle = () => {
        if (industry === "fitness") {
            return "text-2xl font-black tracking-tighter italic uppercase";
        }
        if (industry === "beauty") {
            return "text-2xl font-bold tracking-tight font-serif";
        }
        return "text-2xl font-bold tracking-tight";
    };

    // === ANIMATED BRAND ICON (Looping) ===
    const renderBrandIcon = () => {
        const getIconContainerClass = () => {
            if (industry === "beauty") return "w-10 h-10 rounded-xl bg-primary text-primary-foreground flex items-center justify-center";
            if (industry === "fitness") return "w-10 h-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center";
            if (industry === "professional") return "w-10 h-10 rounded-md bg-primary text-primary-foreground flex items-center justify-center";
            if (industry === "hospitality") return "w-10 h-10 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center";
            if (industry === "retail") return "w-10 h-10 rounded-none bg-primary text-primary-foreground flex items-center justify-center";
            return "w-10 h-10 rounded-md bg-primary text-primary-foreground flex items-center justify-center"; // health default
        };

        if (industry === "beauty") {
            return (
                <div className={getIconContainerClass()}>
                    <Sparkles size={22} animate={true} loop={true} animation="default" />
                </div>
            );
        }

        if (industry === "fitness") {
            return (
                <div className={getIconContainerClass()}>
                    <PlugZap size={22} animate={true} loop={true} animation="default" />
                </div>
            );
        }

        if (industry === "professional") {
            return (
                <div className={getIconContainerClass()}>
                    <Layers size={22} animate={true} loop={true} animation="default-loop" />
                </div>
            );
        }

        if (industry === "hospitality") {
            return (
                <div className={getIconContainerClass()}>
                    <Route size={22} animate={true} loop={true} animation="default-loop" />
                </div>
            );
        }

        if (industry === "retail") {
            return (
                <div className={getIconContainerClass()}>
                    <ChartColumn size={22} animate={true} loop={true} animation="default-loop" />
                </div>
            );
        }

        // Health/Medical default
        return (
            <div className={getIconContainerClass()}>
                <Activity size={22} animate={true} loop={true} animation="default-loop" />
            </div>
        );
    };

    return (
        <aside className={`w-64 h-[100dvh] sticky top-0 flex flex-col transition-all duration-300 z-50 ${getSidebarClass()}`}>
            {/* Logo with Animated Icon */}
            <div className={`p-6 border-b ${industry === "beauty" ? "border-white/20" : industry === "fitness" ? "border-primary/30" : "border-border"} mx-2`}>
                <Link href="/dashboard" className="block">
                    <div className="flex items-center gap-3">
                        {renderBrandIcon()}
                        <div>
                            <h1 className={`${getLogoStyle()} text-primary`}>
                                {industry === "fitness" ? "OVELA" : "Ovela"}
                            </h1>
                            <p className={`text-[10px] text-muted-foreground font-medium uppercase tracking-wider ${industry === "fitness" ? "font-bold" : ""}`}>
                                {theme.name}
                            </p>
                        </div>
                    </div>
                </Link>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 overflow-y-auto">
                <ul className="space-y-1">
                    {navItems.map((item) => {
                        const isActive =
                            pathname === item.href ||
                            (item.href !== "/dashboard" && pathname.startsWith(item.href));

                        return (
                            <li key={item.href}>
                                <Link
                                    href={item.href}
                                    className={`relative flex items-center gap-3 px-4 py-2.5 ${industry === "beauty" ? "rounded-xl" : industry === "fitness" ? "rounded-lg" : "rounded-md"} transition-all duration-200 group ${isActive
                                        ? getActiveItemClass()
                                        : `text-muted-foreground ${industry === "beauty" ? "hover:bg-white/20" : industry === "fitness" ? "hover:bg-primary/10 hover:text-primary" : "hover:bg-secondary hover:text-foreground"}`
                                        }`}
                                >
                                    {isActive && getActiveIndicator()}

                                    <item.icon className={`w-4 h-4 ${isActive ? (industry === "fitness" ? "text-primary-foreground" : "text-primary") : "group-hover:text-foreground"}`} />
                                    <span className="text-sm">{item.label}</span>

                                    {/* Pending Badge */}
                                    {item.hasBadge && pendingCount > 0 && (
                                        <span className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm ${industry === "fitness"
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-primary text-primary-foreground"
                                            }`}>
                                            {pendingCount}
                                        </span>
                                    )}
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            </nav>

            {/* Dark Mode Toggle + Logout */}
            <div className={`p-4 pb-24 lg:pb-4 border-t ${industry === "beauty" ? "border-white/20" : industry === "fitness" ? "border-primary/30" : "border-border"} mx-2 space-y-2`}>
                <button
                    onClick={toggleDarkMode}
                    className={`flex items-center gap-3 px-4 py-2 w-full ${industry === "beauty" ? "rounded-xl" : "rounded-md"} transition-all duration-200 text-sm font-medium text-muted-foreground ${industry === "beauty" ? "hover:bg-white/20" : "hover:bg-secondary"} hover:text-foreground`}
                >
                    {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                    <span>{darkMode ? "Light Mode" : "Dark Mode"}</span>
                </button>

                <button
                    onClick={handleLogout}
                    className={`flex items-center gap-3 px-4 py-2 w-full ${industry === "beauty" ? "rounded-xl" : "rounded-md"} transition-all duration-200 text-sm font-medium text-muted-foreground hover:bg-destructive/10 hover:text-destructive`}
                >
                    <LogOut className="w-4 h-4" />
                    <span>Log out</span>
                </button>
            </div>
        </aside>
    );
}
