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
    Mail,
    CreditCard,
    ExternalLink,
} from "lucide-react";
import { columns } from "@/components/reservations/columns";
import { DataTable } from "@/components/reservations/data-table";
import { PmsBoard } from "@/components/reservations/pms-board";
import { fetchWithAuth } from "@/lib/api-client";

export interface Reservation {
    $id: string;
    guest_name: string;
    guest_phone: string;
    guest_email: string;
    room_type: string;
    room_number?: string;
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

import { useTenant } from "@/contexts/TenantContext";

export default function ReservationsPage() {
    const [reservations, setReservations] = useState<Reservation[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [selectedReservation, setSelectedReservation] = useState<Reservation | null>(null);
    const [isWalkInModalOpen, setIsWalkInModalOpen] = useState(false);
    const [viewMode, setViewMode] = useState<"list" | "board">("board");

    const { tenant } = useTenant();

    useEffect(() => {
        fetchReservations();
    }, [tenant.id]); // Re-fetch on tenant change

    const fetchReservations = async () => {
        try {
            const res = await fetchWithAuth(`/api/dashboard/reservations?limit=100&tenant_id=${tenant.id}`);
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
            const res = await fetchWithAuth(`/api/dashboard/bookings/${id}/approve`, { method: "POST" });
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
            const res = await fetchWithAuth(`/api/dashboard/bookings/${id}/reject`, { method: "POST" });
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
            const res = await fetchWithAuth(`/api/dashboard/bookings/${id}/payment-link`, { method: "POST" });
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
                    <h1 className="text-2xl font-bold text-slate-900">Reservations & PMS</h1>
                    <p className="text-slate-600 mt-1">
                        Manage guest bookings and live room availability
                    </p>
                </div>
                <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-lg border border-slate-200">
                    <button
                        onClick={() => setViewMode("board")}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${viewMode === "board"
                                ? "bg-white shadow-sm text-slate-900 border border-slate-200/50"
                                : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50"
                            }`}
                    >
                        PMS Board
                    </button>
                    <button
                        onClick={() => setViewMode("list")}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${viewMode === "list"
                                ? "bg-white shadow-sm text-slate-900 border border-slate-200/50"
                                : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50"
                            }`}
                    >
                        List View
                    </button>
                </div>
            </div>

            {/* View Mode Content */}
            {viewMode === "board" ? (
                <div className="space-y-4">
                    <div className="flex justify-end">
                        <button
                            onClick={() => setIsWalkInModalOpen(true)}
                            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-slate-900 text-white hover:bg-slate-900/90 h-10 px-4 py-2"
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            Add Walk-in
                        </button>
                    </div>
                    <PmsBoard reservations={reservations} />
                </div>
            ) : (
                <DataTable
                    columns={columns}
                    data={reservations}
                    loading={loading}
                    onRowClick={setSelectedReservation}
                    onAddWalkIn={() => setIsWalkInModalOpen(true)}
                />
            )}

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
                            {/* ── Guest & Room grid ── */}
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
                                    <p className="font-medium capitalize">{selectedReservation.room_type}</p>
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
                                    <p className="text-sm text-gray-500">Rate / Night</p>
                                    <p className="font-medium">${selectedReservation.rate_per_night}</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Total</p>
                                    <p className="font-semibold text-emerald-700">${selectedReservation.total_amount}</p>
                                </div>
                            </div>

                            {/* ── Email row — shows MISSING badge when blank (key for demo) ── */}
                            <div className="pt-3 border-t border-gray-100">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Mail className="w-4 h-4 text-gray-400" />
                                        <p className="text-sm text-gray-500">Email</p>
                                    </div>
                                    {selectedReservation.guest_email ? (
                                        <p className="font-medium text-gray-900 text-sm">{selectedReservation.guest_email}</p>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-600 border border-red-200">
                                            <AlertCircle className="w-3 h-3" />
                                            MISSING
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* ── Payment status row ── */}
                            <div className="pt-3 border-t border-gray-100">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <CreditCard className="w-4 h-4 text-gray-400" />
                                        <p className="text-sm text-gray-500">Payment</p>
                                    </div>
                                    {(() => {
                                        const ps = selectedReservation.payment_status || selectedReservation.status || "unknown";
                                        const styles: Record<string, string> = {
                                            paid:            "bg-emerald-50 text-emerald-700 border-emerald-200",
                                            confirmed:       "bg-emerald-50 text-emerald-700 border-emerald-200",
                                            link_sent:       "bg-sky-50 text-sky-700 border-sky-200",
                                            pending_payment: "bg-amber-50 text-amber-700 border-amber-200",
                                            pending:         "bg-amber-50 text-amber-700 border-amber-200",
                                            outstanding:     "bg-orange-50 text-orange-700 border-orange-200",
                                            email_failed:    "bg-red-50 text-red-700 border-red-200",
                                        };
                                        const cls = styles[ps] ?? "bg-gray-50 text-gray-600 border-gray-200";
                                        return (
                                            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${cls}`}>
                                                {ps.replace(/_/g, " ")}
                                            </span>
                                        );
                                    })()}
                                </div>
                                {/* Payment link — clickable if present */}
                                {selectedReservation.payment_link_url && (
                                    <a
                                        href={selectedReservation.payment_link_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="mt-2 flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 hover:underline"
                                    >
                                        <ExternalLink className="w-3 h-3" />
                                        View payment link
                                    </a>
                                )}
                            </div>

                            {selectedReservation.notes && (
                                <div className="pt-3 border-t border-gray-100">
                                    <p className="text-sm text-gray-500 mb-1">Notes</p>
                                    <p className="text-gray-700 text-sm">{selectedReservation.notes}</p>
                                </div>
                            )}

                            {/* Action Buttons */}
                            {(selectedReservation.status === "pending" || selectedReservation.status === "pending_confirmation") && (
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
            const res = await fetchWithAuth("/api/dashboard/reservations/manual", {
                method: "POST",
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
