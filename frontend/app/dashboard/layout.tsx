"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// DISABLED: General CRM dashboard
// All /dashboard/* routes redirect to /motel
export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const router = useRouter();

    useEffect(() => {
        router.replace("/motel");
    }, [router]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-gray-400">Redirecting to Motel CRM...</div>
        </div>
    );
}
