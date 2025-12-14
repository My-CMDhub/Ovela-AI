"use client";

import { useEffect, useState } from "react";
import { databases, DATABASE_ID } from "@/lib/appwrite";
import { Query } from "appwrite";
import { Users, Search, Phone, Mail, Brain, Calendar, RefreshCw, XCircle, CheckCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface CustomerStats {
    total_bookings?: number;
    total_reschedules?: number;
    total_cancellations?: number;
    requests_approved?: number;
    requests_rejected?: number;
    first_interaction?: string;
    last_interaction?: string;
}

interface Customer {
    $id: string;
    name: string;
    email: string;
    whatsapp_id: string;
    profile_summary: string;
    preferences_json?: string;  // Contains analytics stats
    $createdAt: string;
}

export default function CustomersPage() {
    const [customers, setCustomers] = useState<Customer[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);

    useEffect(() => {
        fetchCustomers();
    }, []);

    const fetchCustomers = async () => {
        setLoading(true);
        try {
            const res = await databases.listDocuments(DATABASE_ID, "customers", [
                Query.orderDesc("$createdAt"),
                Query.limit(100),
            ]);
            setCustomers(res.documents as unknown as Customer[]);
        } catch (error) {
            console.error("Error fetching customers:", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredCustomers = customers.filter(
        (c) =>
            c.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            c.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            c.whatsapp_id?.includes(searchQuery)
    );

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString("en-AU", {
            day: "numeric",
            month: "short",
            year: "numeric",
        });
    };

    return (
        <div className="flex gap-6">
            {/* Customer List */}
            <div className="flex-1">
                {/* Header */}
                <div className="mb-6">
                    <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Customers</h1>
                    <p className="text-gray-500 mt-1">Contacts who have interacted with Ovela</p>
                </div>

                {/* Search */}
                <div className="relative mb-6">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search by name, email, or phone..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl dark:text-black focus:border-rose-400 focus:ring-2 focus:ring-rose-100 outline-none transition"
                    />
                </div>

                {/* Customer List */}
                <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
                    {loading ? (
                        <div className="p-8 text-center text-gray-400">Loading customers...</div>
                    ) : filteredCustomers.length === 0 ? (
                        <div className="p-8 text-center text-gray-400">
                            {searchQuery ? "No customers match your search" : "No customers yet"}
                        </div>
                    ) : (
                        <ul className="divide-y divide-gray-50">
                            {filteredCustomers.map((customer, index) => (
                                <motion.li
                                    key={customer.$id}
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: index * 0.03 }}
                                >
                                    <button
                                        onClick={() => setSelectedCustomer(customer)}
                                        className={`w-full px-6 py-4 flex items-center gap-4 hover:bg-gray-50 transition text-left ${selectedCustomer?.$id === customer.$id ? "bg-rose-50" : ""
                                            }`}
                                    >
                                        <div className="w-10 h-10 bg-rose-100 rounded-full flex items-center justify-center">
                                            <Users className="w-5 h-5 text-rose-600" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-gray-900 truncate">
                                                {customer.name || "Unknown"}
                                            </p>
                                            <p className="text-xs text-gray-400 truncate">{customer.email}</p>
                                        </div>
                                        <span className="text-xs text-gray-400">
                                            {formatDate(customer.$createdAt)}
                                        </span>
                                    </button>
                                </motion.li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>

            {/* Customer Detail Panel */}
            <AnimatePresence>
                {selectedCustomer && (
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        className="w-96 bg-white rounded-xl border border-gray-100 p-6 h-fit sticky top-8"
                    >
                        <div className="flex items-center gap-4 mb-6">
                            <div className="w-14 h-14 bg-rose-100 rounded-full flex items-center justify-center">
                                <Users className="w-7 h-7 text-rose-600" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-gray-900">
                                    {selectedCustomer.name || "Unknown"}
                                </h2>
                                <p className="text-sm text-gray-400">Customer since {formatDate(selectedCustomer.$createdAt)}</p>
                            </div>
                        </div>

                        {/* Contact Info */}
                        <div className="space-y-3 mb-6">
                            {selectedCustomer.email && (
                                <div className="flex items-center gap-3">
                                    <Mail className="w-4 h-4 text-gray-400" />
                                    <span className="text-sm text-gray-700">{selectedCustomer.email}</span>
                                </div>
                            )}
                            {selectedCustomer.whatsapp_id && (
                                <div className="flex items-center gap-3">
                                    <Phone className="w-4 h-4 text-gray-400" />
                                    <span className="text-sm text-gray-700">{selectedCustomer.whatsapp_id}</span>
                                </div>
                            )}
                        </div>

                        {/* Customer Stats */}
                        {(() => {
                            const stats: CustomerStats = selectedCustomer.preferences_json
                                ? JSON.parse(selectedCustomer.preferences_json)
                                : {};
                            const hasStats = stats.total_bookings || stats.total_reschedules || stats.total_cancellations;

                            if (!hasStats) return null;

                            return (
                                <div className="grid grid-cols-2 gap-2 mb-6">
                                    {stats.total_bookings !== undefined && stats.total_bookings > 0 && (
                                        <div className="flex items-center gap-2 p-2 rounded-lg" style={{ backgroundColor: "var(--theme-primary-light, #fff1f2)" }}>
                                            <Calendar className="w-4 h-4" style={{ color: "var(--theme-primary, #e11d48)" }} />
                                            <span className="text-xs font-medium" style={{ color: "var(--theme-primary, #e11d48)" }}>{stats.total_bookings} bookings</span>
                                        </div>
                                    )}
                                    {stats.total_reschedules !== undefined && stats.total_reschedules > 0 && (
                                        <div className="flex items-center gap-2 p-2 bg-amber-50 rounded-lg">
                                            <RefreshCw className="w-4 h-4 text-amber-600" />
                                            <span className="text-xs font-medium text-amber-700">{stats.total_reschedules} reschedules</span>
                                        </div>
                                    )}
                                    {stats.total_cancellations !== undefined && stats.total_cancellations > 0 && (
                                        <div className="flex items-center gap-2 p-2 bg-red-50 rounded-lg">
                                            <XCircle className="w-4 h-4 text-red-500" />
                                            <span className="text-xs font-medium text-red-600">{stats.total_cancellations} cancelled</span>
                                        </div>
                                    )}
                                    {stats.requests_approved !== undefined && stats.requests_approved > 0 && (
                                        <div className="flex items-center gap-2 p-2 bg-green-50 rounded-lg">
                                            <CheckCircle className="w-4 h-4 text-green-600" />
                                            <span className="text-xs font-medium text-green-700">{stats.requests_approved} approved</span>
                                        </div>
                                    )}
                                </div>
                            );
                        })()}

                        {/* AI Profile Summary */}
                        {selectedCustomer.profile_summary && (
                            <div className="rounded-lg p-4" style={{ backgroundColor: "var(--theme-primary-light, #fff1f2)" }}>
                                <div className="flex items-center gap-2 mb-2">
                                    <Brain className="w-4 h-4" style={{ color: "var(--theme-primary, #e11d48)" }} />
                                    <span className="text-sm font-medium" style={{ color: "var(--theme-primary, #881337)" }}>AI Summary</span>
                                </div>
                                <p className="text-sm" style={{ color: "var(--theme-primary, #9f1239)" }}>{selectedCustomer.profile_summary}</p>
                            </div>
                        )}

                        <button
                            onClick={() => setSelectedCustomer(null)}
                            className="mt-6 w-full py-2 text-sm text-gray-500 hover:text-gray-700 transition"
                        >
                            Close
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
