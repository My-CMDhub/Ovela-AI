"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, User, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";

// Use local Next.js API proxy (adds API key server-side)
const API_URL = "/api/dashboard";

interface CalBooking {
    uid: string;
    title: string;
    start: string;
    end: string;
    status: string;
    attendee_name: string;
    attendee_email: string;
}

export default function BookingsPage() {
    const [bookings, setBookings] = useState<CalBooking[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<"upcoming" | "past" | "cancelled">("upcoming");

    useEffect(() => {
        fetchBookings();
    }, [filter]);

    const fetchBookings = async () => {
        setLoading(true);
        try {
            // API key is added server-side by the proxy
            const res = await fetch(`${API_URL}/bookings?status=${filter}`);
            const data = await res.json();

            if (data.success) {
                setBookings(data.bookings);
            }
        } catch (error) {
            console.error("Error fetching bookings:", error);
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateStr: string) => {
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString("en-AU", {
                weekday: "short",
                day: "numeric",
                month: "short",
                timeZone: "Australia/Melbourne"
            });
        } catch {
            return "—";
        }
    };

    const formatTime = (dateStr: string) => {
        try {
            const date = new Date(dateStr);
            return date.toLocaleTimeString("en-AU", {
                hour: "2-digit",
                minute: "2-digit",
                timeZone: "Australia/Melbourne"
            });
        } catch {
            return "—";
        }
    };

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Bookings</h1>
                    <p className="text-gray-500 mt-1">
                        All confirmed appointments
                        <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Native</span>
                    </p>
                </div>

                <div className="flex items-center gap-4">
                    {/* Refresh */}
                    <button
                        onClick={fetchBookings}
                        className="p-2 text-gray-400 hover:text-gray-600 transition"
                        title="Refresh"
                    >
                        <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
                    </button>

                    {/* Filter */}
                    <div className="flex gap-2">
                        {(["upcoming", "past", "cancelled"] as const).map((f) => (
                            <button
                                key={f}
                                onClick={() => setFilter(f)}
                                className={`px-4 py-2 text-sm rounded-lg transition ${filter === f
                                    ? "bg-rose-600 text-white"
                                    : "bg-white text-gray-600 border border-gray-200 hover:border-rose-300"
                                    }`}
                            >
                                {f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Bookings Table */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="bg-white rounded-xl border border-gray-100 overflow-hidden"
            >
                {loading ? (
                    <div className="p-8 text-center text-gray-400">Loading bookings...</div>
                ) : bookings.length === 0 ? (
                    <div className="p-8 text-center text-gray-400">
                        No {filter} bookings found
                    </div>
                ) : (
                    <>
                        {/* Desktop Table */}
                        <table className="w-full hidden md:table">
                            <thead className="bg-gray-50 border-b border-gray-100">
                                <tr>
                                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Customer
                                    </th>
                                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Event
                                    </th>
                                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Date & Time
                                    </th>
                                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-500 uppercase tracking-wider">
                                        Status
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                                {bookings.map((booking, index) => (
                                    <motion.tr
                                        key={booking.uid}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: index * 0.05 }}
                                        className="hover:bg-gray-50"
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 bg-rose-100 rounded-full flex items-center justify-center">
                                                    <User className="w-4 h-4 text-rose-600" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium text-gray-900">
                                                        {booking.attendee_name || "Guest"}
                                                    </p>
                                                    <p className="text-xs text-gray-400">{booking.attendee_email}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <p className="text-sm text-gray-700">{booking.title}</p>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-4">
                                                <div className="flex items-center gap-1 text-gray-600">
                                                    <Calendar className="w-4 h-4" />
                                                    <span className="text-sm">{formatDate(booking.start)}</span>
                                                </div>
                                                <div className="flex items-center gap-1 text-gray-600">
                                                    <Clock className="w-4 h-4" />
                                                    <span className="text-sm">{formatTime(booking.start)}</span>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span
                                                className={`text-xs px-3 py-1 rounded-full font-medium ${booking.status === "accepted"
                                                    ? "bg-green-100 text-green-700"
                                                    : booking.status === "cancelled"
                                                        ? "bg-red-100 text-red-700"
                                                        : "bg-yellow-100 text-yellow-700"
                                                    }`}
                                            >
                                                {booking.status}
                                            </span>
                                        </td>
                                    </motion.tr>
                                ))}
                            </tbody>
                        </table>

                        {/* Mobile Cards */}
                        <div className="md:hidden space-y-4 p-4">
                            {bookings.map((booking, index) => (
                                <motion.div
                                    key={booking.uid + "_mobile"}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="bg-gray-50 rounded-lg p-4 border border-gray-100"
                                >
                                    <div className="flex justify-between items-start mb-3">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 bg-rose-100 rounded-full flex items-center justify-center">
                                                <User className="w-4 h-4 text-rose-600" />
                                            </div>
                                            <div>
                                                <p className="text-sm font-medium text-gray-900">
                                                    {booking.attendee_name || "Guest"}
                                                </p>
                                                <p className="text-xs text-gray-400">{booking.attendee_email}</p>
                                            </div>
                                        </div>
                                        <span
                                            className={`text-xs px-2 py-1 rounded-full font-medium ${booking.status === "accepted"
                                                ? "bg-green-100 text-green-700"
                                                : booking.status === "cancelled"
                                                    ? "bg-red-100 text-red-700"
                                                    : "bg-yellow-100 text-yellow-700"
                                                }`}
                                        >
                                            {booking.status}
                                        </span>
                                    </div>

                                    <div className="space-y-2 mb-2">
                                        <p className="text-sm font-medium text-gray-800">{booking.title}</p>
                                        <div className="flex items-center gap-2 text-gray-600 text-sm">
                                            <Calendar className="w-3.5 h-3.5" />
                                            <span>{formatDate(booking.start)}</span>
                                            <Clock className="w-3.5 h-3.5 ml-2" />
                                            <span>{formatTime(booking.start)}</span>
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </>
                )}
            </motion.div>

            {/* Count */}
            {!loading && bookings.length > 0 && (
                <p className="text-sm text-gray-400 mt-4 text-right">
                    Showing {bookings.length} {filter} booking{bookings.length !== 1 ? "s" : ""}
                </p>
            )}
        </div>
    );
}
