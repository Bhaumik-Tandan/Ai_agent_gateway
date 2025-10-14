import os
import time
import logging
from pathlib import Path
from typing import Dict, Optional
from threading import Thread, Lock

import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .types import PolicyFile, Decision, EvaluationContext


logger = logging.getLogger(__name__)


class PolicyFileHandler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine
        self.last_reload = 0
        self.debounce_seconds = 0.1
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if not (event.src_path.endswith('.yaml') or event.src_path.endswith('.yml')):
            return
        
        now = time.time()
        if now - self.last_reload < self.debounce_seconds:
            return
        
        self.last_reload = now
        logger.info(f"Policy file changed: {os.path.basename(event.src_path)}")
        self.engine.load_policies()


class PolicyEngine:
    def __init__(self, policy_dir: str):
        self.policy_dir = Path(policy_dir)
        self.policies: Dict[str, PolicyFile] = {}
        self.lock = Lock()
        self.observer = None
        
        self.load_policies()
        self._start_watching()
    
    def load_policies(self):
        policy_files = []
        policy_files.extend(self.policy_dir.glob('*.yaml'))
        policy_files.extend(self.policy_dir.glob('*.yml'))
        
        if not policy_files:
            logger.warning(f"No policy files found in {self.policy_dir}")
            return
        
        new_policies = {}
        errors = []
        
        for file_path in policy_files:
            try:
                policy = self._load_policy_file(file_path)
                new_policies[str(file_path)] = policy
                logger.info(f"Loaded policy: {file_path.name} (v{policy.version}, {len(policy.agents)} agents)")
            except Exception as e:
                logger.error(f"Failed to load {file_path.name}: {e}")
                errors.append(f"{file_path.name}: {e}")
        
        if not new_policies and errors:
            logger.error(f"All policy files failed to load: {errors}")
            return
        
        with self.lock:
            self.policies = new_policies
        
        if new_policies:
            logger.info(f"Policies reloaded successfully ({len(new_policies)} files)")
    
    def _load_policy_file(self, file_path: Path) -> PolicyFile:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        policy = PolicyFile(**data)
        
        error = policy.validate_policy()
        if error:
            raise ValueError(f"Validation failed: {error}")
        
        return policy
    
    def _start_watching(self):
        if not self.policy_dir.exists():
            logger.warning(f"Policy directory does not exist: {self.policy_dir}")
            return
        
        event_handler = PolicyFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.policy_dir), recursive=False)
        self.observer.start()
        logger.info(f"Watching for policy changes in {self.policy_dir}")
    
    def evaluate(self, ctx: EvaluationContext) -> Decision:
        with self.lock:
            if not self.policies:
                return Decision(
                    allow=False,
                    reason="No policies loaded",
                    version=0
                )
            
            for policy in self.policies.values():
                decision = policy.evaluate(ctx)
                if decision.allow:
                    return decision
            
            last_decision = list(self.policies.values())[-1].evaluate(ctx)
            return last_decision
    
    def get_stats(self) -> Dict[str, int]:
        with self.lock:
            total_agents = sum(len(p.agents) for p in self.policies.values())
            return {
                'policy_files': len(self.policies),
                'total_agents': total_agents
            }
    
    def close(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()

