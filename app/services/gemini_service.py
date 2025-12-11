"""AI Service for generating responses via Gemini (primary) and Freeway API (fallback)"""
import httpx
from app.config import settings
from app.models.persona import Persona, KnowledgeBase
from app.models.user import User, UsageTracking
from app.models.chat import ChatMessage
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, AsyncIterator
import logging
import json

logger = logging.getLogger(__name__)

# Gemini API Configuration
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_STREAM_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"


class GeminiService:
    """
    Service for interacting with AI.
    Uses Gemini as primary, falls back to Freeway API (paid) on failure.
    """

    def __init__(self, db: Session):
        self.db = db
        # Gemini config (primary)
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.gemini_model = settings.GEMINI_MODEL
        # Freeway config (fallback)
        self.freeway_url = settings.FREEWAY_API_URL
        self.freeway_key = settings.FREEWAY_API_KEY

    def _build_system_prompt(self, persona: Persona, knowledge_bases: List[KnowledgeBase]) -> str:
        """
        Build system prompt from persona configuration and knowledge bases
        """
        prompt_parts = []

        # Base persona identity
        prompt_parts.append(f"You are {persona.name}.")

        if persona.bio:
            prompt_parts.append(f"Bio: {persona.bio}")

        if persona.description:
            prompt_parts.append(f"Description: {persona.description}")

        # Personality traits
        if persona.personality_traits:
            traits = ", ".join(persona.personality_traits)
            prompt_parts.append(f"Personality traits: {traits}")

        # Language style
        if persona.language_style:
            prompt_parts.append(f"Communication style: {persona.language_style}")

        # Expertise areas
        if persona.expertise:
            expertise = ", ".join(persona.expertise)
            prompt_parts.append(f"Areas of expertise: {expertise}")

        # Knowledge base content
        if knowledge_bases:
            prompt_parts.append("\nKnowledge Base:")
            for kb in knowledge_bases:
                if kb.status == "active" and kb.content:
                    prompt_parts.append(f"\n--- {kb.source_name or kb.source_type} ---")
                    prompt_parts.append(kb.content)

        # Final instruction with length optimization
        prompt_parts.append("""
RESPONSE GUIDELINES:
- Keep responses concise and conversational - typically 1-3 short paragraphs
- Get to the point quickly without unnecessary preamble or filler
- Only give longer, detailed responses when:
  * The user explicitly asks for more detail, explanation, or elaboration
  * The topic genuinely requires thorough explanation (complex questions, tutorials, etc.)
  * You're telling a story or creative content the user requested
- Avoid repetition, excessive qualifiers, and verbose language
- Don't pad responses with unnecessary pleasantries or restatements
- Stay in character while being efficient with words

Respond to the user's messages while staying in character and using the knowledge provided above.""")

        return "\n\n".join(prompt_parts)

    def _build_conversation_history(
        self,
        messages: List[ChatMessage],
        limit: int = None
    ) -> List[Dict[str, str]]:
        """
        Build conversation history from chat messages in OpenAI format
        """
        # Use config default if not specified
        if limit is None:
            limit = settings.AI_MAX_CONVERSATION_HISTORY

        # Get recent messages (sorted by created_at)
        recent_messages = sorted(messages, key=lambda x: x.created_at)[-limit:]

        history = []
        for msg in recent_messages:
            role = "user" if msg.sender_type == "user" else "assistant"
            history.append({
                "role": role,
                "content": msg.text
            })

        return history

    def _check_usage_limits(self, user: User, usage: UsageTracking) -> Dict[str, Any]:
        """
        Check if user has exceeded usage limits
        Returns dict with 'allowed' boolean and 'reason' if not allowed
        """
        # Reset daily counters if needed
        usage.check_and_reset_daily()
        self.db.commit()

        # Premium users have unlimited usage
        if user.is_premium:
            return {"allowed": True}

        # Free tier limits
        if usage.messages_today >= settings.FREE_TIER_MESSAGE_LIMIT:
            return {
                "allowed": False,
                "reason": f"Daily message limit reached ({settings.FREE_TIER_MESSAGE_LIMIT} messages/day for free tier)",
                "limit": settings.FREE_TIER_MESSAGE_LIMIT,
                "used": usage.messages_today
            }

        return {"allowed": True}

    def _update_usage_tracking(
        self,
        usage: UsageTracking,
        tokens_used: int
    ):
        """Update usage tracking after successful generation"""
        usage.messages_today += 1
        usage.gemini_api_calls_today += 1
        usage.gemini_tokens_used_total += tokens_used
        self.db.commit()

    async def _make_gemini_request(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make a request to Gemini API.

        Args:
            system_prompt: The system prompt
            messages: List of message dicts with role and content
            temperature: Creativity level
            max_tokens: Maximum tokens in response

        Returns:
            The API response as a dict

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        # Build Gemini-format contents
        contents = []

        # Add conversation history
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        request_body = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": temperature,
            }
        }

        if max_tokens:
            request_body["generationConfig"]["maxOutputTokens"] = max_tokens

        api_url = GEMINI_API_URL.format(model=self.gemini_model) + f"?key={self.gemini_api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=request_body)
            response.raise_for_status()
            return response.json()

    async def _make_freeway_request(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make a request to Freeway API (paid model).

        Args:
            payload: The request payload

        Returns:
            The API response as a dict

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        request_payload = {**payload, "model": "paid"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.freeway_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self.freeway_key
                },
                json=request_payload
            )
            response.raise_for_status()
            return response.json()

    async def generate_response(
        self,
        user_id: str,
        persona_id: str,
        user_message: str,
        conversation_history: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate AI response using Gemini (primary) with Freeway paid fallback.

        Args:
            user_id: User making the request
            persona_id: Persona to use for response
            user_message: The user's message
            conversation_history: Previous messages in the conversation
            temperature: Creativity level (0.0-1.0)
            max_tokens: Maximum tokens in response

        Returns:
            Dict containing response text, tokens used, and sentiment
        """
        try:
            # Get user and usage tracking
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            usage = user.usage_tracking
            if not usage:
                # Create usage tracking if not exists
                usage = UsageTracking(user_id=user_id)
                self.db.add(usage)
                self.db.commit()
                self.db.refresh(usage)

            # Check usage limits
            limit_check = self._check_usage_limits(user, usage)
            if not limit_check["allowed"]:
                return {
                    "error": "usage_limit_exceeded",
                    "message": limit_check["reason"],
                    "limit": limit_check.get("limit"),
                    "used": limit_check.get("used")
                }

            # Apply config defaults for token optimization
            if temperature is None:
                temperature = settings.AI_DEFAULT_TEMPERATURE
            if max_tokens is None:
                max_tokens = settings.AI_DEFAULT_MAX_TOKENS

            # Get persona
            persona = self.db.query(Persona).filter(Persona.id == persona_id).first()
            if not persona:
                raise ValueError("Persona not found")

            # Get knowledge bases
            knowledge_bases = self.db.query(KnowledgeBase).filter(
                KnowledgeBase.persona_id == persona_id,
                KnowledgeBase.status == "active"
            ).all()

            # Build system prompt
            system_prompt = self._build_system_prompt(persona, knowledge_bases)

            # Build conversation history in OpenAI format
            history = self._build_conversation_history(conversation_history)

            # Build messages for the AI (without system message for Gemini, it uses systemInstruction)
            messages = list(history)
            messages.append({"role": "user", "content": user_message})

            # For Freeway fallback - include system message
            freeway_messages = [{"role": "system", "content": system_prompt}]
            freeway_messages.extend(history)
            freeway_messages.append({"role": "user", "content": user_message})

            freeway_payload = {
                "messages": freeway_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Try Gemini first, fallback to Freeway paid
            used_model = f"gemini-{self.gemini_model}"
            response_text = None

            try:
                logger.info(f"Attempting request with Gemini ({self.gemini_model})")
                result = await self._make_gemini_request(
                    system_prompt=system_prompt,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                # Extract response text from Gemini format
                response_text = (
                    result.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )

                if not response_text:
                    raise ValueError("Empty response from Gemini")

                logger.info("Gemini request successful")

            except Exception as gemini_error:
                logger.warning(f"Gemini failed: {str(gemini_error)}. Falling back to Freeway paid...")

                try:
                    result = await self._make_freeway_request(freeway_payload)
                    response_text = result["choices"][0]["message"]["content"]
                    used_model = "freeway-paid"
                    logger.info("Freeway paid fallback succeeded")
                except httpx.HTTPStatusError as freeway_error:
                    logger.error(
                        f"Freeway paid also failed: "
                        f"{freeway_error.response.status_code} - {freeway_error.response.text}"
                    )
                    raise freeway_error

            # Get token usage (estimate if not provided)
            tokens_used = len(response_text) // 4

            # Perform simple sentiment analysis
            sentiment = self._analyze_sentiment(response_text)

            # Update usage tracking
            self._update_usage_tracking(usage, tokens_used)

            # Update persona conversation count
            persona.conversation_count += 1
            self.db.commit()

            return {
                "response": response_text,
                "tokens_used": tokens_used,
                "sentiment": sentiment,
                "model_used": used_model,
                "usage": {
                    "messages_today": usage.messages_today,
                    "limit": settings.FREE_TIER_MESSAGE_LIMIT if not user.is_premium else None
                }
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    def _analyze_sentiment(self, text: str) -> str:
        """
        Basic sentiment analysis
        In production, you could use a proper sentiment model
        """
        text_lower = text.lower()

        # Positive indicators
        positive_words = ['happy', 'great', 'excellent', 'good', 'wonderful', 'amazing', 'love', 'yes', '!']
        # Negative indicators
        negative_words = ['sorry', 'sad', 'bad', 'terrible', 'no', 'unfortunately', 'problem', 'issue']

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    async def _stream_from_gemini(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Stream response from Gemini API.

        Yields:
            Content chunks as they arrive
        """
        # Build Gemini-format contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        generation_config = {"temperature": temperature}
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens

        request_body = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": generation_config
        }

        api_url = GEMINI_STREAM_URL.format(model=self.gemini_model) + f"?key={self.gemini_api_key}&alt=sse"

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", api_url, json=request_body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            chunk_data = json.loads(data)
                            candidates = chunk_data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    text = part.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue

    async def _stream_from_freeway(
        self,
        payload: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """
        Stream response from Freeway API (paid model).

        Yields:
            Content chunks as they arrive
        """
        request_payload = {**payload, "model": "paid", "stream": True}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.freeway_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self.freeway_key
                },
                json=request_payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

    async def generate_streaming_response(
        self,
        user_id: str,
        persona_id: str,
        user_message: str,
        conversation_history: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming AI response using Gemini (primary) with Freeway paid fallback.

        Yields response chunks as they arrive.
        """
        try:
            # Apply config defaults for token optimization
            if temperature is None:
                temperature = settings.AI_DEFAULT_TEMPERATURE
            if max_tokens is None:
                max_tokens = settings.AI_DEFAULT_MAX_TOKENS

            # Similar setup as generate_response
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            usage = user.usage_tracking
            if not usage:
                usage = UsageTracking(user_id=user_id)
                self.db.add(usage)
                self.db.commit()
                self.db.refresh(usage)

            # Check usage limits
            limit_check = self._check_usage_limits(user, usage)
            if not limit_check["allowed"]:
                yield json.dumps({
                    "error": "usage_limit_exceeded",
                    "message": limit_check["reason"]
                })
                return

            # Get persona and knowledge
            persona = self.db.query(Persona).filter(Persona.id == persona_id).first()
            if not persona:
                raise ValueError("Persona not found")

            knowledge_bases = self.db.query(KnowledgeBase).filter(
                KnowledgeBase.persona_id == persona_id,
                KnowledgeBase.status == "active"
            ).all()

            # Build prompts
            system_prompt = self._build_system_prompt(persona, knowledge_bases)
            history = self._build_conversation_history(conversation_history)

            # Build messages for Gemini (without system message)
            messages = list(history)
            messages.append({"role": "user", "content": user_message})

            # For Freeway fallback - include system message
            freeway_messages = [{"role": "system", "content": system_prompt}]
            freeway_messages.extend(history)
            freeway_messages.append({"role": "user", "content": user_message})

            freeway_payload = {
                "messages": freeway_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Try Gemini first, fallback to Freeway paid
            used_model = f"gemini-{self.gemini_model}"
            full_response = ""

            try:
                logger.info(f"Attempting streaming request with Gemini ({self.gemini_model})")
                async for content in self._stream_from_gemini(system_prompt, messages, temperature, max_tokens):
                    full_response += content
                    yield json.dumps({"chunk": content})

                if not full_response:
                    raise ValueError("Empty response from Gemini streaming")

                logger.info("Gemini streaming succeeded")

            except Exception as gemini_error:
                logger.warning(f"Gemini streaming failed: {str(gemini_error)}. Falling back to Freeway paid...")

                # Reset full_response for fallback
                full_response = ""
                try:
                    async for content in self._stream_from_freeway(freeway_payload):
                        full_response += content
                        yield json.dumps({"chunk": content})
                    used_model = "freeway-paid"
                    logger.info("Freeway paid streaming fallback succeeded")
                except Exception as freeway_error:
                    logger.error(f"Freeway paid streaming also failed: {str(freeway_error)}")
                    yield json.dumps({"error": f"Both Gemini and Freeway failed: {str(freeway_error)}"})
                    return

            # After streaming complete, update usage
            tokens_used = len(full_response) // 4
            self._update_usage_tracking(usage, tokens_used)

            # Update persona count
            persona.conversation_count += 1
            self.db.commit()

            # Send final metadata
            yield json.dumps({
                "done": True,
                "tokens_used": tokens_used,
                "sentiment": self._analyze_sentiment(full_response),
                "model_used": used_model
            })

        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            yield json.dumps({"error": str(e)})
