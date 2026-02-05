import ColdCallDashboard from '@/components/cold-calling/cold-call-dashboard';

export default function ColdAgentPage() {
    return (
        <div className="min-h-screen bg-slate-50 py-8">
            <div className="max-w-7xl mx-auto px-4">
                <h1 className="text-3xl font-bold mb-8 text-slate-900">Ovela Outbound Agent</h1>
                <ColdCallDashboard />
            </div>
        </div>
    );
}
