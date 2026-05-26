"use client";

import { useEffect, useState } from "react";
import { fetchWithAuth } from "@/lib/api-client";
import { Reservation } from "@/app/dashboard/reservations/page";
import { useTenant } from "@/contexts/TenantContext";

interface Room {
    $id: string;
    room_number: string;
    room_type: string;
    base_rate: number;
    max_guests: number;
    status: string;
}

export function PmsBoard({ reservations }: { reservations: Reservation[] }) {
    const [rooms, setRooms] = useState<Room[]>([]);
    const [loading, setLoading] = useState(true);
    const { tenant } = useTenant();
    
    // Generate next 7 days
    const dates = Array.from({ length: 7 }).map((_, i) => {
        const d = new Date();
        d.setDate(d.getDate() + i);
        return d.toISOString().split("T")[0];
    });

    useEffect(() => {
        fetchRooms();
    }, [tenant.id]);

    const fetchRooms = async () => {
        try {
            const res = await fetchWithAuth(`/api/dashboard/rooms?tenant_id=${tenant.id}`);
            const data = await res.json();
            if (data.success) {
                setRooms(data.rooms);
            }
        } catch (error) {
            console.error("Error fetching rooms:", error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="p-8 text-center text-slate-500 animate-pulse">Loading Room Inventory...</div>;
    }

    // Helper: Find booking for a specific room and date
    const getBookingForRoomDate = (roomNumber: string, dateStr: string) => {
        return reservations.find(r => {
            if (r.status === "cancelled" || r.status === "rejected") return false;
            // A booking occupies the room if check_in <= date AND check_out > date
            return r.room_number === roomNumber && r.check_in_date <= dateStr && r.check_out_date > dateStr;
        });
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
            <table className="w-full text-sm text-left border-collapse">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-700">
                    <tr>
                        <th className="px-4 py-3 font-semibold border-r border-slate-200 min-w-[150px]">Room</th>
                        {dates.map(date => {
                            const dateObj = new Date(date);
                            const isToday = date === dates[0];
                            return (
                                <th key={date} className={`px-4 py-3 font-semibold border-r border-slate-200 min-w-[120px] ${isToday ? "bg-blue-50 text-blue-700" : ""}`}>
                                    {dateObj.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                                </th>
                            );
                        })}
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                    {rooms.map(room => (
                        <tr key={room.room_number} className="hover:bg-slate-50 transition-colors">
                            <td className="px-4 py-3 border-r border-slate-200 bg-slate-50/50">
                                <div className="font-medium text-slate-900">Room {room.room_number}</div>
                                <div className="text-xs text-slate-500 capitalize">{room.room_type}</div>
                            </td>
                            {dates.map(date => {
                                const booking = getBookingForRoomDate(room.room_number, date);
                                const isToday = date === dates[0];
                                
                                return (
                                    <td key={`${room.room_number}-${date}`} className={`p-2 border-r border-slate-200 relative ${isToday && !booking ? "bg-blue-50/30" : ""}`}>
                                        {booking ? (
                                            <div className={`p-2 rounded border text-xs ${
                                                booking.status === "confirmed" ? "bg-green-100 border-green-200 text-green-800" :
                                                booking.status === "checked_in" ? "bg-blue-100 border-blue-200 text-blue-800" :
                                                "bg-yellow-100 border-yellow-200 text-yellow-800"
                                            }`}>
                                                <div className="font-semibold truncate">{booking.guest_name}</div>
                                                <div className="text-[10px] opacity-80 mt-1">{booking.status.replace("_", " ")}</div>
                                            </div>
                                        ) : (
                                            <div className="h-full w-full flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                                                <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Available</span>
                                            </div>
                                        )}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
