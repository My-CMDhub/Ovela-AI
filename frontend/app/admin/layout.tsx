"use client";

import { AuthProvider } from "@/contexts/AuthContext";
import { Suspense } from "react";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    return (
        <AuthProvider>
            <Suspense fallback={<div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-500">Loading...</div>}>
                {children}
            </Suspense>
        </AuthProvider>
    );
}
