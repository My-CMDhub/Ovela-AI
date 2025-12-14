"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

// Industry-specific theming with deep customization
const INDUSTRY_THEMES = {
    beauty: {
        primary: "rgb(225, 29, 72)",
        primaryLight: "rgb(254, 242, 242)",
        accent: "rgb(236, 72, 153)",
        name: "Beauty & Wellness",
        dark: {
            primary: "rgb(251, 113, 133)",
            primaryLight: "rgb(76, 29, 42)",
            accent: "rgb(244, 114, 182)",
            bg: "rgb(23, 23, 23)",
            card: "rgb(38, 38, 38)",
            text: "rgb(243, 244, 246)",
        },
        style: {
            cardStyle: "elegant",
            pattern: "dots",
            borderRadius: "xl",
            shadow: "soft",
        },
        terminology: {
            customer: "Client",
            booking: "Appointment",
            service: "Treatment",
            dashboard: "Studio Dashboard",
            welcome: "Welcome to your beauty studio",
        },
        personality: {
            tone: "elegant and welcoming",
            emoji: "✨",
            greeting: "Looking gorgeous today!",
        },
        metrics: {
            primary: "Treatments Today",
            secondary: "Client Satisfaction",
            tertiary: "Revenue This Week",
        }
    },
    health: {
        primary: "rgb(5, 150, 105)",
        primaryLight: "rgb(236, 253, 245)",
        accent: "rgb(20, 184, 166)",
        name: "Health & Medical",
        dark: {
            primary: "rgb(52, 211, 153)",
            primaryLight: "rgb(6, 78, 59)",
            accent: "rgb(45, 212, 191)",
            bg: "rgb(17, 24, 39)",
            card: "rgb(31, 41, 55)",
            text: "rgb(243, 244, 246)",
        },
        style: {
            cardStyle: "clinical",
            pattern: "grid",
            borderRadius: "md",
            shadow: "sharp",
        },
        terminology: {
            customer: "Patient",
            booking: "Appointment",
            service: "Consultation",
            dashboard: "Practice Dashboard",
            welcome: "Welcome to your practice",
        },
        personality: {
            tone: "professional and caring",
            emoji: "🏥",
            greeting: "Ready to help patients today",
        },
        metrics: {
            primary: "Appointments Today",
            secondary: "Patient Care Hours",
            tertiary: "Consultations This Week",
        }
    },
    fitness: {
        primary: "rgb(234, 88, 12)",
        primaryLight: "rgb(255, 247, 237)",
        accent: "rgb(245, 158, 11)",
        name: "Fitness & Gym",
        dark: {
            primary: "rgb(251, 146, 60)",
            primaryLight: "rgb(124, 45, 18)",
            accent: "rgb(251, 191, 36)",
            bg: "rgb(15, 15, 15)",
            card: "rgb(30, 30, 30)",
            text: "rgb(243, 244, 246)",
        },
        style: {
            cardStyle: "energetic",
            pattern: "waves",
            borderRadius: "lg",
            shadow: "glow",
        },
        terminology: {
            customer: "Member",
            booking: "Session",
            service: "Class",
            dashboard: "Gym Dashboard",
            welcome: "Welcome to your fitness hub",
        },
        personality: {
            tone: "energetic and motivating",
            emoji: "💪",
            greeting: "Let's crush today's goals!",
        },
        metrics: {
            primary: "Sessions Today",
            secondary: "Active Members",
            tertiary: "Classes This Week",
        }
    },
    professional: {
        primary: "rgb(71, 85, 105)",
        primaryLight: "rgb(248, 250, 252)",
        accent: "rgb(59, 130, 246)",
        name: "Professional Services",
        dark: {
            primary: "rgb(148, 163, 184)",
            primaryLight: "rgb(30, 41, 59)",
            accent: "rgb(96, 165, 250)",
            bg: "rgb(15, 23, 42)",
            card: "rgb(30, 41, 59)",
            text: "rgb(243, 244, 246)",
        },
        style: {
            cardStyle: "minimal",
            pattern: "none",
            borderRadius: "sm",
            shadow: "none",
        },
        terminology: {
            customer: "Client",
            booking: "Meeting",
            service: "Service",
            dashboard: "Business Dashboard",
            welcome: "Welcome to your workspace",
        },
        personality: {
            tone: "professional and efficient",
            emoji: "💼",
            greeting: "Ready for a productive day",
        },
        metrics: {
            primary: "Meetings Today",
            secondary: "Client Engagements",
            tertiary: "Revenue This Month",
        }
    },
    hospitality: {
        primary: "rgb(147, 51, 234)",
        primaryLight: "rgb(250, 245, 255)",
        accent: "rgb(168, 85, 247)",
        name: "Hospitality",
        dark: {
            primary: "rgb(192, 132, 252)",
            primaryLight: "rgb(88, 28, 135)",
            accent: "rgb(196, 181, 253)",
            bg: "rgb(24, 24, 27)",
            card: "rgb(39, 39, 42)",
            text: "rgb(243, 244, 246)",
        },
        style: {
            cardStyle: "luxe",
            pattern: "dots",
            borderRadius: "2xl",
            shadow: "soft",
        },
        terminology: {
            customer: "Guest",
            booking: "Reservation",
            service: "Experience",
            dashboard: "Venue Dashboard",
            welcome: "Welcome to your venue",
        },
        personality: {
            tone: "warm and hospitable",
            emoji: "🌟",
            greeting: "Creating memorable experiences",
        },
        metrics: {
            primary: "Reservations Today",
            secondary: "Guest Satisfaction",
            tertiary: "Bookings This Week",
        }
    },
    retail: {
        primary: "rgb(37, 99, 235)",
        primaryLight: "rgb(239, 246, 255)",
        accent: "rgb(6, 182, 212)",
        name: "Retail",
        dark: {
            primary: "rgb(96, 165, 250)",
            primaryLight: "rgb(30, 58, 138)",
            accent: "rgb(34, 211, 238)",
            bg: "rgb(3, 7, 18)",
            card: "rgb(17, 24, 39)",
            text: "rgb(243, 244, 246)",
        },
        style: {
            cardStyle: "modern",
            pattern: "grid",
            borderRadius: "lg",
            shadow: "soft",
        },
        terminology: {
            customer: "Customer",
            booking: "Appointment",
            service: "Service",
            dashboard: "Store Dashboard",
            welcome: "Welcome to your store",
        },
        personality: {
            tone: "friendly and helpful",
            emoji: "🛍️",
            greeting: "Ready to serve customers",
        },
        metrics: {
            primary: "Appointments Today",
            secondary: "Customer Visits",
            tertiary: "Sales This Week",
        }
    }
} as const;

type Industry = keyof typeof INDUSTRY_THEMES;

interface ThemeContextType {
    industry: Industry;
    theme: typeof INDUSTRY_THEMES[Industry];
    darkMode: boolean;
    setIndustry: (industry: Industry) => void;
    toggleDarkMode: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [industry, setIndustryState] = useState<Industry>("beauty");
    const [darkMode, setDarkMode] = useState(false);

    useEffect(() => {
        const savedDarkMode = localStorage.getItem("darkMode");
        if (savedDarkMode) {
            setDarkMode(savedDarkMode === "true");
        }
    }, []);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const res = await fetch(`${API_URL}/api/dashboard/settings`);
                const data = await res.json();
                if (data.success && data.settings?.industry) {
                    const ind = data.settings.industry as Industry;
                    if (INDUSTRY_THEMES[ind]) {
                        setIndustryState(ind);
                    }
                }
            } catch (error) {
                console.log("Using default theme");
            }
        };
        fetchSettings();
    }, []);

    useEffect(() => {
        const theme = INDUSTRY_THEMES[industry];
        const colors = darkMode ? theme.dark : theme;

        document.documentElement.style.setProperty("--theme-primary", colors.primary);
        document.documentElement.style.setProperty("--theme-primary-light", colors.primaryLight);
        document.documentElement.style.setProperty("--theme-accent", colors.accent);

        if (darkMode) {
            document.documentElement.style.setProperty("--theme-bg", theme.dark.bg);
            document.documentElement.style.setProperty("--theme-card", theme.dark.card);
            document.documentElement.style.setProperty("--theme-text", theme.dark.text);
            document.documentElement.classList.add("dark");
        } else {
            document.documentElement.style.setProperty("--theme-bg", "#fafafa");
            document.documentElement.style.setProperty("--theme-card", "#ffffff");
            document.documentElement.style.setProperty("--theme-text", "#111827");
            document.documentElement.classList.remove("dark");
        }

        document.documentElement.setAttribute("data-industry", industry);
        document.documentElement.setAttribute("data-card-style", theme.style.cardStyle);
    }, [industry, darkMode]);

    const setIndustry = (ind: Industry) => {
        if (INDUSTRY_THEMES[ind]) {
            setIndustryState(ind);
        }
    };

    const toggleDarkMode = () => {
        const newMode = !darkMode;
        setDarkMode(newMode);
        localStorage.setItem("darkMode", String(newMode));
    };

    return (
        <ThemeContext.Provider value={{
            industry,
            theme: INDUSTRY_THEMES[industry],
            darkMode,
            setIndustry,
            toggleDarkMode
        }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error("useTheme must be used within ThemeProvider");
    }
    return context;
}

export { INDUSTRY_THEMES };
export type { Industry };
