from django.utils.deprecation import MiddlewareMixin
import logging
from django.utils.timezone import now

# Set up logger
logger = logging.getLogger(_name_)

class RequestResponseLoggerMiddleware(MiddlewareMixin):
    """
    A middleware that logs request and response data.
    It logs the request method, path, and response status code, along with the current time.
    """
    def process_request(self, request):
        """
        Process the request and log the request details.
        """
        logger.info(f"Request Time: {now()} | Method: {request.method} | Path: {request.path}")

    def process_response(self, request, response):
        """
        Process the response and log the response details.
        """
        logger.info(f"Response Time: {now()} | Status Code: {response.status_code}")
        return response