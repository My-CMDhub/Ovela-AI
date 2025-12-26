"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// DISABLED: General CRM selection page
// Redirects directly to motel CRM
export default function SelectDashboard() {
    const router = useRouter();

    useEffect(() => {
        router.replace("/motel");
    }, [router]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-gray-400">Redirecting...</div>
        </div>
    );
}
