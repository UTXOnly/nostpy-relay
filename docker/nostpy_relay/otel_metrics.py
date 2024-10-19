import os
from otel_metric_base.otel_metrics import OtelMetricBase

otel_metrics = OtelMetricBase(otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
