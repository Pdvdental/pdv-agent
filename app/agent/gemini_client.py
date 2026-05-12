import json
import logging
import pytz
from datetime import datetime
import google.generativeai as genai

from app.config import get_settings
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import TOOL_DECLARATIONS, dispatch
from app.integrations import db

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5


def _init_model():
    s = get_settings()
    tz = pytz.timezone(s.timezone)
    now = datetime.now(tz)
    date_str = now.strftime("%A, %-d de %B de %Y, %H:%M (Europe/Madrid)")
    dynamic_prompt = SYSTEM_PROMPT + f"\n\n# Fecha y hora actual\n{date_str}"

    genai.configure(api_key=s.gemini_api_key)
    return genai.GenerativeModel(
        model_name=s.gemini_model,
        system_instruction=dynamic_prompt,
        tools=[{"function_declarations": TOOL_DECLARATIONS}],
    )


def _build_contents(messages: list[dict]) -> list[dict]:
    contents = []
    for m in messages:
        if m["role"] == "tool":
            parsed = json.loads(m["content"])
            if not isinstance(parsed.get("response"), dict):
                parsed["response"] = {"result": parsed["response"]}
            contents.append({
                "role": "user",
                "parts": [{"function_response": parsed}],
            })
        elif m["tool_calls"]:
            contents.append({
                "role": "model",
                "parts": [{"function_call": json.loads(m["content"])}],
            })
        else:
            contents.append({
                "role": m["role"],
                "parts": [{"text": m["content"]}],
            })
    return contents


def chat_turn(
    db_conversation_id: str,
    chatwoot_conversation_id: int,
    user_message: str,
    source_id: str = None,
) -> str:
    """
    Loads conversation history, calls Gemini, handles function calling loop,
    persists everything, and returns the final text response.
    `source_id` (optional) is the Meta wamid of the user message, used for dedup.
    """
    model = _init_model()

    history = db.get_conversation_messages(db_conversation_id, limit=30)
    db.save_message(db_conversation_id, "user", user_message, source_id=source_id)

    contents = _build_contents(history)
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    for iteration in range(MAX_TOOL_ITERATIONS):
        response = model.generate_content(contents)
        candidate = response.candidates[0]

        # Check for function call
        function_call = None
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_call = part.function_call
                break

        if function_call is None:
            # Final text response
            text = candidate.content.parts[0].text
            db.save_message(db_conversation_id, "model", text)
            return text

        # Execute tool
        tool_name = function_call.name
        tool_args = dict(function_call.args)

        # Inject Chatwoot/DB conversation IDs for escalation tool
        if tool_name == "escalate_to_human":
            tool_args.setdefault("conversation_id", chatwoot_conversation_id)
            tool_args.setdefault("db_conversation_id", db_conversation_id)

        logger.info(f"Calling tool: {tool_name}({tool_args})")
        tool_result = dispatch(tool_name, tool_args)

        # Persist function call + response
        db.save_message(
            db_conversation_id,
            "model",
            json.dumps({"name": tool_name, "args": tool_args}),
            tool_calls={"name": tool_name, "args": tool_args},
        )
        db.save_message(
            db_conversation_id,
            "tool",
            json.dumps({"name": tool_name, "response": tool_result}),
            tool_response={"name": tool_name, "response": tool_result},
        )

        # Append to contents for next iteration
        contents.append({
            "role": "model",
            "parts": [{"function_call": {"name": tool_name, "args": tool_args}}],
        })
        contents.append({
            "role": "user",
            "parts": [{"function_response": {"name": tool_name, "response": {"result": tool_result}}}],
        })

    # Fallback if we hit max iterations without a text response
    fallback = "Lo siento, ha ocurrido un problema procesando tu solicitud. Por favor, inténtalo de nuevo o llama al 93 729 4880."
    db.save_message(db_conversation_id, "model", fallback)
    return fallback