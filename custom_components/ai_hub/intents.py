"""Enhanced intent processing for 智谱清言 - Based on official intent files analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from homeassistant.util.yaml import load_yaml
from homeassistant.core import HomeAssistant

# Import DOMAIN constant
try:
    from .const import DOMAIN
except ImportError:
    # Fallback for testing
    DOMAIN = "ai_hub"

_LOGGER = logging.getLogger(__name__)

# Simple cache for config
_CONFIG_CACHE: Optional[Dict[str, Any]] = None

def clear_intents_cache() -> None:
    """Clear intents cache."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


async def extract_intent_info(text: str, hass: HomeAssistant) -> Optional[Dict[str, Any]]:
    """Intent extraction using intents.yaml configuration only."""
    try:
        text_lower = text.lower().strip()
        _LOGGER.info(f"Intent extraction input: '{text}' -> '{text_lower}'")

        # Load configuration once
        config = await _load_config()
        if not config:
            _LOGGER.error("Failed to load intents configuration")
            return None

        # Check for cancel intent first - using config
        cancel_patterns = config.get('cancel_patterns')
        if cancel_patterns and any(word in text_lower for word in cancel_patterns):
            _LOGGER.info("Cancel intent matched")
            return {"intent": "nevermind", "text": text}

        # Match intents using YAML configuration
        result = await _match_intent_from_yaml(text, text_lower, config)
        _LOGGER.info(f"Intent matching result: {result}")
        return result

    except Exception as e:
        _LOGGER.error(f"Intent extraction failed: {e}")
        return None


async def _load_config() -> Optional[Dict[str, Any]]:
    """Fast config loading with simple cache."""
    global _CONFIG_CACHE

    if _CONFIG_CACHE:
        return _CONFIG_CACHE

    yaml_path = Path(__file__).parent / "intents.yaml"
    if not yaml_path.exists():
        return None

    # Direct synchronous loading for maximum speed
    try:
        _CONFIG_CACHE = load_yaml(str(yaml_path))
        return _CONFIG_CACHE
    except Exception:
        return None


async def _match_intent_from_yaml(text: str, text_lower: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Intent matching using YAML configuration only."""
    try:
        intents = config.get('intents', {})
        if not intents:
            _LOGGER.error("No intents found in configuration")
            return None

        _LOGGER.info(f"Available intents: {list(intents.keys())}")

        # Get expansion rules from config
        expansion_rules = config.get('expansion_rules', {})

        # Try each intent - first match wins
        for intent_name, intent_data in intents.items():
            data = intent_data.get('data')
            if not data:
                continue

            use_ha = intent_data.get('use_home_assistant', False)
            bypass_home_assistant = intent_data.get('bypass_home_assistant', False)

            _LOGGER.info(f"Checking intent: {intent_name}")

            # Check all patterns for this intent
            for item_idx, item in enumerate(data):
                for pattern_idx, pattern in enumerate(item.get('sentences', [])):
                    _LOGGER.debug(f"  Pattern {pattern_idx}: {pattern}")

                    if _pattern_match_from_config(text_lower, pattern, expansion_rules):
                        _LOGGER.info(f"✓ Pattern matched for {intent_name}: {pattern}")

                        result = {
                            "intent": intent_name,
                            "text": text,
                            "confidence": 0.9,
                            "use_home_assistant": use_ha,
                            "bypass_home_assistant": bypass_home_assistant
                        }

                        # Extract slots using config
                        slots = _extract_slots_from_config(text, pattern, config)
                        result.update(slots)

                        return result

        _LOGGER.info("No intents matched")
        return None

    except Exception as e:
        _LOGGER.error(f"Intent matching failed: {e}")
        return None

def _pattern_match_from_config(text_lower: str, pattern: str, expansion_rules: Dict[str, str]) -> bool:
    """Pattern matching using configuration only."""
    # Remove [<let>] and check for polite words
    if '[<let>]' in pattern:
        let_rule = expansion_rules.get('let', '')
        if let_rule:
            let_words = [word.strip() for word in let_rule.split('|') if word.strip()]
            if not any(let_word in text_lower for let_word in let_words):
                return False

    # Clean pattern and extract keywords
    clean_pattern = pattern.replace('[<let>]', '')

    # Remove bracketed content
    while '[' in clean_pattern and ']' in clean_pattern:
        start = clean_pattern.find('[')
        end = clean_pattern.find(']', start)
        if start != -1 and end != -1:
            clean_pattern = clean_pattern[:start] + clean_pattern[end+1:]
        else:
            break

    # Extract keywords using expansion rules
    words = clean_pattern.replace('[', ' ').replace(']', ' ').split()
    keywords = []
    for word in words:
        word = word.strip()
        if word and word not in expansion_rules.keys() and not word.startswith('{'):
            keywords.append(word.lower())

    # Check if all keywords are present
    return all(keyword in text_lower for keyword in keywords)

def _extract_slots_from_config(text: str, pattern: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Slot extraction using configuration only."""
    slots = {}
    text_lower = text.lower()

    # Find slot names in pattern
    slot_patterns = []
    start = 0
    while True:
        start = pattern.find('{', start)
        if start == -1:
            break
        end = pattern.find('}', start)
        if end == -1:
            break
        slot_patterns.append(pattern[start+1:end])
        start = end + 1

    for slot_name in slot_patterns:
        if slot_name == 'name':
            # Use device mappings from config
            device_mappings = config.get('device_mappings', {})
            name_to_domain = device_mappings.get('name_to_domain', {})
            for device_name, domain in name_to_domain.items():
                if device_name in text_lower:
                    slots['name'] = device_name
                    slots['domain'] = domain
                    break

        elif slot_name == 'area':
            # Use common areas from config
            areas = config.get('common_areas', [])
            for area in areas:
                if area in text:
                    slots['area'] = area
                    break

        elif slot_name == 'floor':
            # Simple floor extraction
            words = text.split()
            for word in words:
                if ('层' in word or '楼' in word) and word.replace('层', '').replace('楼', '').isdigit():
                    slots['floor'] = word.replace('层', '').replace('楼', '')
                    break

        elif slot_name in ['temperature', 'brightness_level', 'volume_level', 'position']:
            # Simple number extraction
            words = text.split()
            for word in words:
                if word.isdigit():
                    slots[slot_name] = word
                    break

    return slots


# Configuration-driven pattern matching functions
def _match_pattern(text: str, pattern: str, config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Pattern matching using configuration."""
    if not config:
        return None

    if _pattern_match_from_config(text.lower(), pattern, config.get('expansion_rules', {})):
        return {"match": pattern, "confidence": 0.9}
    return None

def _extract_slots(text: str, pattern: str, match_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Slot extraction using configuration."""
    return _extract_slots_from_config(text, pattern, config)


def get_device_response(intent_type: str, action: str, config: Dict[str, Any], **kwargs) -> str:
    """Get device-specific response from configuration."""
    try:
        if not config:
            _LOGGER.error("No config provided for device response")
            return "操作已完成"

        device_responses = config.get('device_responses', {})
        success_responses = device_responses.get('success_device_control', {})

        # Format the response key
        response_key = f"{action}_{intent_type}"

        # Get response template
        template = success_responses.get(response_key)
        if not template:
            # Fallback to generic success message from config
            responses = config.get('responses', {})
            default_success = responses.get('default', {}).get('success_message')
            if not default_success:
                _LOGGER.error("No default success message found in configuration")
                return "操作已完成"
            return default_success

        # Format the template with provided variables
        try:
            return template.format(**kwargs)
        except KeyError as e:
            _LOGGER.debug("Missing template variable: %s", e)
            return template

    except Exception as e:
        _LOGGER.debug("Failed to get device response: %s", e)
        # Return error response from config if available
        if config:
            error_responses = config.get('responses', {}).get('error', {})
            return error_responses.get('default_error', "操作失败")
        return "操作失败"


class SimpleIntentHandler:
    """Enhanced intent handler for YAML-driven configuration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the intent handler."""
        self.hass = hass

    async def handle_intent(self, intent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Handle recognized intent using enhanced configuration."""
        try:
            intent_type = intent_info.get("intent")
            use_ha = intent_info.get("use_home_assistant", False)

            _LOGGER.info(f"Handling intent: {intent_type}, use_home_assistant: {use_ha}")
            _LOGGER.debug(f"Full intent info: {intent_info}")

            # Load responses from config
            config = await _load_config()
            responses = config.get('responses', {}) if config else {}

            if intent_type == "nevermind":
                # Use configurable response only
                if not responses:
                    _LOGGER.error("No responses configuration found")
                    return {"success": False, "error": "Configuration missing"}

                cancel_message = responses.get('cancel', {}).get('message')
                if not cancel_message:
                    _LOGGER.error("No cancel message found in configuration")
                    return {"success": False, "error": "Cancel message configuration missing"}

                _LOGGER.debug(f"Returning cancel message: {cancel_message}")
                return {"success": True, "message": cancel_message}

            # Check if intent should use Home Assistant (based on YAML config)
            if use_ha:
                _LOGGER.info(f"Routing intent '{intent_type}' to Home Assistant")
                result = await self._handle_via_home_assistant(intent_info)
                _LOGGER.info(f"Home Assistant result: {result}")
                return result

            # Default: delegate to Home Assistant anyway for consistency
            _LOGGER.info(f"Default routing intent '{intent_type}' to Home Assistant")
            result = await self._handle_via_home_assistant(intent_info)
            _LOGGER.info(f"Home Assistant result: {result}")
            return result

        except Exception as e:
            _LOGGER.error("Intent handling failed: %s", e)
            return {"success": False, "error": str(e)}

    async def _handle_via_home_assistant(self, intent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Route intent through Home Assistant system."""
        try:
            from homeassistant.helpers import intent as ha_intent

            intent_type = intent_info.get("intent")
            text = intent_info.get("text", "")

            _LOGGER.debug(f"Creating HA intent: {intent_type} with text: '{text}'")

            # Build HA slots
            ha_slots = {}
            for key, value in intent_info.items():
                if key not in ["intent", "text", "confidence",
                             "use_home_assistant", "bypass_home_assistant"] and value:
                    ha_slots[key] = {"value": str(value)}

            _LOGGER.debug(f"HA slots: {ha_slots}")

            # Create and handle intent - use 'ai_hub' as platform since we are handling the intent
            ha_intent_obj = ha_intent.Intent(intent_type, slots=ha_slots)
            result = await ha_intent.async_handle(self.hass, DOMAIN, ha_intent_obj, text, "")

            _LOGGER.debug(f"HA intent result type: {type(result)}")
            if result:
                _LOGGER.debug(f"HA intent result: {result}")

            # Extract response
            if result and hasattr(result, 'response') and result.response:
                speech = result.response.speech.get("plain", {}).get("speech", "")
                if speech:
                    _LOGGER.info(f"HA returned speech: {speech}")
                    return {"success": True, "message": speech}
                else:
                    _LOGGER.debug("HA returned result but no speech")
            else:
                _LOGGER.debug("HA returned no result")

            # Load responses from config for default message
            config = await _load_config()
            responses = config.get('responses', {}) if config else {}
            default_success = responses.get('default', {}).get('success_message')

            if not default_success:
                _LOGGER.error("No default success message found in configuration")
                return {"success": False, "error": "Default success message configuration missing"}

            _LOGGER.info(f"Returning default success message: {default_success}")
            return {"success": True, "message": default_success}

        except Exception as e:
            _LOGGER.error("HA intent handling failed: %s", e)
            import traceback
            _LOGGER.debug(f"HA intent handling traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}


def get_intent_handler(hass: HomeAssistant) -> SimpleIntentHandler:
    """Get intent handler instance."""
    return SimpleIntentHandler(hass)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up enhanced intent processing."""
    # Preload configuration to ensure cache is populated
    await _load_config()
    _LOGGER.info("Enhanced intent processing setup complete - Based on official intent files analysis")


# Preload configuration at module load
try:
    import asyncio
    asyncio.run(_load_config())
except:
    # Fallback to sync loading if async is not available
    try:
        yaml_path = Path(__file__).parent / "intents.yaml"
        if yaml_path.exists():
            config = load_yaml(str(yaml_path))
            _INTENTS_CONFIG_CACHE = config or {}
    except:
        pass