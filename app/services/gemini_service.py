"""AI Service for generating responses via Freeway API Gateway"""
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


class GeminiService:
    """
    Service for interacting with AI via Freeway API Gateway.
    Named GeminiService for backward compatibility, but now uses Freeway.
    """

    def __init__(self, db: Session):
        self.db = db
        self.api_url = settings.FREEWAY_API_URL
        self.api_key = settings.FREEWAY_API_KEY
        self.model = settings.FREEWAY_MODEL  # "free" or "paid"

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

        # Final instruction
        prompt_parts.append("\nRespond to the user's messages while staying in character and using the knowledge provided above.")

        return "\n\n".join(prompt_parts)

    def _build_conversation_history(
        self,
        messages: List[ChatMessage],
        limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        Build conversation history from chat messages in OpenAI format
        """
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

    async def _make_freeway_request(
        self,
        payload: Dict[str, Any],
        model: str
    ) -> Dict[str, Any]:
        """
        Make a request to Freeway API with the specified model.

        Args:
            payload: The request payload (will be modified with the model)
            model: The model to use ("free" or "paid")

        Returns:
            The API response as a dict

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        request_payload = {**payload, "model": model}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.api_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self.api_key
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
        temperature: float = 0.9,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate AI response using Freeway API Gateway.

        If the primary model (usually "free") fails, automatically falls back
        to the "paid" model to ensure reliability.

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

            # Build messages array for OpenAI-compatible API
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            # Prepare base request payload (without model - will be added per request)
            payload = {
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            # Try primary model first, fallback to paid if it fails
            primary_model = self.model  # Usually "free"
            fallback_model = "paid" if primary_model == "free" else "free"
            used_model = primary_model

            try:
                logger.info(f"Attempting request with primary model: {primary_model}")
                result = await self._make_freeway_request(payload, primary_model)
            except httpx.HTTPStatusError as e:
                # Only fallback on server errors (5xx) or service unavailable
                if e.response.status_code >= 500 or e.response.status_code == 503:
                    logger.warning(
                        f"Primary model '{primary_model}' failed with {e.response.status_code}, "
                        f"falling back to '{fallback_model}'"
                    )
                    try:
                        result = await self._make_freeway_request(payload, fallback_model)
                        used_model = fallback_model
                        logger.info(f"Fallback to '{fallback_model}' succeeded")
                    except httpx.HTTPStatusError as fallback_error:
                        # Both models failed, raise the fallback error
                        logger.error(
                            f"Fallback model '{fallback_model}' also failed: "
                            f"{fallback_error.response.status_code} - {fallback_error.response.text}"
                        )
                        raise fallback_error
                else:
                    # Non-server errors (4xx) should not trigger fallback
                    raise

            # Extract response text from OpenAI format
            response_text = result["choices"][0]["message"]["content"]

            # Get token usage from response
            tokens_used = result.get("usage", {}).get("total_tokens", len(response_text) // 4)

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
                "model_used": used_model,  # Include which model was actually used
                "usage": {
                    "messages_today": usage.messages_today,
                    "limit": settings.FREE_TIER_MESSAGE_LIMIT if not user.is_premium else None
                }
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Freeway API error: {e.response.status_code} - {e.response.text}")
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

    async def _stream_from_freeway(
        self,
        payload: Dict[str, Any],
        model: str
    ) -> AsyncIterator[tuple[str, bool]]:
        """
        Stream response from Freeway API with the specified model.

        Args:
            payload: The request payload (will be modified with the model)
            model: The model to use ("free" or "paid")

        Yields:
            Tuple of (content_chunk, is_error)
            If is_error is True, content_chunk contains error info

        Raises:
            httpx.HTTPStatusError: If the request fails before streaming starts
        """
        request_payload = {**payload, "model": model, "stream": True}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.api_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self.api_key
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
                                    yield content, False
                        except json.JSONDecodeError:
                            continue

    async def generate_streaming_response(
        self,
        user_id: str,
        persona_id: str,
        user_message: str,
        conversation_history: List[ChatMessage],
        temperature: float = 0.9
    ) -> AsyncIterator[str]:
        """
        Generate streaming AI response using Freeway API.

        If the primary model fails, automatically falls back to the paid model.
        Yields response chunks as they arrive.
        """
        try:
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

            # Build messages array
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            # Prepare base request payload (without model and stream - will be added per request)
            payload = {
                "messages": messages,
                "temperature": temperature,
            }

            # Try primary model first, fallback to paid if it fails
            primary_model = self.model  # Usually "free"
            fallback_model = "paid" if primary_model == "free" else "free"
            used_model = primary_model

            # Stream response from Freeway API with fallback
            full_response = ""

            try:
                logger.info(f"Attempting streaming request with primary model: {primary_model}")
                async for content, _ in self._stream_from_freeway(payload, primary_model):
                    full_response += content
                    yield json.dumps({"chunk": content})
            except httpx.HTTPStatusError as e:
                # Only fallback on server errors (5xx)
                if e.response.status_code >= 500:
                    logger.warning(
                        f"Primary model '{primary_model}' failed with {e.response.status_code}, "
                        f"falling back to '{fallback_model}'"
                    )
                    # Reset full_response for fallback
                    full_response = ""
                    try:
                        async for content, _ in self._stream_from_freeway(payload, fallback_model):
                            full_response += content
                            yield json.dumps({"chunk": content})
                        used_model = fallback_model
                        logger.info(f"Fallback to '{fallback_model}' succeeded")
                    except httpx.HTTPStatusError as fallback_error:
                        logger.error(
                            f"Fallback model '{fallback_model}' also failed: "
                            f"{fallback_error.response.status_code}"
                        )
                        yield json.dumps({"error": f"Both models failed: {str(fallback_error)}"})
                        return
                else:
                    yield json.dumps({"error": str(e)})
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
