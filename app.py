import logging
import os
import uuid
from pathlib import Path
from typing import Any, Generator

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, session, stream_with_context
from flask_session import Session
from openai import APIConnectionError, AuthenticationError, BadRequestError, OpenAI, OpenAIError
from pydantic import BaseModel, Field

import prompts_eakademie as chatbot_prompts
from config import Config

load_dotenv(override=False)

app = Flask(__name__, static_url_path="/static")
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.secret_key = app.config.get("SECRET_KEY") or "change-me-in-production"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_KEY_PREFIX"] = "chatbot_"
Session(app)

AZURE_OPENAI_KEY = app.config.get("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_SUBSCRIPTION_KEY")
AZURE_OPENAI_ENDPOINT = app.config.get("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_VERSION = app.config.get("AZURE_API_VERSION", "2024-12-01")
AZURE_DEPLOYMENT = app.config.get("AZURE_OPENAI_DEPLOYMENT") or os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
if AZURE_OPENAI_ENDPOINT and not AZURE_OPENAI_ENDPOINT.startswith(("http://", "https://")):
    AZURE_OPENAI_ENDPOINT = f"https://{AZURE_OPENAI_ENDPOINT.lstrip('/')}"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _azure_connection_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if "404" in message and "Resource not found" in message:
        return (
            "Nepodařilo se připojit k Azure OpenAI: Resource not found. "
            "Zkontroluj, že [`AZURE_OPENAI_ENDPOINT`](.env.example:1) patří ke správnému Azure OpenAI resource a že "
            "[`AZURE_OPENAI_DEPLOYMENT`](.env.example:3) přesně odpovídá názvu deploymentu."
        )
    if not message:
        return "Nepodařilo se připojit k Azure OpenAI. Zkontroluj endpoint, klíč a síťové připojení."
    return f"Nepodařilo se připojit k Azure OpenAI: {message}"


class CourseCitation(BaseModel):
    title: str = Field(..., description="Course title")
    url: str = Field(..., description="Course URL")
    course_id: str | None = Field(default=None, description="Internal course identifier")
    provider: str | None = Field(default=None, description="Content provider")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Assistant reply in Czech")
    citations: list[CourseCitation] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_clarification: bool = Field(default=False)
    clarification_question: str | None = Field(default=None)
    language: str = Field(default="cs")
    metadata: dict[str, Any] = Field(default_factory=dict)


def get_azure_client() -> OpenAI:
    if not AZURE_OPENAI_KEY:
        raise RuntimeError("AZURE_OPENAI_KEY or AZURE_SUBSCRIPTION_KEY is not configured")
    if not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is not configured")
    if not AZURE_DEPLOYMENT:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not configured")

    base_url = AZURE_OPENAI_ENDPOINT.rstrip("/")
    if not base_url.endswith("/models"):
        base_url = f"{base_url}/models"

    return OpenAI(
        api_key=AZURE_OPENAI_KEY,
        base_url=base_url,
    )


def _ensure_history() -> list[dict[str, str]]:
    if "history" not in session:
        session["history"] = [{"role": "assistant", "content": chatbot_prompts.prompteAkademieAIJsonAutomat}]
        session.modified = True
    return session["history"]


def _build_messages(user_message: str) -> list[dict[str, str]]:
    history = _ensure_history()
    history.append({"role": "user", "content": user_message})
    session.modified = True
    return history


def _generate_structured_response(user_message: str) -> ChatResponse:
    messages = _build_messages(user_message)
    try:
        response = get_azure_client().chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=messages,
            temperature=1.0,
            top_p=1.0,
            max_tokens=4096,  # Změněno z 16384 na bezpečnější hodnotu max_tokens
        )
    except (APIConnectionError, AuthenticationError, BadRequestError, OpenAIError, OSError) as exc:
        logger.exception("Azure OpenAI request failed")
        raise RuntimeError(_azure_connection_error_message(exc)) from exc

    reply_content = response.choices[0].message.content or ""
    structured = ChatResponse(reply=reply_content)
    session["history"].append({"role": "assistant", "content": structured.reply})
    session.modified = True
    return structured


def _stream_response(user_message: str) -> Generator[str, None, None]:
    messages = _build_messages(user_message)
    try:
        response = get_azure_client().chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=messages,
            temperature=1.0,
            top_p=1.0,
            max_tokens=4096,  # Změněno z 16384 na bezpečnější hodnotu max_tokens
            stream=True,
        )
    except (APIConnectionError, AuthenticationError, BadRequestError, OpenAIError, OSError) as exc:
        logger.exception("Azure OpenAI stream request failed")
        yield f"data: [CHYBA] {_azure_connection_error_message(exc)}\n\n"
        return

    reply_parts = []
    for chunk in response:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue

        delta_obj = getattr(choices[0], "delta", None)
        if delta_obj is None:
            continue

        delta = getattr(delta_obj, "content", None)
        if delta:
            reply_parts.append(delta)
            yield f"data: {delta}\n\n"

    reply_content = "".join(reply_parts)
    session["history"].append({"role": "assistant", "content": reply_content})
    session.modified = True


@app.context_processor
def inject_config():
    return dict(
        app_name=app.config.get("APP_NAME", "AI asistent"),
        version=app.config.get("VERSION", "v1.0"),
        RELATIVE_URL=app.config.get("RELATIVE_URL", ""),
    )


@app.before_request
def ensure_session():
    if "id" not in session:
        session["id"] = str(uuid.uuid4())


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/")
def index():
    return render_template("chateAkademieAIJson.html")


@app.route("/chateAkademieAIJson")
def chateAkademieAIJson():
    return render_template("chateAkademieAIJson.html")


@app.route("/askchateAkademieAIJson", methods=["POST"])
def askchateAkademieAIJson():
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get("message")

        if not isinstance(user_message, str):
            return jsonify({"reply": "Zpráva musí být text."}), 400

        user_message = user_message.strip()
        if not user_message:
            return jsonify({"reply": "Zpráva nesmí být prázdná."}), 400
        if len(user_message) > 2000:
            return jsonify({"reply": "Zpráva nesmí přesáhnout 2000 znaků."}), 400

        structured = _generate_structured_response(user_message)
        return jsonify(structured.model_dump())
    except RuntimeError as e:
        logger.exception("askchateAkademieAIJson failed")
        return jsonify({"reply": str(e)}), 502
    except Exception as e:
        logger.exception("askchateAkademieAIJson failed")
        return jsonify({"reply": f"Nastala chyba: {str(e)}"}), 500


@app.route("/askchateAkademieAIJson/stream", methods=["POST"])
def askchateAkademieAIJson_stream():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message")

    if not isinstance(user_message, str):
        return jsonify({"reply": "Zpráva musí být text."}), 400

    user_message = user_message.strip()
    if not user_message:
        return jsonify({"reply": "Zpráva nesmí být prázdná."}), 400
    if len(user_message) > 2000:
        return jsonify({"reply": "Zpráva nesmí přesáhnout 2000 znaků."}), 400

    def generate_stream():
        try:
            yield from _stream_response(user_message)
        except RuntimeError as exc:
            logger.exception("askchateAkademieAIJson_stream failed")
            yield f"data: [CHYBA] {str(exc)}\n\n"
        except Exception as exc:
            logger.exception("askchateAkademieAIJson_stream failed")
            yield f"data: [CHYBA] {str(exc)}\n\n"

    return Response(
        stream_with_context(generate_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/resetchateAkademieAIJson")
def resetchateAkademieAIJson():
    session.clear()
    return redirect("/chateAkademieAIJson")


@app.route("/site-map")
def site_map():
    links = []
    for rule in app.url_map.iter_rules():
        methods = ",".join(rule.methods)
        links.append(f"{rule.endpoint}: {rule.rule} [{methods}]")
    return "<br>".join(links)


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
    )
