import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes


class AuditLogger:
    def __init__(self, log_file: str = "logs/aegis.log"):
        Path("logs").mkdir(exist_ok=True)
        
        self.logger = logging.getLogger("aegis.audit")
        self.logger.setLevel(logging.INFO)
        
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(ch)
    
    def log_decision(self, data: Dict[str, Any]):
        self.logger.info(json.dumps(data))


class Telemetry:
    def __init__(self, otel_endpoint: Optional[str] = None):
        self.audit_logger = AuditLogger()
        self.tracer_provider = self._setup_tracing(otel_endpoint)
        self.tracer = trace.get_tracer("aegis-gateway")
    
    def _setup_tracing(self, endpoint: Optional[str]) -> TracerProvider:
        resource = Resource(attributes={
            ResourceAttributes.SERVICE_NAME: "aegis-gateway"
        })
        
        provider = TracerProvider(resource=resource)
        
        if endpoint:
            try:
                exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
                processor = BatchSpanProcessor(exporter)
                provider.add_span_processor(processor)
                logging.info(f"OpenTelemetry exporter configured: {endpoint}")
            except Exception as e:
                logging.warning(f"Failed to setup OTLP exporter: {e}")
        
        trace.set_tracer_provider(provider)
        return provider
    
    def record_decision(
        self,
        agent_id: str,
        tool: str,
        action: str,
        params: Dict[str, Any],
        decision_allow: bool,
        decision_reason: str,
        policy_version: int,
        latency_ms: float,
        tool_latency_ms: float = 0,
        parent_agent: Optional[str] = None
    ):
        with self.tracer.start_as_current_span("policy.decision") as span:
            span.set_attribute("agent.id", agent_id)
            span.set_attribute("tool.name", tool)
            span.set_attribute("tool.action", action)
            span.set_attribute("decision.allow", decision_allow)
            span.set_attribute("policy.version", policy_version)
            span.set_attribute("params.hash", self._hash_params(params))
            span.set_attribute("latency.ms", latency_ms)
            
            if parent_agent:
                span.set_attribute("parent.agent", parent_agent)
            
            trace_id = format(span.get_span_context().trace_id, '032x')
            
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "trace.id": trace_id,
                "agent.id": agent_id,
                "tool.name": tool,
                "tool.action": action,
                "decision.allow": decision_allow,
                "reason": decision_reason,
                "policy.version": policy_version,
                "params.hash": self._hash_params(params),
                "latency.ms": round(latency_ms, 2)
            }
            
            if parent_agent:
                log_data["parent.agent"] = parent_agent
            
            if decision_allow and tool_latency_ms > 0:
                log_data["tool.latency.ms"] = round(tool_latency_ms, 2)
                
                with self.tracer.start_as_current_span("tool.call") as tool_span:
                    tool_span.set_attribute("tool.name", tool)
                    tool_span.set_attribute("tool.action", action)
                    tool_span.set_attribute("latency.ms", tool_latency_ms)
            
            self.audit_logger.log_decision(log_data)
    
    def _hash_params(self, params: Dict[str, Any]) -> str:
        try:
            data = json.dumps(params, sort_keys=True).encode()
            return hashlib.sha256(data).hexdigest()
        except Exception:
            return "error"
    
    def shutdown(self):
        if self.tracer_provider:
            self.tracer_provider.shutdown()

