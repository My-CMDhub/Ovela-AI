"use client";

import { useTenant } from "@/contexts/TenantContext";
import MotelDashboard from "@/components/dashboard/motel-dashboard";
import RestaurantDashboard from "@/components/dashboard/restaurant-dashboard";

export default function DashboardPage() {
    const { tenant, isLoading } = useTenant();

    if (isLoading) {
        return <div className="p-8 text-center text-gray-400">Loading Dashboard...</div>;
    }

    // Niche Router
    if (tenant.industry === "food") {
        return <RestaurantDashboard />;
    }

    // Default to Motel (Hospitality)
    return <MotelDashboard />;
}
