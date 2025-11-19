"""Gemini AI Service for generating responses"""
import google.generativeai as genai
from app.config import settings
from app.models.persona import Persona, KnowledgeBase
from app.models.user import User, UsageTracking
from app.models.chat import ChatMessage
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, AsyncIterator
import logging
import json

logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)


class GeminiService:
    """Service for interacting with Google Gemini AI"""

    def __init__(self, db: Session):
        self.db = db
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

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
        Build conversation history from chat messages
        Limit to recent messages to avoid token limits
        """
        # Get recent messages (sorted by created_at)
        recent_messages = sorted(messages, key=lambda x: x.created_at)[-limit:]

        history = []
        for msg in recent_messages:
            role = "user" if msg.sender_type == "user" else "model"
            history.append({
                "role": role,
                "parts": [msg.text]
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
        Generate AI response using Gemini

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

            # Build conversation history
            history = self._build_conversation_history(conversation_history)

            # Prepare generation config
            generation_config = {
                "temperature": temperature,
                "top_p": 0.95,
                "top_k": 40,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens

            # Start chat with history
            chat = self.model.start_chat(history=history)

            # Generate response with system prompt prepended to first message
            if not history:
                # First message, include system prompt
                full_message = f"{system_prompt}\n\nUser: {user_message}"
            else:
                full_message = user_message

            response = chat.send_message(
                full_message,
                generation_config=genai.types.GenerationConfig(**generation_config)
            )

            # Extract response text
            response_text = response.text

            # Estimate tokens (rough approximation: 1 token ≈ 4 chars)
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
                "usage": {
                    "messages_today": usage.messages_today,
                    "limit": settings.FREE_TIER_MESSAGE_LIMIT if not user.is_premium else None
                }
            }

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

    async def generate_streaming_response(
        self,
        user_id: str,
        persona_id: str,
        user_message: str,
        conversation_history: List[ChatMessage],
        temperature: float = 0.9
    ) -> AsyncIterator[str]:
        """
        Generate streaming AI response using Gemini
        Yields response chunks as they arrive
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

            # Generation config
            generation_config = {
                "temperature": temperature,
                "top_p": 0.95,
                "top_k": 40,
            }

            # Start chat
            chat = self.model.start_chat(history=history)

            # Prepare message
            if not history:
                full_message = f"{system_prompt}\n\nUser: {user_message}"
            else:
                full_message = user_message

            # Stream response
            full_response = ""
            response_stream = chat.send_message(
                full_message,
                generation_config=genai.types.GenerationConfig(**generation_config),
                stream=True
            )

            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    yield json.dumps({"chunk": chunk.text})

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
                "sentiment": self._analyze_sentiment(full_response)
            })

        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            yield json.dumps({"error": str(e)})
