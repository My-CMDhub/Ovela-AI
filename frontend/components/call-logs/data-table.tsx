"use client"

import * as React from "react"
import {
    ColumnDef,
    ColumnFiltersState,
    SortingState,
    VisibilityState,
    flexRender,
    getCoreRowModel,
    getFilteredRowModel,
    getPaginationRowModel,
    getSortedRowModel,
    useReactTable,
} from "@tanstack/react-table"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    DropdownMenu,
    DropdownMenuCheckboxItem,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Search, SlidersHorizontal, Filter } from "lucide-react"

interface DataTableProps<TData, TValue> {
    columns: ColumnDef<TData, TValue>[]
    data: TData[]
    loading?: boolean
    onRowClick?: (row: TData) => void
}

export function DataTable<TData, TValue>({
    columns,
    data,
    loading = false,
    onRowClick,
}: DataTableProps<TData, TValue>) {
    const [sorting, setSorting] = React.useState<SortingState>([])
    const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
    const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
    const [expandedRowId, setExpandedRowId] = React.useState<string | null>(null)

    // Custom filter logic could go here if needed, but default column logic works for strict string matches.
    // For "Status", we might want "includes" check if we allow updating the column definition filterFn.

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        onSortingChange: setSorting,
        getSortedRowModel: getSortedRowModel(),
        onColumnFiltersChange: setColumnFilters,
        getFilteredRowModel: getFilteredRowModel(),
        onColumnVisibilityChange: setColumnVisibility,
        state: {
            sorting,
            columnFilters,
            columnVisibility,
        },
    })

    // Helper for Status Filter
    // We assume there is a column with id "outcome" or accessorKey "outcome"
    const outcomeColumn = table.getColumn("outcome")

    return (
        <div className="space-y-4">
            {/* Table Toolbar */}
            <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
                <div className="flex flex-1 flex-col sm:flex-row gap-2 w-full">
                    <div className="relative w-full max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <Input
                            placeholder="Search phone..."
                            value={(table.getColumn("phone")?.getFilterValue() as string) ?? ""}
                            onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                                table.getColumn("phone")?.setFilterValue(event.target.value)
                            }
                            className="pl-9 h-10 bg-white"
                        />
                    </div>

                    {/* Status Filter */}
                    {outcomeColumn && (
                        <div className="flex items-center gap-2">
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline" size="sm" className="h-10 border-dashed">
                                        <Filter className="mr-2 h-4 w-4" />
                                        Status
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="start" className="w-[200px]">
                                    {["completed", "timeout", "spam", "transferred"].map((status) => (
                                        <DropdownMenuCheckboxItem
                                            key={status}
                                            checked={(outcomeColumn.getFilterValue() as string)?.includes(status)}
                                            onCheckedChange={(checked) => {
                                                // Simple single select for now, or just set filter value directly
                                                // For multi-select, we'd need a more complex state, keep it simple: string match
                                                if (checked) outcomeColumn.setFilterValue(status)
                                                else outcomeColumn.setFilterValue(undefined)
                                            }}
                                            className="capitalize"
                                        >
                                            {status}
                                        </DropdownMenuCheckboxItem>
                                    ))}
                                    <DropdownMenuCheckboxItem
                                        checked={!outcomeColumn.getFilterValue()}
                                        onCheckedChange={() => outcomeColumn.setFilterValue(undefined)}
                                        className="border-t mt-1 font-medium text-gray-500"
                                    >
                                        Clear Filter
                                    </DropdownMenuCheckboxItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    )}
                </div>

                {/* Date Range Placeholders (Visual for now, to fully implement we need column filterFn for dates) */}
                {/* 
                <div className="flex items-center gap-2">
                    <Input type="date" className="h-9 w-[130px] text-xs" />
                    <span className="text-gray-400">-</span>
                    <Input type="date" className="h-9 w-[130px] text-xs" />
                </div>
                 */}

                <div className="flex items-center gap-2">
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" className="ml-auto h-8 hidden lg:flex">
                                <SlidersHorizontal className="mr-2 h-4 w-4" />
                                View
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            {table
                                .getAllColumns()
                                .filter((column) => column.getCanHide())
                                .map((column) => {
                                    return (
                                        <DropdownMenuCheckboxItem
                                            key={column.id}
                                            className="capitalize"
                                            checked={column.getIsVisible()}
                                            onCheckedChange={(value) =>
                                                column.toggleVisibility(!!value)
                                            }
                                        >
                                            {column.id}
                                        </DropdownMenuCheckboxItem>
                                    )
                                })}
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                <Table>
                    <TableHeader className="bg-gray-50/50">
                        {table.getHeaderGroups().map((headerGroup) => (
                            <TableRow key={headerGroup.id} className="hover:bg-transparent">
                                {headerGroup.headers.map((header) => {
                                    return (
                                        <TableHead key={header.id} className="py-3 px-4 font-semibold text-gray-700">
                                            {header.isPlaceholder
                                                ? null
                                                : flexRender(
                                                    header.column.columnDef.header,
                                                    header.getContext()
                                                )}
                                        </TableHead>
                                    )
                                })}
                            </TableRow>
                        ))}
                    </TableHeader>
                    <TableBody>
                        {table.getRowModel().rows?.length ? (
                            table.getRowModel().rows.map((row) => (
                                <React.Fragment key={row.id}>
                                    <TableRow
                                        data-state={row.getIsSelected() && "selected"}
                                        onClick={() => {
                                            setExpandedRowId(expandedRowId === row.id ? null : row.id)
                                            onRowClick && onRowClick(row.original)
                                        }}
                                        className={`cursor-pointer transition-colors hover:bg-gray-50 ${loading ? 'opacity-50 pointer-events-none' : ''} ${expandedRowId === row.id ? 'bg-blue-50/30' : ''}`}
                                    >
                                        {row.getVisibleCells().map((cell) => (
                                            <TableCell key={cell.id} className="py-3 px-4">
                                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                            </TableCell>
                                        ))}
                                    </TableRow>
                                    {expandedRowId === row.id && (
                                        <TableRow className="bg-slate-50/50 hover:bg-slate-50/50 border-t border-slate-100">
                                            <TableCell colSpan={columns.length} className="p-0">
                                                <div className="p-4 md:p-8 space-y-8 animate-in transition-all duration-300 slide-in-from-top-2">
                                                    {/* Premium AI Summary Section */}
                                                    <div className="relative overflow-hidden bg-white rounded-2xl p-5 md:p-6 border border-blue-100 shadow-sm group">
                                                        <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                                                            <svg className="w-12 h-12 text-blue-600" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" /></svg>
                                                        </div>
                                                        <h4 className="text-[10px] font-bold text-blue-600 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
                                                            <span className="relative flex h-2 w-2">
                                                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                                                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                                                            </span>
                                                            AI Analysis
                                                        </h4>
                                                        <p className="text-slate-700 text-sm md:text-base font-medium leading-relaxed max-w-2xl">
                                                            {(row.original as any).call_summary || (
                                                                <span className="text-slate-400 italic">Processing high-level summary...</span>
                                                            )}
                                                        </p>
                                                    </div>

                                                    {/* Chat Transcript Section */}
                                                    <div className="space-y-5">
                                                        <div className="flex items-center justify-between px-2">
                                                            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">
                                                                Call Conversation
                                                            </h4>
                                                            <div className="flex items-center gap-3 text-[10px] font-medium text-slate-400">
                                                                <div className="flex items-center gap-1.5">
                                                                    <div className="w-2 h-2 rounded-full bg-blue-600" /> AI
                                                                </div>
                                                                <div className="flex items-center gap-1.5">
                                                                    <div className="w-2 h-2 rounded-full bg-slate-200" /> Customer
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <div className="space-y-4 max-h-[500px] overflow-y-auto px-1 py-4 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
                                                            {((row.original as any).transcript || []).map((msg: any, idx: number) => {
                                                                const isAi = msg.role === "ai" || msg.role === "assistant";
                                                                return (
                                                                    <div
                                                                        key={idx}
                                                                        className={`flex flex-col ${isAi ? 'items-start' : 'items-end'}`}
                                                                    >
                                                                        <div className={`
                                                                            relative max-w-[90%] md:max-w-[75%] rounded-[20px] px-5 py-3 text-sm leading-relaxed
                                                                            ${isAi
                                                                                ? 'bg-white text-slate-700 rounded-tl-none border border-slate-100 shadow-sm'
                                                                                : 'bg-slate-900 text-white rounded-tr-none shadow-md'}
                                                                        `}>
                                                                            {msg.text}
                                                                        </div>
                                                                        <span className="text-[9px] font-bold text-slate-300 uppercase tracking-tighter mt-1.5 px-2">
                                                                            {isAi ? "Ovela AI" : "Customer"}
                                                                        </span>
                                                                    </div>
                                                                );
                                                            })}
                                                            {(!row.original as any).transcript?.length && (
                                                                <div className="text-center py-12 rounded-2xl border-2 border-dashed border-slate-100">
                                                                    <p className="text-slate-400 text-sm font-medium italic">
                                                                        No transcript data recorded for this duration.
                                                                    </p>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {/* Technical Context Footer */}
                                                    <div className="flex flex-wrap items-center gap-6 pt-6 border-t border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-slate-300">Customer</span>
                                                            <span className="font-mono text-slate-500">{(row.original as any).customer_name || "Not provided"}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-slate-300">SID</span>
                                                            <span className="font-mono text-slate-500">{(row.original as any).call_sid || "N/A"}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-slate-300">Reference</span>
                                                            <span className="font-mono text-slate-500">{(row.original as any).booking_reference || "None"}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </React.Fragment>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={columns.length} className="h-24 text-center text-gray-500">
                                    {loading ? "Refreshing..." : "No results found."}
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between space-x-2 py-2">
                <div className="text-sm text-gray-500">
                    {table.getFilteredRowModel().rows.length} logs
                </div>
                <div className="space-x-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => table.previousPage()}
                        disabled={!table.getCanPreviousPage()}
                        className="h-8 w-24"
                    >
                        Previous
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => table.nextPage()}
                        disabled={!table.getCanNextPage()}
                        className="h-8 w-24"
                    >
                        Next
                    </Button>
                </div>
            </div>
        </div>
    )
}
