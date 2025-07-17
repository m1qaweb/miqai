"""
OpenTelemetry tracing configuration for the AI Video Analysis System.
"""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def configure_tracing(service_name: str = "video-ai-system") -> None:
    """
    Configures OpenTelemetry tracing to send spans to an OTLP collector.
    This should be called once on application startup.
    
    Args:
        service_name: Name of the service for tracing identification
    """
    # Create a resource to identify our service
    resource = Resource(
        attributes={
            "service.name": service_name,
        }
    )

    # Set up a TracerProvider
    trace.set_tracer_provider(TracerProvider(resource=resource))

    # Configure the OTLP exporter to send spans to Tempo
    # The default endpoint for gRPC is localhost:4317, which matches our docker-compose setup.
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4317",
        insecure=True,  # Use insecure connection for local development
    )

    # Use a BatchSpanProcessor to send spans in the background
    span_processor = BatchSpanProcessor(otlp_exporter)

    # Get the global tracer provider and add the span processor
    tracer_provider = trace.get_tracer_provider()
    tracer_provider.add_span_processor(span_processor)

    print(f"OpenTelemetry tracing configured for service: '{service_name}'")
