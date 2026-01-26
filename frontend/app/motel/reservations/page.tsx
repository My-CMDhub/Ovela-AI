"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    CalendarCheck,
    CheckCircle,
    XCircle,
    AlertCircle,
    User,
    BedDouble,
    Calendar,
    Plus,
} from "lucide-react";
import { columns } from "@/components/reservations/columns";
import { DataTable } from "@/components/reservations/data-table";

export interface Reservation {
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
    payment_link_url?: string;
    payment_status?: string;
    notes: string;
    created_at: string;
}

type StatusFilter = "all" | "pending" | "confirmed" | "checked_in" | "checked_out" | "cancelled" | "rejected" | "link_sent" | "approved";

export default function ReservationsPage() {
    const [reservations, setReservations] = useState<Reservation[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
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

    const handleApprove = async (id: string) => {
        if (!confirm("Approve this booking and send payment link?")) return;
        setActionLoading(true);
        try {
            const res = await fetch(`/api/motel/bookings/${id}/approve`, { method: "POST" });
            const data = await res.json();
            if (data.success) {
                alert("Booking approved and payment link sent!");
                fetchReservations();
                setSelectedReservation(null);
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) {
            alert("Network error");
        } finally {
            setActionLoading(false);
        }
    };

    const handleReject = async (id: string) => {
        if (!confirm("Reject this booking?")) return;
        setActionLoading(true);
        try {
            const res = await fetch(`/api/motel/bookings/${id}/reject`, { method: "POST" });
            const data = await res.json();
            if (data.success) {
                fetchReservations();
                setSelectedReservation(null);
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) {
            alert("Network error");
        } finally {
            setActionLoading(false);
        }
    };

    const handleResendLink = async (id: string) => {
        setActionLoading(true);
        try {
            const res = await fetch(`/api/motel/bookings/${id}/payment-link`, { method: "POST" });
            const data = await res.json();
            if (data.success) {
                if (data.payment_link) {
                    prompt("Payment Link:", data.payment_link);
                } else {
                    alert("Link sent!");
                }
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) {
            alert("Network error");
        } finally {
            setActionLoading(false);
        }
    };


    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Reservations</h1>
                    <p className="text-slate-600 mt-1">
                        Manage guest bookings and check-ins
                    </p>
                </div>
            </div>

            {/* Data Table */}
            <DataTable
                columns={columns}
                data={reservations}
                loading={loading}
                onRowClick={setSelectedReservation}
                onAddWalkIn={() => setIsWalkInModalOpen(true)}
            />

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
                    {/* Reuse existing modal content logic but wrapped cleaner if needed */}
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
                                <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
                                    {selectedReservation.status}
                                </span>
                            </div>
                        </div>
                        <div className="p-6 space-y-4">
                            {/* ... (Keep existing modal content logic for now as it's complex) ... */}
                            {/* NOTE: Re-implementing the modal body briefly to ensure it works contextually */}
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
                                    <p className="font-medium">{selectedReservation.room_type}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Guests</p>
                                    <p className="font-medium">{selectedReservation.num_guests}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Check-in</p>
                                    <p className="font-medium">{new Date(selectedReservation.check_in_date).toLocaleDateString()}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Check-out</p>
                                    <p className="font-medium">{new Date(selectedReservation.check_out_date).toLocaleDateString()}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Rate/Night</p>
                                    <p className="font-medium">${selectedReservation.rate_per_night}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Total</p>
                                    <p className="font-medium text-[#D4AF37]">${selectedReservation.total_amount}</p>
                                </div>
                            </div>
                            {selectedReservation.notes && (
                                <div>
                                    <p className="text-sm text-gray-500">Notes</p>
                                    <p className="text-gray-700 mt-1">{selectedReservation.notes}</p>
                                </div>
                            )}

                            {/* Action Buttons */}
                            {selectedReservation.status === "pending" && (
                                <div className="pt-4 border-t border-gray-100 flex gap-3">
                                    <button
                                        onClick={() => handleApprove(selectedReservation.$id)}
                                        disabled={actionLoading}
                                        className="flex-1 px-4 py-2.5 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors font-medium disabled:opacity-50"
                                    >
                                        {actionLoading ? "Processing..." : "Approve & Send Link"}
                                    </button>
                                    <button
                                        onClick={() => handleReject(selectedReservation.$id)}
                                        disabled={actionLoading}
                                        className="px-4 py-2.5 bg-red-100 text-red-700 rounded-xl hover:bg-red-200 transition-colors font-medium disabled:opacity-50"
                                    >
                                        Reject
                                    </button>
                                </div>
                            )}

                            {(selectedReservation.status === "link_sent" || selectedReservation.status === "approved") && (
                                <div className="pt-4 border-t border-gray-100">
                                    <button
                                        onClick={() => handleResendLink(selectedReservation.$id)}
                                        disabled={actionLoading}
                                        className="w-full px-4 py-2 bg-blue-50 text-blue-700 rounded-xl hover:bg-blue-100 transition-colors font-medium"
                                    >
                                        {actionLoading ? "Loading..." : "Get Payment Link"}
                                    </button>
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
                                className="w-full px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors"
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
;


function WalkInModal({ isOpen, onClose, onSuccess }: { isOpen: boolean; onClose: () => void; onSuccess: () => void }) {
    const [loading, setLoading] = useState(false);
    const [formData, setFormData] = useState({
        guest_name: "",
        guest_phone: "",
        guest_email: "",
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
                            <label className="block text-sm font-medium text-gray-700 mb-1">Phone <span className="text-red-500">*</span></label>
                            <input
                                required
                                type="tel"
                                value={formData.guest_phone}
                                onChange={(e) => setFormData({ ...formData, guest_phone: e.target.value })}
                                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Email (Optional)</label>
                            <input
                                type="email"
                                value={formData.guest_email}
                                onChange={(e) => setFormData({ ...formData, guest_email: e.target.value })}
                                className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8B2332]/20 focus:border-[#8B2332]"
                            />
                        </div>
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
                            className="flex-1 px-4 py-2 bg-[#8B2332] text-white rounded-xl bg-slate-900 hover:bg-slate-800 text-white shadow-sm"
                        >
                            {loading ? "Adding..." : "Add Booking"}
                        </button>
                    </div>
                </form>
            </motion.div>
        </div>
    );
}
