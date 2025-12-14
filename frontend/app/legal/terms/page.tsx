"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowLeft, FileText, CreditCard, ShieldAlert, Mail } from "lucide-react";

export default function TermsPage() {
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
                            <FileText className="w-4 h-4" />
                            Legal
                        </div>
                        <h1 className="text-4xl sm:text-5xl font-bold text-foreground mb-4">
                            Terms and Conditions
                        </h1>
                        <p className="text-muted-foreground text-lg">
                            Last updated: December 13, 2025
                        </p>
                    </div>

                    {/* Sections */}
                    <div className="space-y-10">
                        {/* Section 1 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">1. Agreement to Terms</h2>
                            <div className="space-y-4 text-muted-foreground">
                                <p>
                                    We are Vivid Events Australia Pty Ltd, doing business as Ovela ("Company," "we," "us," "our"),
                                    a company registered in Australia at 7/25 Portico Parade, Sydney, New South Wales 2146.
                                </p>
                                <p>
                                    We operate the website{" "}
                                    <a href="https://ovela.dev" className="text-primary hover:underline font-medium">
                                        https://ovela.dev
                                    </a>{" "}
                                    (the "Site"), as well as related products and services (collectively, the "Services").
                                </p>
                                <p className="font-medium text-foreground">
                                    By accessing the Services, you agree to be bound by these Terms. If you do not agree to all of these Terms,
                                    you are prohibited from using the Services.
                                </p>
                            </div>
                        </section>

                        {/* Section 2 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">2. Our Services</h2>
                            <p className="text-muted-foreground">
                                We provide a platform that allows you to send automated messages through artificial intelligence engines via WhatsApp.
                                The Services utilize AI models trained on business data to answer calls and improve customer communication.
                            </p>
                        </section>

                        {/* Section 3 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">3. User Representations</h2>
                            <p className="text-muted-foreground mb-4">By using the Services, you represent and warrant that:</p>
                            <div className="space-y-3">
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <span className="text-primary mt-0.5">✓</span>
                                    <span className="text-muted-foreground">
                                        All registration information you submit will be true, accurate, current, and complete.
                                    </span>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <span className="text-primary mt-0.5">✓</span>
                                    <span className="text-muted-foreground">
                                        You will maintain the accuracy of such information.
                                    </span>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <span className="text-primary mt-0.5">✓</span>
                                    <span className="text-muted-foreground">
                                        You have the legal capacity and agree to comply with these Terms.
                                    </span>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <span className="text-primary mt-0.5">✓</span>
                                    <span className="text-muted-foreground">
                                        You are not under the age of 13.
                                    </span>
                                </div>
                                <div className="flex items-start gap-3 p-3 bg-card border border-border rounded-lg">
                                    <span className="text-primary mt-0.5">✓</span>
                                    <span className="text-muted-foreground">
                                        You will not use the Services for any illegal or unauthorized purpose.
                                    </span>
                                </div>
                            </div>
                        </section>

                        {/* Section 4 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <CreditCard className="w-6 h-6 text-primary" />
                                4. Purchases and Payment
                            </h2>
                            <p className="text-muted-foreground">
                                We accept Visa, Mastercard, and American Express. You agree to provide current, complete, and accurate purchase
                                and account information for all purchases. All payments shall be in Australian Dollars.
                            </p>
                        </section>

                        {/* Section 5 */}
                        <section className="border-l-2 border-primary/30 pl-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4">5. Cancellation</h2>
                            <p className="text-muted-foreground">
                                You can cancel your subscription at any time by contacting us. Your cancellation will take effect at the end
                                of the current paid term.
                            </p>
                        </section>

                        {/* Section 6 */}
                        <section className="bg-red-50 dark:bg-red-950/20 border-2 border-red-200 dark:border-red-800 rounded-xl p-6">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <ShieldAlert className="w-6 h-6 text-red-600 dark:text-red-400" />
                                6. Prohibited Activities
                            </h2>
                            <p className="text-foreground mb-4">
                                You may not access or use the Services for any purpose other than that for which we make the Services available.
                                Prohibited activities include:
                            </p>
                            <ul className="space-y-2 text-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-red-600 dark:text-red-400 mt-1">×</span>
                                    <span>Systematically retrieving data to create a collection or database without written permission.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-red-600 dark:text-red-400 mt-1">×</span>
                                    <span>Tricking, defrauding, or misleading us or other users.</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-red-600 dark:text-red-400 mt-1">×</span>
                                    <span>Interfering with security-related features of the Services.</span>
                                </li>
                            </ul>
                        </section>

                        {/* Contact Section */}
                        <section className="bg-card border border-border rounded-xl p-8">
                            <h2 className="text-2xl font-bold text-foreground mb-4 flex items-center gap-2">
                                <Mail className="w-6 h-6 text-primary" />
                                7. Contact Us
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                To resolve a complaint regarding the Services or to receive further information regarding use of the Services,
                                please contact us at:
                            </p>
                            <div className="space-y-1 text-foreground">
                                <p className="font-semibold">Vivid Events Australia Pty Ltd</p>
                                <p className="text-muted-foreground">7/25 Portico Parade</p>
                                <p className="text-muted-foreground">Sydney, NSW 2146</p>
                                <p className="text-muted-foreground">Australia</p>
                                <p className="text-muted-foreground mt-3">
                                    Phone:{" "}
                                    <a href="tel:0488743734" className="text-primary hover:underline">
                                        0488 743 734
                                    </a>
                                </p>
                                <p className="text-muted-foreground">
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
