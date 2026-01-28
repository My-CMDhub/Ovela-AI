"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Save, Building2, Clock, RefreshCw, Check, Lock, ShieldCheck, Phone } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useTenant } from "@/contexts/TenantContext";
import { account } from "@/lib/appwrite";

// Use localhost for development if env var is missing
// Use relative path for client-side fetches to hit Next.js Proxy
// This ensures route.ts handles the request (and potential rewrites)
const API_URL = "";
// Note: We used to rely on NEXT_PUBLIC_API_URL but that points to Backend directly in some envs, bypassing Proxy.
// By using "", we force it to /api/dashboard/... on the local domain.

interface BusinessSettings {
    business_name: string;
    business_hours: string;
    location: string;
    business_phone: string;
    owner_email: string;
}

const DEFAULT_SETTINGS: BusinessSettings = {
    business_name: "",
    business_hours: "",
    location: "",
    business_phone: "",
    owner_email: ""
};

export default function MotelSettingsPage() {
    const { user, logout } = useAuth();
    const { tenant } = useTenant();
    const [activeTab, setActiveTab] = useState<"general" | "security">("general");

    // Settings State
    const [settings, setSettings] = useState<BusinessSettings>(DEFAULT_SETTINGS);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    // Security State
    const [passwordData, setPasswordData] = useState({ oldPassword: "", newPassword: "", confirmPassword: "" });
    const [passwordError, setPasswordError] = useState("");
    const [passwordSuccess, setPasswordSuccess] = useState("");
    const [updatingPassword, setUpdatingPassword] = useState(false);

    useEffect(() => {
        if (tenant) {
            // Pre-fill with known tenant data so UI isn't empty on error
            setSettings(prev => ({
                ...prev,
                business_name: tenant.name,
                business_phone: tenant.contact_phone,
                // Partial fallbacks or defaults
                owner_email: prev.owner_email || "",
                location: prev.location || "",
                business_hours: prev.business_hours || ""
            }));
            fetchSettings();
        }
    }, [tenant]);

    const fetchSettings = async () => {
        try {
            const res = await fetch(`${API_URL}/api/dashboard/settings?tenant_id=${tenant.id}`);
            if (!res.ok) throw new Error("Failed to fetch settings");

            const data = await res.json();
            if (data.success && data.settings) {
                setSettings(data.settings);
            }
        } catch (error) {
            console.error("Error fetching settings:", error);
            // Don't leave it as "Loading...", just show empty form which is better than broken state
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            const res = await fetch(`${API_URL}/api/dashboard/settings?tenant_id=${tenant.id}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(settings)
            });
            const data = await res.json();
            if (data.success) {
                setSaved(true);
                setTimeout(() => setSaved(false), 3000);
            }
        } catch (error) {
            console.error("Error saving settings:", error);
        } finally {
            setSaving(false);
        }
    };

    const handleUpdatePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setPasswordError("");
        setPasswordSuccess("");

        if (passwordData.newPassword !== passwordData.confirmPassword) {
            setPasswordError("New passwords do not match");
            return;
        }

        if (passwordData.newPassword.length < 8) {
            setPasswordError("Password must be at least 8 characters");
            return;
        }

        setUpdatingPassword(true);
        try {
            await account.updatePassword(passwordData.newPassword, passwordData.oldPassword);
            setPasswordSuccess("Password updated successfully");
            setPasswordData({ oldPassword: "", newPassword: "", confirmPassword: "" });
        } catch (error: any) {
            setPasswordError(error.message || "Failed to update password");
        } finally {
            setUpdatingPassword(false);
        }
    };

    const handleLogout = async () => {
        await logout();
        window.location.href = "/login";
    };

    if (loading) {
        return (
            <div className="animate-pulse space-y-6">
                <div className="h-8 w-48 bg-gray-200 rounded" />
                <div className="h-64 bg-gray-200 rounded-xl" />
            </div>
        );
    }

    return (
        <div className="max-w-3xl">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
                <p className="mt-1 text-slate-500">
                    Manage your motel profile and account security
                </p>
            </div>

            {/* Tabs */}
            <div className="flex gap-4 mb-8 border-b border-slate-200">
                <button
                    onClick={() => setActiveTab("general")}
                    className={`pb-3 px-1 text-sm font-medium transition ${activeTab === "general"
                        ? "border-b-2 text-slate-900"
                        : "text-slate-500 hover:text-slate-700"
                        }`}
                    style={activeTab === "general" ? { borderColor: tenant?.colors?.primary } : {}}
                >
                    Business Info
                </button>
                <button
                    onClick={() => setActiveTab("security")}
                    className={`pb-3 px-1 text-sm font-medium transition ${activeTab === "security"
                        ? "border-b-2 text-slate-900"
                        : "text-slate-500 hover:text-slate-700"
                        }`}
                    style={activeTab === "security" ? { borderColor: tenant?.colors?.primary } : {}}
                >
                    Security
                </button>
            </div>

            {activeTab === "general" ? (
                <div className="space-y-6">
                    {/* Business Info */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="rounded-xl border border-slate-200 p-6 bg-white"
                    >
                        <div className="flex items-center gap-2 mb-6">
                            <Building2 className="w-5 h-5" style={{ color: tenant?.colors?.primary }} />
                            <h2 className="text-lg font-semibold text-slate-900">
                                {tenant?.industry === "food" ? "Restaurant Information" : "Motel Information"}
                            </h2>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    Motel Name
                                </label>
                                <input
                                    type="text"
                                    value={settings.business_name}
                                    onChange={(e) => setSettings({ ...settings, business_name: e.target.value })}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    Reception Phone
                                </label>
                                <input
                                    type="tel"
                                    value={settings.business_phone}
                                    onChange={(e) => setSettings({ ...settings, business_phone: e.target.value })}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                            </div>

                            <div className="md:col-span-2">
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    Address
                                </label>
                                <input
                                    type="text"
                                    value={settings.location}
                                    onChange={(e) => setSettings({ ...settings, location: e.target.value })}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                            </div>

                            <div className="md:col-span-2">
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    Notification Email
                                </label>
                                <input
                                    type="email"
                                    value={settings.owner_email}
                                    onChange={(e) => setSettings({ ...settings, owner_email: e.target.value })}
                                    placeholder="your@email.com"
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                                <p className="text-xs text-slate-400 mt-1">
                                    Receive booking requests and callback notifications here
                                </p>
                            </div>
                        </div>
                    </motion.div>

                    {/* Hours */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="rounded-xl border border-slate-200 p-6 bg-white"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <Clock className="w-5 h-5" style={{ color: tenant?.colors?.primary }} />
                            <h2 className="text-lg font-semibold text-slate-900">
                                {tenant?.industry === "food" ? "Opening Hours" : "Check-in / Check-out"}
                            </h2>
                        </div>

                        <textarea
                            value={settings.business_hours}
                            onChange={(e) => setSettings({ ...settings, business_hours: e.target.value })}
                            rows={3}
                            className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition resize-none"
                        />
                    </motion.div>

                    {/* Save Button */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="flex justify-end gap-3"
                    >
                        <button
                            onClick={fetchSettings}
                            className="flex items-center gap-2 px-4 py-2.5 text-slate-600 hover:text-gray-800 transition"
                        >
                            <RefreshCw className="w-4 h-4" />
                            Reset
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="flex items-center gap-2 px-6 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition disabled:opacity-50"
                        >
                            {saving ? (
                                <>
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                    Saving...
                                </>
                            ) : saved ? (
                                <>
                                    <Check className="w-4 h-4" />
                                    Saved!
                                </>
                            ) : (
                                <>
                                    <Save className="w-4 h-4" />
                                    Save Changes
                                </>
                            )}
                        </button>
                    </motion.div>
                </div>
            ) : (
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-6"
                >
                    {/* Change Password */}
                    <div className="rounded-xl border border-slate-200 p-6 bg-white">
                        <div className="flex items-center gap-2 mb-6">
                            <Lock className="w-5 h-5" style={{ color: tenant?.colors?.primary }} />
                            <h2 className="text-lg font-semibold text-slate-900">Change Password</h2>
                        </div>

                        <form onSubmit={handleUpdatePassword} className="space-y-4 max-w-md">
                            <div>
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    Current Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    value={passwordData.oldPassword}
                                    onChange={(e) => setPasswordData({ ...passwordData, oldPassword: e.target.value })}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    New Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    minLength={8}
                                    value={passwordData.newPassword}
                                    onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                                <p className="text-xs text-slate-500 mt-1">Must be at least 8 characters</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-slate-700">
                                    Confirm New Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    value={passwordData.confirmPassword}
                                    onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-slate-900/20 focus:border-slate-900 outline-none transition"
                                />
                            </div>

                            {passwordError && (
                                <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg">
                                    {passwordError}
                                </div>
                            )}

                            {passwordSuccess && (
                                <div className="p-3 bg-green-50 text-green-600 text-sm rounded-lg flex items-center gap-2">
                                    <Check className="w-4 h-4" />
                                    {passwordSuccess}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={updatingPassword}
                                className="w-full flex justify-center items-center gap-2 px-6 py-2.5 bg-gray-900 text-white rounded-lg hover:bg-black transition disabled:opacity-50"
                            >
                                {updatingPassword ? (
                                    <>
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                        Updating...
                                    </>
                                ) : (
                                    "Update Password"
                                )}
                            </button>
                        </form>
                    </div>

                    {/* Account Security Status */}
                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-6">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-emerald-100 rounded-full">
                                <ShieldCheck className="w-6 h-6 text-emerald-600" />
                            </div>
                            <div>
                                <h3 className="font-semibold text-slate-900">Account Secured</h3>
                                <p className="text-sm text-slate-600">
                                    Logged in as {user?.email}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Logout */}
                    <button
                        onClick={handleLogout}
                        className="w-full flex justify-center items-center gap-2 px-6 py-3 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition"
                    >
                        Log Out
                    </button>
                </motion.div>
            )}
        </div>
    );
}
