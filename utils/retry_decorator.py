import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Type, Tuple, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RetryError(Exception):
    """Custom exception for retry failures"""
    pass

def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    backoff_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retry_on_status_codes: Optional[Tuple[int, ...]] = None,
    no_retry_on_status_codes: Optional[Tuple[int, ...]] = None
):
    """
    Decorator that implements exponential backoff retry logic for API calls.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        backoff_exceptions: Tuple of exceptions that should trigger retries
        retry_on_status_codes: HTTP status codes that should trigger retries
        no_retry_on_status_codes: HTTP status codes that should NOT trigger retries
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    result = func(*args, **kwargs)
                    
                    # Check for HTTP response status codes if applicable
                    if hasattr(result, 'status_code'):
                        status_code = result.status_code
                        
                        # If we have specific status codes to not retry on
                        if no_retry_on_status_codes and status_code in no_retry_on_status_codes:
                            return result
                        
                        # If we have specific status codes to retry on
                        if retry_on_status_codes and status_code not in retry_on_status_codes:
                            return result
                        
                        # Default behavior: retry on 5xx errors and some 4xx errors
                        if status_code >= 500 or status_code in [408, 429]:
                            if attempt < max_retries:
                                delay = _calculate_delay(attempt, base_delay, max_delay, exponential_base, jitter)
                                logger.warning(
                                    f"HTTP {status_code} error in {func.__name__} "
                                    f"(attempt {attempt + 1}/{max_retries + 1}). "
                                    f"Retrying in {delay:.2f} seconds..."
                                )
                                time.sleep(delay)
                                continue
                            else:
                                logger.error(
                                    f"Max retries exceeded for {func.__name__} "
                                    f"with HTTP {status_code} error"
                                )
                                return result
                    
                    # If we get here, the function succeeded
                    if attempt > 0:
                        logger.info(
                            f"Function {func.__name__} succeeded after {attempt + 1} attempts"
                        )
                    return result
                    
                except backoff_exceptions as e:
                    last_exception = e
                    
                    # Don't retry on the last attempt
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries exceeded for {func.__name__}. "
                            f"Last exception: {str(e)}"
                        )
                        break
                    
                    # Calculate delay for next attempt
                    delay = _calculate_delay(attempt, base_delay, max_delay, exponential_base, jitter)
                    
                    logger.warning(
                        f"Exception in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{type(e).__name__}: {str(e)}. Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
            
            # If we get here, all retries failed
            raise RetryError(
                f"Function {func.__name__} failed after {max_retries + 1} attempts. "
                f"Last exception: {str(last_exception)}"
            ) from last_exception
        
        return wrapper
    return decorator

def _calculate_delay(
    attempt: int, 
    base_delay: float, 
    max_delay: float, 
    exponential_base: float, 
    jitter: bool
) -> float:
    """Calculate the delay for the next retry attempt"""
    delay = base_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)
    
    if jitter:
        # Add random jitter (±25% of the delay)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
        delay = max(0, delay)  # Ensure delay is not negative
    
    return delay

# Specific decorators for common use cases

def twitch_api_retry(
    max_retries: int = 3,
    base_delay: float = 1.0
):
    """
    Retry decorator specifically configured for Twitch API calls.
    Handles rate limiting (429) and server errors (5xx).
    """
    return retry_with_exponential_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        backoff_exceptions=(Exception,),
        retry_on_status_codes=(429, 500, 502, 503, 504),
        no_retry_on_status_codes=(400, 401, 403, 404)
    )

def database_retry(
    max_retries: int = 2,
    base_delay: float = 0.5
):
    """
    Retry decorator specifically configured for database operations.
    Uses shorter delays and fewer retries.
    """
    return retry_with_exponential_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=5.0,
        exponential_base=2.0,
        jitter=True,
        backoff_exceptions=(Exception,)
    )

def general_api_retry(
    max_retries: int = 3,
    base_delay: float = 2.0
):
    """
    General purpose retry decorator for external API calls.
    """
    return retry_with_exponential_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
        backoff_exceptions=(Exception,),
        retry_on_status_codes=(408, 429, 500, 502, 503, 504),
        no_retry_on_status_codes=(400, 401, 403, 404)
    )

# Circuit breaker pattern (advanced retry logic)
class CircuitBreaker:
    """
    Circuit breaker pattern implementation for preventing cascading failures.
    Can be used alongside retry decorators.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = 'HALF_OPEN'
                    logger.info(f"Circuit breaker for {func.__name__} moved to HALF_OPEN state")
                else:
                    raise RetryError(
                        f"Circuit breaker for {func.__name__} is OPEN. "
                        f"Will retry after {self.timeout} seconds."
                    )
            
            try:
                result = func(*args, **kwargs)
                
                # Success - reset circuit breaker
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                    self.failure_count = 0
                    logger.info(f"Circuit breaker for {func.__name__} moved to CLOSED state")
                
                return result
                
            except self.expected_exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                    logger.warning(
                        f"Circuit breaker for {func.__name__} moved to OPEN state "
                        f"after {self.failure_count} failures"
                    )
                
                raise e
        
        return wrapper

# Example usage decorators for the Apex Legends app
def apex_leaderboard_retry():
    """Retry decorator for Apex Legends leaderboard scraping"""
    return retry_with_exponential_backoff(
        max_retries=2,
        base_delay=3.0,
        max_delay=15.0,
        exponential_base=2.0,
        jitter=True,
        backoff_exceptions=(Exception,)
    )

def tracker_gg_retry():
    """Retry decorator for Tracker.gg API calls"""
    return retry_with_exponential_backoff(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        backoff_exceptions=(Exception,),
        retry_on_status_codes=(429, 500, 502, 503, 504),
        no_retry_on_status_codes=(400, 401, 403, 404)
    )