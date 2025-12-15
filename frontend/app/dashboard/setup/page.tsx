"use client";

import { Phone, CheckCircle, ArrowRight, MessageCircle, Smartphone } from "lucide-react";

export default function SetupGuidePage() {
    return (
        <div className="p-8 max-w-3xl">
            <h1 className="text-2xl font-bold text-gray-900 mb-2 dark:text-white">Setup Guide</h1>
            <p className="text-gray-500 mb-8">Complete these steps to activate your AI receptionist</p>

            {/* Step 1 */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
                <div className="flex gap-4">
                    <div className="flex-shrink-0 w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
                        <span className="text-indigo-600 font-bold">1</span>
                    </div>
                    <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-2">Set Up Call Forwarding</h3>
                        <p className="text-gray-600 mb-4">
                            Forward unanswered calls from your business phone to activate the AI assistant.
                        </p>

                        <div className="bg-gray-50 rounded-lg p-4 mb-4">
                            <p className="font-medium text-gray-900 mb-2">Forward to this number:</p>
                            <p className="text-2xl font-mono text-indigo-600">+61 3 4823 6219</p>
                        </div>

                        <details className="text-sm text-gray-600">
                            <summary className="cursor-pointer font-medium text-indigo-600 hover:text-indigo-800">
                                How to set up on my phone →
                            </summary>
                            <div className="mt-3 space-y-3 pl-4 border-l-2 border-indigo-200">
                                <div>
                                    <p className="font-medium">iPhone:</p>
                                    <p>Settings → Phone → Call Forwarding → Enable → Enter number above</p>
                                </div>
                                <div>
                                    <p className="font-medium">Android:</p>
                                    <p>Phone app → ⋮ Menu → Settings → Call Forwarding → Forward when unanswered</p>
                                </div>
                                <div>
                                    <p className="font-medium">Through your carrier:</p>
                                    <p>Call Telstra/Optus/Vodafone support and ask to enable "conditional call forwarding"</p>
                                </div>
                            </div>
                        </details>
                    </div>
                </div>
            </div>

            {/* Step 2 */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
                <div className="flex gap-4">
                    <div className="flex-shrink-0 w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
                        <span className="text-indigo-600 font-bold">2</span>
                    </div>
                    <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-2">Update Your Business Settings</h3>
                        <p className="text-gray-600 mb-4">
                            Go to Settings and add your business name, services, and hours so the AI knows how to respond.
                        </p>
                        <a
                            href="/dashboard/settings"
                            className="inline-flex items-center gap-2 text-indigo-600 font-medium hover:text-indigo-800"
                        >
                            Go to Settings <ArrowRight className="w-4 h-4" />
                        </a>
                    </div>
                </div>
            </div>

            {/* Step 3 */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
                <div className="flex gap-4">
                    <div className="flex-shrink-0 w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
                        <span className="text-indigo-600 font-bold">3</span>
                    </div>
                    <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-2">Test It!</h3>
                        <p className="text-gray-600 mb-4">
                            Call your business number from another phone. Let it ring (don't answer).
                            You should receive a WhatsApp message within 30 seconds!
                        </p>
                    </div>
                </div>
            </div>

            {/* How It Works */}
            <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl p-6 mt-8">
                <h3 className="font-semibold text-gray-900 mb-4">How It Works</h3>
                <div className="flex items-center gap-3 text-sm text-gray-600">
                    <div className="flex items-center gap-2">
                        <Phone className="w-5 h-5 text-indigo-500" />
                        <span>Customer calls</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-gray-400" />
                    <div className="flex items-center gap-2">
                        <Smartphone className="w-5 h-5 text-orange-500" />
                        <span>No answer</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-gray-400" />
                    <div className="flex items-center gap-2">
                        <MessageCircle className="w-5 h-5 text-green-500" />
                        <span>AI sends WhatsApp</span>
                    </div>
                    <ArrowRight className="w-4 h-4 text-gray-400" />
                    <div className="flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-blue-500" />
                        <span>You approve in dashboard</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
