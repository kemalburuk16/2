# adminpanel/automation/human_behavior.py
"""
Human behavior simulation for Instagram automation
Provides realistic delays, actions, and patterns
"""
import random
import time
import logging
from typing import List, Dict, Any
from .config import (MIN_ACTION_DELAY, MAX_ACTION_DELAY, COMMENT_TEMPLATES,
                    EXPLORE_HASHTAGS, ACTIVITY_WEIGHTS)

logger = logging.getLogger(__name__)

class HumanBehaviorSimulator:
    """Simulates human-like behavior patterns"""
    
    def __init__(self):
        self.last_action_time = 0
        self.action_history = []
        self.session_start_time = time.time()
    
    def human_delay(self, min_delay: float = None, max_delay: float = None) -> None:
        """Add realistic delay between actions"""
        min_delay = min_delay or MIN_ACTION_DELAY
        max_delay = max_delay or MAX_ACTION_DELAY
        
        # Add some randomness to make it more human-like
        base_delay = random.uniform(min_delay, max_delay)
        
        # Add occasional longer pauses (like reading content)
        if random.random() < 0.1:  # 10% chance
            base_delay += random.uniform(5, 15)
        
        # Add micro-pauses (like hesitation)
        if random.random() < 0.3:  # 30% chance
            base_delay += random.uniform(0.5, 2)
        
        logger.debug(f"Human delay: {base_delay:.2f} seconds")
        time.sleep(base_delay)
        self.last_action_time = time.time()
    
    def random_scroll_behavior(self, driver) -> None:
        """Simulate human-like scrolling behavior"""
        try:
            # Random scroll patterns
            scroll_patterns = [
                # Slow scroll down
                lambda: driver.execute_script("window.scrollBy(0, 300);"),
                # Quick scroll down
                lambda: driver.execute_script("window.scrollBy(0, 600);"),
                # Scroll up slightly (like going back to check something)
                lambda: driver.execute_script("window.scrollBy(0, -150);"),
                # Stay at current position (like reading)
                lambda: None
            ]
            
            pattern = random.choice(scroll_patterns)
            if pattern:
                pattern()
                self.human_delay(1, 3)
                
        except Exception as e:
            logger.warning(f"Error during scroll behavior: {e}")
    
    def random_mouse_movement(self, driver) -> None:
        """Simulate random mouse movements"""
        try:
            # This would require more advanced mouse simulation
            # For now, we'll just add some random clicks on safe areas
            pass
        except Exception as e:
            logger.warning(f"Error during mouse movement: {e}")
    
    def get_random_comment(self) -> str:
        """Get a random comment from templates"""
        return random.choice(COMMENT_TEMPLATES)
    
    def should_perform_action(self, action_type: str) -> bool:
        """Decide if an action should be performed based on probability"""
        return random.random() < ACTIVITY_WEIGHTS.get(action_type, 0.1)
    
    def get_reading_time(self, content_type: str = "post") -> float:
        """Get realistic reading/viewing time for content"""
        times = {
            "post": (2, 8),
            "story": (1, 4),
            "profile": (3, 10),
            "comment": (1, 3)
        }
        
        min_time, max_time = times.get(content_type, (2, 5))
        return random.uniform(min_time, max_time)
    
    def simulate_human_typing(self, element, text: str) -> None:
        """Simulate human-like typing with realistic delays"""
        try:
            element.clear()
            for char in text:
                element.send_keys(char)
                # Random typing speed
                time.sleep(random.uniform(0.05, 0.2))
                
                # Occasional typos and corrections (simplified)
                if random.random() < 0.02:  # 2% chance of typo
                    # Type wrong character then backspace
                    wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                    element.send_keys(wrong_char)
                    time.sleep(random.uniform(0.1, 0.3))
                    element.send_keys("\b")  # Backspace
                    time.sleep(random.uniform(0.1, 0.2))
                    
        except Exception as e:
            logger.warning(f"Error during human typing simulation: {e}")
            # Fallback to normal typing
            element.clear()
            element.send_keys(text)
    
    def get_explore_hashtag(self) -> str:
        """Get a random hashtag for exploration"""
        return random.choice(EXPLORE_HASHTAGS)
    
    def should_take_break(self) -> bool:
        """Decide if it's time for a longer break"""
        session_duration = time.time() - self.session_start_time
        # Take break every 20-40 minutes
        return session_duration > random.uniform(1200, 2400)
    
    def take_break(self, short: bool = True) -> None:
        """Take a break between activities"""
        if short:
            # Short break (like checking phone notifications)
            break_time = random.uniform(10, 30)
        else:
            # Longer break (like getting coffee)
            break_time = random.uniform(60, 180)
        
        logger.info(f"Taking {'short' if short else 'long'} break: {break_time:.1f} seconds")
        time.sleep(break_time)
    
    def vary_behavior_pattern(self) -> Dict[str, Any]:
        """Generate varied behavior pattern for session"""
        patterns = [
            {
                "name": "active_scroller",
                "scroll_frequency": 0.8,
                "like_probability": 0.4,
                "comment_probability": 0.05,
                "story_probability": 0.6
            },
            {
                "name": "casual_browser",
                "scroll_frequency": 0.5,
                "like_probability": 0.2,
                "comment_probability": 0.02,
                "story_probability": 0.3
            },
            {
                "name": "engaged_user",
                "scroll_frequency": 0.6,
                "like_probability": 0.6,
                "comment_probability": 0.1,
                "story_probability": 0.8
            }
        ]
        
        return random.choice(patterns)
    
    def log_action(self, action_type: str, details: str = "") -> None:
        """Log performed action for pattern analysis"""
        self.action_history.append({
            "action": action_type,
            "timestamp": time.time(),
            "details": details
        })
        
        # Keep only last 100 actions
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]