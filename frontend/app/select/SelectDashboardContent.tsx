"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Building2, Hotel, ArrowRight } from "lucide-react";

export default function SelectDashboardContent() {
    const router = useRouter();

    const dashboards = [
        {
            id: "motel",
            name: "The Lydoun Motel",
            subtitle: "Chiltern, Victoria",
            description: "Manage reservations & guests",
            icon: Hotel,
            href: "/motel",
            gradient: "from-[#8B2332] to-[#A0352C]",
            bgPattern: "bg-[url('/images/motel-pattern.svg')]",
            highlight: "Voice AI Active",
        },
        {
            id: "general",
            name: "General CRM",
            subtitle: "Multi-Industry Platform",
            description: "WhatsApp, bookings & customer management",
            icon: Building2,
            href: "/dashboard",
            gradient: "from-blue-600 to-indigo-600",
            bgPattern: "",
            highlight: "All Industries",
        },
    ];

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-6">
            <div className="max-w-4xl w-full">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center mb-12"
                >
                    <h1 className="text-3xl font-bold text-gray-900 mb-2">
                        Welcome to Ovela AI
                    </h1>
                    <p className="text-gray-600">
                        Select a dashboard to continue
                    </p>
                </motion.div>

                {/* Dashboard Cards */}
                <div className="grid md:grid-cols-2 gap-6">
                    {dashboards.map((dashboard, index) => (
                        <motion.div
                            key={dashboard.id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.1 }}
                            onClick={() => router.push(dashboard.href)}
                            className="group cursor-pointer"
                        >
                            <div className="relative h-full bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden border border-gray-100">
                                {/* Colored Header */}
                                <div className={`h-32 bg-gradient-to-r ${dashboard.gradient} relative overflow-hidden`}>
                                    {/* Pattern overlay */}
                                    <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_30%_50%,white_1px,transparent_1px)] bg-[length:20px_20px]" />

                                    {/* Icon */}
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <dashboard.icon className="w-16 h-16 text-white/80" strokeWidth={1.5} />
                                    </div>

                                    {/* Highlight Badge */}
                                    <div className="absolute top-4 right-4">
                                        <span className="px-3 py-1 bg-white/20 backdrop-blur-sm rounded-full text-xs font-medium text-white">
                                            {dashboard.highlight}
                                        </span>
                                    </div>
                                </div>

                                {/* Content */}
                                <div className="p-6">
                                    <h2 className="text-xl font-bold text-gray-900 mb-1">
                                        {dashboard.name}
                                    </h2>
                                    <p className="text-sm text-gray-500 mb-3">
                                        {dashboard.subtitle}
                                    </p>
                                    <p className="text-gray-600 mb-4">
                                        {dashboard.description}
                                    </p>

                                    {/* Enter Button */}
                                    <div className="flex items-center text-gray-900 font-medium group-hover:text-[#8B2332] transition-colors">
                                        <span>Enter Dashboard</span>
                                        <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>

                {/* Footer */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="text-center mt-12 text-gray-400 text-sm"
                >
                    Powered by Ovela AI
                </motion.div>
            </div>
        </div>
    );
}
