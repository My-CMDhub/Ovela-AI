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
                                        <TableRow className="bg-slate-50/50 hover:bg-slate-50/50">
                                            <TableCell colSpan={columns.length} className="p-0 border-t-0">
                                                <div className="p-6 space-y-6 animate-in slide-in-from-top-1 duration-200">
                                                    {/* AI Summary Section */}
                                                    <div className="bg-white rounded-lg p-4 border border-blue-100 shadow-sm">
                                                        <h4 className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-2 flex items-center gap-2">
                                                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                                                            AI Summary
                                                        </h4>
                                                        <p className="text-slate-700 text-sm leading-relaxed">
                                                            {(row.original as any).call_summary || "Summarizing call details..."}
                                                        </p>
                                                    </div>

                                                    {/* Transcript Section */}
                                                    <div className="space-y-4">
                                                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-2">
                                                            Call Transcript
                                                        </h4>
                                                        <div className="space-y-3 max-h-[400px] overflow-y-auto px-2 py-1 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
                                                            {((row.original as any).transcript || []).map((msg: any, idx: number) => {
                                                                const isAi = msg.role === "ai" || msg.role === "assistant";
                                                                return (
                                                                    <div
                                                                        key={idx}
                                                                        className={`flex flex-col ${isAi ? 'items-start' : 'items-end'}`}
                                                                    >
                                                                        <div className={`
                                                                            max-w-[85%] md:max-w-[70%] rounded-2xl px-4 py-2 text-sm shadow-sm
                                                                            ${isAi
                                                                                ? 'bg-white text-slate-800 rounded-tl-none border border-slate-100'
                                                                                : 'bg-blue-600 text-white rounded-tr-none'}
                                                                        `}>
                                                                            {msg.text}
                                                                        </div>
                                                                        <span className="text-[10px] text-slate-400 mt-1 px-1">
                                                                            {isAi ? "Voice AI" : "Customer"}
                                                                        </span>
                                                                    </div>
                                                                );
                                                            })}
                                                            {(!row.original as any).transcript?.length && (
                                                                <div className="text-center py-8 text-slate-400 text-sm italic">
                                                                    Transcript not available for this call.
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {/* Metadata Footer */}
                                                    <div className="flex flex-wrap gap-4 pt-4 border-t border-slate-200/60 text-xs text-slate-500">
                                                        <div className="flex items-center gap-1.5">
                                                            <span className="font-medium">Call ID:</span>
                                                            <span className="font-mono">{(row.original as any).call_sid || "N/A"}</span>
                                                        </div>
                                                        <div className="flex items-center gap-1.5">
                                                            <span className="font-medium">Ref:</span>
                                                            <span className="font-mono">{(row.original as any).booking_reference || "None"}</span>
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
