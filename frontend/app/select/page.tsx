"use client";

import { AuthProvider } from "@/contexts/AuthContext";
import SelectDashboardProtected from "./SelectDashboardProtected";

export default function SelectDashboard() {
    return (
        <AuthProvider>
            <SelectDashboardProtected />
        </AuthProvider>
    );
}
