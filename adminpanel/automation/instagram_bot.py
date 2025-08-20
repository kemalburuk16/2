# adminpanel/automation/instagram_bot.py
"""
Main Instagram automation bot class
Handles browser automation, login, and activities
"""
import json
import logging
import random
import time
from typing import Dict, List, Optional, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from .config import (CHROME_OPTIONS, SESSION_TIMEOUT, USER_AGENTS, VIEWPORT_SIZES)
from .human_behavior import HumanBehaviorSimulator
from .session_manager import AutomationSessionManager

logger = logging.getLogger(__name__)

class InstagramBot:
    """Main Instagram automation bot"""
    
    def __init__(self, session_manager: AutomationSessionManager):
        self.session_manager = session_manager
        self.driver = None
        self.current_session = None
        self.behavior_simulator = HumanBehaviorSimulator()
        self.is_logged_in = False
        
    def setup_driver(self) -> bool:
        """Setup Chrome webdriver with proper configuration"""
        try:
            chrome_options = Options()
            
            # Add all configuration options
            for option in CHROME_OPTIONS:
                chrome_options.add_argument(option)
            
            # Random user agent
            user_agent = random.choice(USER_AGENTS)
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Random viewport size
            width, height = random.choice(VIEWPORT_SIZES)
            chrome_options.add_argument(f"--window-size={width},{height}")
            
            # Disable logging
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Anti-detection measures
            chrome_options.add_experimental_option("detach", True)
            
            # Setup service
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(SESSION_TIMEOUT)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome driver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            return False
    
    def load_session_cookies(self, session: Dict[str, Any]) -> bool:
        """Load Instagram session cookies"""
        try:
            # First navigate to Instagram
            self.driver.get("https://www.instagram.com/")
            self.behavior_simulator.human_delay(2, 4)
            
            # Prepare cookies
            cookies_to_add = []
            
            # Essential cookies
            essential_cookies = ['sessionid', 'ds_user_id', 'csrftoken']
            for cookie_name in essential_cookies:
                if cookie_name in session:
                    cookies_to_add.append({
                        'name': cookie_name,
                        'value': session[cookie_name],
                        'domain': '.instagram.com'
                    })
            
            # Additional cookies if available
            if 'cookies' in session and isinstance(session['cookies'], dict):
                for name, value in session['cookies'].items():
                    if name not in essential_cookies and value:
                        cookies_to_add.append({
                            'name': name,
                            'value': str(value),
                            'domain': '.instagram.com'
                        })
            
            # Add cookies to browser
            for cookie in cookies_to_add:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"Could not add cookie {cookie['name']}: {e}")
            
            # Refresh page to apply cookies
            self.driver.refresh()
            self.behavior_simulator.human_delay(3, 5)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load session cookies: {e}")
            return False
    
    def verify_login(self) -> bool:
        """Verify if we're successfully logged in"""
        try:
            # Check for indicators that we're logged in
            login_indicators = [
                "//a[@href='/accounts/activity/']",  # Activity link
                "//a[contains(@href, '/direct/')]",   # Messages link
                "//svg[@aria-label='New post']",      # New post button
                "//a[contains(@href, 'explore')]"     # Explore link
            ]
            
            for indicator in login_indicators:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    logger.info("Login verification successful")
                    self.is_logged_in = True
                    return True
                except TimeoutException:
                    continue
            
            # Check if we're on login page (indicating failure)
            login_elements = [
                "//input[@name='username']",
                "//button[text()='Log In']"
            ]
            
            for element in login_elements:
                try:
                    self.driver.find_element(By.XPATH, element)
                    logger.warning("Still on login page - session invalid")
                    return False
                except NoSuchElementException:
                    continue
            
            logger.warning("Could not verify login status")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying login: {e}")
            return False
    
    def navigate_to_home(self) -> bool:
        """Navigate to Instagram home feed"""
        try:
            self.driver.get("https://www.instagram.com/")
            self.behavior_simulator.human_delay(2, 4)
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to home: {e}")
            return False
    
    def like_random_posts(self, count: int = 3) -> int:
        """Like random posts from feed"""
        liked_count = 0
        try:
            for i in range(count):
                if not self.session_manager.can_perform_activity(
                    self.current_session.get('sessionid'), 'likes'
                ):
                    logger.info("Daily like limit reached")
                    break
                
                # Find like buttons
                like_buttons = self.driver.find_elements(
                    By.XPATH, 
                    "//span[contains(@class, 'fr66n')]/button[contains(@class, 'wpO6b')]"
                )
                
                if not like_buttons:
                    logger.warning("No like buttons found")
                    break
                
                # Select random post to like
                button = random.choice(like_buttons)
                
                # Check if already liked (red heart)
                try:
                    svg = button.find_element(By.TAG_NAME, "svg")
                    fill = svg.get_attribute("fill")
                    if fill and "#ed4956" in fill.lower():
                        continue  # Already liked
                except:
                    pass
                
                # Scroll to button
                self.driver.execute_script("arguments[0].scrollIntoView();", button)
                self.behavior_simulator.human_delay(1, 2)
                
                # Click like button
                button.click()
                liked_count += 1
                
                # Update session activity
                self.session_manager.update_session_activity(
                    self.current_session.get('sessionid'), 'likes'
                )
                
                logger.info(f"Liked post {i+1}")
                self.behavior_simulator.human_delay(3, 8)
                
                # Random scroll behavior
                if random.random() < 0.7:
                    self.behavior_simulator.random_scroll_behavior(self.driver)
                
        except Exception as e:
            logger.error(f"Error liking posts: {e}")
        
        return liked_count
    
    def view_random_stories(self, count: int = 5) -> int:
        """View random stories"""
        viewed_count = 0
        try:
            # Look for story rings
            story_elements = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'Fd52H')]//button"
            )
            
            if not story_elements:
                logger.warning("No stories found")
                return 0
            
            for i in range(min(count, len(story_elements))):
                if not self.session_manager.can_perform_activity(
                    self.current_session.get('sessionid'), 'stories'
                ):
                    logger.info("Daily story view limit reached")
                    break
                
                try:
                    # Click on story
                    story = random.choice(story_elements)
                    story.click()
                    viewed_count += 1
                    
                    # Watch story for realistic time
                    view_time = self.behavior_simulator.get_reading_time("story")
                    time.sleep(view_time)
                    
                    # Close story (press escape or click close)
                    self.driver.find_element(By.TAG_NAME, "body").send_keys("\033")  # ESC key
                    
                    # Update activity
                    self.session_manager.update_session_activity(
                        self.current_session.get('sessionid'), 'stories'
                    )
                    
                    logger.info(f"Viewed story {i+1}")
                    self.behavior_simulator.human_delay(2, 4)
                    
                except Exception as e:
                    logger.warning(f"Error viewing story {i+1}: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Error viewing stories: {e}")
        
        return viewed_count
    
    def browse_explore_page(self, duration: int = 30) -> bool:
        """Browse explore page for specified duration"""
        try:
            # Navigate to explore
            self.driver.get("https://www.instagram.com/explore/")
            self.behavior_simulator.human_delay(2, 4)
            
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Random scrolling
                self.behavior_simulator.random_scroll_behavior(self.driver)
                
                # Occasionally click on posts
                if random.random() < 0.3:
                    try:
                        posts = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
                        if posts:
                            post = random.choice(posts)
                            post.click()
                            
                            # View post for realistic time
                            view_time = self.behavior_simulator.get_reading_time("post")
                            time.sleep(view_time)
                            
                            # Close post
                            self.driver.find_element(By.TAG_NAME, "body").send_keys("\033")
                            self.behavior_simulator.human_delay(1, 3)
                            
                    except Exception as e:
                        logger.warning(f"Error viewing explore post: {e}")
                
                self.behavior_simulator.human_delay(3, 7)
            
            logger.info(f"Browsed explore page for {duration} seconds")
            return True
            
        except Exception as e:
            logger.error(f"Error browsing explore: {e}")
            return False
    
    def perform_session_activity(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Perform automated activity for a session"""
        self.current_session = session
        results = {
            "session_user": session.get("user", "unknown"),
            "success": False,
            "activities": {},
            "error": None
        }
        
        try:
            # Setup driver
            if not self.setup_driver():
                results["error"] = "Failed to setup driver"
                return results
            
            # Load session
            if not self.load_session_cookies(session):
                results["error"] = "Failed to load session cookies"
                return results
            
            # Verify login
            if not self.verify_login():
                results["error"] = "Session invalid - not logged in"
                self.session_manager.mark_session_failed(session.get('sessionid'))
                return results
            
            # Navigate to home
            if not self.navigate_to_home():
                results["error"] = "Failed to navigate to home"
                return results
            
            # Perform activities
            behavior_pattern = self.behavior_simulator.vary_behavior_pattern()
            logger.info(f"Using behavior pattern: {behavior_pattern['name']}")
            
            # Like posts
            if random.random() < behavior_pattern.get('like_probability', 0.3):
                liked = self.like_random_posts(random.randint(1, 3))
                results["activities"]["likes"] = liked
            
            # View stories
            if random.random() < behavior_pattern.get('story_probability', 0.5):
                viewed = self.view_random_stories(random.randint(2, 5))
                results["activities"]["stories_viewed"] = viewed
            
            # Browse explore
            if random.random() < 0.4:
                browse_duration = random.randint(20, 60)
                browsed = self.browse_explore_page(browse_duration)
                results["activities"]["explore_browsed"] = browsed
            
            # Mark session as successful
            self.session_manager.mark_session_success(session.get('sessionid'))
            results["success"] = True
            
            logger.info(f"Completed activity for session {session.get('user')}")
            
        except Exception as e:
            logger.error(f"Error during session activity: {e}")
            results["error"] = str(e)
            self.session_manager.mark_session_failed(session.get('sessionid'))
        
        finally:
            # Clean up
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
        return results
    
    def cleanup(self) -> None:
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None