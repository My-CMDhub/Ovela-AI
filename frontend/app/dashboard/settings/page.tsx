"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Save, Building2, Clock, Sparkles, Tag, RefreshCw, Check, Lock, ShieldCheck } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { account } from "@/lib/appwrite";

// Backend API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface BusinessSettings {
    business_name: string;
    industry: string;
    business_hours: string;
    services: string;
    location: string;
    phone: string;
    owner_email: string;  // Email for booking notifications
    business_phone: string;  // Phone shown to customers
    custom_instructions: string;
    current_promotions: string;
    ai_tone: "professional" | "friendly" | "casual";
}

const DEFAULT_SETTINGS: BusinessSettings = {
    business_name: "",
    industry: "beauty",
    business_hours: "Monday - Friday: 9:00 AM - 5:00 PM",
    services: "",
    location: "",
    phone: "",
    owner_email: "",
    business_phone: "",
    custom_instructions: "",
    current_promotions: "",
    ai_tone: "friendly"
};

export default function SettingsPage() {
    const { user } = useAuth();
    const { setIndustry, darkMode } = useTheme();
    const [activeTab, setActiveTab] = useState<"general" | "security">("general");

    // General Settings State
    const [settings, setSettings] = useState<BusinessSettings>(DEFAULT_SETTINGS);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [industryLocked, setIndustryLocked] = useState(false);

    // Security State
    const [passwordData, setPasswordData] = useState({ oldPassword: "", newPassword: "", confirmPassword: "" });
    const [passwordError, setPasswordError] = useState("");
    const [passwordSuccess, setPasswordSuccess] = useState("");
    const [updatingPassword, setUpdatingPassword] = useState(false);

    useEffect(() => {
        fetchSettings();
        fetchIndustryLock();
    }, []);

    const fetchSettings = async () => {
        try {
            const res = await fetch(`${API_URL}/api/dashboard/settings`);
            const data = await res.json();
            if (data.success && data.settings) {
                setSettings({ ...DEFAULT_SETTINGS, ...data.settings });
            }
        } catch (error) {
            console.error("Error fetching settings:", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchIndustryLock = async () => {
        try {
            const res = await fetch(`${API_URL}/api/dashboard/settings/industry-lock`);
            const data = await res.json();
            if (data.success) {
                setIndustryLocked(data.locked);
            }
        } catch (error) {
            console.error("Error fetching industry lock:", error);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            const res = await fetch(`${API_URL}/api/dashboard/settings`, {
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

    // Handle industry change with live theme preview
    const handleIndustryChange = (newIndustry: string) => {
        setSettings({ ...settings, industry: newIndustry });
        // Immediately update theme for live preview
        setIndustry(newIndustry as any);
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
            console.error("Password update error:", error);
            setPasswordError(error.message || "Failed to update password. Please check your old password.");
        } finally {
            setUpdatingPassword(false);
        }
    };

    if (loading) {
        return (
            <div className="animate-pulse space-y-6">
                <div className="h-8 w-48 rounded" style={{ backgroundColor: darkMode ? "rgb(55, 65, 81)" : "rgb(229, 231, 235)" }} />
                <div className="h-64 rounded-xl" style={{ backgroundColor: darkMode ? "rgb(55, 65, 81)" : "rgb(229, 231, 235)" }} />
            </div>
        );
    }

    return (
        <div className="max-w-3xl">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Settings</h1>
                <p className="mt-1 text-gray-500 dark:text-gray-400">
                    Manage your business profile and account security
                </p>
            </div>

            {/* Tabs */}
            <div className="flex gap-4 mb-8 border-b border-gray-200 dark:border-neutral-800">
                <button
                    onClick={() => setActiveTab("general")}
                    className={`pb-3 px-1 text-sm font-medium transition ${activeTab === "general"
                        ? "border-b-2 text-rose-600"
                        : ""
                        }`}
                    style={{
                        borderColor: activeTab === "general" ? "var(--theme-primary, #e11d48)" : "transparent",
                        color: activeTab === "general" ? "var(--theme-primary, #e11d48)" : (darkMode ? "rgb(156, 163, 175)" : "rgb(107, 114, 128)")
                    }}
                >
                    General Settings
                </button>
                <button
                    onClick={() => setActiveTab("security")}
                    className={`pb-3 px-1 text-sm font-medium transition ${activeTab === "security"
                        ? "border-b-2"
                        : ""
                        }`}
                    style={{
                        borderColor: activeTab === "security" ? "var(--theme-primary, #e11d48)" : "transparent",
                        color: activeTab === "security" ? "var(--theme-primary, #e11d48)" : (darkMode ? "rgb(156, 163, 175)" : "rgb(107, 114, 128)")
                    }}
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
                        className="rounded-xl border p-6 bg-white dark:bg-neutral-900 border-gray-100 dark:border-neutral-800"
                    >
                        <div className="flex items-center gap-2 mb-6">
                            <Building2 className="w-5 h-5 text-rose-600" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Business Information</h2>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    Business Name
                                </label>
                                <input
                                    type="text"
                                    value={settings.business_name}
                                    onChange={(e) => setSettings({ ...settings, business_name: e.target.value })}
                                    placeholder="e.g., Glow Beauty Studio"
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300 flex items-center gap-2">
                                    Industry
                                    {industryLocked && (
                                        <span className="flex items-center gap-1 text-xs text-muted-foreground" title="Industry is locked by administrator">
                                            <Lock className="w-3 h-3" />
                                            Locked
                                        </span>
                                    )}
                                </label>
                                <select
                                    value={settings.industry}
                                    onChange={(e) => handleIndustryChange(e.target.value)}
                                    disabled={industryLocked}
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <option value="beauty">Beauty & Wellness</option>
                                    <option value="health">Health & Medical</option>
                                    <option value="fitness">Fitness & Gym</option>
                                    <option value="professional">Professional Services</option>
                                    <option value="hospitality">Hospitality</option>
                                    <option value="retail">Retail</option>
                                </select>
                                {industryLocked && (
                                    <p className="text-xs text-muted-foreground mt-1">
                                        Industry setting is locked and cannot be changed.
                                    </p>
                                )}
                                <p className="text-xs text-gray-400 mt-1">Theme changes instantly - save to persist</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    Location
                                </label>
                                <input
                                    type="text"
                                    value={settings.location}
                                    onChange={(e) => setSettings({ ...settings, location: e.target.value })}
                                    placeholder="e.g., 123 Collins Street, Melbourne"
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    Business Phone
                                </label>
                                <input
                                    type="tel"
                                    value={settings.business_phone || settings.phone}
                                    onChange={(e) => setSettings({ ...settings, business_phone: e.target.value, phone: e.target.value })}
                                    placeholder="e.g., 0475 921 152"
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
                                />
                                <p className="text-xs text-gray-400 mt-1">Shown to customers in WhatsApp messages</p>
                            </div>

                            <div className="md:col-span-2">
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    Your (Owner's) Email (for notifications)
                                </label>
                                <input
                                    type="email"
                                    value={settings.owner_email}
                                    onChange={(e) => setSettings({ ...settings, owner_email: e.target.value })}
                                    placeholder="your@email.com"
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
                                />
                                <p className="text-xs text-gray-400 mt-1">You'll receive booking requests and notifications at this email</p>
                            </div>
                        </div>
                    </motion.div>

                    {/* Business Hours */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="rounded-xl border p-6 bg-white dark:bg-neutral-900 border-gray-100 dark:border-neutral-800"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <Clock className="w-5 h-5 text-rose-600" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Business Hours</h2>
                        </div>

                        <textarea
                            value={settings.business_hours}
                            onChange={(e) => setSettings({ ...settings, business_hours: e.target.value })}
                            placeholder="Monday - Friday: 9:00 AM - 5:00 PM&#10;Saturday: 10:00 AM - 2:00 PM&#10;Sunday: Closed"
                            rows={4}
                            className="w-full px-4 py-2.5 border border-gray-200 dark:border-neutral-700 rounded-lg focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition resize-none bg-white dark:bg-neutral-800 text-gray-900 dark:text-white"
                        />
                        <p className="text-xs text-gray-400 mt-2">
                            The AI will tell customers when you&apos;re open and won&apos;t book outside these hours
                        </p>
                    </motion.div>

                    {/* Services */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="rounded-xl border p-6 bg-white dark:bg-neutral-900 border-gray-100 dark:border-neutral-800"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <Sparkles className="w-5 h-5 text-rose-600" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Services Offered</h2>
                        </div>

                        <textarea
                            value={settings.services}
                            onChange={(e) => setSettings({ ...settings, services: e.target.value })}
                            placeholder="Classic Facial - $120 (60 min)&#10;Eyebrow Wax & Shape - $35 (20 min)&#10;Lash Lift & Tint - $95 (60 min)"
                            rows={5}
                            className="w-full px-4 py-2.5 border border-gray-200 dark:border-neutral-700 rounded-lg focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition resize-none bg-white dark:bg-neutral-800 text-gray-900 dark:text-white"
                        />
                        <p className="text-xs text-gray-400 mt-2">
                            List your services with prices. The AI will recommend these to customers.
                        </p>
                    </motion.div>

                    {/* Promotions */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="rounded-xl border p-6 bg-white dark:bg-neutral-900 border-gray-100 dark:border-neutral-800"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <Tag className="w-5 h-5 text-rose-600" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Current Promotions</h2>
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Optional</span>
                        </div>

                        <textarea
                            value={settings.current_promotions}
                            onChange={(e) => setSettings({ ...settings, current_promotions: e.target.value })}
                            placeholder="e.g., 20% off first visit for new clients&#10;Free eyebrow wax with any facial booking this month"
                            rows={3}
                            className="w-full px-4 py-2.5 border border-gray-200 dark:border-neutral-700 rounded-lg focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition resize-none bg-white dark:bg-neutral-800 text-gray-900 dark:text-white"
                        />
                        <p className="text-xs text-gray-400 mt-2">
                            The AI will naturally mention active deals when relevant — not every message.
                        </p>
                    </motion.div>

                    {/* AI Personality */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="rounded-xl border p-6 bg-white dark:bg-neutral-900 border-gray-100 dark:border-neutral-800"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <Sparkles className="w-5 h-5 text-rose-600" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">AI Personality</h2>
                        </div>

                        <div className="grid grid-cols-3 gap-3 mb-4">
                            {(["professional", "friendly", "casual"] as const).map((tone) => (
                                <button
                                    key={tone}
                                    onClick={() => setSettings({ ...settings, ai_tone: tone })}
                                    className={`py-3 px-4 rounded-lg border text-sm font-medium transition ${settings.ai_tone === tone
                                        ? "bg-rose-600 text-white border-rose-600"
                                        : "bg-white dark:bg-neutral-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-neutral-700 hover:border-rose-300"
                                        }`}
                                >
                                    {tone.charAt(0).toUpperCase() + tone.slice(1)}
                                </button>
                            ))}
                        </div>

                        <div className="mt-4">
                            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                Custom Instructions (Optional)
                            </label>
                            <textarea
                                value={settings.custom_instructions}
                                onChange={(e) => setSettings({ ...settings, custom_instructions: e.target.value.slice(0, 500) })}
                                maxLength={500}
                                placeholder="e.g., Always ask if they've been here before. Mention we require 24hr cancellation notice. Recommend our signature facial to new clients."
                                rows={4}
                                className="w-full px-4 py-2.5 border border-gray-200 dark:border-neutral-700 rounded-lg focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition resize-none bg-white dark:bg-neutral-800 text-gray-900 dark:text-white"
                            />
                            <div className="flex justify-between mt-2">
                                <p className="text-xs text-gray-400">
                                    Extra instructions the AI will follow. Keep it concise for best results.
                                </p>
                                <span className={`text-xs ${settings.custom_instructions.length > 450 ? 'text-amber-500' : 'text-gray-400'}`}>
                                    {settings.custom_instructions.length}/500
                                </span>
                            </div>
                        </div>
                    </motion.div>

                    {/* Save Button */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.5 }}
                        className="flex justify-end gap-3"
                    >
                        <button
                            onClick={fetchSettings}
                            className="flex items-center gap-2 px-4 py-2.5 text-gray-600 hover:text-gray-800 transition"
                        >
                            <RefreshCw className="w-4 h-4" />
                            Reset
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="flex items-center gap-2 px-6 py-2.5 bg-rose-600 text-white rounded-lg hover:bg-rose-700 transition disabled:opacity-50"
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
                                    Save Settings
                                </>
                            )}
                        </button>
                    </motion.div>

                    {/* Info Box */}
                    <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                        <p className="text-sm text-blue-800">
                            <strong>💡 How it works:</strong> Your AI uses smart defaults that work for most businesses.
                            Any settings you add here will layer on top — the AI adapts naturally without sounding robotic.
                        </p>
                    </div>
                </div>
            ) : (
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-6"
                >
                    <div className="rounded-xl border p-6 bg-white dark:bg-neutral-900 border-gray-100 dark:border-neutral-800">
                        <div className="flex items-center gap-2 mb-6">
                            <Lock className="w-5 h-5 text-rose-600" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Change Password</h2>
                        </div>

                        <form onSubmit={handleUpdatePassword} className="space-y-4 max-w-md">
                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    Current Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    value={passwordData.oldPassword}
                                    onChange={(e) => setPasswordData({ ...passwordData, oldPassword: e.target.value })}
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    New Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    minLength={8}
                                    value={passwordData.newPassword}
                                    onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
                                />
                                <p className="text-xs text-gray-500 mt-1">Must be at least 8 characters</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                                    Confirm New Password
                                </label>
                                <input
                                    type="password"
                                    required
                                    value={passwordData.confirmPassword}
                                    onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                                    className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 outline-none transition bg-white dark:bg-neutral-800 border-gray-200 dark:border-neutral-700 text-gray-900 dark:text-white"
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
                                    <>
                                        Update Password
                                    </>
                                )}
                            </button>
                        </form>
                    </div>

                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-6">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-emerald-100 rounded-full">
                                <ShieldCheck className="w-6 h-6 text-emerald-600" />
                            </div>
                            <div>
                                <h3 className="font-semibold text-gray-900">Account Secured</h3>
                                <p className="text-sm text-gray-600">
                                    Your session is protected with secure encryption.
                                </p>
                            </div>
                        </div>
                    </div>
                </motion.div>
            )}
        </div>
    );
}
