from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Permission(BaseModel):
    tool: str
    actions: List[str]
    conditions: Optional[Dict[str, Any]] = None
    require_approval: bool = False


class Agent(BaseModel):
    id: str
    allow: List[Permission]
    deny_if_parent: Optional[List[str]] = None
    allow_only_parents: Optional[List[str]] = None


class PolicyFile(BaseModel):
    version: int
    agents: List[Agent]

    def validate_policy(self) -> Optional[str]:
        if self.version <= 0:
            return f"version must be positive, got {self.version}"
        
        if not self.agents:
            return "at least one agent must be defined"
        
        agent_ids = set()
        for agent in self.agents:
            if not agent.id:
                return f"agent id is required"
            if agent.id in agent_ids:
                return f"duplicate agent id: {agent.id}"
            agent_ids.add(agent.id)
            
            if not agent.allow:
                return f"agent {agent.id}: at least one permission required"
            
            for perm in agent.allow:
                if not perm.tool:
                    return f"agent {agent.id}: tool is required"
                if not perm.actions:
                    return f"agent {agent.id}: at least one action required"
        
        return None

    def evaluate(self, ctx: 'EvaluationContext') -> 'Decision':
        agent = next((a for a in self.agents if a.id == ctx.agent_id), None)
        
        if not agent:
            return Decision(
                allow=False,
                reason=f"Agent '{ctx.agent_id}' not found in policy",
                version=self.version
            )
        
        if ctx.parent_agent:
            if agent.deny_if_parent and ctx.parent_agent in agent.deny_if_parent:
                return Decision(
                    allow=False,
                    reason=f"Agent '{ctx.agent_id}' denied when called by parent '{ctx.parent_agent}'",
                    version=self.version
                )
            
            if agent.allow_only_parents and ctx.parent_agent not in agent.allow_only_parents:
                return Decision(
                    allow=False,
                    reason=f"Agent '{ctx.agent_id}' can only be called by: {agent.allow_only_parents}, not '{ctx.parent_agent}'",
                    version=self.version
                )
        else:
            if agent.allow_only_parents:
                return Decision(
                    allow=False,
                    reason=f"Agent '{ctx.agent_id}' requires a parent agent from: {agent.allow_only_parents}",
                    version=self.version
                )
        
        for perm in agent.allow:
            if perm.tool != ctx.tool:
                continue
            
            if ctx.action not in perm.actions:
                continue
            
            if perm.conditions:
                violation = self._check_conditions(perm.conditions, ctx.params)
                if violation:
                    return Decision(
                        allow=False,
                        reason=violation,
                        version=self.version
                    )
            
            if perm.require_approval:
                return Decision(
                    allow=False,
                    reason=f"Action {ctx.tool}.{ctx.action} requires approval",
                    version=self.version,
                    require_approval=True,
                    approval_context={
                        "agent_id": ctx.agent_id,
                        "tool": ctx.tool,
                        "action": ctx.action,
                        "params": ctx.params,
                        "parent_agent": ctx.parent_agent
                    }
                )
            
            return Decision(
                allow=True,
                reason="Policy allows this action",
                version=self.version
            )
        
        return Decision(
            allow=False,
            reason=f"No policy allows agent '{ctx.agent_id}' to perform {ctx.tool}.{ctx.action}",
            version=self.version
        )

    def _check_conditions(self, conditions: Dict[str, Any], params: Dict[str, Any]) -> Optional[str]:
        if 'max_amount' in conditions:
            max_amount = float(conditions['max_amount'])
            amount = params.get('amount')
            if amount is None:
                return "Missing 'amount' parameter"
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return "Invalid 'amount' parameter"
            if amount > max_amount:
                return f"Amount {amount:.2f} exceeds max_amount={max_amount:.2f}"
        
        if 'currencies' in conditions:
            allowed = conditions['currencies']
            currency = params.get('currency')
            if not currency:
                return "Missing 'currency' parameter"
            if currency not in allowed:
                return f"Currency '{currency}' not in allowed list: {allowed}"
        
        if 'folder_prefix' in conditions:
            prefix = conditions['folder_prefix']
            path = params.get('path')
            if not path:
                return "Missing 'path' parameter"
            if not path.startswith(prefix):
                return f"Path '{path}' does not match folder_prefix='{prefix}'"
        
        return None


class Decision(BaseModel):
    allow: bool
    reason: str
    version: int = 0
    require_approval: bool = False
    approval_context: Optional[Dict[str, Any]] = None


class EvaluationContext(BaseModel):
    agent_id: str
    tool: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    parent_agent: Optional[str] = None

