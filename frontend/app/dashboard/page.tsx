"use client";

import { useTenant } from "@/contexts/TenantContext";
import ClientDashboard from "@/components/dashboard/client-dashboard";
import { Loader2 } from "lucide-react";

export default function DashboardPage() {
    const { tenant, isLoading } = useTenant();

    if (isLoading || !tenant) {
        return (
            <div className="flex h-[80vh] items-center justify-center" style={{ color: "var(--theme-primary)" }}>
                <Loader2 className="w-8 h-8 animate-spin" />
            </div>
        );
    }

    // Unified Architecture: All tenants get the same powerful ClientDashboard
    // Data isolation is guaranteed backend-side.
    return <ClientDashboard />;
}
