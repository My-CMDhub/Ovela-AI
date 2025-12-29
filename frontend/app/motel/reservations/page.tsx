"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    CalendarCheck,
    Search,
    Filter,
    Clock,
    CheckCircle,
    XCircle,
    AlertCircle,
    Phone,
    User,
    BedDouble,
    Calendar,
    Plus,
} from "lucide-react";

interface Reservation {
    $id: string;
    guest_name: string;
    guest_phone: string;
    guest_email: string;
    room_type: string;
    check_in_date: string;
    check_out_date: string;
    num_guests: number;
    num_nights: number;
    rate_per_night: number;
    total_amount: number;
    status: string;
    source: string;
    booking_reference: string;
    notes: string;
    created_at: string;
}

type StatusFilter = "all" | "pending" | "confirmed" | "checked_in" | "checked_out" | "cancelled";

export default function ReservationsPage() {
    const [reservations, setReservations] = useState<Reservation[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [selectedReservation, setSelectedReservation] = useState<Reservation | null>(null);
    const [isWalkInModalOpen, setIsWalkInModalOpen] = useState(false);

    useEffect(() => {
        fetchReservations();
    }, []);

    const fetchReservations = async () => {
        try {
            const res = await fetch("/api/motel/reservations?limit=100");
            const data = await res.json();
            if (data.success) {
                setReservations(data.reservations);
            }
        } catch (error) {
            console.error("Error fetching reservations:", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredReservations = reservations.filter((res) => {
        // Status filter
        if (statusFilter !== "all" && res.status !== statusFilter) return false;

        // Search filter
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            return (
                res.guest_name?.toLowerCase().includes(query) ||
                res.guest_phone?.includes(query) ||
                res.booking_reference?.toLowerCase().includes(query)
            );
        }

        return true;
    });

    const formatDate = (dateStr: string) => {
        if (!dateStr) return "";
        const date = new Date(dateStr);
        return date.toLocaleDateString("en-AU", {
            weekday: "short",
            day: "numeric",
            month: "short",
        });
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "confirmed": return <CheckCircle className="w-4 h-4 text-green-600" />;
            case "pending": return <Clock className="w-4 h-4 text-yellow-600" />;
            case "checked_in": return <User className="w-4 h-4 text-blue-600" />;
            case "cancelled": return <XCircle className="w-4 h-4 text-red-600" />;
            default: return <AlertCircle className="w-4 h-4 text-gray-600" />;
        }
    };

    const getStatusBadge = (status: string) => {
        const styles: Record<string, string> = {
            pending: "bg-yellow-100 text-yellow-700 border-yellow-200",
            confirmed: "bg-green-100 text-green-700 border-green-200",
            checked_in: "bg-blue-100 text-blue-700 border-blue-200",
            checked_out: "bg-gray-100 text-gray-700 border-gray-200",
            cancelled: "bg-red-100 text-red-700 border-red-200",
        };
        return styles[status] || "bg-gray-100 text-gray-700 border-gray-200";
    };

    const getRoomTypeLabel = (type: string) => {
        const labels: Record<string, string> = {
            queen: "Queen Room",
            twin: "Twin Room",
            family: "Family Room",
            accessible: "Accessible Room",
        };
        return labels[type] || type;
    };

    const statusOptions: { value: StatusFilter; label: string; count: number }[] = [
        { value: "all", label: "All", count: reservations.length },
        { value: "pending", label: "Pending", count: reservations.filter(r => r.status === "pending").length },
        { value: "confirmed", label: "Confirmed", count: reservations.filter(r => r.status === "confirmed").length },
        { value: "checked_in", label: "Checked In", count: reservations.filter(r => r.status === "checked_in").length },
        { value: "cancelled", label: "Cancelled", count: reservations.filter(r => r.status === "cancelled").length },
    ];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Reservations</h1>
                    <p className="text-gray-600 mt-1">
                        Manage guest bookings and check-ins
                    </p>
                </div>
                <button
                    onClick={() => setIsWalkInModalOpen(true)}
                    className="flex items-center gap-2 px-4 py-2.5 bg-[#8B2332] text-white rounded-xl hover:bg-[#6B1A26] transition-colors shadow-sm font-medium"
                >
                    <Plus className="w-4 h-4" />
                    Add Walk-in
                </button>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-4">
                {/* Search */}
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search by name, phone, or reference..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                    />
                </div>

                {/* Status Tabs */}
                <div className="flex gap-2 overflow-x-auto pb-2 sm:pb-0">
                    {statusOptions.map((option) => (
                        <button
                            key={option.value}
                            onClick={() => setStatusFilter(option.value)}
                            className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors
                                ${statusFilter === option.value
                                    ? "bg-[#8B2332] text-white"
                                    : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-200"
                                }`}
                        >
                            {option.label}
                            <span className={`ml-2 px-1.5 py-0.5 rounded-full text-xs
                                ${statusFilter === option.value
                                    ? "bg-white/20"
                                    : "bg-gray-100"
                                }`}>
                                {option.count}
                            </span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Reservations List */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
            >
                {loading ? (
                    <div className="p-12 text-center text-gray-400">
                        Loading reservations...
                    </div>
                ) : filteredReservations.length === 0 ? (
                    <div className="p-12 text-center">
                        <CalendarCheck className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                        <p className="text-gray-500 font-medium">No reservations found</p>
                        <p className="text-sm text-gray-400 mt-1">
                            {searchQuery || statusFilter !== "all"
                                ? "Try adjusting your filters"
                                : "Voice bookings will appear here"}
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-gray-50 border-b border-gray-100">
                                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">Guest</th>
                                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">Room</th>
                                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">Dates</th>
                                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">Status</th>
                                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-600">Reference</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                                {filteredReservations.map((res) => (
                                    <tr
                                        key={res.$id}
                                        className="hover:bg-gray-50 transition-colors cursor-pointer"
                                        onClick={() => setSelectedReservation(res)}
                                    >
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 bg-[#8B2332]/10 rounded-full flex items-center justify-center">
                                                    <User className="w-5 h-5 text-[#8B2332]" />
                                                </div>
                                                <div>
                                                    <p className="font-medium text-gray-900">{res.guest_name}</p>
                                                    <p className="text-sm text-gray-500">{res.guest_phone}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <BedDouble className="w-4 h-4 text-gray-400" />
                                                <span className="text-gray-900">{getRoomTypeLabel(res.room_type)}</span>
                                            </div>
                                            <p className="text-sm text-gray-500">{res.num_guests} guest{res.num_guests > 1 ? "s" : ""}</p>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <Calendar className="w-4 h-4 text-gray-400" />
                                                <span className="text-gray-900">{formatDate(res.check_in_date)}</span>
                                            </div>
                                            <p className="text-sm text-gray-500">
                                                → {formatDate(res.check_out_date)} ({res.num_nights || 1} night{(res.num_nights || 1) > 1 ? "s" : ""})
                                            </p>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium border ${getStatusBadge(res.status)}`}>
                                                {getStatusIcon(res.status)}
                                                {res.status?.replace("_", " ")}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <p className="font-mono text-sm text-gray-600">{res.booking_reference}</p>
                                            <p className="text-xs text-gray-400">{res.source}</p>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </motion.div>

            {/* Walk-in Modal */}
            <AnimatePresence>
                {isWalkInModalOpen && (
                    <WalkInModal
                        isOpen={isWalkInModalOpen}
                        onClose={() => setIsWalkInModalOpen(false)}
                        onSuccess={() => {
                            setIsWalkInModalOpen(false);
                            fetchReservations();
                        }}
                    />
                )}
            </AnimatePresence>

            {/* Reservation Detail Modal */}
            {selectedReservation && (
                <div
                    className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
                    onClick={() => setSelectedReservation(null)}
                >
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="bg-white rounded-2xl max-w-lg w-full max-h-[80vh] overflow-auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="p-6 border-b border-gray-100">
                            <div className="flex items-center justify-between">
                                <h3 className="text-lg font-semibold text-gray-900">
                                    Reservation Details
                                </h3>
                                <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadge(selectedReservation.status)}`}>
                                    {selectedReservation.status}
                                </span>
                            </div>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-gray-500">Guest Name</p>
                                    <p className="font-medium">{selectedReservation.guest_name}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Phone</p>
                                    <p className="font-medium">{selectedReservation.guest_phone}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Room Type</p>
                                    <p className="font-medium">{getRoomTypeLabel(selectedReservation.room_type)}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Guests</p>
                                    <p className="font-medium">{selectedReservation.num_guests}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Check-in</p>
                                    <p className="font-medium">{formatDate(selectedReservation.check_in_date)}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Check-out</p>
                                    <p className="font-medium">{formatDate(selectedReservation.check_out_date)}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Rate/Night</p>
                                    <p className="font-medium">${selectedReservation.rate_per_night}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Total</p>
                                    <p className="font-medium text-[#8B2332]">${selectedReservation.total_amount}</p>
                                </div>
                            </div>
                            {selectedReservation.notes && (
                                <div>
                                    <p className="text-sm text-gray-500">Notes</p>
                                    <p className="text-gray-700 mt-1">{selectedReservation.notes}</p>
                                </div>
                            )}
                            <div className="pt-4 border-t border-gray-100">
                                <p className="text-xs text-gray-400">
                                    Reference: {selectedReservation.booking_reference} · Source: {selectedReservation.source}
                                </p>
                            </div>
                        </div>
                        <div className="p-6 border-t border-gray-100 bg-gray-50">
                            <button
                                onClick={() => setSelectedReservation(null)}
                                className="w-full px-4 py-2 bg-[#8B2332] text-white rounded-xl hover:bg-[#6B1A26] transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </div>
    );
}

function WalkInModal({ isOpen, onClose, onSuccess }: { isOpen: boolean; onClose: () => void; onSuccess: () => void }) {
    const [loading, setLoading] = useState(false);
    const [formData, setFormData] = useState({
        guest_name: "",
        guest_phone: "",
        room_type: "queen",
        check_in_date: "",
        check_out_date: "",
        guests: 1,
        notes: ""
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            const res = await fetch("/api/motel/reservations/manual", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(formData),
            });

            const data = await res.json();

            if (data.success) {
                onSuccess();
            } else {
                alert(data.error || "Failed to create walk-in booking");
            }
        } catch (error) {
            console.error("Error creating walk-in:", error);
            alert("Network error, please try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] overflow-auto"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-6 border-b border-gray-100">
                    <h3 className="text-lg font-semibold text-gray-900">Add Walk-in Booking</h3>
                    <p className="text-sm text-gray-500">Manually record a guest booking</p>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Guest Name</label>
                        <input
                            required
                            type="text"
                            value={formData.guest_name}
                            onChange={(e) => setFormData({ ...formData, guest_name: e.target.value })}
                            className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Phone (Optional)</label>
                            <input
                                type="tel"
                                value={formData.guest_phone}
                                onChange={(e) => setFormData({ ...formData, guest_phone: e.target.value })}
                                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Room Type</label>
                            <select
                                value={formData.room_type}
                                onChange={(e) => setFormData({ ...formData, room_type: e.target.value })}
                                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            >
                                <option value="queen">Queen Room</option>
                                <option value="twin">Twin Room</option>
                                <option value="family">Family Room</option>
                                <option value="accessible">Accessible Room</option>
                            </select>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Check-in</label>
                            <input
                                required
                                type="date"
                                value={formData.check_in_date}
                                onChange={(e) => setFormData({ ...formData, check_in_date: e.target.value })}
                                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Check-out</label>
                            <input
                                required
                                type="date"
                                value={formData.check_out_date}
                                onChange={(e) => setFormData({ ...formData, check_out_date: e.target.value })}
                                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                        <textarea
                            value={formData.notes}
                            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                            className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            rows={2}
                            placeholder="Any special requests..."
                        />
                    </div>

                    <div className="pt-4 flex gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="flex-1 px-4 py-2 bg-[#8B2332] text-white rounded-xl hover:bg-[#6B1A26] transition-colors disabled:opacity-50"
                        >
                            {loading ? "Adding..." : "Add Booking"}
                        </button>
                    </div>
                </form>
            </motion.div>
        </div>
    );
}
