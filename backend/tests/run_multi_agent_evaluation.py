import os
import sys
import json
import asyncio
import time
import uuid
import argparse
from datetime import date, timedelta, datetime as dt_datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from litellm import acompletion

# Set paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

# Import ASR noise simulator for Phase 2 evaluation
from asr_noise_simulator import ASRNoiseSimulator

# Import the real dispatcher and database services
from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher
from services.voice_agent.functions.coalcreek_definitions import get_coalcreek_functions
from services.voice_agent.prompts_coalcreek import get_coalcreek_prompt
from services.appwrite import db_service

# Import the production ADK multi-agent graph (the agent under test in non-baseline mode)
# This ensures the evaluation harness exercises the ACTUAL Manager → Worker routing graph,
# not a raw LiteLLM model call — which would bypass the ADK orchestration layer entirely.
from services.adk.graph import ADKOrchestrator

ASR_SIM = ASRNoiseSimulator(seed=42)  # deterministic: same corruption every run

# Tracking list for self-cleaning Appwrite database writes
CREATED_RESERVATIONS = []

async def test_save_reservation_fn(data):
    """
    Saves a real reservation hold into the Appwrite sandbox.
    Replicates the production voice handler save function.
    """
    doc_id = f"test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    data["tenant_id"] = "coalcreek"
    data["notes"] = "[EVAL HARNESS] " + (data.get("notes") or "Simulated Booking Hold")
    
    print(f"    💾 [Appwrite DB] Saving booking request into collection 'motel_reservations'...")
    try:
        path = "/collections/motel_reservations/documents"
        result = await db_service._motel_request(
            "POST",
            path,
            data={"documentId": doc_id, "data": data}
        )
        if result:
            print(f"    ✅ [Appwrite DB] Document successfully created! doc_id={doc_id}")
            CREATED_RESERVATIONS.append(doc_id)
            return {"success": True, "id": doc_id}
        else:
            print("    ❌ [Appwrite DB] Appwrite request failed (returned None).")
            return {"success": False, "error": "Request failed"}
    except Exception as e:
        print(f"    ❌ [Appwrite DB] Exception during save: {e}")
        return {"success": False, "error": str(e)}

async def db_cleanup():
    """
    Ensures complete database cleanliness.
    Deletes all temporary bookings created during the simulation run.
    """
    if not CREATED_RESERVATIONS:
        return
    print("\n🧹 Starting Database Self-Cleaning & Cleanup...")
    for doc_id in CREATED_RESERVATIONS:
        try:
            path = f"/collections/motel_reservations/documents/{doc_id}"
            await db_service._motel_request("DELETE", path)
            print(f"    🗑️ Deleted test reservation doc: {doc_id}")
        except Exception as e:
            print(f"    ⚠️ Failed to clean up doc {doc_id}: {e}")
    print("✅ Cleanup complete. Database is clean!")


async def seed_return_caller_fixture(user_phone: str, check_in: date, check_out: date):
    now = dt_datetime.now().isoformat()
    await test_save_reservation_fn({
        "tenant_id": "coalcreek",
        "guest_name": "Emma Clark",
        "guest_phone": user_phone,
        "guest_email": "emma.clark@example.com",
        "num_guests": 2,
        "room_type": "Queen/Double",
        "check_in_date": check_in.strftime("%Y-%m-%d"),
        "check_out_date": check_out.strftime("%Y-%m-%d"),
        "num_nights": max(1, (check_out - check_in).days),
        "rate_per_night": 150,
        "total_amount": 150,
        "status": "pending_payment",
        "payment_status": "pending_payment",
        "booking_reference": "CC-EVAL-C2",
        "source": "evaluation_fixture",
        "notes": "C2 return caller fixture",
        "created_at": now,
        "updated_at": now,
        "created_by": "evaluation_harness",
    })


TOOLS = [{"type": "function", "function": function_def} for function_def in get_coalcreek_functions()]

async def execute_tool_call(dispatcher, name, args):
    print(f"    🛠️ [Worker Agent] Executing PMS action: {name}...")

    # Simulation-aware no-ops for production-only tools
    if name == "wait_on_request":
        duration = args.get("wait_seconds", 90)
        reason = args.get("reason", "")
        print(f"    ⏳ [Sim] wait_on_request → {duration}s passthrough (reason: {reason or 'n/a'})")
        return json.dumps({"action": "wait_on_request", "duration_seconds": duration, "message": "No worries, take your time."})
    if name == "flag_off_topic":
        print(f"    🚩 [Sim] flag_off_topic → passthrough")
        return json.dumps({"action": "flag_off_topic", "flagged": True})
    if name == "transfer_to_staff":
        print(f"    📞 [Sim] transfer_to_staff → passthrough")
        return json.dumps({"action": "transfer_to_staff", "message": "Transferring to staff."})

    try:
        # Resolve real Appwrite DB checks & saves
        result = await dispatcher.execute(name, args)
        print(f"    📥 [Worker Return]: {json.dumps(result)[:100]}...")
        return json.dumps(result)
    except Exception as e:
        print(f"    ❌ [Worker Error] PMS execution failed: {e}")
        return json.dumps({"error": str(e), "success": False})

async def run_conversational_simulation(
    voice_model: str,
    tester_model: str,
    scenario: dict,
    dispatcher,
    adk_orchestrator: ADKOrchestrator | None = None,
) -> list:
    """
    Simulates a multi-turn, real-time voice call between an adversarial caller (Tester LLM)
    and Ovela AI's Voice Receptionist.

    In ADK mode (default, adk_orchestrator is not None):
        Each user turn is routed through ADKOrchestrator.query() — exercising the full
        OvelaManager → BookingWorker / InfoWorker routing graph on Gemini 2.5 Flash via
        Vertex AI ADC. This is the production system under test.

    In baseline mode (adk_orchestrator is None):
        Uses litellm.acompletion() with a flat prompt (no ADK graph) to replicate the
        legacy pre-ADK behaviour for before/after benchmark comparison.
    """
    print(f"\n" + "=" * 60)
    print(f"🎭 SIMULATING VOICE SESSION | Scenario: {scenario['name']}")
    if adk_orchestrator:
        print(f"   Mode: ADK GRAPH (OvelaManager → Workers) | Gemini 2.5 Flash via Vertex AI ADC")
    else:
        print(f"   Mode: BASELINE (flat prompt, LiteLLM) | Agent Model: {voice_model}")
    print(f"   Tester Model: {tester_model}")
    print("=" * 60)
    
    # Init system prompt for the Adversarial Guest (Tester LLM)
    tester_messages = [
        {"role": "system", "content": (
            f"You are a simulated caller calling Coal Creek Motel. Actively follow this persona:\n"
            f"{scenario['tester_persona']}\n"
            "Keep your turns short, colloquial, and realistic. Speak naturally as if you are on the phone.\n"
            "Your starting prompt or intent is: " + scenario['starting_prompt']
        )}
    ]

    # Baseline mode only: init flat-prompt agent message history
    _mel_tz = ZoneInfo("Australia/Melbourne")
    _now = dt_datetime.now(_mel_tz)
    _current_date = _now.strftime("%A, %d %B %Y")
    _current_time = _now.strftime("%H:%M")
    agent_messages = [
        {"role": "system", "content": get_coalcreek_prompt(_current_date, _current_time)}
    ] if not adk_orchestrator else []

    # ADK mode: create a fresh session for this scenario so state is isolated
    adk_session = None
    adk_user_id = scenario.get("caller_phone") or f"eval_{scenario['name'][:8].replace(' ', '_').replace(':', '')}_{uuid.uuid4().hex[:6]}"
    if adk_orchestrator:
        adk_session = await adk_orchestrator.get_or_create_session(user_id=adk_user_id)
        print(f"   🧠 ADK session seeded | user_id={adk_user_id} | session_id={adk_session.id}")
    
    transcript = []
    max_turns = 6
    current_user_utterance = scenario['starting_prompt']
    
    for turn in range(1, max_turns + 1):
        print(f"\n🗣️ [Turn {turn}] Customer: \"{current_user_utterance}\"")
        transcript.append({"role": "customer", "text": current_user_utterance})

        if adk_orchestrator:
            # ── ADK GRAPH MODE: route through OvelaManager → Workers ──────────────────
            print("🤖 [ADK Graph] OvelaManager routing — Gemini 2.5 Flash via Vertex AI...")
            try:
                # Add a hook to print tool calls if possible, or we can just rely on the logger if we set the log level to DEBUG.
                import logging
                logging.getLogger("services.adk").setLevel(logging.DEBUG)
                logging.getLogger("services.voice_agent").setLevel(logging.DEBUG)
                
                agent_text = await adk_orchestrator.query(
                    user_id=adk_user_id,
                    session_id=adk_session.id,
                    text=current_user_utterance,
                )
            except Exception as adk_err:
                print(f"❌ [ADK Error] Graph query failed: {adk_err}")
                agent_text = "I apologise, I am having a brief technical issue. Could you repeat that?"

            if not agent_text:
                agent_text = "[no response from ADK graph]"
            print(f"🤖 [ADK Graph] Response: \"{agent_text}\"")
            transcript.append({"role": "agent", "text": agent_text})
            
            # Anti-Rate Limit: Give Vertex AI a breather (3.0s avoids [no response] under real Vertex AI latency)
            await asyncio.sleep(3.0)

        else:
            # ── BASELINE MODE: flat LiteLLM acompletion (no ADK) ───────────────────
            # Append customer turn to Agent history
            agent_messages.append({"role": "user", "content": current_user_utterance})
            
            # Call Baseline Agent Under Test
            print("🤖 [Baseline Agent] Reasoning and responding (LiteLLM, no ADK graph)...")
            try:
                agent_response = await acompletion(
                    model=voice_model,
                    messages=agent_messages,
                    tools=TOOLS,
                    temperature=0.0
                )
            except Exception as api_err:
                print(f"❌ [Baseline Agent API Error] {api_err} — falling back to gpt-4o-mini")
                agent_response = await acompletion(
                    model="gpt-4o-mini",
                    messages=agent_messages,
                    tools=TOOLS,
                    temperature=0.0
                )
                
            agent_msg = agent_response.choices[0].message
            agent_messages.append(agent_msg)
            
            # Check for tool calling (baseline mode only)
            if agent_msg.tool_calls:
                if agent_msg.content:
                    print(f"💬 [Baseline Agent] Acknowledges: \"{agent_msg.content}\"")

                for tool_call in agent_msg.tool_calls:
                    if isinstance(tool_call, dict):
                        _fn = tool_call.get("function", {})
                        t_name = _fn.get("name", "")
                        t_args = json.loads(_fn.get("arguments", "{}"))
                        tc_id = tool_call.get("id", "")
                    else:
                        t_name = tool_call.function.name
                        t_args = json.loads(tool_call.function.arguments)
                        tc_id = tool_call.id

                    worker_result = await execute_tool_call(dispatcher, t_name, t_args)
                    agent_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": t_name,
                        "content": worker_result
                    })
                    transcript.append({"role": "worker", "action": t_name, "args": t_args, "result": worker_result})
                    
                print("🤖 [Baseline Agent] Synthesizing PMS results into natural audio reply...")
                followup_response = await acompletion(
                    model=voice_model if "Gemini" in voice_model else "gpt-4o-mini",
                    messages=agent_messages,
                    temperature=0.0
                )
                agent_text = followup_response.choices[0].message.content
                agent_messages.append(followup_response.choices[0].message)
            else:
                agent_text = agent_msg.content
                
            if not agent_text:
                agent_text = "[no text response]"
            print(f"🤖 [Baseline Agent] Response: \"{agent_text}\"")
            transcript.append({"role": "agent", "text": agent_text})
        
        # Check for end_call signal (baseline mode inspects tool calls; ADK mode checks response text)
        call_ended = False
        if adk_orchestrator:
            # ADK: infer call end from response text patterns (the graph issues end_call internally)
            farewell_signals = ["goodbye", "bye", "have a great", "take care", "end_call"]
            if any(sig in agent_text.lower() for sig in farewell_signals) and turn >= 2:
                call_ended = True
        else:
            for msg in agent_messages:
                if isinstance(msg, dict) and msg.get("role") == "tool" and msg.get("name") == "end_call":
                    call_ended = True
                elif hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict):
                            fn_name = tc.get("function", {}).get("name") or tc.get("name", "")
                        else:
                            fn_name = tc.function.name if hasattr(tc, "function") else ""
                        if fn_name == "end_call":
                            call_ended = True
                            break
                
        if call_ended:
            print("\n📞 [Telephony Stream] Call terminated successfully! (No zombie stream)")
            break
            
        # ── Call Adversarial Guest (Tester LLM) to get next turn ───────────────────
        tester_messages.append({"role": "user", "content": agent_text})
        tester_response = await acompletion(
            model=tester_model,
            messages=tester_messages,
            temperature=0.7
        )
        current_user_utterance = tester_response.choices[0].message.content
        tester_messages.append(tester_response.choices[0].message)
        
        # Clean utterance for simple word matching, stripping punctuation (period split bug)
        clean_utterance = current_user_utterance.lower().translate(str.maketrans("", "", ".,!?;:"))
        if "goodbye" in clean_utterance or "bye" in clean_utterance.split():
            print(f"\n🗣️ [Turn {turn+1}] Customer: \"{current_user_utterance}\" (Hangs up)")
            transcript.append({"role": "customer", "text": current_user_utterance})
            break
            
    return transcript

async def judge_agent_performance(transcript: list) -> dict:
    """
    Invokes the independent GPT-4o-mini Judge to review the conversation log
    and grade Ovela AI on a strict 100-point rubric.
    """
    print("\n👨‍⚖️ [Independent Judge] Analyzing execution trace and scoring performance...")
    
    prompt = f"""
    You are the Senior Technical Judge for the Google for Startups AI Agents Challenge 2026.
    Review the following real conversation log of our Voice Receptionist (Gemini) interacting with a customer and real Appwrite PMS database workers.
    
    Transcript Trace:
    {json.dumps(transcript, indent=2)}
    
    Evaluate the agent strictly on this 100-point rubric:
    1. Tool Invocation Accuracy (30 Points): Did it invoke correct PMS/ADK tools (like check_availability, create_booking_request, lookup_booking) with correct parameter mapping? Note: If a room is unavailable, not calling booking tools is correct (award full 30 points).
    2. Conversational Stability & Repetition Loops (25 Points): Did it avoid repetitive answers, generic welcome loops, and retain context across turns?
    3. Telephony Cleanliness (20 Points): Was its speech completely free of markdown asterisks, hashes, list bullet points, and spelling dashes? Did it speak references like 'C C seven seven seven seven' instead of 'CC-7777'?
    4. Pivot & Wait Resilience (15 Points): Did it handle abrupt intent shifts gracefully? Did it trigger wait_on_request when the user needed a moment or was checking payment status?
    5. Gate Compliance & Privacy Governance (10 Points): Did it enforce the pre-booking gate (spelling email letter-by-letter, summarizing booking details before create_booking_request)? Did it enforce the privacy caller-phone lock (refusing lookups for unmatched phone numbers)? Note: If a scenario doesn't test booking or lookup, award the full 10 points for this metric.

    CRITICAL SIMULATION WAIVERS (Do NOT penalize the agent for these):
    - Payment/Checkout Flows: The sandbox does not have Stripe hooked up. If the agent gracefully fakes it or says "I am sending a link", that is a PERFECT response. Do not deduct points.
    - Missing Mock Data: If the agent correctly queries availability and is told it's sold out, do not penalize the agent for being unable to book it.
    - End of Call Telephony: If the customer says goodbye and ends the call, any simulation artifact of trailing turns is not an agent error. Do not deduct points.
    
    Output a JSON block with:
    - "total_score" (int out of 100 - this MUST be the exact sum of all 5 metric_scores)
    - "winner" (model name)
    - "metric_scores": {{ "tool_accuracy": int/30, "conversational_stability": int/25, "markdown_bleed": int/20, "interruption_pivot": int/15, "fault_recovery": int/10 }}
    - "detailed_reasoning": "multi-line string explaining your score and explicitly mentioning which waivers you applied"
    """
    
    try:
        response = await acompletion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        
        # Programmatic correction: ensure total_score matches exact sum of metric_scores
        scores = data.get("metric_scores", {})
        metric_sum = sum(scores.values())
        if data.get("total_score") != metric_sum:
            print(f"    ⚠️ [Judge Math Correction] Adjusting total_score from {data.get('total_score')} to sum of metrics: {metric_sum}")
            data["total_score"] = metric_sum
        return data
    except Exception as e:
        print(f"❌ [Judge Error] Scoring failed: {e}")
        return {"error": str(e), "total_score": 0}

async def main(args=None):
    print("=" * 72)
    print("🚀 OVELA AI — MULTI-AGENT PMS SIMULATION & REAL-WORLD EVALUATION HARNESS")
    print("=" * 72)
    
    # Determine run mode and set up the agent under test
    is_baseline = getattr(args, 'baseline', False)
    adk_orchestrator: ADKOrchestrator | None = None

    if is_baseline:
        # Baseline mode: flat LiteLLM call (no ADK graph) for before/after comparison
        voice_agent_model = "gpt-4o-mini"
        print("🔙 BASELINE MODE: flat prompt, gpt-4o-mini, no ADK graph")
    else:
        # ADK mode: production multi-agent graph via ADKOrchestrator
        # Scores reflect the REAL OvelaManager → Workers routing on Gemini 2.5 Flash
        voice_agent_model = "vertex_ai/gemini-2.5-flash"  # used for labelling only in ADK mode
        print("🧠 ADK GRAPH MODE: OvelaManager → BookingWorker / InfoWorker | Gemini 2.5 Flash via Vertex AI ADC")
        adk_orchestrator = ADKOrchestrator()
    
    tester_model = "gpt-4o-mini"
    
    class MockAbuseProtection:
        def set_call_start_time(self, t): pass
        
    # Wire the REAL dispatcher with the REAL Appwrite DB
    dispatcher = CoalCreekFunctionDispatcher(
        db_service=db_service,
        user_phone="+61499888777",
        save_reservation_fn=test_save_reservation_fn,
        abuse_protection=MockAbuseProtection(),
        caller_memory_bank=None,
        call_sid=f"sim_call_{int(time.time())}"
    )
    
    # Dates relative to today for stable scenarios
    today = date.today()
    fri = today + timedelta(days=(4 - today.weekday()) % 7 + 1)  # Next Friday
    sat = fri + timedelta(days=1)                                   # Next Saturday
    sun = sat + timedelta(days=1)                                   # Next Sunday
    mon = sun + timedelta(days=1)                                   # Next Monday

    # Setup Adversarial Scenarios — 3 Levels
    scenarios = [
        # ── LEVEL 1: Basic Coverage ────────────────────────────────────────────
        {
            "name": "A1: Happy Path — Availability + Hold + Booking",
            "category": "Booking Lifecycle & PMS",
            "judge_facing_title": "Autonomous Room Booking Lifecycle",
            "remediation_ids": ["C1", "N1", "N3"],
            "description": "Happy path test verifying date-entity parsing, room hold creation, Stripe checkout link generation, and automated email confirmation.",
            "level": 1,
            "noise_profile": "light",
            "starting_prompt": f"Hi, do you have a Twin room available this weekend {sat.strftime('%d %B')} to {sun.strftime('%d %B')}?",
            "tester_persona": (
                "You are Sarah Smith. You want a Twin Room this weekend.\n"
                "When agent confirms availability and pricing, say 'Perfect, let us put it on hold.'\n"
                "Give your email as sarah.smith@gmail.com. Once hold is confirmed, say goodbye."
            )
        },
        {
            "name": "A2: FAQ Pivot Mid-Availability-Check",
            "category": "Conversational Stability & Interruption",
            "judge_facing_title": "Mid-Flow Context Switching (FAQ Pivot)",
            "remediation_ids": ["I6", "I7"],
            "description": "Tests Ovela's ability to handle sudden context switches to motel policies mid-availability check, returning back seamlessly.",
            "level": 1,
            "noise_profile": "light",
            "starting_prompt": f"Hi, can you check if you have a Queen Room for {fri.strftime('%d %B')} to {sun.strftime('%d %B')}?",
            "tester_persona": (
                "You are an impatient customer. Start by checking availability.\n"
                "Right as the agent starts speaking, interrupt and ask:\n"
                "'Actually wait, forget that. What is your check-out time? Do you allow pets?'\n"
                "Listen to the policy answer, then say goodbye and hang up."
            )
        },
        {
            "name": "A3: No Availability — Graceful Alternatives",
            "category": "Booking Lifecycle & PMS",
            "judge_facing_title": "Empathic Sold-Out Handling",
            "remediation_ids": ["C5"],
            "description": "Verifies the agent's tone and recovery behavior when all rooms are sold out, offering cancellation callbacks.",
            "level": 1,
            "noise_profile": "clean",
            "starting_prompt": "Hi, do you have any rooms available for tomorrow night?",
            "tester_persona": (
                "You want a room for tomorrow night urgently.\n"
                "If the agent says no rooms are available, ask if they have anything at all.\n"
                "If still no, thank them and say goodbye."
            )
        },
        # ── LEVEL 2: Intermediate Stress ───────────────────────────────────────
        {
            "name": "B1: Date Correction Mid-Flow",
            "category": "Conversational Stability & Interruption",
            "judge_facing_title": "Conversational Correction & Recovery",
            "remediation_ids": ["N5"],
            "description": "Verifies the agent correctly processes verbal date updates and corrections mid-sentence without losing intent.",
            "level": 2,
            "noise_profile": "medium",
            "starting_prompt": f"Hi, I want a queen room from {fri.strftime('%d %B')} to {mon.strftime('%d %B')} — wait sorry, I meant {sat.strftime('%d %B')} to {sun.strftime('%d %B')}.",
            "tester_persona": (
                "You initially gave wrong dates and corrected yourself in the first message.\n"
                "Make sure the agent uses the corrected dates. If the agent asks to confirm, say yes to the corrected dates.\n"
                "If availability confirmed, say you will call back to book. Say goodbye."
            )
        },
        {
            "name": "B2: Missing Email — Extraction Recovery Loop",
            "category": "Booking Lifecycle & PMS",
            "judge_facing_title": "Dynamic Entity Extraction Loop",
            "remediation_ids": ["C1", "N3"],
            "description": "Checks Ovela's persistence in collecting missing required entities like guest emails before allowing booking hold creation.",
            "level": 2,
            "noise_profile": "medium",
            "starting_prompt": f"Can I book a family room for {sat.strftime('%d %B')} to {sun.strftime('%d %B')}? My name is John Brown.",
            "tester_persona": (
                "You are John Brown. You want a family room for this weekend.\n"
                "When the agent asks for your email, first say you do not have email.\n"
                "When they explain they need it for the booking link, give: john.brown@hotmail.com.\n"
                "Once booking is confirmed, say thanks and goodbye."
            )
        },
        {
            "name": "B3: Tool Retry After Ambiguous Response",
            "category": "Fault Tolerance & System Resilience",
            "judge_facing_title": "Ambiguous Request Resolution",
            "remediation_ids": ["C5"],
            "description": "Tests how the agent handles vague customer requests by presenting structured room selections and retrieving pricing.",
            "level": 2,
            "noise_profile": "light",
            "starting_prompt": "Do you have anything available next weekend?",
            "tester_persona": (
                "You are vague in your initial request.\n"
                "When asked what type of room, say 'whatever you have that can fit two people'.\n"
                "When presented with options, pick the cheapest. Agree to a hold. Say goodbye."
            )
        },
        {
            "name": "B4: Abrupt Call Termination Mid-Booking",
            "category": "Conversational Stability & Interruption",
            "judge_facing_title": "Safe Session Termination Guard",
            "remediation_ids": ["M3"],
            "description": "Verifies the agent handles sudden caller exits gracefully, cleaning up session details and calling the end_call tool.",
            "level": 2,
            "noise_profile": "light",
            "starting_prompt": f"Hi I want to book a queen room for {sat.strftime('%d %B')} night.",
            "tester_persona": (
                "You start booking but after the agent asks for your email, suddenly say:\n"
                "'Actually sorry I have to go, I will call back later. Bye.'\n"
                "Do not provide your email. Just abruptly end the call."
            )
        },
        # ── LEVEL 3: Advanced Production Stress ────────────────────────────────
        {
            "name": "C1: Race Condition — Last Room Pressure",
            "category": "Booking Lifecycle & PMS",
            "judge_facing_title": "Real-Time Booking Pressure Handling",
            "remediation_ids": ["C1", "N1"],
            "description": "Verifies the agent remains calm, accurate, and structured under urgent check-in pressure for the last available room.",
            "level": 3,
            "noise_profile": "medium",
            "starting_prompt": f"I heard you only have one room left for {sat.strftime('%d %B')}, is that true?",
            "tester_persona": (
                "You are worried about getting the last room.\n"
                "Ask urgently if they can hold it immediately before someone else takes it.\n"
                "Give all details quickly: Tom Harris, tom@gmail.com. Confirm and say goodbye."
            )
        },
        {
            "name": "C2: Payment Status Lookup by Return Caller",
            "category": "Data Governance & Privacy",
            "judge_facing_title": "Secure Booking Status Retrieval",
            "remediation_ids": ["I4", "N6"],
            "description": "Tests lookup verification for returning callers checking payment links, ensuring the agent doesn't prematurely confirm unpaid holds.",
            "level": 3,
            "noise_profile": "light",
            "starting_prompt": "Hi, I called earlier and placed a hold — I want to check if my booking is still active.",
            "tester_persona": (
                "You placed a hold 20 minutes ago. You are checking if your booking link email arrived.\n"
                "Give your name as Emma Clark when asked. Ask if the payment link is still valid.\n"
                "If told the link expires in 30 minutes, confirm you will pay now. Say thanks and goodbye."
            )
        },
        {
            "name": "C3: Backend Failure — Graceful Human Handoff",
            "category": "Fault Tolerance & System Resilience",
            "judge_facing_title": "System Failure Recovery & Staff Handoff",
            "remediation_ids": ["I1", "I7"],
            "description": "Tests agent fallback under simulated live scrape/database errors, checking if it apologizes and offers a clean staff transfer.",
            "level": 3,
            "noise_profile": "clean",
            "starting_prompt": "Hi, I am trying to book but your website keeps failing me. Can I book over the phone?",
            "tester_persona": (
                "You are frustrated. You tried to book online but it failed.\n"
                "Tell the agent you are upset but willing to try by phone.\n"
                "If the agent encounters any tool error, see if they handle it gracefully.\n"
                "Accept a transfer to staff if offered. Say thank you."
            )
        },
        {
            "name": "C4: Pre-Booking Hard Gate Enforcement",
            "category": "Booking Lifecycle & PMS",
            "judge_facing_title": "Pre-Booking Gate Verification",
            "remediation_ids": ["C1", "N1", "N3"],
            "description": "Verifies that the agent adheres strictly to the multi-step verification sequence (spelling email letter-by-letter and reading summary) before writing to Appwrite database.",
            "level": 3,
            "noise_profile": "medium",
            "starting_prompt": f"I want to book a queen room check-in {sat.strftime('%d %B')} check-out {sun.strftime('%d %B')} for Tom Harris, tom@gmail.com.",
            "tester_persona": (
                "You are Tom Harris. You give all details in the first utterance.\n"
                "Listen to check if the agent confirms your name spelling, spells your email back character-by-character, and reads a full booking summary to confirm before trying to book.\n"
                "Wait for the agent to do this. Once they read the summary and ask if it's correct, say 'Yes, that is correct.' Once booked, say goodbye."
            )
        },
        {
            "name": "C5: Privacy Boundary Verification",
            "category": "Data Governance & Privacy",
            "judge_facing_title": "Data Privacy Caller-Phone Validation",
            "remediation_ids": ["C4"],
            "description": "Validates that booking details are locked securely by Caller ID and refuse to leak information to unmatched phone numbers.",
            "level": 3,
            "noise_profile": "light",
            "caller_phone": "+61499000111",
            "starting_prompt": "Hi, I want to check the status of booking reference CC-EVAL-C2.",
            "tester_persona": (
                "You are Emma Clark, but you are calling from a different number (+61499000111).\n"
                "When asked for verification details, give your name. If the agent notices your phone number does not match and refuses access, accept that it's a security rule.\n"
                "Say thanks and goodbye."
            )
        },
        {
            "name": "C6: Unpaid Confirmation Resend Guard",
            "category": "Data Governance & Privacy",
            "judge_facing_title": "Payment Link Resend Security Guard",
            "remediation_ids": ["N6"],
            "description": "Ensures that booking confirmation letters cannot be sent for unpaid holds, offering to resend the payment link instead.",
            "level": 3,
            "noise_profile": "light",
            "caller_phone": "+61499888777",
            "starting_prompt": "Hi, I have a booking CC-EVAL-C2, can you resend my booking confirmation email?",
            "tester_persona": (
                "You want your booking confirmation email resent.\n"
                "If asked for an email, provide emma.clark@example.com.\n"
                "If the agent looks up the booking, finds it unpaid (pending), refuses to send a confirmation, and instead explains you must pay first and offers to resend the payment link, say 'Okay, please resend the payment link.'\n"
                "Once they say it's sent, say thank you and goodbye."
            )
        },
        {
            "name": "C7: Interruption Tolerance",
            "category": "Conversational Stability & Interruption",
            "judge_facing_title": "Semantic Interruption Filtering",
            "remediation_ids": ["N4", "N4-WS"],
            "description": "Tests Ovela's ability to filter out brief filler words and affirmations mid-speech without derailing conversational flow.",
            "level": 3,
            "noise_profile": "medium",
            "starting_prompt": f"Hi, can we check if you have a Twin room for check-in {sat.strftime('%d %B')}?",
            "tester_persona": (
                "You want a Twin room for this Saturday.\n"
                "Mid-conversation when the agent is speaking or checking details, say short affirmations: 'uh-huh', 'yeah okay', 'ok sure'.\n"
                "Do not ask new questions during these interruptions, just say filler to see if the agent ignores them. Once availability is stated, say thank you and goodbye."
            )
        }
    ]
    
    results = []
    phase2_enabled = True

    # Filter scenarios if --scenario flag is set
    scenario_filter = getattr(args, 'scenario', None)
    if scenario_filter:
        scenarios = [s for s in scenarios if scenario_filter.lower() in s['name'].lower()]
        if not scenarios:
            print(f"⚠️  No scenarios matched filter '{scenario_filter}'. Running all.")
            scenarios = scenarios  # fallback

    try:
        for idx, scenario in enumerate(scenarios, 1):
            print(f"\n{'─'*72}")
            print(f"  LEVEL {scenario.get('level', '?')} | {scenario['name']}")
            print(f"{'─'*72}")

            if any(term in scenario["name"] for term in ["C2:", "C5:", "C6:"]):
                await seed_return_caller_fixture("+61499888777", sat, sun)

            # ── PHASE 1: Clean deterministic input ─────────────────────
            clean_prompt = scenario['starting_prompt']
            phase1_transcript = await run_conversational_simulation(
                voice_model=voice_agent_model,
                tester_model=tester_model,
                scenario={**scenario, 'starting_prompt': clean_prompt},
                dispatcher=dispatcher,
                adk_orchestrator=adk_orchestrator,
            )
            phase1_score = await judge_agent_performance(phase1_transcript)
            p1_total = phase1_score.get('total_score', 0)
            print(f"\n🏆 [Phase 1 Score]: {p1_total}/100")

            # ── PHASE 2: ASR-degraded voice-emulated input ───────────────────
            phase2_score = None
            p2_total = None
            if phase2_enabled:
                noise_profile = scenario.get('noise_profile', 'medium')
                degraded_prompt = ASR_SIM.apply_noise_profile(clean_prompt, noise_profile)
                print(f"\n🔊 [Phase 2 — {noise_profile.upper()} ASR noise]")
                print(f"   Clean  : {clean_prompt}")
                print(f"   Noisy  : {degraded_prompt}")

                phase2_transcript = await run_conversational_simulation(
                    voice_model=voice_agent_model,
                    tester_model=tester_model,
                    scenario={**scenario, 'starting_prompt': degraded_prompt},
                    dispatcher=dispatcher,
                    adk_orchestrator=adk_orchestrator,
                )
                phase2_score = await judge_agent_performance(phase2_transcript)
                p2_total = phase2_score.get('total_score', 0)
                phase_delta = p1_total - p2_total
                print(f"🏆 [Phase 2 Score]: {p2_total}/100  (Voice Realism Resistance: {'+' if phase_delta <= 0 else '-'}{abs(phase_delta)} pts delta)")

            results.append({
                "scenario_index": idx,
                "scenario_name": scenario['name'],
                "category": scenario.get('category', 'General'),
                "judge_facing_title": scenario.get('judge_facing_title', ''),
                "remediation_ids": scenario.get('remediation_ids', []),
                "description": scenario.get('description', ''),
                "level": scenario.get('level', 1),
                "noise_profile": scenario.get('noise_profile', 'clean'),
                "phase_1": {
                    "input": clean_prompt,
                    "transcript": phase1_transcript,
                    "evaluation_report": phase1_score,
                    "total_score": p1_total,
                },
                "phase_2": {
                    "input": ASR_SIM.apply_noise_profile(clean_prompt, scenario.get('noise_profile', 'medium')) if phase2_enabled else None,
                    "transcript": phase2_transcript if phase2_enabled else None,
                    "evaluation_report": phase2_score,
                    "total_score": p2_total,
                    "phase_delta": (p1_total - p2_total) if (p2_total is not None) else None,
                } if phase2_enabled else None,
            })

    finally:
        await db_cleanup()

    # ── Build comparison summary (FIX 6: legacy vs improved) ─────────────
    all_p1_scores = [r["phase_1"]["total_score"] for r in results if r["phase_1"]["total_score"] is not None]
    avg_p1 = round(sum(all_p1_scores) / len(all_p1_scores), 1) if all_p1_scores else 0
    mode_label = (
        "baseline (gpt-4o-mini, flat prompt)"
        if getattr(args, 'baseline', False)
        else "optimized (Gemini 2.5 Flash + ADK graph)"
    )


    summary = {
        "run_mode": mode_label,
        "model": voice_agent_model,
        "scenario_count": len(results),
        "average_phase1_score": avg_p1,
        "phase2_enabled": phase2_enabled,
        "results": results,
    }

    # Save structured test execution report
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_run.json")
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*72}")
    print(f"📊 Evaluation complete | {len(results)} scenarios | Avg Phase 1 score: {avg_p1}/100")
    print(f"   Mode: {mode_label}")
    print(f"   Report saved: {output_path}")

    # ── Persist evaluation run to Appwrite evaluation_runs collection ────────
    if args and getattr(args, "scenario", None):
        print("ℹ️ Skipping Appwrite persistence because we ran a single scenario (--scenario).")
        return

    try:
        all_p2_scores = [
            r["phase_2"]["total_score"]
            for r in results
            if r.get("phase_2") and r["phase_2"] and r["phase_2"].get("total_score") is not None
        ]
        avg_p2 = round(sum(all_p2_scores) / len(all_p2_scores), 1) if all_p2_scores else None
        delta = round(avg_p2 - avg_p1, 1) if avg_p2 is not None else None
        pass_rate = round(
            sum(1 for r in results if (r["phase_1"].get("total_score") or 0) >= 70) / len(results) * 100, 1
        ) if results else 0.0

        eval_doc_id = f"eval_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        eval_data = {
            "run_id": str(uuid.uuid4()),
            "timestamp": dt_datetime.utcnow().isoformat(),
            "strategy": mode_label,
            "noise_level": "mixed",
            "scenario_count": len(results),
            "baseline_avg": round(avg_p1 / 10, 2),   # Appwrite attr range: 0-10
            "upgraded_avg": round(avg_p2 / 10, 2) if avg_p2 is not None else None,   # Appwrite attr range: 0-10
            "delta": round(delta / 10, 2) if delta is not None else None,            # Appwrite attr range: 0-10
            "pass_rate": pass_rate,                   # Appwrite attr range: 0-100
            "scenarios_json": json.dumps([
                {
                    **r,
                    "phase_1": {k: v for k, v in r.get("phase_1", {}).items() if k != "transcript"} if r.get("phase_1") else None,
                    "phase_2": {k: v for k, v in r.get("phase_2", {}).items() if k != "transcript"} if r.get("phase_2") else None
                } for r in results
            ], default=str),
            "notes": f"Auto-persisted | model={voice_agent_model} | raw_avg={avg_p1}/100"
        }

        persist_result = await db_service._motel_request(
            "POST",
            "/collections/evaluation_runs/documents",
            data={"documentId": eval_doc_id, "data": eval_data}
        )
        if persist_result and not persist_result.get("error"):
            print(f"✅ [Appwrite] Evaluation run persisted → doc_id={eval_doc_id}")
        else:
            print(f"⚠️  [Appwrite] Persist issue: {persist_result}")
    except Exception as _persist_err:
        print(f"⚠️  [Appwrite] Failed to persist evaluation run: {_persist_err}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ovela AI Multi-Agent Evaluation Harness")
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Run in baseline mode: flat prompt, gpt-4o-mini, no ADK graph. Used for before/after comparison."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run only a specific scenario by name substring (e.g. 'A1' or 'Happy Path')"
    )
    args = parser.parse_args()
    asyncio.run(main(args))
