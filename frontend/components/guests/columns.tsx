"use client"

import { ColumnDef } from "@tanstack/react-table"
import { MoreHorizontal, ArrowUpDown, User, Phone, Mail, Star, Calendar } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"

export type Guest = {
    $id: string
    name: string
    phone: string
    email?: string
    total_stays: number
    last_stay_date?: string
    preferred_room_type?: string
    notes?: string
    is_vip?: string // "true" or "false" string from DB
    status?: string // "inquiry" or "guest"
    created_at?: string
}

const formatDate = (dateStr?: string) => {
    if (!dateStr) return "—"
    return new Date(dateStr).toLocaleDateString("en-AU", { month: "short", day: "numeric", year: "numeric" })
}

export const columns: ColumnDef<Guest>[] = [
    {
        accessorKey: "name",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    className="-ml-4 hover:bg-transparent text-slate-600"
                >
                    Guest
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => {
            const isVip = row.original.is_vip === "true"
            return (
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-medium border border-slate-200">
                        {row.original.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900">{row.getValue("name")}</span>
                            {isVip && <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />}
                        </div>
                        {isVip && <span className="text-[10px] text-amber-600 font-medium">VIP Guest</span>}
                    </div>
                </div>
            )
        },
    },
    {
        accessorKey: "phone",
        header: "Contact",
        cell: ({ row }) => {
            return (
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2 text-sm text-slate-700">
                        <Phone className="w-3 h-3 text-slate-400" />
                        {row.getValue("phone")}
                    </div>
                    {row.original.email && (
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                            <Mail className="w-3 h-3 text-slate-400" />
                            {row.original.email}
                        </div>
                    )}
                </div>
            )
        },
    },
    {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => {
            const status = row.original.status || "inquiry";
            const isGuest = status !== "inquiry";

            return (
                <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border
                    ${isGuest
                        ? "bg-green-50 text-green-700 border-green-200"
                        : "bg-slate-50 text-slate-600 border-slate-200"
                    }`}
                >
                    {isGuest ? "Guest" : "Inquiry"}
                </div>
            )
        }
    },
    {
        accessorKey: "total_stays",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    className="-ml-4 hover:bg-transparent text-slate-600"
                >
                    Stays
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => {
            return (
                <div className="pl-4 font-medium text-slate-700">
                    {row.getValue("total_stays")}
                </div>
            )
        }
    },
    {
        accessorKey: "last_stay_date",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    className="-ml-4 hover:bg-transparent text-slate-600"
                >
                    Last Stay
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => {
            return (
                <div className="flex items-center gap-2 text-sm text-slate-600">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    {formatDate(row.getValue("last_stay_date"))}
                </div>
            )
        },
    },
    {
        id: "actions",
        cell: ({ row }) => {
            const guest = row.original
            return (
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0 text-slate-500 hover:text-slate-900">
                            <span className="sr-only">Open menu</span>
                            <MoreHorizontal className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuItem onClick={() => navigator.clipboard.writeText(guest.phone)}>
                            Copy Phone
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem>View History</DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            )
        },
    },
]
