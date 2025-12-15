"use client";

import { useState, useEffect } from "react";
import { Check, X, Phone, Clock, User, Calendar, RefreshCw } from "lucide-react";

interface BookingRequest {
    $id: string;
    customer_name: string;
    customer_phone: string;
    service_name?: string;
    preferred_date?: string;
    preferred_time?: string;
    notes?: string;
    status: "pending" | "approved" | "rejected";
    source?: string;
    created_at?: string;
}

// Use local Next.js API proxy (adds API key server-side)
const API_URL = "/api/dashboard";

export default function RequestsPage() {
    const [requests, setRequests] = useState<BookingRequest[]>([]);
    const [filter, setFilter] = useState<string>("pending");
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    // Rejection modal state
    const [showRejectModal, setShowRejectModal] = useState(false);
    const [rejectReason, setRejectReason] = useState("");
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [rejectingName, setRejectingName] = useState<string>("");

    const fetchRequests = async () => {
        setLoading(true);
        try {
            // API key is added server-side by the proxy
            const url = filter
                ? `${API_URL}/requests?status=${filter}`
                : `${API_URL}/requests`;
            const res = await fetch(url);
            const data = await res.json();
            setRequests(data.requests || []);
        } catch (error) {
            console.error("Failed to fetch requests:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRequests();
    }, [filter]);

    const handleApprove = async (id: string) => {
        setActionLoading(id);
        try {
            // API key is added server-side by the proxy
            await fetch(`${API_URL}/requests/${id}/approve`, {
                method: "PATCH"
            });
            fetchRequests();
        } catch (error) {
            console.error("Failed to approve:", error);
        } finally {
            setActionLoading(null);
        }
    };

    // Open rejection modal
    const openRejectModal = (id: string, name: string) => {
        setRejectingId(id);
        setRejectingName(name);
        setRejectReason("");
        setShowRejectModal(true);
    };

    // Confirm rejection with reason
    const confirmReject = async () => {
        if (!rejectingId) return;
        setActionLoading(rejectingId);
        try {
            // API key is added server-side by the proxy
            const reasonParam = rejectReason ? `?reason=${encodeURIComponent(rejectReason)}` : "";
            await fetch(`${API_URL}/requests/${rejectingId}/reject${reasonParam}`, {
                method: "PATCH"
            });
            setShowRejectModal(false);
            setRejectingId(null);
            setRejectReason("");
            fetchRequests();
        } catch (error) {
            console.error("Failed to reject:", error);
        } finally {
            setActionLoading(null);
        }
    };

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return "N/A";
        try {
            return new Date(dateStr).toLocaleDateString("en-AU", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return dateStr;
        }
    };

    return (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Booking Requests</h1>
                    <p className="text-gray-500">Manage appointment requests from customers</p>
                </div>
                <button
                    onClick={fetchRequests}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 dark:text-black"
                >
                    <RefreshCw className={`w-4 h-4 dark ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-2 mb-6">
                {["pending", "approved", "rejected", ""].map((status) => (
                    <button
                        key={status || "all"}
                        onClick={() => setFilter(status)}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${filter === status
                            ? "bg-indigo-600 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                            }`}
                    >
                        {status === "" ? "All" : status.charAt(0).toUpperCase() + status.slice(1)}
                    </button>
                ))}
            </div>

            {/* Requests List */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                </div>
            ) : requests.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 rounded-xl">
                    <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No {filter} requests</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {requests.map((request) => (
                        <div
                            key={request.$id}
                            className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow"
                        >
                            <div className="flex flex-col md:flex-row justify-between items-start gap-4">
                                <div className="space-y-2">
                                    <div className="flex items-center gap-3">
                                        <User className="w-5 h-5 text-gray-400" />
                                        <span className="font-medium text-gray-900">
                                            {request.customer_name}
                                        </span>
                                        {request.source === "missed_call" && (
                                            <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs rounded-full">
                                                📞 Missed Call
                                            </span>
                                        )}
                                    </div>

                                    <div className="flex items-center gap-3 text-gray-500">
                                        <Phone className="w-4 h-4" />
                                        <a href={`tel:${request.customer_phone}`} className="hover:text-indigo-600">
                                            {request.customer_phone}
                                        </a>
                                    </div>

                                    {request.service_name && (
                                        <div className="text-gray-600">
                                            <span className="font-medium">Service:</span> {request.service_name}
                                        </div>
                                    )}

                                    {(request.preferred_date || request.preferred_time) && (
                                        <div className="flex items-center gap-2 text-gray-600">
                                            <Calendar className="w-4 h-4" />
                                            {request.preferred_date} {request.preferred_time}
                                        </div>
                                    )}

                                    {request.notes && (
                                        <p className="text-sm text-gray-500 italic">{request.notes}</p>
                                    )}

                                    <p className="text-xs text-gray-400">
                                        Received: {formatDate(request.created_at)}
                                    </p>
                                </div>

                                {/* Actions */}
                                <div className="w-full md:w-auto flex flex-col sm:flex-row gap-2 mt-4 md:mt-0">
                                    {request.status === "pending" && (
                                        <div className="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
                                            <button
                                                onClick={() => handleApprove(request.$id)}
                                                disabled={actionLoading === request.$id}
                                                className="flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 w-full sm:w-auto"
                                            >
                                                <Check className="w-4 h-4" />
                                                Approve
                                            </button>
                                            <button
                                                onClick={() => openRejectModal(request.$id, request.customer_name)}
                                                disabled={actionLoading === request.$id}
                                                className="flex items-center justify-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 disabled:opacity-50 w-full sm:w-auto"
                                            >
                                                <X className="w-4 h-4" />
                                                Reject
                                            </button>
                                        </div>
                                    )}

                                    {request.status === "approved" && (
                                        <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                                            ✓ Approved
                                        </span>
                                    )}

                                    {request.status === "rejected" && (
                                        <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
                                            ✗ Rejected
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Rejection Reason Modal */}
            {showRejectModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4 shadow-xl">
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">
                            Reject Request
                        </h3>
                        <p className="text-gray-500 text-sm mb-4">
                            Rejecting appointment request from <strong>{rejectingName}</strong>.
                            Optionally provide a reason (will be sent to customer).
                        </p>
                        <textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="e.g., Fully booked on that day, please try another date..."
                            rows={3}
                            className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:border-red-400 focus:ring-2 focus:ring-red-100 outline-none transition resize-none mb-4"
                        />
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowRejectModal(false)}
                                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmReject}
                                disabled={actionLoading === rejectingId}
                                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                            >
                                {actionLoading === rejectingId ? (
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                    <X className="w-4 h-4" />
                                )}
                                Confirm Rejection
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
