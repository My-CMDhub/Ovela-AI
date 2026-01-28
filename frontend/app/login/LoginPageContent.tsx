"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";

export default function LoginPageContent() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [agreed, setAgreed] = useState(false);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            const user = await login(email, password);

            // Multi-Tenant Routing Logic
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const tenantId = (user.prefs as any)?.tenant_id;

            if (tenantId) {
                // Client: Strict redirect to their dashboard
                router.push(`/dashboard?tenant=${tenantId}`);
            } else {
                // Admin/Owner: Redirect to Command Center
                router.push("/admin");
            }
        } catch {
            setError("Invalid email or password");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 via-white to-pink-50">
            <div className="w-full max-w-md p-8">
                {/* Logo */}
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-serif text-rose-900">Ovela</h1>
                    <p className="text-gray-500 mt-2">Business Dashboard</p>
                </div>

                {/* Login Card */}
                <div className="bg-white rounded-2xl shadow-xl p-8 border border-rose-100">
                    <h2 className="text-xl font-semibold text-gray-800 mb-6">Welcome back</h2>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                                Email
                            </label>
                            <input
                                id="email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="w-full px-4 py-3 rounded-lg border border-gray-200 focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition"
                                placeholder="you@business.com"
                                required
                            />
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 rounded-lg border border-gray-200 focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition"
                                placeholder="••••••••"
                                required
                            />
                        </div>

                        {/* Consent Checkbox */}
                        <div className="flex items-start">
                            <div className="flex items-center h-5">
                                <input
                                    id="consent"
                                    type="checkbox"
                                    checked={agreed}
                                    onChange={(e) => setAgreed(e.target.checked)}
                                    className="w-4 h-4 rounded border-gray-300 text-rose-600 focus:ring-rose-500"
                                    required
                                />
                            </div>
                            <div className="ml-3 text-sm">
                                <label htmlFor="consent" className="text-gray-500">
                                    I agree to the{" "}
                                    <a href="/legal/terms" target="_blank" className="text-rose-600 hover:text-rose-500 hover:underline">
                                        Terms of Service
                                    </a>{" "}
                                    and{" "}
                                    <a href="/legal/privacy" target="_blank" className="text-rose-600 hover:text-rose-500 hover:underline">
                                        Privacy Policy
                                    </a>
                                </label>
                            </div>
                        </div>

                        {error && (
                            <p className="text-red-500 text-sm animate-pulse">
                                {error}
                            </p>
                        )}

                        <button
                            type="submit"
                            disabled={loading || !agreed}
                            className="w-full py-3 bg-rose-600 hover:bg-rose-700 text-white font-medium rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? "Signing in..." : "Sign In"}
                        </button>
                    </form>
                </div>

                <p className="text-center text-gray-400 text-sm mt-6">
                    Powered by Ovela AI
                </p>
            </div>
        </div>
    );
}
