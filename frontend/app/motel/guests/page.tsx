"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
    Users,
} from "lucide-react";
import { columns } from "@/components/guests/columns";
import { DataTable } from "@/components/guests/data-table";

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

import { useTenant } from "@/contexts/TenantContext";

export default function GuestsPage() {
    const [guests, setGuests] = useState<Guest[]>([]);
    const [loading, setLoading] = useState(true);
    const { tenant } = useTenant();

    useEffect(() => {
        fetchGuests();
    }, [tenant.id]);

    const fetchGuests = async () => {
        try {
            const res = await fetch(`/api/motel/guests?tenant_id=${tenant.id}`);
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

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Guests</h1>
                    <p className="text-slate-600 mt-1">
                        Guest profiles and stay history
                    </p>
                </div>
                <div className="text-sm text-slate-500 font-medium">
                    {guests.length} total guests
                </div>
            </div>

            <DataTable
                columns={columns}
                data={guests}
                loading={loading}
            />
        </div>
    );
}

