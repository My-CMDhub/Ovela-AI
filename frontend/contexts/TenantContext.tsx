"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useAuth } from "./AuthContext";

export type TenantId = "coalcreek" | "saranda" | string;

interface TenantConfig {
    id: TenantId;
    name: string;
    colors: {
        primary: string; // Brand color
        secondary: string; // Accent color
    };
    logoChar: string; // Fallback logo
    industry: "hospitality" | "food"; // Niche-specific UI
}

// Tenant Registry
export const TENANTS: Record<string, TenantConfig> = {
    coalcreek: {
        id: "coalcreek",
        name: "Coal Creek Motel",
        colors: {
            primary: "#D4AF37", // Gold
            secondary: "#1E293B", // Slate 800
        },
        logoChar: "C",
        industry: "hospitality",
    },
    saranda: {
        id: "saranda",
        name: "Saranda on Hutton",
        colors: {
            primary: "#0EA5E9", // Sky Blue
            secondary: "#0F172A", // Slate 900
        },
        logoChar: "S",
        industry: "food",
    },
};

interface TenantContextType {
    tenant: TenantConfig;
    setTenant: (id: string) => void;
    isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export function TenantProvider({ children }: { children: ReactNode }) {
    const { user, loading: authLoading } = useAuth();
    const searchParams = useSearchParams();
    const router = useRouter();
    const pathname = usePathname();

    const [currentTenantId, setCurrentTenantId] = useState<string>("coalcreek");
    const [isLoading, setIsLoading] = useState(true);

    // Resolve Tenant
    useEffect(() => {
        if (authLoading) return;

        // 1. Check URL Param
        const paramTenant = searchParams.get("tenant");

        // 2. Check User Preferences (if logged in)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const userTenant = (user?.prefs as any)?.tenant_id;

        // Priority: Param > User Pref > Default (Coal Creek)
        let resolvedTenant = paramTenant || userTenant || "coalcreek";

        // Validate
        if (!TENANTS[resolvedTenant]) {
            console.warn(`Unknown tenant '${resolvedTenant}', falling back to Coal Creek`);
            resolvedTenant = "coalcreek";
        }

        setCurrentTenantId(resolvedTenant);
        setIsLoading(false);

    }, [searchParams, user, authLoading]);

    // Function to switch tenant
    const handleSetTenant = (id: string) => {
        if (!TENANTS[id]) return;

        // Persist to URL
        const params = new URLSearchParams(searchParams.toString());
        params.set("tenant", id);
        router.push(`${pathname}?${params.toString()}`);

        setCurrentTenantId(id);
    };

    const tenant = TENANTS[currentTenantId] || TENANTS["coalcreek"];

    return (
        <TenantContext.Provider
            value={{
                tenant,
                setTenant: handleSetTenant,
                isLoading
            }}
        >
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
