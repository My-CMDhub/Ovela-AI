"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useAuth } from "./AuthContext";

export interface TenantConfig {
    id: string;
    name: string;
    logoChar: string;
    contact_phone: string;
    industry: string;
}

interface TenantContextType {
    tenant: TenantConfig;
    isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export function TenantProvider({ children }: { children: ReactNode }) {
    const { user, loading: authLoading } = useAuth();
    const [tenant, setTenant] = useState<TenantConfig | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        if (authLoading) return;

        if (user) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const prefs = user.prefs as any;
            const tenantId = prefs?.tenant_id || "coalcreek"; // Default fallback

            // Build tenant dynamically from user prefs directly
            // This guarantees complete data isolation without hardcoded dictionary mappings
            setTenant({
                id: tenantId,
                name: prefs?.tenant_name || (tenantId === "coalcreek" ? "Coal Creek Motel" : "Ovela Client"),
                logoChar: (prefs?.tenant_name?.[0] || tenantId[0] || "O").toUpperCase(),
                contact_phone: prefs?.tenant_phone || "0400 000 000",
                industry: prefs?.tenant_industry || "universal" // Unified architecture strategy
            });
        }

        setIsLoading(false);
    }, [user, authLoading]);

    if (!tenant && !isLoading && user) {
        return <div className="min-h-screen flex items-center justify-center text-[var(--theme-muted)]">Loading Environment...</div>;
    }

    return (
        <TenantContext.Provider value={{ tenant: tenant!, isLoading }}>
            {children}
        </TenantContext.Provider>
    );
}

export function useTenant() {
    const context = useContext(TenantContext);
    if (context === undefined) {
        throw new Error("useTenant must be used within a TenantProvider");
    }
    return context;
}
