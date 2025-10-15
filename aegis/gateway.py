import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from collections import deque
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .policy import PolicyEngine, EvaluationContext
from .adapters.payments import PaymentsAdapter, CreateRequest as PaymentCreateRequest, RefundRequest
from .adapters.files import FilesAdapter, ReadRequest, WriteRequest
from .telemetry import Telemetry


logger = logging.getLogger(__name__)


class DecisionHistory:
    def __init__(self, max_size: int = 50):
        self.decisions = deque(maxlen=max_size)
        self.lock = None
    
    def add(self, decision: Dict[str, Any]):
        self.decisions.append(decision)
    
    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self.decisions)[-limit:]


class ApprovalGate:
    def __init__(self):
        self.pending: Dict[str, Dict[str, Any]] = {}
    
    def create_approval_request(self, decision_context: Dict[str, Any]) -> str:
        request_id = str(uuid.uuid4())
        self.pending[request_id] = {
            "id": request_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "pending",
            **decision_context
        }
        return request_id
    
    def approve(self, request_id: str) -> Optional[Dict[str, Any]]:
        if request_id in self.pending:
            request = self.pending.pop(request_id)
            request["status"] = "approved"
            request["approved_at"] = datetime.utcnow().isoformat() + "Z"
            return request
        return None
    
    def get_pending(self) -> List[Dict[str, Any]]:
        return list(self.pending.values())


class Gateway:
    def __init__(self, policy_engine: PolicyEngine, telemetry: Telemetry):
        self.policy_engine = policy_engine
        self.telemetry = telemetry
        self.payments = PaymentsAdapter()
        self.files = FilesAdapter()
        self.history = DecisionHistory()
        self.approval_gate = ApprovalGate()
    
    async def handle_tool_call(
        self,
        tool: str,
        action: str,
        params: Dict[str, Any],
        agent_id: str,
        parent_agent: Optional[str] = None,
        approval_id: Optional[str] = None
    ):
        start_time = time.time()
        
        if approval_id:
            approved_request = self.approval_gate.approve(approval_id)
            if not approved_request:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "ApprovalNotFound",
                        "reason": f"Approval request '{approval_id}' not found or already processed"
                    }
                )
            logger.info(f"Executing approved request: {approval_id}")
        
        ctx = EvaluationContext(
            agent_id=agent_id,
            tool=tool,
            action=action,
            params=params,
            parent_agent=parent_agent
        )
        
        decision = self.policy_engine.evaluate(ctx)
        policy_latency = (time.time() - start_time) * 1000
        
        if decision.require_approval and not approval_id:
            request_id = self.approval_gate.create_approval_request(
                decision.approval_context or {}
            )
            
            self.telemetry.record_decision(
                agent_id=agent_id,
                tool=tool,
                action=action,
                params=params,
                decision_allow=False,
                decision_reason=f"Requires approval: {decision.reason}",
                policy_version=decision.version,
                latency_ms=policy_latency,
                parent_agent=parent_agent
            )
            
            self.history.add({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": agent_id,
                "tool": tool,
                "action": action,
                "decision": "approval_required",
                "reason": decision.reason,
                "approval_id": request_id,
                "parent_agent": parent_agent
            })
            
            raise HTTPException(
                status_code=202,
                detail={
                    "error": "ApprovalRequired",
                    "reason": decision.reason,
                    "approval_id": request_id,
                    "message": f"Call POST /approve/{request_id} to approve this action"
                }
            )
        
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
            
            self.history.add({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": agent_id,
                "tool": tool,
                "action": action,
                "decision": "denied",
                "reason": decision.reason,
                "parent_agent": parent_agent
            })
            
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
            
            self.history.add({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": agent_id,
                "tool": tool,
                "action": action,
                "decision": "allowed_but_tool_error",
                "reason": f"Tool error: {str(e)}",
                "parent_agent": parent_agent
            })
            
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
        
        self.history.add({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": agent_id,
            "tool": tool,
            "action": action,
            "decision": "allowed",
            "reason": decision.reason,
            "parent_agent": parent_agent,
            "approval_id": approval_id
        })
        
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
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.post("/tools/{tool}/{action}")
    async def handle_request(
        tool: str,
        action: str,
        request: Request,
        x_agent_id: str = Header(..., alias="X-Agent-ID"),
        x_parent_agent: Optional[str] = Header(None, alias="X-Parent-Agent"),
        x_approval_id: Optional[str] = Header(None, alias="X-Approval-ID")
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
            parent_agent=x_parent_agent,
            approval_id=x_approval_id
        )
    
    @app.get("/health")
    async def health_check():
        stats = policy_engine.get_stats()
        return {
            "status": "healthy",
            "service": "aegis-gateway",
            "policy": stats
        }
    
    @app.get("/api/admin/agents")
    async def get_agents():
        agents = []
        for policy_file in policy_engine.policies.values():
            for agent in policy_file.agents:
                agents.append({
                    "id": agent.id,
                    "permissions": [
                        {
                            "tool": perm.tool,
                            "actions": perm.actions,
                            "conditions": perm.conditions,
                            "require_approval": perm.require_approval
                        } for perm in agent.allow
                    ],
                    "deny_if_parent": agent.deny_if_parent,
                    "allow_only_parents": agent.allow_only_parents
                })
        return {"agents": agents}
    
    @app.get("/api/admin/policies")
    async def get_policies():
        policies = []
        for path, policy_file in policy_engine.policies.items():
            policies.append({
                "path": path,
                "version": policy_file.version,
                "agent_count": len(policy_file.agents)
            })
        return {"policies": policies}
    
    @app.get("/api/admin/decisions")
    async def get_recent_decisions(limit: int = 50):
        return {
            "decisions": gateway.history.get_recent(limit),
            "total": len(gateway.history.decisions)
        }
    
    @app.get("/api/admin/approvals/pending")
    async def get_pending_approvals():
        return {
            "pending_approvals": gateway.approval_gate.get_pending()
        }
    
    @app.post("/api/approve/{approval_id}")
    async def approve_request(
        approval_id: str,
        x_agent_id: str = Header(..., alias="X-Agent-ID"),
        x_parent_agent: Optional[str] = Header(None, alias="X-Parent-Agent")
    ):
        """Approve a pending request and execute it"""
        # Get the approved request details
        pending = gateway.approval_gate.pending.get(approval_id)
        if not pending:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "ApprovalNotFound",
                    "reason": f"Approval request '{approval_id}' not found"
                }
            )
        
        # Execute the approved action
        return await gateway.handle_tool_call(
            tool=pending["tool"],
            action=pending["action"],
            params=pending["params"],
            agent_id=pending["agent_id"],
            parent_agent=pending.get("parent_agent"),
            approval_id=approval_id
        )
    
    @app.on_event("shutdown")
    async def shutdown_event():
        policy_engine.close()
        telemetry.shutdown()
    
    return app

