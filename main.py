from dotenv import load_dotenv
import os
import time
from langfuse import Langfuse

# load envs immediately
load_dotenv()

def _norm_env(key):
    v = os.getenv(key)
    if not v:
        return None
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()

LANGFUSE_SECRET_KEY = _norm_env("LANGFUSE_SECRET_KEY") or _norm_env("LANGFUSE_API_KEY")
LANGFUSE_PUBLIC_KEY = _norm_env("LANGFUSE_PUBLIC_KEY")
LANGFUSE_BASE_URL = _norm_env("LANGFUSE_BASE_URL") or _norm_env("LANGFUSE_HOST") or "http://localhost:3000"

# export envs
os.environ["LANGFUSE_SECRET_KEY"] = LANGFUSE_SECRET_KEY
os.environ["LANGFUSE_PUBLIC_KEY"] = LANGFUSE_PUBLIC_KEY
os.environ["LANGFUSE_HOST"] = LANGFUSE_BASE_URL

# Import after setting env vars
from langfuse.openai import OpenAI

# Initialize both clients
langfuse_client = Langfuse(
    secret_key=LANGFUSE_SECRET_KEY,
    public_key=LANGFUSE_PUBLIC_KEY,
    host=LANGFUSE_BASE_URL
)

openai_client = OpenAI()

SYSTEM_PROMPT = """
You are an AI agent who solves user query within 40 words.
"""

# Your evaluator name from Langfuse UI
EVALUATOR_NAME = "test_for_llm_as_judge"

def wait_for_judge_score(trace_id, max_wait_seconds=120, poll_interval=5):
    """
    Poll Langfuse for the judge score until it appears or timeout.
    """
    print(f"\n[DEBUG] Waiting for judge score...")
    print(f"[DEBUG] Trace ID: {trace_id}")
    print(f"[DEBUG] Evaluator name: {EVALUATOR_NAME}")
    print(f"[DEBUG] Max wait time: {max_wait_seconds}s")
    
    start_time = time.time()
    attempts = 0
    
    while (time.time() - start_time) < max_wait_seconds:
        attempts += 1
        elapsed = int(time.time() - start_time)
        print(f"[DEBUG] Attempt {attempts} ({elapsed}s elapsed)...", end="", flush=True)
        
        try:
            # Fetch the trace from Langfuse
            trace = langfuse_client.fetch_trace(trace_id)
            
            if trace:
                print(f" Trace found!")
                
                # Debug: Print trace info
                scores = getattr(trace, 'scores', None)
                if scores:
                    print(f"[DEBUG] Scores in trace: {len(scores)}")
                    
                    for idx, score in enumerate(scores):
                        score_name = getattr(score, 'name', 'unknown')
                        score_value = getattr(score, 'value', None)
                        score_string = getattr(score, 'string_value', None)
                        print(f"[DEBUG] Score {idx}: name='{score_name}', value={score_value}, string_value={score_string}")
                        
                        # Check if this is our evaluator
                        if score_name == EVALUATOR_NAME:
                            final_score = score_value if score_value is not None else score_string
                            
                            if final_score is not None:
                                # Convert to int if it's a string
                                try:
                                    final_score = int(float(final_score))
                                except (ValueError, TypeError):
                                    pass
                                
                                print(f"\n[SUCCESS] Found judge score: {final_score}")
                                return {"score": final_score, "found": True}
                else:
                    print(" No scores yet")
            else:
                print(" Trace not found")
            
            # Wait before next attempt
            if (time.time() - start_time) < max_wait_seconds:
                time.sleep(poll_interval)
        
        except Exception as e:
            print(f" Error: {e}")
            time.sleep(poll_interval)
    
    print(f"\n[WARNING] Judge score not found after {max_wait_seconds}s and {attempts} attempts")
    return {"score": None, "found": False}

def get_trace_id_from_response(response):
    """
    Extract trace ID from OpenAI response with Langfuse wrapper.
    """
    # Try multiple methods to get trace ID
    
    # Method 1: Check for langfuse_observation_id in response
    if hasattr(response, 'langfuse_observation_id'):
        return response.langfuse_observation_id
    
    # Method 2: Check for _langfuse_trace_id
    if hasattr(response, '_langfuse_trace_id'):
        return response._langfuse_trace_id
    
    # Method 3: Check in system_fingerprint or other metadata
    if hasattr(response, 'system_fingerprint'):
        fp = response.system_fingerprint
        if fp and len(fp) == 36:  # UUID length with dashes
            return fp
    
    # Method 4: Try to access internal attributes
    if hasattr(response, '__dict__'):
        for key, value in response.__dict__.items():
            if 'trace' in key.lower() and isinstance(value, str) and len(value) == 36:
                return value
    
    return None

def main():
    print("=" * 60)
    print("Chatbot with Langfuse LLM Judge")
    print("=" * 60)
    print(f"Evaluator: {EVALUATOR_NAME}")
    print(f"Langfuse host: {LANGFUSE_BASE_URL}")
    print(f"Type 'exit' to quit")
    print("=" * 60)
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "exit":
            break
        
        if not user_input:
            continue

        try:
            # Make the OpenAI call with Langfuse wrapper (it auto-traces)
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ]
            )

            assistant_message = response.choices[0].message.content
            
            # Try to get trace ID from response
            trace_id = get_trace_id_from_response(response)
            
            # If not found, flush and get the latest trace
            if not trace_id:
                print("[DEBUG] Trace ID not found in response, flushing and fetching latest...")
                langfuse_client.flush()
                time.sleep(2)  # Wait for trace to be registered
                
                try:
                    # Fetch latest traces
                    traces_response = langfuse_client.fetch_traces(limit=1, page=1)
                    if traces_response and hasattr(traces_response, 'data') and len(traces_response.data) > 0:
                        latest_trace = traces_response.data[0]
                        trace_id = latest_trace.id
                        print(f"[DEBUG] Using latest trace: {trace_id}")
                except Exception as e:
                    print(f"[ERROR] Could not fetch latest trace: {e}")
            
            if not trace_id:
                print("\n[ERROR] Could not determine trace ID")
                print("[INFO] Response will be shown without judge evaluation")
                print(f"\nAssistant: {assistant_message}")
                continue
            
            print(f"\n[INFO] Trace created: {trace_id}")
            print(f"[INFO] View in Langfuse: {LANGFUSE_BASE_URL}/trace/{trace_id}")
            
            # Wait for the judge score
            print(f"\n[INFO] Waiting for LLM judge evaluation (this may take up to 2 minutes)...")
            result = wait_for_judge_score(trace_id, max_wait_seconds=120, poll_interval=5)
            
            if result["found"]:
                score = result["score"]
                print(f"\n{'='*60}")
                print(f"JUDGE DECISION: {'APPROVED' if score == 1 else 'REJECTED'} (score: {score})")
                print(f"{'='*60}")
                
                print("\nAssistant: ", end="")
                if score == 1:
                    print(assistant_message)
                else:
                    print("We could not process your request")
            else:
                print(f"\n{'='*60}")
                print("TIMEOUT: Judge score not available")
                print(f"{'='*60}")
                print("\n[ERROR] Possible issues:")
                print("  1. Evaluator not running (check if it's ACTIVE in Langfuse UI)")
                print("  2. Variable mapping incorrect:")
                print("     - {{user_message}} should map to: Trace -> Input")
                print("     - {{assistant_response}} should map to: Trace -> Output")
                print("  3. Evaluator delay too short (try 5-10 seconds)")
                print("  4. Evaluator filter not matching traces")
                print(f"\n  Check trace manually: {LANGFUSE_BASE_URL}/trace/{trace_id}")
                print(f"\nShowing response anyway:")
                print(f"Assistant: {assistant_message}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()