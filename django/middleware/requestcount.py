# extension of chain of responsibility
from django.utils.deprecation import MiddlewareMixin
from django.utils.timezone import now

class RequestCountMiddleware(MiddlewareMixin):
    def _init_(self, get_response):
        super()._init_(get_response)
        self.request_count = 0  # Initialize the counter for requests

    def process_request(self, request):
        # This method is called for each request before the view is called
        self.request_count += 1
        print(f"Request {self.request_count} processed at {now()}")
    
    def process_response(self, request, response):
        # This method is called for each response before it is sent back to the client
        response['X-Request-Count'] = self.request_count  # Add the request count to the response headers
        return response