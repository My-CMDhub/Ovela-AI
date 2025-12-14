"use client";

import { AuthProvider } from "@/contexts/AuthContext";
import LoginPageContent from "./LoginPageContent";

export default function LoginPage() {
    return (
        <AuthProvider>
            <LoginPageContent />
        </AuthProvider>
    );
}
