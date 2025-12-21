"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    Users,
    Phone,
    Mail,
    Calendar,
    Star,
    BedDouble,
    Search,
} from "lucide-react";

interface Guest {
    $id: string;
    name: string;
    phone: string;
    email?: string;
    total_stays: number;
    last_stay_date?: string;
    preferred_room_type?: string;
    notes?: string;
    is_vip?: string;
    created_at?: string;
}

export default function GuestsPage() {
    const [guests, setGuests] = useState<Guest[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

    useEffect(() => {
        fetchGuests();
    }, []);

    const fetchGuests = async () => {
        try {
            const res = await fetch("/api/motel/guests");
            const data = await res.json();
            if (data.success) {
                setGuests(data.guests);
            }
        } catch (error) {
            console.error("Error fetching guests:", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredGuests = guests.filter((guest) => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
            guest.name?.toLowerCase().includes(query) ||
            guest.phone?.includes(query) ||
            guest.email?.toLowerCase().includes(query)
        );
    });

    const formatDate = (dateStr: string | undefined) => {
        if (!dateStr) return "—";
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-AU", {
            day: "numeric",
            month: "short",
            year: "numeric",
        });
    };

    const getRoomTypeLabel = (type: string | undefined) => {
        if (!type) return "No preference";
        const labels: Record<string, string> = {
            queen: "Queen Room",
            twin: "Twin Room",
            family: "Family Room",
            accessible: "Accessible Room",
        };
        return labels[type] || type;
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Guests</h1>
                    <p className="text-gray-600 mt-1">
                        Guest profiles and stay history
                    </p>
                </div>
                <div className="text-sm text-gray-500">
                    {guests.length} total guests
                </div>
            </div>

            {/* Search */}
            <div className="relative max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                    type="text"
                    placeholder="Search by name, phone, or email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                />
            </div>

            {/* Guests Grid */}
            {loading ? (
                <div className="text-center py-12 text-gray-400">Loading guests...</div>
            ) : filteredGuests.length === 0 ? (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center"
                >
                    <Users className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                    <p className="text-gray-500 font-medium">No guest profiles yet</p>
                    <p className="text-sm text-gray-400 mt-1">
                        {searchQuery
                            ? "Try adjusting your search"
                            : "Guest profiles will be created from voice bookings"}
                    </p>
                </motion.div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredGuests.map((guest, index) => (
                        <motion.div
                            key={guest.$id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow"
                        >
                            {/* Guest Header */}
                            <div className="flex items-start justify-between mb-4">
                                <div className="flex items-center gap-3">
                                    <div className="w-12 h-12 bg-[#8B2332]/10 rounded-full flex items-center justify-center">
                                        <span className="text-lg font-bold text-[#8B2332]">
                                            {guest.name?.charAt(0)?.toUpperCase() || "G"}
                                        </span>
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                                            {guest.name}
                                            {guest.is_vip === "true" && (
                                                <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                                            )}
                                        </h3>
                                        <p className="text-sm text-gray-500">
                                            {guest.total_stays || 0} stay{(guest.total_stays || 0) !== 1 ? "s" : ""}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Contact Info */}
                            <div className="space-y-2 text-sm">
                                <div className="flex items-center gap-2 text-gray-600">
                                    <Phone className="w-4 h-4 text-gray-400" />
                                    <span>{guest.phone}</span>
                                </div>
                                {guest.email && (
                                    <div className="flex items-center gap-2 text-gray-600">
                                        <Mail className="w-4 h-4 text-gray-400" />
                                        <span className="truncate">{guest.email}</span>
                                    </div>
                                )}
                                <div className="flex items-center gap-2 text-gray-600">
                                    <Calendar className="w-4 h-4 text-gray-400" />
                                    <span>Last stay: {formatDate(guest.last_stay_date)}</span>
                                </div>
                                {guest.preferred_room_type && (
                                    <div className="flex items-center gap-2 text-gray-600">
                                        <BedDouble className="w-4 h-4 text-gray-400" />
                                        <span>Prefers: {getRoomTypeLabel(guest.preferred_room_type)}</span>
                                    </div>
                                )}
                            </div>

                            {/* Notes */}
                            {guest.notes && (
                                <div className="mt-4 pt-4 border-t border-gray-100">
                                    <p className="text-xs text-gray-500 line-clamp-2">
                                        {guest.notes}
                                    </p>
                                </div>
                            )}
                        </motion.div>
                    ))}
                </div>
            )}
        </div>
    );
}
