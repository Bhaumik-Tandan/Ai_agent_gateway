import time
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .policy import PolicyEngine, EvaluationContext
from .adapters.payments import PaymentsAdapter, CreateRequest as PaymentCreateRequest, RefundRequest
from .adapters.files import FilesAdapter, ReadRequest, WriteRequest
from .telemetry import Telemetry


logger = logging.getLogger(__name__)


class Gateway:
    def __init__(self, policy_engine: PolicyEngine, telemetry: Telemetry):
        self.policy_engine = policy_engine
        self.telemetry = telemetry
        self.payments = PaymentsAdapter()
        self.files = FilesAdapter()
    
    async def handle_tool_call(
        self,
        tool: str,
        action: str,
        params: Dict[str, Any],
        agent_id: str,
        parent_agent: Optional[str] = None
    ):
        start_time = time.time()
        
        ctx = EvaluationContext(
            agent_id=agent_id,
            tool=tool,
            action=action,
            params=params
        )
        
        decision = self.policy_engine.evaluate(ctx)
        policy_latency = (time.time() - start_time) * 1000
        
        if not decision.allow:
            self.telemetry.record_decision(
                agent_id=agent_id,
                tool=tool,
                action=action,
                params=params,
                decision_allow=False,
                decision_reason=decision.reason,
                policy_version=decision.version,
                latency_ms=policy_latency,
                parent_agent=parent_agent
            )
            
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "PolicyViolation",
                    "reason": decision.reason
                }
            )
        
        tool_start = time.time()
        try:
            response = await self._forward_to_tool(tool, action, params)
            tool_latency = (time.time() - tool_start) * 1000
        except Exception as e:
            tool_latency = (time.time() - tool_start) * 1000
            
            self.telemetry.record_decision(
                agent_id=agent_id,
                tool=tool,
                action=action,
                params=params,
                decision_allow=True,
                decision_reason=f"Policy allows, but tool error: {str(e)}",
                policy_version=decision.version,
                latency_ms=policy_latency,
                tool_latency_ms=tool_latency,
                parent_agent=parent_agent
            )
            
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "ToolError",
                    "reason": str(e)
                }
            )
        
        self.telemetry.record_decision(
            agent_id=agent_id,
            tool=tool,
            action=action,
            params=params,
            decision_allow=True,
            decision_reason=decision.reason,
            policy_version=decision.version,
            latency_ms=policy_latency,
            tool_latency_ms=tool_latency,
            parent_agent=parent_agent
        )
        
        return response
    
    async def _forward_to_tool(self, tool: str, action: str, params: Dict[str, Any]):
        if tool == "payments":
            if action == "create":
                req = PaymentCreateRequest(**params)
                return self.payments.create(req).dict()
            elif action == "refund":
                req = RefundRequest(**params)
                return self.payments.refund(req).dict()
            else:
                raise ValueError(f"unknown action: {action}")
        
        elif tool == "files":
            if action == "read":
                req = ReadRequest(**params)
                return self.files.read(req).dict()
            elif action == "write":
                req = WriteRequest(**params)
                return self.files.write(req).dict()
            else:
                raise ValueError(f"unknown action: {action}")
        
        else:
            raise ValueError(f"unknown tool: {tool}")


def create_app(policy_dir: str = "./policies", otel_endpoint: Optional[str] = None) -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    telemetry = Telemetry(otel_endpoint)
    policy_engine = PolicyEngine(policy_dir)
    gateway = Gateway(policy_engine, telemetry)
    
    app = FastAPI(title="Aegis Gateway", version="1.0.0")
    
    @app.post("/tools/{tool}/{action}")
    async def handle_request(
        tool: str,
        action: str,
        request: Request,
        x_agent_id: str = Header(..., alias="X-Agent-ID"),
        x_parent_agent: Optional[str] = Header(None, alias="X-Parent-Agent")
    ):
        try:
            params = await request.json()
        except Exception:
            params = {}
        
        return await gateway.handle_tool_call(
            tool=tool,
            action=action,
            params=params,
            agent_id=x_agent_id,
            parent_agent=x_parent_agent
        )
    
    @app.get("/health")
    async def health_check():
        stats = policy_engine.get_stats()
        return {
            "status": "healthy",
            "service": "aegis-gateway",
            "policy": stats
        }
    
    @app.on_event("shutdown")
    async def shutdown_event():
        policy_engine.close()
        telemetry.shutdown()
    
    return app

