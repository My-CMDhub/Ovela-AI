"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowLeft, Shield, Lock, Database, Clock, Mail } from "lucide-react";

export default function PrivacyPage() {
    return (
        <div className="min-h-screen bg-background">
            {/* Header */}
            <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <Link
                        href="/login"
                        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors group"
                    >
                        <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
                        Back to Home
                    </Link>
                </div>
            </header>

            {/* Content */}
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                >
                    {/* Title Section */}
                    <div className="mb-12">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
                            <Shield className="w-4 h-4" />
                            Legal
                        </div>
                        <h1 className="text-4xl sm:text-5xl font-bold text-foreground mb-4">
                            Privacy Policy
                        </h1>
                        <p className="text-muted-foreground text-lg">
                            Last updated: December 13, 2025
                        </p>
                    </div>

                    {/* Introduction */}
                    <div className="prose prose-gray dark:prose-invert max-w-none mb-12">
                        <p className="text-lg text-muted-foreground leading-relaxed">
                            Vivid Events Australia Pty Ltd ("we," "us," or "our") respects the privacy of our users ("user" or "you").
                            This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you visit
                            our website{" "}
                            <a href="https://ovela.dev" className="text-primary hover:underline font-medium">
                                ovela.dev
                            </a>{" "}
                            and use our services.
                        </p>
                    </div>

                    {/* Sections */}
                    <div className="space-y-10">
                        {/* Section 1 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <Database className="w-6 h-6 text-primary" />
                                1. Collection of Your Information
                            </h2>
                            <p className="text-muted-foreground mb-4">
                                We may collect information about you in a variety of ways. The information we may collect includes:
                            </p>
                            <div className="grid gap-3">
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Personal Data</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Name, email address, and telephone number provided during registration.
                                    </p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Business Data</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Information about your business, including services offered, pricing, and operating hours.
                                    </p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Conversation Data</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Messages exchanged via WhatsApp or phone for AI processing and service improvement.
                                    </p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Usage Data</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Information about how you interact with our dashboard and services.
                                    </p>
                                </div>
                            </div>
                        </section>

                        {/* Section 2 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">2. Use of Your Information</h2>
                            <p className="text-muted-foreground mb-4">We use information collected to:</p>
                            <ul className="space-y-2 text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Create and manage your account.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Process your subscription payments.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Enable AI-driven communication with your customers on your behalf.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Send transactional emails regarding bookings and appointments.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Improve our AI models and service quality.</span>
                                </li>
                            </ul>
                        </section>

                        {/* AI Processing Disclosure */}
                        <section className="bg-amber-50 dark:bg-amber-950/20 border-2 border-amber-200 dark:border-amber-800 rounded-xl p-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <Lock className="w-6 h-6 text-amber-600 dark:text-amber-400" />
                                3. AI Processing Disclosure
                            </h2>
                            <p className="text-foreground">
                                <strong>Important:</strong> Our service uses artificial intelligence to process customer conversations
                                via WhatsApp and phone. Conversation content is analysed to provide automated responses,
                                extract booking information, and improve our AI models. Messages are stored securely and
                                used solely for providing the service.
                            </p>
                        </section>

                        {/* Section 4 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">4. Third-Party Service Providers</h2>
                            <p className="text-muted-foreground mb-4">We share your information with the following service providers:</p>
                            <div className="grid sm:grid-cols-2 gap-3">
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Twilio (USA)</h3>
                                    <p className="text-sm text-muted-foreground">Voice call handling and phone number services.</p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Meta Platforms (USA)</h3>
                                    <p className="text-sm text-muted-foreground">WhatsApp Business API for messaging.</p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Resend (USA)</h3>
                                    <p className="text-sm text-muted-foreground">Transactional email delivery.</p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Appwrite (Self-hosted)</h3>
                                    <p className="text-sm text-muted-foreground">Database and authentication services.</p>
                                </div>
                                <div className="bg-card border border-border rounded-lg p-4">
                                    <h3 className="font-semibold text-foreground mb-1">Stripe (USA)</h3>
                                    <p className="text-sm text-muted-foreground">Payment processing for subscriptions.</p>
                                </div>
                            </div>
                        </section>

                        {/* Section 5 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <Clock className="w-6 h-6 text-primary" />
                                5. Data Retention
                            </h2>
                            <p className="text-muted-foreground mb-4">We retain your data for the following periods:</p>
                            <div className="space-y-3">
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <div className="font-semibold text-foreground min-w-[140px]">Account Data:</div>
                                    <div className="text-muted-foreground">Until you delete your account or 2 years after last activity.</div>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <div className="font-semibold text-foreground min-w-[140px]">Booking Records:</div>
                                    <div className="text-muted-foreground">12 months from the appointment date.</div>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <div className="font-semibold text-foreground min-w-[140px]">Conversation Logs:</div>
                                    <div className="text-muted-foreground">30 days, then automatically deleted.</div>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <div className="font-semibold text-foreground min-w-[140px]">Payment Records:</div>
                                    <div className="text-muted-foreground">7 years as required by Australian tax law.</div>
                                </div>
                            </div>
                        </section>

                        {/* Section 6 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">6. Your Rights & Opt-Out</h2>
                            <p className="text-muted-foreground mb-4">You have the right to:</p>
                            <ul className="space-y-2 text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Request access to your personal data.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Request deletion of your account and data.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Opt out of WhatsApp notifications by replying "STOP" to any message.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-primary mt-1">•</span>
                                    <span>Withdraw consent for AI processing (note: this may affect service availability).</span>
                                </li>
                            </ul>
                        </section>

                        {/* Section 7 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">7. Security</h2>
                            <p className="text-muted-foreground">
                                We use administrative, technical, and physical security measures to protect your information.
                                All data is encrypted in transit (TLS) and at rest. Despite our efforts, no security measures are perfect.
                            </p>
                        </section>

                        {/* Contact Section */}
                        <section className="bg-card border border-border rounded-xl p-8">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <Mail className="w-6 h-6 text-primary" />
                                8. Contact Us
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                If you have questions or wish to exercise your rights, contact us at:
                            </p>
                            <div className="space-y-1 text-foreground">
                                <p className="font-semibold">Vivid Events Australia Pty Ltd</p>
                                <p className="text-muted-foreground">7/25 Portico Parade</p>
                                <p className="text-muted-foreground">Sydney, NSW 2146</p>
                                <p className="text-muted-foreground">Australia</p>
                                <p className="text-muted-foreground mt-3">
                                    Email:{" "}
                                    <a href="mailto:patel.vraj11@outlook.com" className="text-primary hover:underline">
                                        patel.vraj11@outlook.com
                                    </a>
                                </p>
                            </div>
                        </section>
                    </div>
                </motion.div>
            </div>

            {/* Footer */}
            <footer className="border-t border-border mt-16">
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
                        <p>© 2025 Vivid Events Australia Pty Ltd. All rights reserved.</p>
                        <div className="flex gap-6">
                            <Link href="/legal/terms" className="hover:text-foreground transition-colors">
                                Terms & Conditions
                            </Link>
                            <Link href="/legal/privacy" className="hover:text-foreground transition-colors">
                                Privacy Policy
                            </Link>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
}
